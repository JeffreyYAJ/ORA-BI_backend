"""Planification SQL ETL à partir du profil source et de la demande utilisateur."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import get_settings

SQL_SYSTEM = """Tu génères une requête PostgreSQL SELECT unique pour répondre à une demande ETL.
Utilise UNIQUEMENT la table qualifiée fournie et les colonnes du profil.
Réponds en JSON : {"sql": "SELECT ...", "explanation": "..."}
Règles : SELECT seulement, pas de point-virgule multiple, inclure LIMIT si non agrégé global."""


def _fallback_sql(profile: dict[str, Any], instruction: str) -> dict[str, str]:
    qname = profile.get("qualified_name") or "ora_demo.transactions"
    instr = instruction.lower()

    if any(w in instr for w in ("devise", "currency", "par devise")):
        return {
            "sql": (
                f"SELECT currency, COUNT(*) AS nb_transactions, "
                f"ROUND(SUM(amount)::numeric, 2) AS total_amount "
                f"FROM {qname} GROUP BY currency ORDER BY total_amount DESC"
            ),
            "explanation": "Agrégation par devise (nombre et montant total).",
        }
    if any(w in instr for w in ("catégor", "category", "par categor")):
        return {
            "sql": (
                f"SELECT category, COUNT(*) AS nb, ROUND(AVG(amount)::numeric, 2) AS montant_moyen "
                f"FROM {qname} GROUP BY category ORDER BY nb DESC"
            ),
            "explanation": "Statistiques par catégorie de transaction.",
        }
    if any(w in instr for w in ("top", "plus grand", "maximum", "montant")):
        return {
            "sql": f"SELECT * FROM {qname} ORDER BY amount DESC LIMIT 10",
            "explanation": "Top 10 des transactions par montant.",
        }
    if any(w in instr for w in ("france", "fr ", " pays", "country")):
        return {
            "sql": (
                f"SELECT country_code, COUNT(*) AS nb, ROUND(SUM(amount)::numeric, 2) AS total "
                f"FROM {qname} GROUP BY country_code"
            ),
            "explanation": "Répartition par pays.",
        }
    return {
        "sql": f"SELECT * FROM {qname} LIMIT 20",
        "explanation": "Aperçu des données source (20 lignes).",
    }


async def _llm_sql(profile: dict[str, Any], instruction: str) -> dict[str, str] | None:
    settings = get_settings()
    payload = {
        "qualified_table": profile.get("qualified_name"),
        "columns": profile.get("columns"),
        "row_count": profile.get("row_count"),
        "user_request": instruction,
    }
    user_msg = json.dumps(payload, ensure_ascii=False, indent=2)

    try:
        if settings.llm_provider.lower() == "gemini" and settings.gemini_api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
            body = {
                "systemInstruction": {"parts": [{"text": SQL_SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif settings.llm_provider.lower() == "openai" and settings.openai_api_key:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": settings.openai_model,
                        "messages": [
                            {"role": "system", "content": SQL_SYSTEM},
                            {"role": "user", "content": user_msg},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
        else:
            return None

        data = json.loads(text.strip().removeprefix("```json").removesuffix("```"))
        if data.get("sql"):
            return {"sql": data["sql"], "explanation": data.get("explanation", "")}
    except Exception:
        return None
    return None


async def plan_etl_sql(profile: dict[str, Any], instruction: str) -> dict[str, str]:
    if not profile.get("connected"):
        raise ValueError(profile.get("error") or "Source non connectée")
    planned = await _llm_sql(profile, instruction)
    return planned or _fallback_sql(profile, instruction)
