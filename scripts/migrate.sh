#!/usr/bin/env bash
# Applique les migrations Alembic (requis pour Gardien / pipeline_runs).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -d .venv ]]; then
  echo "Créez le venv d'abord (voir README)."
  exit 1
fi

echo "Migrations Alembic → $(.venv/bin/python -m alembic current 2>/dev/null | tail -1 || echo '?')"
.venv/bin/python -m alembic upgrade head
echo "OK — schéma à jour ($(.venv/bin/python -m alembic current | tail -1))"
