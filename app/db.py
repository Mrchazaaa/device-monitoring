from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from app.models import ActivityEvent, DeviceStatus, ScanDevice


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class PresenceStore:
    def __init__(self, database: Path | str):
        self.database_path = self._sqlite_path(database)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @staticmethod
    def _sqlite_path(database: Path | str) -> str:
        if isinstance(database, Path):
            return str(database)

        database_value = str(database)
        parsed = urlparse(database_value)
        if parsed.scheme != "sqlite":
            if parsed.scheme:
                raise ValueError(f"Unsupported database scheme: {parsed.scheme}")
            return database_value

        if parsed.netloc:
            raise ValueError("SQLite connection strings must not include a host")
        if parsed.params or parsed.query or parsed.fragment:
            raise ValueError("SQLite connection string parameters are not supported")
        if parsed.path == "/:memory:":
            raise ValueError("In-memory SQLite databases are not supported")
        if not parsed.path:
            raise ValueError("SQLite connection string must include a database path")
        if parsed.path.startswith("//"):
            return parsed.path[1:]
        return parsed.path.lstrip("/")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def migrate(self) -> None:
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac TEXT NOT NULL UNIQUE,
                    ip TEXT,
                    hostname TEXT,
                    vendor TEXT,
                    label TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    online INTEGER NOT NULL DEFAULT 0,
                    missed_scans INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS presence_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL CHECK (event_type IN ('online', 'offline')),
                    happened_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_devices_online ON devices(online);
                CREATE INDEX IF NOT EXISTS idx_presence_events_happened_at ON presence_events(happened_at);
                """
            )

    def record_scan(
        self,
        scan_devices: list[ScanDevice],
        offline_after_missed_scans: int,
        now: datetime | None = None,
    ) -> None:
        now = now or utc_now()
        now_iso = now.isoformat()
        seen_by_mac = {device.mac.lower(): device for device in scan_devices}

        with self.connect() as conn:
            existing = {
                row["mac"].lower(): row
                for row in conn.execute("SELECT * FROM devices").fetchall()
            }

            for mac, device in seen_by_mac.items():
                row = existing.get(mac)
                if row is None:
                    cursor = conn.execute(
                        """
                        INSERT INTO devices
                            (mac, ip, hostname, vendor, first_seen, last_seen, online, missed_scans)
                        VALUES (?, ?, ?, ?, ?, ?, 1, 0)
                        """,
                        (mac, device.ip, device.hostname, device.vendor, now_iso, now_iso),
                    )
                    conn.execute(
                        "INSERT INTO presence_events (device_id, event_type, happened_at) VALUES (?, 'online', ?)",
                        (cursor.lastrowid, now_iso),
                    )
                    continue

                was_online = bool(row["online"])
                conn.execute(
                    """
                    UPDATE devices
                    SET ip = COALESCE(?, ip),
                        hostname = COALESCE(?, hostname),
                        vendor = COALESCE(?, vendor),
                        last_seen = ?,
                        online = 1,
                        missed_scans = 0
                    WHERE id = ?
                    """,
                    (device.ip, device.hostname, device.vendor, now_iso, row["id"]),
                )
                if not was_online:
                    conn.execute(
                        "INSERT INTO presence_events (device_id, event_type, happened_at) VALUES (?, 'online', ?)",
                        (row["id"], now_iso),
                    )

            for mac, row in existing.items():
                if mac in seen_by_mac or not bool(row["online"]):
                    continue

                missed_scans = int(row["missed_scans"]) + 1
                should_mark_offline = missed_scans >= offline_after_missed_scans
                conn.execute(
                    "UPDATE devices SET missed_scans = ?, online = ? WHERE id = ?",
                    (missed_scans, 0 if should_mark_offline else 1, row["id"]),
                )
                if should_mark_offline:
                    conn.execute(
                        "INSERT INTO presence_events (device_id, event_type, happened_at) VALUES (?, 'offline', ?)",
                        (row["id"], now_iso),
                    )

    def list_devices(self) -> list[DeviceStatus]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM devices
                ORDER BY online DESC, COALESCE(label, hostname, vendor, mac) COLLATE NOCASE
                """
            ).fetchall()
        return [self._device_from_row(row) for row in rows]

    def recent_activity(self, limit: int = 20) -> list[ActivityEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT d.mac, d.label, d.hostname, d.vendor, e.event_type, e.happened_at
                FROM presence_events e
                JOIN devices d ON d.id = e.device_id
                ORDER BY e.happened_at DESC, e.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ActivityEvent(
                mac=row["mac"],
                label=row["label"],
                hostname=row["hostname"],
                vendor=row["vendor"],
                event_type=row["event_type"],
                happened_at=parse_dt(row["happened_at"]),
            )
            for row in rows
        ]


    def presence_timeline(self, since: datetime, until: datetime) -> dict[str, object]:
        since_iso = since.isoformat()
        until_iso = until.isoformat()
        with self.connect() as conn:
            device_rows = conn.execute(
                """
                SELECT *
                FROM devices
                ORDER BY COALESCE(label, hostname, vendor, mac) COLLATE NOCASE
                """
            ).fetchall()
            event_rows = conn.execute(
                """
                SELECT d.mac, e.event_type, e.happened_at
                FROM presence_events e
                JOIN devices d ON d.id = e.device_id
                WHERE e.happened_at >= ? AND e.happened_at <= ?
                ORDER BY e.happened_at ASC, e.id ASC
                """,
                (since_iso, until_iso),
            ).fetchall()
            initial_rows = conn.execute(
                """
                SELECT d.mac, e.event_type
                FROM devices d
                LEFT JOIN presence_events e ON e.id = (
                    SELECT pe.id
                    FROM presence_events pe
                    WHERE pe.device_id = d.id AND pe.happened_at <= ?
                    ORDER BY pe.happened_at DESC, pe.id DESC
                    LIMIT 1
                )
                """,
                (since_iso,),
            ).fetchall()

        initial_by_mac = {row["mac"]: row["event_type"] for row in initial_rows}
        devices = []
        for row in device_rows:
            initial_event = initial_by_mac.get(row["mac"])
            first_seen = parse_dt(row["first_seen"])
            initial_online = initial_event == "online"
            if initial_event is None and first_seen <= since:
                initial_online = bool(row["online"])
            devices.append(
                {
                    "mac": row["mac"],
                    "display_name": self._device_from_row(row).display_name,
                    "machine_name": self._device_from_row(row).machine_name,
                    "hostname": row["hostname"],
                    "ip": row["ip"],
                    "vendor": row["vendor"],
                    "online": bool(row["online"]),
                    "initial_online": initial_online,
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"],
                }
            )

        return {
            "range": {"since": since_iso, "until": until_iso},
            "devices": devices,
            "events": [
                {
                    "mac": row["mac"],
                    "event_type": row["event_type"],
                    "happened_at": row["happened_at"],
                }
                for row in event_rows
            ],
        }

    def update_label(self, mac: str, label: str | None) -> None:
        label = label.strip() if label else None
        with self.connect() as conn:
            conn.execute("UPDATE devices SET label = ? WHERE mac = ?", (label, mac.lower()))

    def _device_from_row(self, row: sqlite3.Row) -> DeviceStatus:
        return DeviceStatus(
            id=row["id"],
            mac=row["mac"],
            ip=row["ip"],
            hostname=row["hostname"],
            vendor=row["vendor"],
            label=row["label"],
            first_seen=parse_dt(row["first_seen"]),
            last_seen=parse_dt(row["last_seen"]),
            online=bool(row["online"]),
            missed_scans=int(row["missed_scans"]),
        )
