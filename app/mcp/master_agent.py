import json
import re
from typing import Any
from uuid import UUID
import os

import httpx
from cursor_sdk import CursorAgentError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.mcp.cursor_llm import call_cursor_composer, cursor_error_message
from app.models.agent_task import AgentTask
from app.models.enums import AgentRole
from app.services.agent_task_service import create_agent_task

SYSTEM_PROMPT = """You are the Master Agent for DataPipe, a visual ETL system for banking pipelines.
You orchestrate specialized agents (Profiler, Engineer, Debugger, Guardian, QA, Auditor).
Respond in Markdown. Be concise and actionable. Prefer French when the user writes in French.

When the user needs data profiling, transformation code, or auditing, you may delegate by including
a JSON block at the end of your response (only when delegation is needed):

```delegation
[{"agent_role": "PROFILER", "instruction": "...", "node_id": null}]
```

Valid agent_role values: PROFILER, ENGINEER, DEBUGGER, GUARDIAN, QA, AUDITOR.
Specialized agents are NOT executed in MVP — tasks stay PENDING for human review.

Ask clarifying questions if the user has not uploaded data files or provided DB credentials.
"""

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class MasterAgentRunner:
    def __init__(self, db: AsyncSession, pipeline_id: UUID) -> None:
        self.db = db
        self.pipeline_id = pipeline_id
        self.settings = get_settings()

    async def run(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> tuple[dict[str, Any], list[AgentTask]]:
        reply_text = await self._call_llm(user_content, pipeline_context, history)
        delegations, clean_content = self._parse_delegations(reply_text)

        new_tasks: list[AgentTask] = []
        for d in delegations:
            role_str = d.get("agent_role", "PROFILER")
            try:
                role = AgentRole(role_str)
            except ValueError:
                continue
            if role == AgentRole.MASTER:
                continue
            node_id = d.get("node_id")
            task = await create_agent_task(
                self.db,
                self.pipeline_id,
                agent_role=role,
                instruction=d.get("instruction", ""),
                node_id=UUID(node_id) if node_id else None,
            )
            new_tasks.append(task)

        metadata: dict[str, Any] = {}
        if delegations:
            metadata["delegations"] = delegations
        if "?" in clean_content or "upload" in clean_content.lower():
            metadata["requires_user_input"] = True
        if clean_content.startswith("⚠️"):
            metadata["llm_error"] = True

        return {"content": clean_content, "metadata": metadata}, new_tasks

    def _pipeline_context_text(self, pipeline_context: dict[str, Any]) -> str:
        return json.dumps(
            {
                "pipeline_id": pipeline_context.get("id"),
                "name": pipeline_context.get("name"),
                "nodes": [
                    {
                        "id": str(n["id"]),
                        "type": n["type"],
                        "subtype": n["subtype"],
                        "label": n["label"],
                        "status": n.get("status"),
                    }
                    for n in pipeline_context.get("nodes", [])
                ],
                "edges": pipeline_context.get("edges", []),
            },
            indent=2,
            ensure_ascii=False,
        )

    async def _call_llm(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> str:
        provider = self.settings.llm_provider.lower()
        try:
            if provider == "cursor" and self.settings.cursor_api_key:
                return await call_cursor_composer(
                    SYSTEM_PROMPT, pipeline_context, history, user_content
                )
            if provider == "gemini" and self.settings.gemini_api_key:
                return await self._gemini_chat(user_content, pipeline_context, history)
            if provider == "openai" and self.settings.openai_api_key:
                return await self._openai_chat(user_content, pipeline_context, history)
        except CursorAgentError as exc:
            return cursor_error_message(exc)
        except httpx.HTTPStatusError as exc:
            return self._http_error_message(exc)
        except httpx.RequestError as exc:
            return f"⚠️ **Erreur réseau LLM** : impossible de joindre le fournisseur ({exc})."

        return self._fallback_response(user_content, pipeline_context)

    async def _gemini_chat(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> str:
        context_text = self._pipeline_context_text(pipeline_context)
        system_text = f"{SYSTEM_PROMPT}\n\nCurrent pipeline context:\n{context_text}"

        contents: list[dict[str, Any]] = []
        for h in history[-10:]:
            role = "user" if h["sender"] == "USER" else "model"
            contents.append({"role": role, "parts": [{"text": h["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_content}]})

        model = self.settings.gemini_model
        url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.3},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                url,
                params={"key": self.settings.gemini_api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return "⚠️ **Gemini** : réponse vide (aucun candidat)."
        parts = candidates[0].get("content", {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if p.get("text")]
        if not texts:
            block_reason = candidates[0].get("finishReason", "unknown")
            return f"⚠️ **Gemini** : contenu bloqué ou vide (raison : `{block_reason}`)."
        return "\n".join(texts)

    async def _openai_chat(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append(
            {
                "role": "system",
                "content": f"Current pipeline context:\n{self._pipeline_context_text(pipeline_context)}",
            }
        )
        for h in history[-10:]:
            role = "user" if h["sender"] == "USER" else "assistant"
            messages.append({"role": role, "content": h["content"]})
        messages.append({"role": "user", "content": user_content})

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.openai_model,
                    "messages": messages,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _http_error_message(self, exc: httpx.HTTPStatusError) -> str:
        provider = self.settings.llm_provider
        code = exc.response.status_code
        detail = ""
        try:
            body = exc.response.json()
            if provider == "gemini":
                detail = body.get("error", {}).get("message", "")
            else:
                detail = body.get("error", {}).get("message", "") if isinstance(body.get("error"), dict) else str(body)
        except Exception:
            detail = exc.response.text[:300]

        hints = {
            429: "Quota ou limite de débit dépassée. Attendez quelques minutes ou vérifiez votre plan.",
            401: "Clé API invalide ou expirée.",
            403: "Accès refusé (clé ou API non activée).",
            404: "Modèle introuvable — vérifiez le nom du modèle dans `.env`.",
        }
        hint = hints.get(code, "Consultez la documentation du fournisseur LLM.")
        msg = f"⚠️ **Erreur {provider.upper()} HTTP {code}** : {hint}"
        if detail:
            msg += f"\n\nDétail : _{detail[:500]}_"
        return msg

    def _fallback_response(self, user_content: str, pipeline_context: dict[str, Any]) -> str:
        nodes = pipeline_context.get("nodes", [])
        edges = pipeline_context.get("edges", [])
        summary = (
            f"Pipeline **{pipeline_context.get('name')}** : "
            f"{len(nodes)} nœud(s), {len(edges)} liaison(s)."
        )
        reply = (
            f"{summary}\n\n"
            f"Votre question : _{user_content}_\n\n"
            "Mode **offline** : configurez `CURSOR_API_KEY` et `LLM_PROVIDER=cursor` dans `.env`, "
            "puis redémarrez l'API (voir docs/CURSOR_API_KEYS.md).\n\n"
        )
        if "profil" in user_content.lower() or "anomal" in user_content.lower():
<<<<<<< HEAD
            instruction = f"Profile pipeline data per user request: {user_content[:200]}"
            delegation = (
                '[{"agent_role": "PROFILER", "instruction": '
                + json.dumps(instruction)
                + ', "node_id": null}]'
            )
            reply += f"I would delegate profiling to the Profiler agent.\n\n```delegation\n{delegation}\n```"
=======
            instruction = f"Profiler les données : {user_content[:200]}"
            delegation = (
                '[{"agent_role": "PROFILER", "instruction": '
                + json.dumps(instruction, ensure_ascii=False)
                + ', "node_id": null}]'
            )
            reply += f"Délégation suggérée vers le Profiler.\n\n```delegation\n{delegation}\n```"
>>>>>>> b6678a9 (removed apis)
        elif nodes:
            reply += "Précisez la transformation souhaitée ou uploadez un fichier source CSV/JSON."
        else:
            reply += "Ajoutez des nœuds SOURCE (CSV/JSON) sur le canvas pour commencer."
        return reply

    def _parse_delegations(self, text: str) -> tuple[list[dict[str, Any]], str]:
        pattern = r"```delegation\s*([\s\S]*?)```"
        match = re.search(pattern, text)
        if not match:
            return [], text.strip()
        try:
            delegations = json.loads(match.group(1).strip())
            if isinstance(delegations, dict):
                delegations = [delegations]
        except json.JSONDecodeError:
            delegations = []
        clean = re.sub(pattern, "", text).strip()
        return delegations, clean
