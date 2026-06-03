"""Génération de questions contextuelles pour les agents (LLM ou règles)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import get_settings
from app.models.enums import AgentRole, WorkflowPhase

QUESTION_SYSTEM = """Tu es un agent spécialisé DataPipe (ETL bancaire).
À partir du contexte d'exécution JSON (données déjà étudiées et masquées RGPD), propose des questions
**uniquement si un choix utilisateur est nécessaire** pour continuer le workflow.
Réponds en JSON strict (pas de markdown) :
{"questions": [{"text": "...", "choices": ["option A", "option B"]}]}
- Maximum 3 questions.
- Questions en français, courtes, liées au contexte (colonnes, PII, source/sink, transformations).
- choices peut être [] si réponse libre.
- Si rien n'est requis : {"questions": []}
"""


def _fallback_questions(
    agent_role: AgentRole,
    context: dict[str, Any],
    phase: WorkflowPhase,
    instruction: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    gaps = context.get("gaps") or []

    if phase == WorkflowPhase.INITIAL_STUDY:
        primary = (context.get("live_data_profile") or {}).get("primary_source") or {}
        if primary.get("connected") and primary.get("column_names"):
            out.append(
                {
                    "text": (
                        f"La source `{primary.get('qualified_name')}` contient {primary.get('row_count', 0)} "
                        f"lignes ({', '.join(primary['column_names'][:6])}…). "
                        "Quelle colonne est l'identifiant métier principal ?"
                    ),
                    "choices": primary["column_names"][:6],
                }
            )
        if "Aucun nœud SOURCE" in " ".join(gaps):
            out.append(
                {
                    "text": "Quelle sera la source principale des données (CSV, API, base PostgreSQL) ?",
                    "choices": ["CSV / fichier", "API REST", "PostgreSQL", "Autre"],
                }
            )
        if context.get("pii_total", 0) > 0 and agent_role in (AgentRole.GUARDIAN, AgentRole.PROFILER):
            out.append(
                {
                    "text": (
                        "Des données personnelles ont été détectées dès l'étude initiale. "
                        "Quel niveau de masquage appliquer dans les aperçus et logs ?"
                    ),
                    "choices": ["Masquage strict", "Masquage partiel", "Anonymisation complète"],
                }
            )
        for node in context.get("nodes", [])[:2]:
            cols = node.get("columns")
            if cols and not context.get("user_answers"):
                out.append(
                    {
                        "text": f"Sur le nœud « {node.get('label')} », quelle colonne identifie le client ?",
                        "choices": [str(c) for c in cols[:5]] if isinstance(cols, list) else [],
                    }
                )
                break

    if phase == WorkflowPhase.NODE_EXECUTION and context.get("current_node"):
        node = context["current_node"]
        if node.get("pii_count", 0) > 0:
            out.append(
                {
                    "text": (
                        f"Le nœud « {node.get('label')} » contient des PII. "
                        "Confirmez-vous la poursuite du traitement avec masquage RGPD ?"
                    ),
                    "choices": ["Oui, avec masquage", "Non, arrêter le pipeline"],
                }
            )

    if phase == WorkflowPhase.AGENT_TASK and instruction:
        if agent_role == AgentRole.PROFILER and "profil" in instruction.lower():
            if not context.get("nodes"):
                out.append(
                    {
                        "text": "Quels fichiers ou tables souhaitez-vous profiler en priorité ?",
                        "choices": [],
                    }
                )
        if agent_role == AgentRole.GUARDIAN and context.get("pii_total", 0) > 0:
            out.append(
                {
                    "text": instruction[:200] + " — Validez-vous l'analyse conformité sur ces données ?",
                    "choices": ["Oui", "Non, revoir le schéma"],
                }
            )

    return out[:3]


async def _llm_questions(
    agent_role: AgentRole,
    context: dict[str, Any],
    phase: WorkflowPhase,
    instruction: str | None,
) -> list[dict[str, Any]] | None:
    settings = get_settings()
    payload = {
        "agent_role": agent_role.value,
        "phase": phase.value,
        "instruction": instruction,
        "execution_context": context,
    }
    user_msg = json.dumps(payload, ensure_ascii=False, indent=2)

    try:
        if settings.llm_provider.lower() == "gemini" and settings.gemini_api_key:
            return await _gemini_questions(user_msg)
        if settings.llm_provider.lower() == "openai" and settings.openai_api_key:
            return await _openai_questions(user_msg)
    except Exception:
        return None
    return None


async def _gemini_questions(user_msg: str) -> list[dict[str, Any]] | None:
    settings = get_settings()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": QUESTION_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
        r.raise_for_status()
        data = r.json()
    text = data["candidates"][0]["content"]["parts"][0].get("text", "")
    return _parse_questions_json(text)


async def _openai_questions(user_msg: str) -> list[dict[str, Any]] | None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": QUESTION_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    return _parse_questions_json(text)


def _parse_questions_json(text: str) -> list[dict[str, Any]] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    items = data.get("questions", data if isinstance(data, list) else [])
    if not isinstance(items, list):
        return None
    result = []
    for item in items[:3]:
        if isinstance(item, dict) and item.get("text"):
            result.append(
                {
                    "text": str(item["text"]).strip(),
                    "choices": item.get("choices") if isinstance(item.get("choices"), list) else [],
                }
            )
    return result


async def generate_contextual_questions(
    agent_role: AgentRole,
    context: dict[str, Any],
    phase: WorkflowPhase,
    instruction: str | None = None,
    *,
    max_questions: int = 3,
) -> list[dict[str, Any]]:
    """Questions adaptées au contexte ; LLM si configuré, sinon heuristiques."""
    llm = await _llm_questions(agent_role, context, phase, instruction)
    questions = llm if llm is not None else _fallback_questions(agent_role, context, phase, instruction)
    return questions[:max_questions]
