from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ScanDevice:
    mac: str
    ip: str | None = None
    hostname: str | None = None
    vendor: str | None = None


@dataclass(frozen=True)
class DeviceStatus:
    id: int
    mac: str
    ip: str | None
    hostname: str | None
    vendor: str | None
    label: str | None
    first_seen: datetime
    last_seen: datetime
    online: bool
    missed_scans: int

    @property
    def display_name(self) -> str:
        return self.label or self.hostname or self.vendor or self.mac

    @property
    def machine_name(self) -> str | None:
        if self.label and self.hostname and self.hostname != self.label:
            return self.hostname
        return None


@dataclass(frozen=True)
class ActivityEvent:
    mac: str
    label: str | None
    hostname: str | None
    vendor: str | None
    event_type: str
    happened_at: datetime

    @property
    def display_name(self) -> str:
        return self.label or self.hostname or self.vendor or self.mac

    @property
    def machine_name(self) -> str | None:
        if self.label and self.hostname and self.hostname != self.label:
            return self.hostname
        return None
