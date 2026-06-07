from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    app_log_level: str
    database_url: str
    scan_interval_seconds: int
    offline_after_missed_scans: int
    network_interface: str | None
    scan_cidr: str | None
    loki_url: str | None
    loki_labels: dict[str, str]
    loki_username: str | None
    loki_password: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            database_path = os.getenv("DATABASE_PATH", "./data/presence.db")
            database_url = f"sqlite:///{database_path}"

        return cls(
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            app_log_level=_parse_log_level(os.getenv("APP_LOG_LEVEL", "DEBUG")),
            database_url=database_url,
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "60")),
            offline_after_missed_scans=int(os.getenv("OFFLINE_AFTER_MISSED_SCANS", "2")),
            network_interface=os.getenv("NETWORK_INTERFACE") or None,
            scan_cidr=os.getenv("SCAN_CIDR") or None,
            loki_url=os.getenv("LOKI_URL") or None,
            loki_labels=_parse_loki_labels(os.getenv("LOKI_LABELS")),
            loki_username=os.getenv("LOKI_USERNAME") or None,
            loki_password=os.getenv("LOKI_PASSWORD") or None,
        )


def _parse_loki_labels(value: str | None) -> dict[str, str]:
    if not value:
        return {"application": "home-wifi-presence"}

    labels = json.loads(value)
    if not isinstance(labels, dict) or not all(
        isinstance(key, str) and isinstance(label_value, str)
        for key, label_value in labels.items()
    ):
        raise ValueError("LOKI_LABELS must be a JSON object containing string keys and values")
    return labels


def _parse_log_level(value: str) -> str:
    level = value.upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("APP_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    return level
