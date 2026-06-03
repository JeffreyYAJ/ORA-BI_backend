# DataPipe Backend (ORA-BI)

Visual ETL backend for banking data pipelines. Provides REST + WebSocket APIs for a ReactFlow frontend and a Master Agent chat orchestrator.

**Installation sans Docker** : PostgreSQL et l’API tournent sur votre machine. Vous exposez l’API à vos collègues sur le réseau local (LAN).

## Stack

- Python 3.11+
- PostgreSQL 16+ (installation système)
- FastAPI, SQLAlchemy 2 (async), Alembic
- FastMCP (optionnel, IDE)

## Quick start (local)

### 1. PostgreSQL

**Ubuntu / Debian**

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo -u postgres psql -f scripts/setup_postgres.sql
```

**macOS** : voir [docs/EXPOSITION_RESEAU.md](docs/EXPOSITION_RESEAU.md).

### 2. Environnement Python

```bash
cp .env.example .env
# Éditez .env : CURSOR_API_KEY, CORS si besoin (voir docs/CURSOR_API_KEYS.md)

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev,mcp]"
```

### 3. Migrations

```bash
alembic upgrade head
```

### 4. Lancer l’API (accessible sur le LAN)

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

L’API écoute sur `0.0.0.0:8000` par défaut.

| URL | Usage |
|-----|--------|
| http://127.0.0.1:8000/docs | Swagger (vous) |
| http://\<votre-ip\>:8000/docs | Swagger (collègues) |
| http://\<votre-ip\>:8000/health | Santé |

Guide détaillé partage réseau : **[docs/EXPOSITION_RESEAU.md](docs/EXPOSITION_RESEAU.md)**

Référence des routes : **[docs/API_ROUTES.md](docs/API_ROUTES.md)**  
Workflow `curl` : **[docs/WORKFLOW_CURL.md](docs/WORKFLOW_CURL.md)** — démo rapide `./scripts/demo_workflow.sh`, **usage normal** `./scripts/workflow_normal.sh`

## Variables d’environnement

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Connexion PostgreSQL locale |
| `API_HOST` | `0.0.0.0` pour exposer au LAN (défaut) |
| `API_PORT` | Port HTTP (défaut `8000`) |
| `CORS_ORIGINS` | URLs frontend autorisées (virgules) |
| `CORS_ALLOW_ALL` | `true` = tout autoriser en dev LAN |
| `LLM_PROVIDER` | `cursor` (défaut), `gemini`, ou `openai` |
| `CURSOR_API_KEY` | Clé Cursor — modèle Composer ([guide](docs/CURSOR_API_KEYS.md)) |
| `CURSOR_MODEL` | ex. `composer-2.5` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | Alternatives si autre `LLM_PROVIDER` |

Vérification : `GET /health` → `llm_provider`, `llm_configured`.

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

Connect to: `ws://<host>:8000/api/v1/ws/pipelines/{pipeline_id}`

| type | When |
|------|------|
| `pipeline.updated` | Pipeline metadata changed |
| `node.created` / `node.updated` / `node.deleted` | Node mutations |
| `edge.created` / `edge.deleted` | Edge mutations |
| `chat.message` | New chat message |
| `agent_task.updated` | Master delegated a task |

## MCP server (IDE, optionnel)

```bash
pip install -e ".[mcp]"
fastmcp run app/mcp/server.py:mcp
```

## Manual MVP test

```bash
curl http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/api/v1/pipelines \
  -H 'Content-Type: application/json' -d '{"name":"Bank ETL Demo"}' | jq .
```

## Security (MVP)

No authentication. Use only on a trusted LAN/VPN. Do not expose to the public Internet without HTTPS and auth (phase 2).

## Tests

```bash
pytest
```
