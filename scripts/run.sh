#!/usr/bin/env bash
# Lance l'API en local, accessible sur le réseau (LAN).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"

if [[ ! -d .venv ]]; then
  echo "Créez d'abord le venv : python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e ."
  exit 1
fi

echo "DataPipe API → http://${HOST}:${PORT}"
echo "Docs         → http://127.0.0.1:${PORT}/docs"
if command -v hostname >/dev/null 2>&1; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  if [[ -n "${LAN_IP:-}" ]]; then
    echo "Collègues (LAN) → http://${LAN_IP}:${PORT}"
  fi
fi

exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
