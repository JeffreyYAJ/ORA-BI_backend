#!/usr/bin/env bash
# Workflow d'utilisation normale — scénario bancaire complet
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
API="${BASE}/api/v1"

echo "=============================================="
echo " DataPipe — Workflow utilisation normale"
echo "=============================================="

echo ""
echo "=== 0. Santé API + LLM ==="
curl -sf "${BASE}/health" | jq .

echo ""
echo "=== 1. Créer le projet ETL ==="
PIPELINE_ID=$(curl -sf -X POST "${API}/pipelines" \
  -H "Content-Type: application/json" \
  -d '{"name":"Flux transactions bancaires Q1 2026"}' | jq -r '.id')
echo "PIPELINE_ID=$PIPELINE_ID"

echo ""
echo "=== 2. Ajouter les nœuds (SOURCE → TRANSFORM → SINK) ==="
NODE_SOURCE=$(curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/nodes" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "SOURCE",
    "subtype": "csv",
    "label": "Transactions CSV",
    "position": {"x": 0, "y": 120},
    "data": {
      "file": "transactions_2024.csv",
      "delimiter": ";",
      "encoding": "utf-8"
    },
    "status": "IDLE"
  }' | jq -r '.id')
echo "NODE_SOURCE=$NODE_SOURCE"

NODE_TRANSFORM=$(curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/nodes" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "TRANSFORM",
    "subtype": "python_script",
    "label": "Nettoyage montants et devises",
    "position": {"x": 320, "y": 120},
    "data": {
      "description": "Normaliser montants, supprimer doublons, valider IBAN"
    },
    "status": "IDLE"
  }' | jq -r '.id')
echo "NODE_TRANSFORM=$NODE_TRANSFORM"

NODE_SINK=$(curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/nodes" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "SINK",
    "subtype": "postgres_sink",
    "label": "DWH fact_transactions",
    "position": {"x": 640, "y": 120},
    "data": {
      "table": "fact_transactions",
      "schema": "dwh_banking"
    },
    "status": "IDLE"
  }' | jq -r '.id')
echo "NODE_SINK=$NODE_SINK"

echo ""
echo "=== 3. Relier le flux ==="
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/edges" \
  -H "Content-Type: application/json" \
  -d "{\"source_node_id\": \"${NODE_SOURCE}\", \"target_node_id\": \"${NODE_TRANSFORM}\"}" | jq -c '{id, source, target}'
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/edges" \
  -H "Content-Type: application/json" \
  -d "{\"source_node_id\": \"${NODE_TRANSFORM}\", \"target_node_id\": \"${NODE_SINK}\"}" | jq -c '{id, source, target}'

echo ""
echo "=== 4. Définir l architecture cible (STAR) ==="
curl -sf -X PATCH "${API}/pipelines/${PIPELINE_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ACTIVE",
    "architecture_design": {
      "model_type": "STAR",
      "scd_type": "TYPE_2",
      "target_tables": ["fact_transactions", "dim_client", "dim_compte"],
      "justification": "Modèle en étoile pour reporting OLAP bancaire"
    }
  }' | jq '{id, name, status, architecture_design}'

echo ""
echo "=== 5. Simuler préparation exécution (nœud en PENDING) ==="
curl -sf -X PATCH "${API}/pipelines/${PIPELINE_ID}/nodes/${NODE_TRANSFORM}" \
  -H "Content-Type: application/json" \
  -d '{"status": "PENDING"}' | jq '{id, label, status}'

echo ""
echo "=== 6. Vérifier le graphe (comme ReactFlow) ==="
curl -sf "${API}/pipelines/${PIPELINE_ID}" | jq '{
  name, status,
  node_count: (.nodes | length),
  edge_count: (.edges | length),
  nodes: [.nodes[] | {label, type, subtype, status}],
  edges
}'

echo ""
echo "=== 7. Chat — découverte du pipeline (Agent Maître / Cursor) ==="
echo "(peut prendre 30s–2min...)"
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"content": "Décris mon pipeline ETL et dis-moi ce qui manque pour le lancer en production."}' \
  | jq '{
    user: .user_message.content_md[0:80],
    agent_preview: .agent_message.content_md[0:500],
    tasks_count: (.agent_tasks | length),
    metadata: .agent_message.metadata
  }'

echo ""
echo "=== 8. Chat — demande de profilage (délégation PROFILER) ==="
echo "(peut prendre 30s–2min...)"
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"content": "Profile les données du CSV et détecte les anomalies logiques sans règles métier fixes."}' \
  | jq '{
    agent_preview: .agent_message.content_md[0:400],
    agent_tasks: [.agent_tasks[] | {agent_role, status, instruction: .instruction[0:120]}],
    metadata: .agent_message.metadata
  }'

echo ""
echo "=== 9. Chat — demande script de transformation (délégation ENGINEER) ==="
echo "(peut prendre 30s–2min...)"
curl -sf -X POST "${API}/pipelines/${PIPELINE_ID}/chat" \
  -H "Content-Type: application/json" \
  -d "{\"content\": \"Génère un script pandas pour le nœud de transformation ${NODE_TRANSFORM} (nettoyage montants).\"}" \
  | jq '{
    agent_preview: .agent_message.content_md[0:400],
    agent_tasks: [.agent_tasks[] | {agent_role, status, node_id}],
    metadata: .agent_message.metadata
  }'

echo ""
echo "=== 10. Historique chat ==="
curl -sf "${API}/pipelines/${PIPELINE_ID}/chat" | jq '[.[] | {sender, preview: .content_md[0:100], created_at}]'

echo ""
echo "=== 11. Liste des pipelines ==="
curl -sf "${API}/pipelines?limit=5" | jq '[.[] | {id, name, status, updated_at}]'

echo ""
echo "=============================================="
echo " Terminé."
echo " PIPELINE_ID=$PIPELINE_ID"
echo " Swagger: ${BASE}/docs"
echo "=============================================="
