#!/usr/bin/env bash
# Test ultime : exécution pipeline → approbations → question Gardien (PII) → réponse → fin
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="${API_BASE:-http://127.0.0.1:8000/api/v1}"
HDR=(-H "Content-Type: application/json")

echo "=== Test ultime Gardien — questions pendant l'exécution ==="
echo "API: $BASE"
echo

curl -sf "${BASE%/api/v1}/health" >/dev/null || { echo "❌ API injoignable. Lancez ./scripts/run.sh"; exit 1; }

echo "1. Création pipeline « Guardian Questions Demo »"
PIPE=$(curl -sf -X POST "$BASE/pipelines" "${HDR[@]}" -d '{"name":"Guardian Questions Demo"}')
PID=$(echo "$PIPE" | jq -r '.id')
echo "   pipeline_id=$PID"

echo "2. Nœud SOURCE avec PII (déclenchera question après approbations)"
NODE=$(curl -sf -X POST "$BASE/pipelines/$PID/nodes" "${HDR[@]}" -d '{
  "type": "SOURCE",
  "subtype": "csv",
  "label": "Clients sensibles",
  "data": {
    "columns": ["email", "nom", "telephone"],
    "sample_row": "claire.bernard@banque-exemple.fr",
    "phone": "+33612345678"
  }
}')
NID=$(echo "$NODE" | jq -r '.id')
echo "   node_id=$NID"

echo "3. Démarrage exécution (pause : approbation PIPELINE_RUN)"
RUN_JSON=$(curl -sf -X POST "$BASE/pipelines/$PID/runs" "${HDR[@]}" -d '{}')
RUN_ID=$(echo "$RUN_JSON" | jq -r '.run.id')
RUN_STATUS=$(echo "$RUN_JSON" | jq -r '.run.status')
echo "   run_id=$RUN_ID status=$RUN_STATUS"
if [[ "$RUN_STATUS" != "AWAITING_APPROVAL" ]]; then
  echo "❌ Attendu AWAITING_APPROVAL, reçu $RUN_STATUS"
  exit 1
fi

approve_all_pending() {
  local step="$1"
  local approvals
  approvals=$(curl -sf "$BASE/pipelines/$PID/approvals?status=PENDING" || echo "[]")
  local count
  count=$(echo "$approvals" | jq 'length')
  if [[ "$count" -eq 0 ]]; then
    echo "   ($step) aucune approbation en attente" >&2
    return 0
  fi
  echo "   ($step) $count approbation(s) à valider" >&2
  echo "$approvals" | jq -c '.[]' | while read -r row; do
    local aid title
    aid=$(echo "$row" | jq -r '.id')
    title=$(echo "$row" | jq -r '.title')
    echo "      → Approuver: $title ($aid)" >&2
    curl -sf -X POST "$BASE/pipelines/$PID/approvals/$aid/decide" "${HDR[@]}" \
      -d '{"approved": true, "comment": "Test ultime — validation humaine"}' >/dev/null
  done
}

answer_all_pending_questions() {
  local qs count
  qs=$(curl -sf "$BASE/pipelines/$PID/questions?run_id=$RUN_ID&pending_only=true" || echo "[]")
  count=$(echo "$qs" | jq 'length')
  [[ "$count" -eq 0 ]] && return 0
  echo "   Réponses à $count question(s) contextuelle(s)" >&2
  echo "$qs" | jq -c '.[]' | while read -r q; do
    local qid text role
    qid=$(echo "$q" | jq -r '.id')
    text=$(echo "$q" | jq -r '.question_text')
    role=$(echo "$q" | jq -r '.agent_role')
    echo "      → [$role] $text" >&2
    curl -sf -X POST "$BASE/pipelines/$PID/questions/$qid/answer" "${HDR[@]}" \
      -d '{"answer": "Choix validé pour le test — adapté au contexte étudié."}' >/dev/null
  done
}

echo "4–5. Boucle approbations, étude initiale, questions contextuelles"
get_run() {
  curl -sf "$BASE/pipelines/$PID/runs/$RUN_ID"
}

advance_until_question_or_done() {
  local max_rounds=8 round=0
  while (( round++ < max_rounds )); do
    local state status pending
    state=$(get_run)
    status=$(echo "$state" | jq -r '.status')
    pending=$(echo "$state" | jq '[.pending_approvals[]?] | length')
    echo "   status=$status pending_approvals=$pending" >&2

    if [[ "$status" == "AWAITING_USER_INPUT" ]]; then
      answer_all_pending_questions
      continue
    fi
    if [[ "$status" == "COMPLETED" ]]; then
      printf '%s' "$state"
      return 0
    fi

    if [[ "$pending" -gt 0 ]]; then
      approve_all_pending "round-$round"
      continue
    fi

    if [[ "$status" == "AWAITING_APPROVAL" || "$status" == "RUNNING" ]]; then
      state=$(curl -s -X POST "$BASE/pipelines/$PID/runs/$RUN_ID/resume" "${HDR[@]}" -d '{}')
      if echo "$state" | jq -e '.detail' >/dev/null 2>&1; then
        echo "   resume: $(echo "$state" | jq -r '.detail')" >&2
        continue
      fi
      status=$(echo "$state" | jq -r '.status')
      echo "   après resume: status=$status" >&2
      if [[ "$status" == "AWAITING_USER_INPUT" ]]; then
        answer_all_pending_questions
        continue
      fi
      if [[ "$status" == "COMPLETED" ]]; then
        printf '%s' "$state"
        return 0
      fi
    fi
  done
  echo "❌ Trop de tours sans atteindre une question ou la fin" >&2
  exit 1
}

STATE=$(advance_until_question_or_done)
STATUS=$(echo "$STATE" | jq -r '.status')

echo "6. Questions posées (étude initiale + exécution)"
echo "$STATE" | jq -r '.pending_questions[]? | "   - [\(.agent_role)] \(.question_text)"' 2>/dev/null || true
echo "$STATE" | jq -r '[.events[] | select(.event_type == "USER_QUESTION" or .event_type == "GUARDIAN_QUESTION")] | .[-3:][] | "   event: \(.message_md | .[0:100])"'

while [[ "$STATUS" == "AWAITING_USER_INPUT" ]]; do
  answer_all_pending_questions
  STATE=$(curl -sf -X POST "$BASE/pipelines/$PID/runs/$RUN_ID/resume" "${HDR[@]}" -d '{}' 2>/dev/null || get_run)
  STATUS=$(echo "$STATE" | jq -r '.status')
  echo "   status=$STATUS" >&2
done

if [[ "$STATUS" == "AWAITING_APPROVAL" ]]; then
  approve_all_pending "post-questions"
  STATE=$(curl -sf -X POST "$BASE/pipelines/$PID/runs/$RUN_ID/resume" "${HDR[@]}" -d '{}')
  STATUS=$(echo "$STATE" | jq -r '.status')
fi

ANSWER_JSON=$(get_run)
FINAL_STATUS=$(echo "$ANSWER_JSON" | jq -r '.status')
echo "7. Statut final=$FINAL_STATUS"

if [[ "$FINAL_STATUS" != "COMPLETED" ]]; then
  echo "❌ Attendu COMPLETED, reçu $FINAL_STATUS"
  echo "$ANSWER_JSON" | jq '.events[-5:]'
  exit 1
fi

echo
echo "=== ✅ Test ultime réussi ==="
echo "Pipeline : $PID"
echo "Run      : $RUN_ID"
echo "Événements clés :"
echo "$ANSWER_JSON" | jq -r '.events[] | "  - \(.event_type): \(.message_md | .[0:80])"'
