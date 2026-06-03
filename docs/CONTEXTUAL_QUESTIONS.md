# Questions contextuelles — workflow

## Principe

1. **Étude initiale** (`INITIAL_STUDY`) au premier `resume` d’un run : scan des nœuds, PII masqués, lacunes (pas de SOURCE/SINK, etc.).
2. **Profiler** puis **Gardien** (si PII) génèrent des questions via `question_generator` (LLM si configuré, sinon règles).
3. **Réponses** stockées dans `user_questions` + `run.context.user_answers` — réutilisées par la suite.
4. **Par nœud** (`NODE_EXECUTION`) : questions RGPD adaptées au nœud courant.
5. **Tâches agents** (`AGENT_TASK`) : chaque agent (Profiler, Engineer, Guardian, …) pose des questions liées à son rôle et au contexte.

## API

| Méthode | Route |
|---------|--------|
| GET | `/api/v1/pipelines/{id}/questions?run_id=&pending_only=true` |
| POST | `/api/v1/pipelines/{id}/questions/{question_id}/answer` `{"answer": "..."}` |
| POST | `/api/v1/pipelines/{id}/runs/{run_id}/answer` (alias, `question_id` UUID) |

## WebSocket

- `user_input.required` — nouvelle question
- `user_input.answered` — réponse enregistrée

## Migration

```bash
alembic upgrade head   # révision 003
```
