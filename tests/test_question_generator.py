from app.agents.question_generator import _fallback_questions
from app.models.enums import AgentRole, WorkflowPhase


def test_fallback_initial_study_no_source():
    ctx = {"gaps": ["Aucun nœud SOURCE — origine des données non définie."], "nodes": [], "pii_total": 0}
    qs = _fallback_questions(AgentRole.PROFILER, ctx, WorkflowPhase.INITIAL_STUDY, None)
    assert qs
    assert "source" in qs[0]["text"].lower()


def test_fallback_node_pii():
    ctx = {
        "current_node": {"label": "Clients", "pii_count": 2},
        "pii_total": 2,
        "gaps": [],
        "nodes": [],
    }
    qs = _fallback_questions(AgentRole.GUARDIAN, ctx, WorkflowPhase.NODE_EXECUTION, None)
    assert any("PII" in q["text"] or "masquage" in q["text"] for q in qs)


def test_fallback_profiler_columns():
    ctx = {
        "gaps": [],
        "nodes": [{"label": "Import CSV", "columns": ["id_client", "email"]}],
        "pii_total": 0,
    }
    qs = _fallback_questions(AgentRole.PROFILER, ctx, WorkflowPhase.INITIAL_STUDY, None)
    assert any("colonne" in q["text"].lower() for q in qs)
