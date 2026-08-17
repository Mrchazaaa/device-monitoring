from fastapi.testclient import TestClient

from app.main import app, scanner_service, store
from app.models import ScanDevice


async def noop_stop():
    return None



def test_scan_api_runs_scanner(monkeypatch):
    called = False

    async def fake_run_once():
        nonlocal called
        called = True

    monkeypatch.setattr(scanner_service, "start", lambda: None)
    monkeypatch.setattr(scanner_service, "stop", noop_stop)
    monkeypatch.setattr(scanner_service, "run_once", fake_run_once)

    with TestClient(app) as client:
        response = client.post("/api/scan")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert called is True


def test_devices_api(tmp_path, monkeypatch):
    test_store = store.__class__(tmp_path / "presence.db")
    test_store.record_scan([ScanDevice(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.44", hostname="raspberrypi2.mynet")], 2)
    test_store.update_label("aa:bb:cc:dd:ee:ff", "Laptop")
    monkeypatch.setattr("app.main.store", test_store)
    monkeypatch.setattr(scanner_service, "start", lambda: None)
    monkeypatch.setattr(scanner_service, "stop", noop_stop)

    with TestClient(app) as client:
        response = client.get("/api/devices")

    assert response.status_code == 200
    device = response.json()["devices"][0]
    assert device["mac"] == "aa:bb:cc:dd:ee:ff"
    assert device["display_name"] == "Laptop"
    assert device["machine_name"] == "raspberrypi2.mynet"


def test_presence_history_api(tmp_path, monkeypatch):
    test_store = store.__class__(tmp_path / "presence.db")
    test_store.record_scan([ScanDevice(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.44", hostname="raspberrypi2.mynet")], 2)
    test_store.update_label("aa:bb:cc:dd:ee:ff", "Laptop")
    monkeypatch.setattr("app.main.store", test_store)
    monkeypatch.setattr(scanner_service, "start", lambda: None)
    monkeypatch.setattr(scanner_service, "stop", noop_stop)

    with TestClient(app) as client:
        response = client.get("/api/presence-history?hours=24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["devices"][0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert payload["devices"][0]["display_name"] == "Laptop"
    assert payload["devices"][0]["machine_name"] == "raspberrypi2.mynet"
    assert payload["range"]["since"]
    assert payload["range"]["until"]
