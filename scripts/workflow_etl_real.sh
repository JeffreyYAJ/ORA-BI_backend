#!/usr/bin/env bash
# Workflow ETL complet :
# 1. Seed base démo  2. Pipeline SOURCE PostgreSQL  3. Introspection en ligne
# 4. Run + validation utilisateur  5. Demande ETL  6. Affichage résultats
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then set -a; source .env; set +a; fi

BASE="${API_BASE:-http://127.0.0.1:8000/api/v1}"
HDR=(-H "Content-Type: application/json")
PGURL="${DATABASE_URL:-postgresql+asyncpg://datapipe:datapipe@localhost:5432/datapipe}"
PGURL="${PGURL/postgresql+asyncpg/postgresql}"

echo "=============================================="
echo " Workflow ETL réel — base en ligne → validation → ETL"
echo "=============================================="

curl -sf "${BASE%/api/v1}/health" | jq . >/dev/null || { echo "❌ API non démarrée"; exit 1; }

echo ""
echo "=== 1. Seed schéma ora_demo.transactions ==="
if command -v psql >/dev/null 2>&1; then
  psql "$PGURL" -f scripts/seed_demo_banking.sql -q
  echo "   OK (psql)"
else
  .venv/bin/python -c "
import asyncio, asyncpg
async def main():
    dsn = '${PGURL}'
    sql = open('scripts/seed_demo_banking.sql').read()
    conn = await asyncpg.connect(dsn)
    await conn.execute(sql)
    await conn.close()
asyncio.run(main())
"
  echo "   OK (asyncpg)"
fi

echo ""
echo "=== 2. Créer pipeline ETL bancaire ==="
PIPE=$(curl -sf -X POST "$BASE/pipelines" "${HDR[@]}" -d '{"name":"ETL Transactions ora_demo"}')
PID=$(echo "$PIPE" | jq -r '.id')
echo "   pipeline_id=$PID"

SRC=$(curl -sf -X POST "$BASE/pipelines/$PID/nodes" "${HDR[@]}" -d '{
  "type": "SOURCE",
  "subtype": "sql_query",
  "label": "PostgreSQL ora_demo.transactions",
  "position": {"x": 0, "y": 100},
  "data": {
    "schema": "ora_demo",
    "table": "transactions",
    "use_app_database": true
  }
}')
N_SRC=$(echo "$SRC" | jq -r '.id')

TRANS=$(curl -sf -X POST "$BASE/pipelines/$PID/nodes" "${HDR[@]}" -d '{
  "type": "TRANSFORM",
  "subtype": "sql_query",
  "label": "Agrégation par devise",
  "position": {"x": 300, "y": 100},
  "data": {"description": "GROUP BY currency"}
}')
N_TR=$(echo "$TRANS" | jq -r '.id')

SINK=$(curl -sf -X POST "$BASE/pipelines/$PID/nodes" "${HDR[@]}" -d '{
  "type": "SINK",
  "subtype": "postgres_sink",
  "label": "Rapport agrégé",
  "position": {"x": 600, "y": 100},
  "data": {"schema": "ora_demo", "table": "transactions_agg"}
}')
N_SN=$(echo "$SINK" | jq -r '.id')

curl -sf -X POST "$BASE/pipelines/$PID/edges" "${HDR[@]}" -d "{\"source_node_id\":\"$N_SRC\",\"target_node_id\":\"$N_TR\"}" >/dev/null
curl -sf -X POST "$BASE/pipelines/$PID/edges" "${HDR[@]}" -d "{\"source_node_id\":\"$N_TR\",\"target_node_id\":\"$N_SN\"}" >/dev/null
echo "   Graphe SOURCE → TRANSFORM → SINK"

echo ""
echo "=== 3. Lecture base en ligne (introspection) ==="
INTRO=$(curl -sf -X POST "$BASE/pipelines/$PID/etl/introspect" "${HDR[@]}" -d '{}')
echo "$INTRO" | jq -r '.live_data_profile.summary_md'
echo "$INTRO" | jq '{rows: .live_data_profile.primary_source.row_count, columns: .live_data_profile.primary_source.column_names}'

echo ""
echo "=== 4. Lancer exécution + validations utilisateur ==="
RUN=$(curl -sf -X POST "$BASE/pipelines/$PID/runs" "${HDR[@]}" -d '{}')
RUN_ID=$(echo "$RUN" | jq -r '.run.id')
echo "   run_id=$RUN_ID"

approve_all() {
  curl -sf "$BASE/pipelines/$PID/approvals?status=PENDING" | jq -c '.[]' | while read -r a; do
    aid=$(echo "$a" | jq -r '.id')
    curl -sf -X POST "$BASE/pipelines/$PID/approvals/$aid/decide" "${HDR[@]}" \
      -d '{"approved":true,"comment":"Workflow ETL réel"}' >/dev/null
  done
}

answer_all() {
  curl -sf "$BASE/pipelines/$PID/questions?run_id=$RUN_ID&pending_only=true" | jq -c '.[]' | while read -r q; do
    qid=$(echo "$q" | jq -r '.id')
    echo "   Q: $(echo "$q" | jq -r '.question_text')" >&2
    curl -sf -X POST "$BASE/pipelines/$PID/questions/$qid/answer" "${HDR[@]}" \
      -d '{"answer":"id — identifiant technique de la ligne (choix validé pour le workflow)"}' >/dev/null
  done
}

for round in 1 2 3 4 5 6 7 8; do
  ST=$(curl -sf "$BASE/pipelines/$PID/runs/$RUN_ID" | jq -r '.status')
  echo "   round $round status=$ST" >&2
  [[ "$ST" == "COMPLETED" ]] && break
  approve_all || true
  answer_all || true
  curl -sf -X POST "$BASE/pipelines/$PID/runs/$RUN_ID/resume" "${HDR[@]}" -d '{}' >/dev/null 2>&1 || true
done

echo ""
echo "=== 5. Demande ETL utilisateur (chat + exécution) ==="
ETL_REQUEST="Agrège les transactions par devise : nombre d'opérations et montant total, trié par montant décroissant."
echo "   Demande: $ETL_REQUEST"

CHAT=$(curl -sf -X POST "$BASE/pipelines/$PID/chat" "${HDR[@]}" -d "$(jq -n --arg c "$ETL_REQUEST" '{content: $c}')")
echo ""
echo "--- Réponse Agent Maître (extrait) ---"
echo "$CHAT" | jq -r '.agent_message.content_md' | head -40

echo ""
echo "=== 6. Résultats ETL (API dédiée) ==="
ETL=$(curl -sf -X POST "$BASE/pipelines/$PID/etl/execute" "${HDR[@]}" -d "$(jq -n --arg i "$ETL_REQUEST" '{instruction: $i}')")
echo "$ETL" | jq '{sql, explanation, row_count}'
echo ""
echo "--- Tableau résultat (Markdown) ---"
echo "$ETL" | jq -r '.summary_md'

echo ""
echo "=== 7. GET /etl/results ==="
curl -sf "$BASE/pipelines/$PID/etl/results" | jq '{instruction, sql, row_count, rows: .rows}'

echo ""
echo "=============================================="
echo " ✅ Workflow ETL réel terminé"
echo " Pipeline: $PID"
echo " Run:      $RUN_ID"
echo "=============================================="
