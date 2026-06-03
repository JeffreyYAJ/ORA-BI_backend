# Workflow ETL réel (base en ligne → validation → résultats)

## Prérequis

```bash
./scripts/run.sh          # API + migrations
# PostgreSQL avec DATABASE_URL du .env
```

## Lancer le scénario complet

```bash
./scripts/workflow_etl_real.sh
```

## Étapes du script

| # | Action | API / outil |
|---|--------|-------------|
| 1 | Créer `ora_demo.transactions` (8 lignes bancaires) | `scripts/seed_demo_banking.sql` |
| 2 | Pipeline SOURCE (PostgreSQL) → TRANSFORM → SINK | REST CRUD |
| 3 | **Lecture en ligne** : colonnes, COUNT, échantillon masqué RGPD | `POST …/etl/introspect` |
| 4 | Run pipeline : étude initiale + **questions** Profiler/Gardien + approbations | `POST …/runs`, `…/questions/…/answer` |
| 5 | Demande ETL en langage naturel (chat Maître) | `POST …/chat` |
| 6 | Exécution SQL SELECT + **tableau résultat** | `POST …/etl/execute` |
| 7 | Récupération résultats stockés | `GET …/etl/results` |

## Configuration SOURCE (nœud)

```json
{
  "schema": "ora_demo",
  "table": "transactions",
  "use_app_database": true
}
```

`use_app_database: true` utilise la même instance que `DATABASE_URL` (recommandé en dev).

## Exemple de résultat ETL

Demande : *« Agrège par devise, nombre et montant total, tri décroissant »*

| currency | nb_transactions | total_amount |
|----------|-----------------|--------------|
| EUR | 6 | 23586.44 |
| GBP | 1 | 780.00 |
| USD | 1 | 320.00 |

## Sécurité

- Uniquement requêtes **SELECT** sur la source
- Échantillons et résultats **masqués** (emails, IBAN) dans les réponses API
- Approbations Gardien pour actions sensibles (export, suppression colonnes, etc.)
