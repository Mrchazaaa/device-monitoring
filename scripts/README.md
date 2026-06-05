# Scripts

Run these scripts from the repository checkout. They use `.venv` by default; set
`VENV_DIR` to use a different virtual environment.

| Script | Purpose |
| --- | --- |
| `setup-dev.sh` | Creates the virtual environment, installs Python requirements and missing `apt` packages, copies `.env.example` to `.env` when needed, and creates `data/`. Pass `--skip-system-packages` to skip `apt` installs. |
| `setup-production.sh` | Prepares the production environment, installs a path-aware systemd service, and enables and starts it. Pass `--no-start` to install without starting or `--skip-system-packages` to skip `apt` installs. |
| `dev-server.sh` | Loads `.env` and starts the app with Uvicorn reload enabled. Uses `APP_HOST` and `APP_PORT`, defaulting to `0.0.0.0:8000`. |
| `test.sh` | Runs pytest in the configured virtual environment, forwarding all arguments to pytest. |

Typical workflow:

```bash
scripts/setup-dev.sh
scripts/test.sh
scripts/dev-server.sh
```

Production setup:

```bash
scripts/setup-production.sh
```

The production service runs as root so `arp-scan` can capture network traffic.
Run with `--no-start` to review `.env` before starting the service.
