"""Agent Maître via Cursor SDK (modèle Composer)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cursor_sdk import AgentOptions, AsyncAgent, AsyncClient, CursorAgentError, LocalAgentOptions

from app.config import get_settings


def build_cursor_prompt(
    system_prompt: str,
    pipeline_context: dict[str, Any],
    history: list[dict[str, str]],
    user_content: str,
) -> str:
    """Assemble un prompt unique pour Agent.prompt (one-shot)."""
    context_json = json.dumps(
        {
            "pipeline_id": pipeline_context.get("id"),
            "name": pipeline_context.get("name"),
            "nodes": pipeline_context.get("nodes", []),
            "edges": pipeline_context.get("edges", []),
        },
        indent=2,
        ensure_ascii=False,
    )
    lines = [
        system_prompt.strip(),
        "",
        "## Contexte pipeline (JSON)",
        context_json,
        "",
        "## Historique récent",
    ]
    if history:
        for h in history[-10:]:
            role = "Utilisateur" if h["sender"] == "USER" else "Agent Maître"
            lines.append(f"**{role}** : {h['content']}")
    else:
        lines.append("(aucun message précédent)")
    lines.extend(["", "## Message actuel", user_content.strip()])
    return "\n".join(lines)


async def call_cursor_composer(
    system_prompt: str,
    pipeline_context: dict[str, Any],
    history: list[dict[str, str]],
    user_content: str,
) -> str:
    settings = get_settings()
    if not settings.cursor_api_key:
        raise CursorAgentError("CURSOR_API_KEY manquante")

    workspace = Path(settings.cursor_workspace).resolve()
    prompt = build_cursor_prompt(system_prompt, pipeline_context, history, user_content)
    options = AgentOptions(
        api_key=settings.cursor_api_key,
        model="composer-2.5",
        local=LocalAgentOptions(cwd=str(workspace)),
    )

    async with await AsyncClient.launch_bridge(workspace=str(workspace)) as client:
        result = await AsyncAgent.prompt(prompt, options, client=client)

    if result.status == "error":
        return (
            f"⚠️ **Erreur Cursor (run {result.id})** : l'agent a échoué pendant l'exécution. "
            "Consultez les logs Cursor ou réessayez."
        )
    text = (result.result or "").strip()
    if not text:
        return "⚠️ **Cursor** : réponse vide."
    return text


def cursor_error_message(exc: Exception) -> str:
    if isinstance(exc, CursorAgentError):
        retry = getattr(exc, "is_retryable", False)
        return (
            f"⚠️ **Erreur Cursor** : {exc}\n\n"
            f"Réessayable : `{retry}`. Vérifiez `CURSOR_API_KEY` et que Cursor CLI est installé "
            "(runtime local). Voir docs/CURSOR_API_KEYS.md."
        )
    return f"⚠️ **Erreur Cursor** : {exc}"
