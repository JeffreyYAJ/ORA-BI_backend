"""Workflow ETL : exécution de la demande utilisateur sur la source profilée."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.db_introspection import execute_readonly_query
from app.etl.sql_planner import plan_etl_sql
from app.models.enums import NodeType
from app.schemas.etl import EtlExecuteResponse
from app.services.data_source_service import get_live_profile, introspect_pipeline_sources
from app.services.pipeline_service import get_pipeline_or_404


def _primary_source_node(pipeline) -> tuple[dict, dict] | None:
    profile = get_live_profile(pipeline)
    if not profile or not profile.get("primary_source"):
        return None
    primary = profile["primary_source"]
    node_id = primary.get("node_id")
    for node in pipeline.nodes:
        if str(node.id) == node_id and node.type == NodeType.SOURCE:
            return node.internal_data or {}, primary
    for node in pipeline.nodes:
        if node.type == NodeType.SOURCE:
            for src in profile.get("sources", []):
                if src.get("node_id") == str(node.id) and src.get("connected"):
                    return node.internal_data or {}, src
    return None


def _rows_to_markdown_table(rows: list[dict[str, Any]], max_cols: int = 8) -> str:
    if not rows:
        return "_Aucune ligne retournée._"
    cols = list(rows[0].keys())[:max_cols]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body_lines = []
    for row in rows[:30]:
        body_lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    return "\n".join([header, sep, *body_lines])


async def execute_user_etl(
    db: AsyncSession,
    pipeline_id: UUID,
    instruction: str,
) -> EtlExecuteResponse:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    profile_bundle = get_live_profile(pipeline)
    if not profile_bundle or not profile_bundle.get("primary_source"):
        profile_bundle = await introspect_pipeline_sources(db, pipeline_id)
        pipeline = await get_pipeline_or_404(db, pipeline_id)

    pair = _primary_source_node(pipeline)
    if not pair:
        raise ValueError(
            "Aucune source PostgreSQL connectée. Lancez POST .../etl/introspect après configuration SOURCE."
        )
    node_data, profile = pair

    plan = await plan_etl_sql(profile, instruction)
    result = await execute_readonly_query(node_data, plan["sql"], limit=50)

    summary_md = (
        f"## Résultat ETL\n\n"
        f"**Demande** : {instruction}\n\n"
        f"**Explication** : {plan.get('explanation', '')}\n\n"
        f"**SQL** :\n```sql\n{result['sql']}\n```\n\n"
        f"**{result['row_count']} ligne(s)**\n\n"
        f"{_rows_to_markdown_table(result['rows'])}\n"
    )

    design = dict(pipeline.architecture_design or {})
    design["last_etl_result"] = {
        "instruction": instruction,
        "sql": result["sql"],
        "explanation": plan.get("explanation", ""),
        "row_count": result["row_count"],
        "rows": result["rows"],
        "summary_md": summary_md,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    pipeline.architecture_design = design
    await db.flush()

    return EtlExecuteResponse(
        instruction=instruction,
        sql=result["sql"],
        explanation=plan.get("explanation", ""),
        row_count=result["row_count"],
        rows=result["rows"],
        summary_md=summary_md,
        stored_in_pipeline=True,
    )


async def get_last_etl_result(db: AsyncSession, pipeline_id: UUID) -> dict[str, Any] | None:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    design = pipeline.architecture_design or {}
    return design.get("last_etl_result")
