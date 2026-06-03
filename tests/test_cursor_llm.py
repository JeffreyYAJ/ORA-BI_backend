from app.mcp.cursor_llm import build_cursor_prompt


def test_build_cursor_prompt_includes_context_and_user_message():
    prompt = build_cursor_prompt(
        "System instructions",
        {"id": "p1", "name": "Test", "nodes": [], "edges": []},
        [{"sender": "USER", "content": "Hello"}],
        "Describe pipeline",
    )
    assert "System instructions" in prompt
    assert "Test" in prompt
    assert "Describe pipeline" in prompt
    assert "Hello" in prompt
