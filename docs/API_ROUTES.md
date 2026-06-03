# DataPipe — Référence des routes API

Base URL locale : `http://localhost:8000`  
Préfixe API : `/api/v1`  
Documentation interactive : `http://localhost:8000/docs`

**Authentification (MVP)** : aucune. Toutes les routes sont publiques en développement.

**IA requise** : seule la route `POST …/chat` appelle l’Agent Maître (OpenAI si `OPENAI_API_KEY` est définie, sinon mode offline).

---

## Sommaire

| # | Méthode | Route | IA | Tag |
|---|---------|-------|----|-----|
| 1 | GET | `/health` | Non | Santé |
| 2 | POST | `/api/v1/pipelines` | Non | Pipelines |
| 3 | GET | `/api/v1/pipelines` | Non | Pipelines |
| 4 | GET | `/api/v1/pipelines/{pipeline_id}` | Non | Pipelines |
| 5 | PATCH | `/api/v1/pipelines/{pipeline_id}` | Non | Pipelines |
| 6 | DELETE | `/api/v1/pipelines/{pipeline_id}` | Non | Pipelines |
| 7 | POST | `/api/v1/pipelines/{pipeline_id}/nodes` | Non | Nœuds |
| 8 | PATCH | `/api/v1/pipelines/{pipeline_id}/nodes/{node_id}` | Non | Nœuds |
| 9 | DELETE | `/api/v1/pipelines/{pipeline_id}/nodes/{node_id}` | Non | Nœuds |
| 10 | POST | `/api/v1/pipelines/{pipeline_id}/edges` | Non | Liaisons |
| 11 | DELETE | `/api/v1/pipelines/{pipeline_id}/edges/{edge_id}` | Non | Liaisons |
| 12 | GET | `/api/v1/pipelines/{pipeline_id}/chat` | Non | Chat |
| 13 | POST | `/api/v1/pipelines/{pipeline_id}/chat` | **Oui** | Chat |
| 14 | WS | `/api/v1/ws/pipelines/{pipeline_id}` | Non | WebSocket |

---

## 1. Santé

### `GET /health`

| | |
|---|---|
| **Utilité** | Vérifier que l’API est démarrée (load balancer, monitoring, CI). |
| **Usage typique** | Ping avant les tests ou au démarrage du frontend. |
| **Corps requête** | Aucun |
| **Réponse** | `200` — `{"status": "ok"}` |
| **IA** | Non |
| **WebSocket** | Non |

**Exemple**

```bash
curl http://localhost:8000/health
```

---

## 2. Pipelines (projets ETL)

Un **pipeline** est l’enveloppe du projet : nom, statut, design d’architecture cible (JSON), et graphe complet (nœuds + liaisons).

### `POST /api/v1/pipelines`

| | |
|---|---|
| **Utilité** | Créer un nouveau projet ETL vide sur le canvas. |
| **Usage typique** | Bouton « Nouveau pipeline » dans le frontend ReactFlow. |
| **Corps requête** | `PipelineCreate` |
| **Réponse** | `201` — `PipelineRead` (graphe vide : `nodes: []`, `edges: []`) |
| **IA** | Non |
| **WebSocket** | Émet `pipeline.updated` |

**Corps (JSON)**

