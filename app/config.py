from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    database_path: Path
    scan_interval_seconds: int
    offline_after_missed_scans: int
    network_interface: str | None
    scan_cidr: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            database_path=Path(os.getenv("DATABASE_PATH", "./data/presence.db")),
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "60")),
            offline_after_missed_scans=int(os.getenv("OFFLINE_AFTER_MISSED_SCANS", "2")),
            network_interface=os.getenv("NETWORK_INTERFACE") or None,
            scan_cidr=os.getenv("SCAN_CIDR") or None,
        )
