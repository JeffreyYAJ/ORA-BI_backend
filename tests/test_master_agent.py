import httpx

from app.mcp.master_agent import MasterAgentRunner


def test_parse_delegations():
    runner = MasterAgentRunner(db=None, pipeline_id=None)  # type: ignore[arg-type]
    text = (
        "I will profile the data.\n\n"
        '```delegation\n[{"agent_role": "PROFILER", "instruction": "Audit CSV", "node_id": null}]\n```'
    )
    delegations, clean = runner._parse_delegations(text)
    assert len(delegations) == 1
    assert delegations[0]["agent_role"] == "PROFILER"
    assert "delegation" not in clean


def test_fallback_response():
    runner = MasterAgentRunner(db=None, pipeline_id=None)  # type: ignore[arg-type]
    ctx = {
        "name": "Test",
        "nodes": [{"id": "1", "type": "SOURCE", "subtype": "csv", "label": "A", "status": "IDLE"}],
        "edges": [],
    }
    reply = runner._fallback_response("profile anomalies", ctx)
    assert "PROFILER" in reply or "offline" in reply.lower()


def test_http_error_message_429():
    runner = MasterAgentRunner(db=None, pipeline_id=None)  # type: ignore[arg-type]
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(429, request=request, text='{"error":{"message":"quota"}}')
    msg = runner._http_error_message(httpx.HTTPStatusError("429", request=request, response=response))
    assert "429" in msg
    assert "⚠️" in msg
