#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Virtual environment is not ready. Run scripts/setup-dev.sh first." >&2
  exit 1
fi

mkdir -p data
exec "$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
