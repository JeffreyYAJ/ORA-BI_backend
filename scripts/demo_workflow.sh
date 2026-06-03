#!/usr/bin/env bash
# Démonstration complète DataPipe + agents (curl)
# Usage : ./scripts/demo_workflow.sh
#        BASE=http://192.168.1.42:8000 ./scripts/demo_workflow.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
API="${BASE}/api/v1"

echo "=== Health ==="
curl -sf "${BASE}/health" | jq .

echo "=== Create pipeline ==="
PIPELINE_ID=$(curl -sf -X POST "${API}/pipelines" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo curl agents"}' | jq -r '.id')
echo "PIPELINE_ID=$PIPELINE_ID"

echo "=== Nodes ==="
NODE_SOURCE=$(curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/nodes" \
  -H "Content-Type: application/json" \
  -d '{"type":"SOURCE","subtype":"csv","label":"CSV","position":{"x":0,"y":0}}' | jq -r '.id')
NODE_TRANSFORM=$(curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/nodes" \
  -H "Content-Type: application/json" \
  -d '{"type":"TRANSFORM","subtype":"python_script","label":"Transform","position":{"x":250,"y":0}}' | jq -r '.id')
NODE_SINK=$(curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/nodes" \
  -H "Content-Type: application/json" \
  -d '{"type":"SINK","subtype":"postgres_sink","label":"Sink","position":{"x":500,"y":0}}' | jq -r '.id')

echo "=== Edges ==="
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/edges" \
  -H "Content-Type: application/json" \
  -d "{\"source_node_id\":\"${NODE_SOURCE}\",\"target_node_id\":\"${NODE_TRANSFORM}\"}" | jq -c .
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/edges" \
  -H "Content-Type: application/json" \
  -d "{\"source_node_id\":\"${NODE_TRANSFORM}\",\"target_node_id\":\"${NODE_SINK}\"}" | jq -c .

echo "=== Graph ==="
curl -sf "${API}/pipelines/${PIPELINE_ID}" | jq '{name, nodes: [.nodes[].label], edges: .edges}'

echo "=== Chat: describe pipeline ==="
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"content":"Décris ce pipeline."}' \
  | jq '{agent_preview: .agent_message.content_md[0:300], tasks: .agent_tasks}'

echo "=== Chat: trigger PROFILER delegation ==="
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"content":"Profile les données et détecte les anomalies logiques."}' \
  | jq '{agent_tasks, metadata: .agent_message.metadata}'

echo "=== Chat history (message count) ==="
curl -sf "${API}/pipelines/${PIPELINE_ID}/chat" | jq 'length'

echo "Done. PIPELINE_ID=$PIPELINE_ID"
