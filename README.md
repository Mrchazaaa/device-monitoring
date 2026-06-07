# Home Wi-Fi Presence

[![Tests](https://github.com/mrchazaaa/device-monitoring/actions/workflows/tests.yml/badge.svg)](https://github.com/mrchazaaa/device-monitoring/actions/workflows/tests.yml)

A small Raspberry Pi service that scans your home LAN with `arp-scan`, stores device presence in SQLite, and exposes a local dashboard.

## Quick Start

For a fast development setup, run:

```bash
scripts/setup-dev.sh
scripts/dev-server.sh
```

Or run the setup steps manually:

```bash
sudo apt update
sudo apt install -y arp-scan python3-venv

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://<raspberry-pi-ip>:8000`.

Do not expose this app directly to the internet. The first version is intended for trusted LAN access and does not include login.

## Configuration

Environment variables:

| Name | Default | Description |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Host used by the systemd service. |
| `APP_PORT` | `8000` | HTTP port used by the systemd service. |
| `APP_LOG_LEVEL` | `DEBUG` | Log level for `app.*` loggers: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `DATABASE_URL` | `sqlite:///./data/presence.db` | SQLite or PostgreSQL connection string. `DATABASE_PATH` is still supported as a SQLite fallback. |
| `SCAN_INTERVAL_SECONDS` | `60` | Seconds between scans. |
| `OFFLINE_AFTER_MISSED_SCANS` | `2` | Missed scans before marking a device offline. |
| `NETWORK_INTERFACE` | auto-detect | Interface passed to `arp-scan`, for example `wlan0` or `eth0`. |
| `SCAN_CIDR` | auto-detect | Optional subnet override, for example `192.168.1.0/24`. |
| `LOKI_URL` | disabled | Full Loki push endpoint, for example `http://loki:3100/loki/api/v1/push`. |
| `LOKI_LABELS` | `{"application":"home-wifi-presence"}` | JSON object of static labels added to every Loki stream. |
| `LOKI_USERNAME` | unset | Optional username for Loki basic authentication. |
| `LOKI_PASSWORD` | unset | Optional password for Loki basic authentication. |

Application debug logs are enabled by default without enabling debug logs from Uvicorn or other dependencies. Set `APP_LOG_LEVEL` to a higher level to reduce application log output.

When `LOKI_URL` is configured, application and Uvicorn logs are sent to Loki on a background thread while continuing to use the existing console and systemd journal output. Each Loki stream also receives dynamic `severity` and `logger` labels. For example:

```bash
LOKI_URL=http://loki:3100/loki/api/v1/push
LOKI_LABELS='{"application":"home-wifi-presence","environment":"production"}'
```

PostgreSQL is selected with a standard connection URL. The database user must be able to create tables and indexes on first startup:

```bash
DATABASE_URL=postgresql://presence:secret@db.example.com/presence
```

Existing SQLite data is not automatically copied to PostgreSQL.

## Running as a Service

Edit `systemd/home-wifi-presence.service` so `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` match your checkout path, then install it:

```bash
sudo cp systemd/home-wifi-presence.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now home-wifi-presence
sudo systemctl status home-wifi-presence
```

`arp-scan` usually needs elevated network privileges. If you see an error like `pcap_activate: <interface>: You don't have permission to perform this capture on that device`, run the app with sufficient privileges:

```bash
sudo uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For a long-running install, either run the systemd service as root or grant packet-capture privileges to the installed binary:

```bash
sudo setcap cap_net_raw,cap_net_admin=eip "$(command -v arp-scan)"
```

If scanning still fails, set `NETWORK_INTERFACE` in `.env` to the LAN interface shown by `ip route`, for example `wlan0`, `eth0`, or `wlp1s0`.

## Development

```bash
scripts/test.sh
scripts/dev-server.sh
```
