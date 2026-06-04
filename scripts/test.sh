#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

cd "$ROOT_DIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Virtual environment is not ready. Run scripts/setup-dev.sh first." >&2
  exit 1
fi

exec "$VENV_DIR/bin/python" -m pytest "$@"
