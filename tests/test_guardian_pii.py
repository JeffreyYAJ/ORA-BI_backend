from app.guardian.pii import mask_structure, scan_structure
from app.guardian.policy import analyze_node_data_change
from app.models.enums import GuardianOperationType


def test_scan_email():
    findings = scan_structure({"contact": "jean.dupont@banque.fr"})
    assert any(f.pii_type == "email" for f in findings)


def test_mask_structure():
    masked, findings = mask_structure({"note": "contact secret@example.com please"})
    assert findings
    assert "secret@example.com" not in str(masked)


def test_delete_column_requires_approval():
    ops = analyze_node_data_change(
        {"columns": ["a", "b", "email"]},
        {"columns": ["a", "b"]},
    )
    assert (GuardianOperationType.DELETE_COLUMN, {"removed_columns": ["email"]}) in ops
