from typing import Any

from app.models.enums import GuardianOperationType, NodeType
from app.models.node import Node
from app.guardian.pii import scan_structure

ALWAYS_REQUIRES_APPROVAL = frozenset(
    {
        GuardianOperationType.DELETE_COLUMN,
        GuardianOperationType.EXPORT_DATA,
        GuardianOperationType.SINK_WRITE,
        GuardianOperationType.PII_EXPOSURE,
    }
)


def operation_requires_approval(operation: GuardianOperationType) -> bool:
    return operation in ALWAYS_REQUIRES_APPROVAL


def _column_names(data: dict[str, Any]) -> set[str]:
    cols = data.get("columns") or data.get("schema") or data.get("fields")
    if isinstance(cols, list):
        return {str(c).lower() for c in cols if c}
    if isinstance(cols, dict):
        return {str(k).lower() for k in cols.keys()}
    return set()


def analyze_node_data_change(
    old_data: dict[str, Any],
    new_data: dict[str, Any],
) -> list[tuple[GuardianOperationType, dict[str, Any]]]:
    operations: list[tuple[GuardianOperationType, dict[str, Any]]] = []
    old_cols = _column_names(old_data)
    new_cols = _column_names(new_data)
    removed = old_cols - new_cols
    if removed:
        operations.append(
            (
                GuardianOperationType.DELETE_COLUMN,
                {"removed_columns": sorted(removed)},
            )
        )

    explicit_delete = new_data.get("delete_columns") or old_data.get("delete_columns")
    if explicit_delete:
        cols = explicit_delete if isinstance(explicit_delete, list) else [explicit_delete]
        operations.append(
            (
                GuardianOperationType.DELETE_COLUMN,
                {"removed_columns": [str(c) for c in cols]},
            )
        )

    if new_data.get("export") is True or new_data.get("allow_export") is True:
        operations.append((GuardianOperationType.EXPORT_DATA, {"export": True}))

    if new_data.get("bulk_transform") is True:
        operations.append((GuardianOperationType.BULK_TRANSFORM, {"bulk_transform": True}))

    return operations


def detect_node_execution_risks(node: Node) -> list[tuple[GuardianOperationType, dict[str, Any], str]]:
    """Risks detected when executing a node in a pipeline run."""
    risks: list[tuple[GuardianOperationType, dict[str, Any], str]] = []
    data = node.internal_data or {}

    if node.type == NodeType.SINK:
        risks.append(
            (
                GuardianOperationType.SINK_WRITE,
                {"node_id": str(node.id), "subtype": node.subtype.value},
                f"Écriture vers sortie **{node.label}** ({node.subtype.value})",
            )
        )

    if data.get("export") or data.get("allow_export"):
        risks.append(
            (
                GuardianOperationType.EXPORT_DATA,
                {"node_id": str(node.id)},
                f"Export de données demandé sur **{node.label}**",
            )
        )

    if data.get("delete_columns"):
        risks.append(
            (
                GuardianOperationType.DELETE_COLUMN,
                {"columns": data["delete_columns"]},
                f"Suppression de colonnes sur **{node.label}**",
            )
        )

    pii = scan_structure(data)
    if pii:
        risks.append(
            (
                GuardianOperationType.PII_EXPOSURE,
                {"findings_count": len(pii)},
                f"Données personnelles dans la config du nœud **{node.label}**",
            )
        )

    return risks
