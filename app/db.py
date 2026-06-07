from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.database import create_database
from app.models import ActivityEvent, DeviceStatus, ScanDevice


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def isoformat_dt(value: str | datetime) -> str:
    return parse_dt(value).isoformat()


class PresenceStore:
    def __init__(self, database: Path | str):
        self.database = create_database(database)
        self.database.migrate()

    def record_scan(
        self,
        scan_devices: list[ScanDevice],
        offline_after_missed_scans: int,
        now: datetime | None = None,
    ) -> None:
        now = now or utc_now()
        seen_by_mac = {device.mac.lower(): device for device in scan_devices}

        with self.database.connect() as conn:
            existing = {
                row["mac"].lower(): row
                for row in self.database.execute(conn, "SELECT * FROM devices").fetchall()
            }

            for mac, device in seen_by_mac.items():
                row = existing.get(mac)
                if row is None:
                    device_id = self.database.insert(
                        conn,
                        """
                        INSERT INTO devices
                            (mac, ip, hostname, vendor, first_seen, last_seen, online, missed_scans)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (mac, device.ip, device.hostname, device.vendor, now, now, True),
                    )
                    self.database.execute(
                        conn,
                        "INSERT INTO presence_events (device_id, event_type, happened_at) VALUES (?, 'online', ?)",
                        (device_id, now),
                    )
                    continue

                was_online = bool(row["online"])
                self.database.execute(
                    conn,
                    """
                    UPDATE devices
                    SET ip = COALESCE(?, ip),
                        hostname = COALESCE(?, hostname),
                        vendor = COALESCE(?, vendor),
                        last_seen = ?,
                        online = ?,
                        missed_scans = 0
                    WHERE id = ?
                    """,
                    (device.ip, device.hostname, device.vendor, now, True, row["id"]),
                )
                if not was_online:
                    self.database.execute(
                        conn,
                        "INSERT INTO presence_events (device_id, event_type, happened_at) VALUES (?, 'online', ?)",
                        (row["id"], now),
                    )

            for mac, row in existing.items():
                if mac in seen_by_mac or not bool(row["online"]):
                    continue

                missed_scans = int(row["missed_scans"]) + 1
                should_mark_offline = missed_scans >= offline_after_missed_scans
                self.database.execute(
                    conn,
                    "UPDATE devices SET missed_scans = ?, online = ? WHERE id = ?",
                    (missed_scans, not should_mark_offline, row["id"]),
                )
                if should_mark_offline:
                    self.database.execute(
                        conn,
                        "INSERT INTO presence_events (device_id, event_type, happened_at) VALUES (?, 'offline', ?)",
                        (row["id"], now),
                    )

    def list_devices(self) -> list[DeviceStatus]:
        with self.database.connect() as conn:
            rows = self.database.execute(
                conn,
                """
                SELECT *
                FROM devices
                ORDER BY online DESC, LOWER(COALESCE(label, hostname, vendor, mac))
                """,
            ).fetchall()
        return [self._device_from_row(row) for row in rows]

    def recent_activity(self, limit: int = 20) -> list[ActivityEvent]:
        with self.database.connect() as conn:
            rows = self.database.execute(
                conn,
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
        with self.database.connect() as conn:
            device_rows = self.database.execute(
                conn,
                """
                SELECT *
                FROM devices
                ORDER BY LOWER(COALESCE(label, hostname, vendor, mac))
                """,
            ).fetchall()
            event_rows = self.database.execute(
                conn,
                """
                SELECT d.mac, e.event_type, e.happened_at
                FROM presence_events e
                JOIN devices d ON d.id = e.device_id
                WHERE e.happened_at >= ? AND e.happened_at <= ?
                ORDER BY e.happened_at ASC, e.id ASC
                """,
                (since, until),
            ).fetchall()
            initial_rows = self.database.execute(
                conn,
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
                (since,),
            ).fetchall()

        initial_by_mac = {row["mac"]: row["event_type"] for row in initial_rows}
        devices = []
        for row in device_rows:
            initial_event = initial_by_mac.get(row["mac"])
            first_seen = parse_dt(row["first_seen"])
            initial_online = initial_event == "online"
            if initial_event is None and first_seen <= since:
                initial_online = bool(row["online"])
            device = self._device_from_row(row)
            devices.append(
                {
                    "mac": row["mac"],
                    "display_name": device.display_name,
                    "machine_name": device.machine_name,
                    "hostname": row["hostname"],
                    "ip": row["ip"],
                    "vendor": row["vendor"],
                    "online": bool(row["online"]),
                    "initial_online": initial_online,
                    "first_seen": isoformat_dt(row["first_seen"]),
                    "last_seen": isoformat_dt(row["last_seen"]),
                }
            )

        return {
            "range": {"since": since_iso, "until": until_iso},
            "devices": devices,
            "events": [
                {
                    "mac": row["mac"],
                    "event_type": row["event_type"],
                    "happened_at": isoformat_dt(row["happened_at"]),
                }
                for row in event_rows
            ],
        }

    def update_label(self, mac: str, label: str | None) -> None:
        label = label.strip() if label else None
        with self.database.connect() as conn:
            self.database.execute(conn, "UPDATE devices SET label = ? WHERE mac = ?", (label, mac.lower()))

    def _device_from_row(self, row: Mapping[str, Any]) -> DeviceStatus:
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
