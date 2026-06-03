"""Contexte d'exécution partagé : étude des données du pipeline dès le début du workflow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.guardian.pii import findings_summary, mask_structure, scan_structure
from app.models.enums import NodeType
from app.models.pipeline import Pipeline


def build_execution_context(pipeline: Pipeline, *, phase: str = "INITIAL_STUDY") -> dict[str, Any]:
    """Snapshot structuré pour les agents (données masquées RGPD)."""
    nodes_study: list[dict[str, Any]] = []
    all_findings: list[dict[str, str]] = []
    has_source = False
    has_sink = False

    for node in pipeline.nodes:
        raw = node.internal_data or {}
        masked, pii_list = mask_structure(raw)
        all_findings.extend(pii_list)
        if node.type == NodeType.SOURCE:
            has_source = True
        if node.type == NodeType.SINK:
            has_sink = True

        columns = raw.get("columns") or raw.get("schema") or raw.get("fields")
        nodes_study.append(
            {
                "id": str(node.id),
                "label": node.label,
                "type": node.type.value,
                "subtype": node.subtype.value,
                "columns": columns,
                "masked_data_preview": masked,
                "pii_count": len(pii_list),
                "pii_types": list({p.get("pii_type") for p in pii_list}),
            }
        )

    gaps: list[str] = []
    if not has_source:
        gaps.append("Aucun nœud SOURCE — origine des données non définie.")
    if not has_sink:
        gaps.append("Aucun nœud SINK — destination des données non définie.")
    total_pii = len(all_findings)
    if total_pii > 0:
        gaps.append(f"{total_pii} indicateur(s) PII détecté(s) dans la configuration des nœuds.")

    return {
        "phase": phase,
        "pipeline_id": str(pipeline.id),
        "pipeline_name": pipeline.name,
        "node_count": len(pipeline.nodes),
        "edge_count": len(pipeline.edges),
        "nodes": nodes_study,
        "gaps": gaps,
        "pii_total": total_pii,
        "pii_summary": findings_summary(all_findings)
        if all_findings
        else "Aucune donnée personnelle détectée dans la configuration.",
        "architecture_design": pipeline.architecture_design,
    }


def merge_user_answers(context: dict[str, Any], answers: list[dict[str, str]]) -> dict[str, Any]:
    merged = dict(context)
    merged["user_answers"] = {a["question_id"]: a["answer"] for a in answers}
    return merged
