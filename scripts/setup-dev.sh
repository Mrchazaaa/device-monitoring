#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
INSTALL_SYSTEM_PACKAGES=1

usage() {
  cat <<'USAGE'
Usage: scripts/setup-dev.sh [--skip-system-packages]

Creates a Python virtual environment, installs requirements, creates .env
from .env.example when needed, and prepares the local data directory.

Options:
  --skip-system-packages  Do not install apt packages such as arp-scan.
  -h, --help              Show this help text.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-system-packages)
      INSTALL_SYSTEM_PACKAGES=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ "$INSTALL_SYSTEM_PACKAGES" -eq 1 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    packages=()
    command -v arp-scan >/dev/null 2>&1 || packages+=(arp-scan)
    python3 -m venv --help >/dev/null 2>&1 || packages+=(python3-venv)

    if [[ "${#packages[@]}" -gt 0 ]]; then
      sudo apt-get update
      sudo apt-get install -y "${packages[@]}"
    fi
  else
    echo "apt-get not found; skipping system package installation." >&2
    echo "Install arp-scan and python3-venv with your OS package manager if needed." >&2
  fi
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

mkdir -p data

cat <<EOF_READY
Development environment ready.

Activate it with:
  . "$VENV_DIR/bin/activate"

Run the app with:
  scripts/dev-server.sh

Run tests with:
  scripts/test.sh
EOF_READY
