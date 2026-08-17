#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
SERVICE_NAME="${SERVICE_NAME:-home-wifi-presence}"
INSTALL_SYSTEM_PACKAGES=1
START_SERVICE=1

if [[ "$VENV_DIR" != /* ]]; then
  VENV_DIR="$ROOT_DIR/$VENV_DIR"
fi

usage() {
  cat <<'USAGE'
Usage: scripts/setup-production.sh [--skip-system-packages] [--no-start]

Prepares the application and installs it as a systemd service. Run this from
the checkout that should be used in production.

Options:
  --skip-system-packages  Do not install apt packages such as arp-scan.
  --no-start              Enable the service without starting it now.
  -h, --help              Show this help text.

Environment:
  VENV_DIR      Virtual environment path (default: <checkout>/.venv).
  SERVICE_NAME  systemd service name (default: home-wifi-presence).
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-system-packages)
      INSTALL_SYSTEM_PACKAGES=0
      shift
      ;;
    --no-start)
      START_SERVICE=0
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

if [[ "$ROOT_DIR" =~ [[:space:]%] ]] || [[ "$VENV_DIR" =~ [[:space:]%] ]]; then
  echo "Production paths must not contain whitespace or '%'." >&2
  exit 1
fi

if [[ ! "$SERVICE_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.@-]*$ ]]; then
  echo "SERVICE_NAME contains unsupported characters: $SERVICE_NAME" >&2
  exit 1
fi

if [[ "$EUID" -eq 0 ]]; then
  SUDO=()
elif command -v sudo >/dev/null 2>&1; then
  SUDO=(sudo)
else
  echo "This script needs root access to install and enable the systemd service." >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ "$INSTALL_SYSTEM_PACKAGES" -eq 1 ]]; then
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found. Install arp-scan and python3-venv, then rerun with --skip-system-packages." >&2
    exit 1
  fi

  packages=()
  command -v arp-scan >/dev/null 2>&1 || packages+=(arp-scan)
  python3 -m venv --help >/dev/null 2>&1 || packages+=(python3-venv)

  if [[ "${#packages[@]}" -gt 0 ]]; then
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y "${packages[@]}"
  fi
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created $ROOT_DIR/.env from .env.example."
fi

mkdir -p data

unit_file="$(mktemp)"
trap 'rm -f "$unit_file"' EXIT

cat >"$unit_file" <<EOF_UNIT
[Unit]
Description=Home Wi-Fi Presence Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT_DIR
EnvironmentFile=$ROOT_DIR/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host \${APP_HOST} --port \${APP_PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF_UNIT

"${SUDO[@]}" install -m 0644 "$unit_file" "/etc/systemd/system/$SERVICE_NAME.service"
"${SUDO[@]}" systemctl daemon-reload

if [[ "$START_SERVICE" -eq 1 ]]; then
  "${SUDO[@]}" systemctl enable "$SERVICE_NAME.service"
  "${SUDO[@]}" systemctl restart "$SERVICE_NAME.service"
  "${SUDO[@]}" systemctl --no-pager --full status "$SERVICE_NAME.service"
else
  "${SUDO[@]}" systemctl enable "$SERVICE_NAME.service"
fi

cat <<EOF_READY
Production service installed.

Configuration:
  $ROOT_DIR/.env

Useful commands:
  sudo systemctl status $SERVICE_NAME
  sudo systemctl restart $SERVICE_NAME
  sudo journalctl -u $SERVICE_NAME -f
EOF_READY