```json
{
  "name": "Bank ETL Demo"
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `name` | string (1–255) | Oui | Nom affiché du projet |

---

### `GET /api/v1/pipelines`

| | |
|---|---|
| **Utilité** | Lister tous les projets (écran d’accueil, sélecteur de pipeline). |
| **Usage typique** | Dashboard listant les pipelines récents. |
| **Query params** | `skip` (défaut 0), `limit` (défaut 50, max 100) |
| **Réponse** | `200` — liste de `PipelineListItem` |
| **IA** | Non |

**Champs réponse**

| Champ | Description |
|-------|-------------|
| `id` | UUID du pipeline |
| `name` | Nom |
| `status` | `DRAFT`, `ACTIVE`, `ARCHIVED` |
| `updated_at` | Dernière modification |

---

### `GET /api/v1/pipelines/{pipeline_id}`

| | |
|---|---|
| **Utilité** | Charger le **graphe complet** pour ReactFlow (nœuds, positions, liaisons). |
| **Usage typique** | Ouverture d’un pipeline dans l’éditeur visuel ; source de vérité du canvas. |
| **Réponse** | `200` — `PipelineRead` |
| **Erreurs** | `404` si pipeline inconnu |
| **IA** | Non |

**Structure réponse (extrait)**

```json
{
  "id": "uuid",
  "name": "Bank ETL Demo",
  "status": "DRAFT",
  "architecture_design": null,
  "updated_at": "2026-06-03T12:00:00Z",
  "nodes": [
    {
      "id": "uuid",
      "type": "SOURCE",
      "subtype": "csv",
      "label": "Transactions CSV",
      "position": { "x": 0, "y": 0 },
      "data": {},
      "status": "IDLE"
    }
  ],
  "edges": [
    {
      "id": "uuid",
      "source": "uuid-noeud-source",
      "target": "uuid-noeud-cible"
    }
  ]
}
```

**Alignement ReactFlow** : `nodes[].id` = id ReactFlow ; `edges[].source` / `target` = handles.

---

### `PATCH /api/v1/pipelines/{pipeline_id}`

| | |
|---|---|
| **Utilité** | Mettre à jour les métadonnées du projet (nom, statut, cible décisionnelle). |
| **Usage typique** | Renommer le projet ; passer en `ACTIVE` ; enregistrer le design star/snowflake choisi par l’IA. |
| **Corps requête** | `PipelineUpdate` (tous les champs optionnels) |
| **Réponse** | `200` — `PipelineRead` |
| **IA** | Non |
| **WebSocket** | Émet `pipeline.updated` |

**Corps (JSON) — exemple**

```json
{
  "name": "Pipeline Production",
  "status": "ACTIVE",
  "architecture_design": {
    "model_type": "STAR",
    "scd_type": "TYPE_2",
    "justification": "Choix IA pour le DWH bancaire"
  }
}
```

| Champ | Valeurs possibles |
|-------|-------------------|
| `status` | `DRAFT`, `ACTIVE`, `ARCHIVED` |

---

### `DELETE /api/v1/pipelines/{pipeline_id}`

| | |
|---|---|
| **Utilité** | Supprimer définitivement un projet et tout ce qui est lié (nœuds, edges, chat, tâches agents). |
| **Usage typique** | Suppression depuis la liste des projets. |
| **Réponse** | `204` (sans corps) |
| **IA** | Non |

---

## 3. Nœuds (blocs du graphe)

Un **nœud** représente une étape du flux : source de données, transformation, ou destination.

### `POST /api/v1/pipelines/{pipeline_id}/nodes`

| | |
|---|---|
| **Utilité** | Ajouter un bloc sur le canvas (CSV, JSON, script Python, requête SQL, sink Postgres, etc.). |
| **Usage typique** | Glisser-déposer ou « Ajouter une source » dans ReactFlow. |
| **Corps requête** | `NodeCreate` |
| **Réponse** | `201` — `NodeRead` |
| **IA** | Non |
| **WebSocket** | Émet `node.created` |

**Corps (JSON) — exemple source CSV**

```json
{
  "type": "SOURCE",
  "subtype": "csv",
  "label": "Transactions CSV",
  "position": { "x": 100, "y": 200 },
  "data": { "file_path": "/uploads/transactions.csv" },
  "status": "IDLE"
}
```

| Champ | Valeurs / notes |
|-------|-----------------|
| `type` | `SOURCE`, `TRANSFORM`, `SINK` |
| `subtype` | `csv`, `json`, `python_script`, `sql_query`, `postgres_sink`, `sqlite`, `generic` |
| `data` | JSON libre : schéma, code généré, config connexion |
| `status` | `IDLE`, `PENDING`, `VALID`, `ERROR` |

---

### `PATCH /api/v1/pipelines/{pipeline_id}/nodes/{node_id}`

| | |
|---|---|
| **Utilité** | Modifier un nœud existant (position, label, données internes, statut d’exécution). |
| **Usage typique** | Déplacer un nœud sur la grille ; mettre à jour le code de transformation ; marquer `VALID` ou `ERROR`. |
| **Corps requête** | `NodeUpdate` (champs partiels) |
| **Réponse** | `200` — `NodeRead` |
| **IA** | Non |
| **WebSocket** | Émet `node.updated` |

**Exemple — déplacement**

```json
{
  "position": { "x": 250, "y": 180 }
}
```

---

### `DELETE /api/v1/pipelines/{pipeline_id}/nodes/{node_id}`

| | |
|---|---|
| **Utilité** | Retirer un bloc du graphe ; supprime aussi les **liaisons** connectées à ce nœud. |
| **Usage typique** | Suppression d’un nœud depuis le canvas. |
| **Réponse** | `204` |
| **IA** | Non |
| **WebSocket** | Émet `node.deleted` |

---

## 4. Liaisons (edges — flux de données)

Une **liaison** relie deux nœuds et symbolise le flux de données entre eux.

### `POST /api/v1/pipelines/{pipeline_id}/edges`

| | |
|---|---|
| **Utilité** | Connecter deux nœuds (câble visuel source → cible). |
| **Usage typique** | L’utilisateur relie la sortie d’une source vers une transformation dans ReactFlow. |
| **Corps requête** | `EdgeCreate` |
| **Réponse** | `201` — `EdgeRead` |
| **Erreurs** | `400` si source = cible ; `404` si nœud hors pipeline |
| **IA** | Non |
| **WebSocket** | Émet `edge.created` |

**Corps (JSON)**

```json
{
  "source_node_id": "uuid-noeud-source",
  "target_node_id": "uuid-noeud-cible"
}
```

**Réponse**

```json
{
  "id": "uuid-edge",
  "source": "uuid-noeud-source",
  "target": "uuid-noeud-cible"
}
```

---

### `DELETE /api/v1/pipelines/{pipeline_id}/edges/{edge_id}`

| | |
|---|---|
| **Utilité** | Supprimer une connexion entre deux nœuds sans supprimer les nœuds. |
| **Usage typique** | L’utilisateur déconnecte deux blocs sur le canvas. |
| **Réponse** | `204` |
| **IA** | Non |
| **WebSocket** | Émet `edge.deleted` |

---

## 5. Chat (Agent Maître)

### `GET /api/v1/pipelines/{pipeline_id}/chat`

| | |
|---|---|
| **Utilité** | Récupérer l’**historique** des messages utilisateur / Agent Maître. |
| **Usage typique** | Afficher le fil de discussion au chargement du panneau chat. |
| **Réponse** | `200` — liste de `ChatMessageRead` (ordre chronologique) |
| **IA** | Non (lecture base de données uniquement) |

**Champs message**

| Champ | Description |
|-------|-------------|
| `sender` | `USER` ou `MASTER_AGENT` |
| `content_md` | Contenu Markdown |
| `metadata` | Ex. `requires_user_input`, `delegations` |
| `created_at` | Horodatage |

---

### `POST /api/v1/pipelines/{pipeline_id}/chat`

| | |
|---|---|
| **Utilité** | Envoyer un message à l’**Agent Maître** : conseils, délégation aux agents spécialisés, questions sur le graphe. |
| **Usage typique** | Zone de saisie chat dans l’UI ; assistant IA du pipeline ETL. |
| **Corps requête** | `ChatMessageCreate` |
| **Réponse** | `200` — `ChatResponse` |
| **IA** | **Oui** — OpenAI si `OPENAI_API_KEY` ; sinon réponse offline + délégations possibles |
| **WebSocket** | Émet `chat.message` (×2) et `agent_task.updated` si délégation |

**Corps (JSON)**

```json
{
  "content": "Décris mon pipeline et propose un profilage des anomalies"
}
```

**Réponse (JSON)**

```json
{
  "user_message": { "id": "...", "sender": "USER", "content_md": "...", ... },
  "agent_message": { "id": "...", "sender": "MASTER_AGENT", "content_md": "...", ... },
  "agent_tasks": [
    {
      "id": "...",
      "agent_role": "PROFILER",
      "instruction": "...",
      "status": "PENDING",
      ...
    }
  ]
}
```

**Comportement IA**

- Analyse le contexte du graphe (nœuds, liaisons, statuts).
- Peut créer des `AgentTask` en statut `PENDING` (Profiler, Engineer, etc.) — non exécutées en MVP.
- Peut demander upload de fichier ou credentials DB (`metadata.requires_user_input`).

---

## 6. WebSocket (synchronisation temps réel)

### `WS /api/v1/ws/pipelines/{pipeline_id}`

| | |
|---|---|
| **Utilité** | Recevoir en temps réel les changements du pipeline (multi-onglets, collaboration future). |
| **Usage typique** | Le frontend s’abonne à la room du `pipeline_id` et met à jour le canvas sans recharger. |
| **IA** | Non (canal de notification uniquement) |
| **Protocole** | Connexion WebSocket ; le client peut envoyer du texte (keep-alive) ; le serveur pousse des événements JSON |

**Format événement**

```json
{
  "type": "node.updated",
  "pipeline_id": "uuid",
  "payload": { }
}
```

| `type` | Déclenché par |
|--------|----------------|
| `pipeline.updated` | POST/PATCH pipeline |
| `node.created` | POST node |
| `node.updated` | PATCH node |
| `node.deleted` | DELETE node |
| `edge.created` | POST edge |
| `edge.deleted` | DELETE edge |
| `chat.message` | POST chat (message user + réponse agent) |
| `agent_task.updated` | Délégation créée via POST chat |

**Exemple connexion**

```
ws://localhost:8000/api/v1/ws/pipelines/{pipeline_id}
```

---

## 7. Outils MCP (hors routes HTTP FastAPI)

Serveur lancé séparément pour l’IDE Cursor :

```bash
fastmcp run app/mcp/server.py:mcp
```

| Outil | Utilité | IA |
|-------|---------|-----|
| `get_pipeline_context` | Contexte graphe complet pour raisonnement agent | Non (DB) |
| `summarize_graph` | Résumé texte du pipeline | Non |
| `create_agent_task_tool` | Créer une tâche agent `PENDING` | Non |
| `stub_specialized_agent` | Message stub agents non disponibles en MVP | Non |

---

## Parcours de test recommandé

1. `GET /health`
2. `POST /api/v1/pipelines` → noter `id`
3. `POST …/nodes` × 3 (SOURCE → TRANSFORM → SINK)
4. `POST …/edges` × 2
5. `GET /api/v1/pipelines/{id}` → vérifier le graphe
6. `POST …/chat` → tester l’Agent Maître
7. WebSocket + `PATCH …/nodes/{id}` → vérifier `node.updated`

---

## Codes d’erreur courants

| Code | Signification |
|------|----------------|
| `404` | Pipeline, nœud ou liaison introuvable |
| `400` | Liaison invalide (source = cible) |
| `422` | Corps JSON invalide (validation Pydantic) |
| `500` | Erreur serveur (DB, LLM, etc.) |

---

## Fichiers source

| Route | Fichier |
|-------|---------|
| Pipelines | `app/api/v1/pipelines.py` |
| Nœuds | `app/api/v1/nodes.py` |
| Liaisons | `app/api/v1/edges.py` |
| Chat | `app/api/v1/chat.py` |
| WebSocket | `app/api/v1/ws.py` |
| Montage app | `app/main.py` |
| Schémas | `app/schemas/` |
| Événements WS | `app/websocket/events.py` |
