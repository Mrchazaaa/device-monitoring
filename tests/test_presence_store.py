from datetime import datetime, timezone

from app.db import PresenceStore
from app.models import ScanDevice


def at(second: int) -> datetime:
    return datetime(2026, 1, 1, 12, 0, second, tzinfo=timezone.utc)


def test_presence_transitions_online_offline_and_back(tmp_path):
    store = PresenceStore(tmp_path / "presence.db")
    device = ScanDevice(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.25", vendor="Test Vendor")

    store.record_scan([device], offline_after_missed_scans=2, now=at(0))
    [status] = store.list_devices()
    assert status.online is True
    assert status.missed_scans == 0

    store.record_scan([], offline_after_missed_scans=2, now=at(1))
    [status] = store.list_devices()
    assert status.online is True
    assert status.missed_scans == 1

    store.record_scan([], offline_after_missed_scans=2, now=at(2))
    [status] = store.list_devices()
    assert status.online is False
    assert status.missed_scans == 2

    store.record_scan([device], offline_after_missed_scans=2, now=at(3))
    [status] = store.list_devices()
    assert status.online is True
    assert status.missed_scans == 0

    events = store.recent_activity()
    assert [event.event_type for event in events] == ["online", "offline", "online"]


def test_update_label_persists(tmp_path):
    store = PresenceStore(tmp_path / "presence.db")
    store.record_scan([ScanDevice(mac="aa:bb:cc:dd:ee:ff")], offline_after_missed_scans=2, now=at(0))

    store.update_label("AA:BB:CC:DD:EE:FF", "Kitchen speaker")

    [status] = store.list_devices()
    assert status.label == "Kitchen speaker"
    assert status.display_name == "Kitchen speaker"


def test_presence_timeline_includes_initial_state_and_range_events(tmp_path):
    store = PresenceStore(tmp_path / "presence.db")
    device = ScanDevice(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.25", vendor="Test Vendor")

    store.record_scan([device], offline_after_missed_scans=1, now=at(0))
    store.record_scan([], offline_after_missed_scans=1, now=at(1))
    store.record_scan([device], offline_after_missed_scans=1, now=at(2))

    timeline = store.presence_timeline(at(1), at(3))

    assert timeline["devices"][0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert timeline["devices"][0]["initial_online"] is False
    assert [event["event_type"] for event in timeline["events"]] == ["offline", "online"]


def test_presence_store_accepts_sqlite_connection_string(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'presence.db'}"
    store = PresenceStore(database_url)

    store.record_scan([ScanDevice(mac="aa:bb:cc:dd:ee:ff")], offline_after_missed_scans=2, now=at(0))

    [status] = store.list_devices()
    assert status.mac == "aa:bb:cc:dd:ee:ff"


def test_presence_store_rejects_unsupported_connection_string():
    try:
        PresenceStore("postgresql://user:password@localhost/presence")
    except ValueError as exc:
        assert "Unsupported database scheme: postgresql" in str(exc)
    else:
        raise AssertionError("Expected unsupported database scheme to be rejected")


def test_presence_store_rejects_in_memory_sqlite_connection_string():
    try:
        PresenceStore("sqlite:///:memory:")
    except ValueError as exc:
        assert "In-memory SQLite databases are not supported" in str(exc)
    else:
        raise AssertionError("Expected in-memory SQLite to be rejected")
