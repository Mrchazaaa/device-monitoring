from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from app.config import Settings
from app.db import PresenceStore, utc_now
from app.logging_config import configure_loki_logging
from app.scanner import ArpScanError, ArpScanner
from app.service import ScannerService

load_dotenv()
settings = Settings.from_env()
store = PresenceStore(settings.database_url)
scanner_service = ScannerService(
    store=store,
    scanner=ArpScanner(settings.network_interface, settings.scan_cidr),
    interval_seconds=settings.scan_interval_seconds,
    offline_after_missed_scans=settings.offline_after_missed_scans,
)



@asynccontextmanager
async def lifespan(_: FastAPI):
    loki_listener = configure_loki_logging(
        url=settings.loki_url,
        labels=settings.loki_labels,
        app_log_level=settings.app_log_level,
        username=settings.loki_username,
        password=settings.loki_password,
    )
    scanner_service.start()
    try:
        yield
    finally:
        await scanner_service.stop()
        if loki_listener is not None:
            loki_listener.stop()


app = FastAPI(title="Home Wi-Fi Presence", lifespan=lifespan)


@app.post("/api/scan")
async def api_scan():
    try:
        await scanner_service.run_once()
    except ArpScanError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/devices")
async def api_devices():
    return {
        "devices": [
            {
                **device.__dict__,
                "display_name": device.display_name,
                "machine_name": device.machine_name,
            }
            for device in store.list_devices()
        ]
    }


@app.get("/api/presence-history")
async def api_presence_history(hours: int = Query(default=24, ge=1, le=24 * 365)):
    until = utc_now()
    since = until - timedelta(hours=hours)
    return store.presence_timeline(since, until)


@app.get("/api/activity")
async def api_activity():
    return {
        "activity": [
            {
                **event.__dict__,
                "display_name": event.display_name,
                "machine_name": event.machine_name,
            }
            for event in store.recent_activity()
        ]
    }
