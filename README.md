# DataPipe Backend (ORA-BI)

Visual ETL backend for banking data pipelines. Provides REST + WebSocket APIs for a ReactFlow frontend and a Master Agent chat orchestrator.

## Stack

- Python 3.11+
- FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL
- FastMCP (IDE agent tools)

## Quick start

### 1. Database

```bash
docker compose up -d db
cp .env.example .env
```

### 2. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev,mcp]"
```

### 3. Migrations

```bash
alembic upgrade head
```

### 4. Run API

```bash
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs: http://localhost:8000/docs

Référence détaillée des routes (usage, utilité, exemples) : [docs/API_ROUTES.md](docs/API_ROUTES.md)

### Docker (API + DB)

```bash
docker compose up --build
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `OPENAI_API_KEY` | Enables full Master Agent LLM (optional) |
| `LLM_MODEL` | OpenAI model (default: `gpt-4o-mini`) |

Without `OPENAI_API_KEY`, the Master Agent uses a deterministic offline fallback.

## REST API (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/pipelines` | Create project |
| GET | `/pipelines` | List projects |
| GET | `/pipelines/{id}` | Full graph (ReactFlow-ready) |
| PATCH | `/pipelines/{id}` | Update name, status, architecture_design |
| DELETE | `/pipelines/{id}` | Delete project |
| POST | `/pipelines/{id}/nodes` | Create node |
| PATCH | `/pipelines/{id}/nodes/{node_id}` | Update node |
| DELETE | `/pipelines/{id}/nodes/{node_id}` | Delete node + linked edges |
| POST | `/pipelines/{id}/edges` | Create edge |
| DELETE | `/pipelines/{id}/edges/{edge_id}` | Delete edge |
| GET | `/pipelines/{id}/chat` | Chat history |
| POST | `/pipelines/{id}/chat` | Send message → Master Agent reply |

### ReactFlow payload

`GET /pipelines/{id}` returns:

```json
{
  "nodes": [{ "id": "uuid", "position": { "x": 0, "y": 0 }, "type": "SOURCE", ... }],
  "edges": [{ "id": "uuid", "source": "node-uuid", "target": "node-uuid" }]
}
```

## WebSocket

Connect to: `ws://localhost:8000/api/v1/ws/pipelines/{pipeline_id}`

Events (JSON):

| type | When |
|------|------|
| `pipeline.updated` | Pipeline metadata changed |
| `node.created` / `node.updated` / `node.deleted` | Node mutations |
| `edge.created` / `edge.deleted` | Edge mutations |
| `chat.message` | New chat message |
| `agent_task.updated` | Master delegated a task |

Example event:

```json
{
  "type": "node.updated",
  "pipeline_id": "...",
  "payload": { "id": "...", "position": { "x": 100, "y": 200 }, ... }
}
```

## MCP server (IDE)

```bash
fastmcp run app/mcp/server.py:mcp
```

Tools: `get_pipeline_context`, `summarize_graph`, `create_agent_task_tool`, `stub_specialized_agent`.

## Manual MVP test

```bash
# Create pipeline
curl -s -X POST http://localhost:8000/api/v1/pipelines \
  -H 'Content-Type: application/json' -d '{"name":"Bank ETL Demo"}' | jq .

# Save PIPELINE_ID from response, then create nodes and edges...
curl -s -X POST "http://localhost:8000/api/v1/pipelines/$PIPELINE_ID/nodes" \
  -H 'Content-Type: application/json' \
  -d '{"type":"SOURCE","subtype":"csv","label":"Transactions CSV","position":{"x":0,"y":0}}' | jq .

# Chat with Master Agent (offline mode works without API key)
curl -s -X POST "http://localhost:8000/api/v1/pipelines/$PIPELINE_ID/chat" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Profile the data for anomalies"}' | jq .
```

## Security (MVP)

No authentication. Do not expose publicly without adding JWT/RBAC (phase 2).

## Tests

```bash
pytest
```
