"""Introspection des sources PostgreSQL du pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.etl.db_introspection import introspect_table
from app.models.enums import NodeType
from app.models.pipeline import Pipeline
from app.services.pipeline_service import get_pipeline_or_404


async def introspect_pipeline_sources(db: AsyncSession, pipeline_id: UUID) -> dict[str, Any]:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    profiles: list[dict[str, Any]] = []

    for node in pipeline.nodes:
        if node.type != NodeType.SOURCE:
            continue
        data = dict(node.internal_data or {})
        if not data.get("table"):
            profiles.append(
                {
                    "node_id": str(node.id),
                    "label": node.label,
                    "subtype": node.subtype.value,
                    "connected": False,
                    "error": "Ajoutez schema + table (PostgreSQL) pour lecture en ligne",
                }
            )
            continue

        profile = await introspect_table(data)
        profile["node_id"] = str(node.id)
        profile["label"] = node.label
        profile["subtype"] = node.subtype.value
        profiles.append(profile)

    live = next((p for p in profiles if p.get("connected")), None)
    summary_md = _format_profile_summary(profiles)

    design = dict(pipeline.architecture_design or {})
    design["live_data_profile"] = {
        "sources": profiles,
        "primary_source": live,
        "summary_md": summary_md,
    }
    pipeline.architecture_design = design
    await db.flush()

    return design["live_data_profile"]


def _format_profile_summary(profiles: list[dict[str, Any]]) -> str:
    lines = ["## Profil des sources (lecture en ligne)"]
    for p in profiles:
        if not p.get("connected"):
            lines.append(f"- **{p.get('label')}** : non connecté — {p.get('error', '?')}")
            continue
        cols = ", ".join(p.get("column_names", [])[:12])
        lines.append(
            f"- **{p.get('label')}** : `{p.get('qualified_name')}` — "
            f"{p.get('row_count', 0)} ligne(s), colonnes : {cols}"
        )
        if p.get("sample_rows"):
            lines.append(f"  - Échantillon masqué RGPD : {len(p['sample_rows'])} ligne(s)")
    return "\n".join(lines)


def get_live_profile(pipeline: Pipeline) -> dict[str, Any] | None:
    design = pipeline.architecture_design or {}
    return design.get("live_data_profile")
