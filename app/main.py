from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.db import PresenceStore, utc_now
from app.scanner import ArpScanError, ArpScanner
from app.service import ScannerService

load_dotenv()
settings = Settings.from_env()
store = PresenceStore(settings.database_path)
scanner_service = ScannerService(
    store=store,
    scanner=ArpScanner(settings.network_interface, settings.scan_cidr),
    interval_seconds=settings.scan_interval_seconds,
    offline_after_missed_scans=settings.offline_after_missed_scans,
)

templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(_: FastAPI):
    scanner_service.start()
    try:
        yield
    finally:
        await scanner_service.stop()


app = FastAPI(title="Home Wi-Fi Presence", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "devices": store.list_devices(),
            "activity": store.recent_activity(),
        },
    )


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


@app.post("/devices/{mac}/label")
async def update_label(mac: str, label: str = Form(default="")):
    store.update_label(mac, label)
    return RedirectResponse("/", status_code=303)
