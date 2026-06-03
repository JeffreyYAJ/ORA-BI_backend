# Obtenir les clés API Cursor (DataPipe)

Ce guide explique comment configurer l’**Agent Maître** avec le modèle **Composer** de Cursor (via le SDK officiel).

## Configuration `.env`

```env
LLM_PROVIDER=cursor
CURSOR_API_KEY=
CURSOR_MODEL=composer-2.5
# Optionnel : répertoire pour l'agent local (défaut = racine du projet)
# CURSOR_WORKSPACE=/home/you/Desktop/ORA_BI_back
```

Redémarrez l’API après modification :

```bash
./scripts/run.sh
```

Vérification :

```bash
curl -s http://127.0.0.1:8000/health | jq .
# → "llm_provider": "cursor", "llm_configured": true
```

---

## Où créer une clé API Cursor

1. Ouvrez **[Cursor Dashboard → Integrations / API Keys](https://cursor.com/dashboard)** (section clés utilisateur).
2. Ou, pour une équipe : **Team Settings → Service accounts** (clé de compte de service).
3. Créez une clé et copiez-la **immédiatement** (souvent préfixe `cursor_...` ou format documenté sur le dashboard).
4. Collez-la dans `.env` :

   ```env
   CURSOR_API_KEY=cursor_votre_cle_ici
   ```

Documentation officielle :

- [Vue d’ensemble des API Cursor](https://cursor.com/docs/api)
- [SDK Python](https://cursor.com/docs/sdk/python)
- [SDK TypeScript](https://cursor.com/docs/sdk/typescript)

---

## Prérequis techniques (runtime local)

DataPipe utilise le **SDK Cursor en mode local** : l’agent s’exécute sur votre machine dans le workspace du projet.

- **Cursor** installé (application ou CLI selon votre environnement).
- Le binaire / bridge Cursor doit être accessible pour `AsyncClient.launch_bridge`.
- Connexion Internet pour l’API Cursor (facturation token-based).

Si le bridge ne démarre pas, l’API renverra un message `⚠️ Erreur Cursor` dans le chat au lieu d’un HTTP 500.

---

## Modèles disponibles

| Variable | Exemple | Description |
|----------|---------|-------------|
| `CURSOR_MODEL` | `composer-2.5` | Modèle Composer récent (recommandé) |
| | `composer-2` | Variante stable |
| | `auto` | Laisse Cursor choisir |

Pour lister les modèles autorisés sur votre compte (avec clé configurée) :

```bash
source .venv/bin/activate
export CURSOR_API_KEY="votre_cle"
python -c "from cursor_sdk import Cursor; print([m.id for m in Cursor.models.list()])"
```

---

## Autres fournisseurs (optionnel)

| `LLM_PROVIDER` | Clé requise |
|----------------|-------------|
| `cursor` | `CURSOR_API_KEY` |
| `gemini` | `GEMINI_API_KEY` |
| `openai` | `OPENAI_API_KEY` |

Un seul provider actif à la fois.

---

## Dépannage

| Symptôme | Piste |
|----------|--------|
| `llm_configured: false` | `CURSOR_API_KEY` vide ou API non redémarrée |
| `Invalid API key` | Régénérer la clé sur le dashboard |
| Erreur bridge / timeout | Cursor non installé ou workspace incorrect |
| Réponse lente | Normal : un agent Cursor peut prendre 30s–2min |
| `offline` dans le chat | Provider ≠ cursor ou clé absente |

---

## Sécurité

- Ne commitez **jamais** `.env` ni de clés dans `app/config.py`.
- Révoquez toute clé exposée par erreur sur GitHub.
