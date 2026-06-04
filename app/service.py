from __future__ import annotations

import asyncio
import logging

from app.db import PresenceStore
from app.scanner import ArpScanError, ArpScanner

logger = logging.getLogger(__name__)


class ScannerService:
    def __init__(
        self,
        store: PresenceStore,
        scanner: ArpScanner,
        interval_seconds: int,
        offline_after_missed_scans: int,
    ):
        self.store = store
        self.scanner = scanner
        self.interval_seconds = interval_seconds
        self.offline_after_missed_scans = offline_after_missed_scans
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._scan_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            await self._task

    async def run_once(self) -> None:
        async with self._scan_lock:
            devices = await asyncio.to_thread(self.scanner.scan)
            self.store.record_scan(devices, self.offline_after_missed_scans)

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except ArpScanError as exc:
                logger.warning("Device scan failed: %s", exc)
            except Exception:
                logger.exception("Device scan failed")

            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                pass
