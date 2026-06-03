# Gardien — exécution, PII, approbations

## Vue d'ensemble

| Fonctionnalité | Implémentation |
|----------------|----------------|
| Agent **GUARDIAN** | Exécution auto après délégation Maître (`POST …/chat`) ou `POST …/agent-tasks/{id}/execute` |
| **PII / RGPD** | Scan regex + colonnes sensibles (`app/guardian/pii.py`), aperçus masqués dans les approbations |
| **Approbation humaine** | Table `guardian_approvals` — suppression colonnes, export, sink, run pipeline |
| **Exécution pipeline** | `POST …/runs` → pause sur risques → `POST …/approvals/{id}/decide` → `POST …/runs/{id}/resume` |
| **Questions pendant run** | Événements `GUARDIAN_QUESTION` + `POST …/runs/{id}/answer` |

## Migration

```bash
source .venv/bin/activate
alembic upgrade head   # révisions 002 + 003
```

Voir [CONTEXTUAL_QUESTIONS.md](CONTEXTUAL_QUESTIONS.md) — étude initiale et questions adaptées au contexte.

## Routes API

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/v1/pipelines/{id}/runs` | Démarre une exécution (approbation globale requise) |
| GET | `/api/v1/pipelines/{id}/runs/{run_id}` | État, événements, approbations en attente |
| POST | `/api/v1/pipelines/{id}/runs/{run_id}/resume` | Reprend après approbations / réponses |
| POST | `/api/v1/pipelines/{id}/runs/{run_id}/answer` | Répond à une question Gardien (`question_id`, `answer`) |
| GET | `/api/v1/pipelines/{id}/approvals` | Liste (`?status=PENDING`) |
| POST | `/api/v1/pipelines/{id}/approvals/{id}/decide` | `{"approved": true, "comment": "…"}` |
| GET | `/api/v1/pipelines/{id}/agent-tasks` | Liste des tâches agents |
| POST | `/api/v1/pipelines/{id}/agent-tasks/{id}/execute` | Exécute une tâche (GUARDIAN = scan PII complet) |

### PATCH nœud bloqué (409)

Si `data` contient `export: true`, `delete_columns`, ou suppression de colonnes dans `columns` :

```json
{
  "detail": {
    "detail": "Modification bloquée — approbation humaine requise…",
    "approval_required": true,
    "approval": { "id": "…", "operation_type": "DELETE_COLUMN", … }
  }
}
```

Puis `POST …/approvals/{id}/decide` avec `approved: true` pour appliquer le patch.

## WebSocket

Événements additionnels :

- `guardian.approval_required`
- `guardian.approval_resolved`
- `pipeline.run_updated`
- `pipeline.run_event`

## Test ultime (questions pendant l’exécution)

```bash
./scripts/guardian_questions_ultimate.sh
```

Scénario : pipeline avec PII → approbation du run → **question Gardien** (`AWAITING_USER_INPUT`) → réponse via `POST …/answer` → run `COMPLETED`.

## Exemple curl (workflow)

```bash
BASE=http://127.0.0.1:8000/api/v1
PID="<pipeline-uuid>"

# 1. Nœud avec PII
curl -s -X POST "$BASE/pipelines/$PID/nodes" -H "Content-Type: application/json" -d '{
  "type": "SOURCE", "subtype": "csv", "label": "Clients",
  "data": {"columns": ["email","nom"], "sample": "jean.dupont@banque.fr"}
}'

# 2. Délégation Gardien via chat
curl -s -X POST "$BASE/pipelines/$PID/chat" -H "Content-Type: application/json" \
  -d '{"content": "Vérifie les PII et conformité RGPD sur ce pipeline"}'

# 3. Lancer exécution
RUN=$(curl -s -X POST "$BASE/pipelines/$PID/runs" | jq -r '.run.id')

# 4. Approuver
APPROVAL=$(curl -s "$BASE/pipelines/$PID/approvals?status=PENDING" | jq -r '.[0].id')
curl -s -X POST "$BASE/pipelines/$PID/approvals/$APPROVAL/decide" \
  -H "Content-Type: application/json" -d '{"approved": true}'

# 5. Reprendre
curl -s -X POST "$BASE/pipelines/$PID/runs/$RUN/resume"
```

## Limites actuelles

- Pas d'exécution Python/SQL réelle des nœuds (simulation + statut `VALID`).
- PROFILER / ENGINEER : exécution simulée hors GUARDIAN.
- Détection PII heuristique (regex), pas de modèle NER.
