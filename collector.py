"""Periodic HTTP collector for the air-quality endpoint."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .db import init_db, insert_radiation, insert_reading, log_error

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectorConfig:
    endpoint: str
    db_path: Path
    interval_seconds: int = 10
    timeout_seconds: float = 5


class AirDataCollector:
    def __init__(self, config: CollectorConfig):
        self.config = config
        init_db(config.db_path)

    def fetch_payload(self) -> dict[str, Any]:
        request = Request(
            self.config.endpoint,
            headers={"Accept": "application/json", "User-Agent": "air-monitor/0.1"},
        )
        with urlopen(request, timeout=self.config.timeout_seconds) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(64 * 1024)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON response: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("JSON response must be an object")

        if content_type and "json" not in content_type.lower():
            LOGGER.warning("Endpoint returned non-JSON content type: %s", content_type)

        return payload

    def collect_once(self) -> dict[str, Any]:
        try:
            payload = self.fetch_payload()
            inserted = insert_reading(self.config.db_path, payload)
        except HTTPError as exc:
            message = f"HTTP {exc.code}: {exc.reason}"
            self._record_failure("http", message)
            return {"ok": False, "stage": "http", "message": message}
        except URLError as exc:
            message = str(exc.reason)
            self._record_failure("network", message)
            return {"ok": False, "stage": "network", "message": message}
        except TimeoutError as exc:
            message = str(exc)
            self._record_failure("timeout", message)
            return {"ok": False, "stage": "timeout", "message": message}
        except (OSError, ValueError) as exc:
            message = str(exc)
            self._record_failure("payload", message)
            return {"ok": False, "stage": "payload", "message": message}

        if inserted:
            LOGGER.info("Stored reading timestamp=%s", payload.get("timestamp"))
            return {"ok": True, "inserted": True, "timestamp": payload.get("timestamp")}

        LOGGER.info("Skipped duplicate reading timestamp=%s", payload.get("timestamp"))
        return {"ok": True, "inserted": False, "timestamp": payload.get("timestamp")}

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        LOGGER.info(
            "Collector started endpoint=%s interval=%ss",
            self.config.endpoint,
            self.config.interval_seconds,
        )
        while not stop_event.is_set():
            started = time.monotonic()
            self.collect_once()
            elapsed = time.monotonic() - started
            delay = max(0.1, self.config.interval_seconds - elapsed)
            stop_event.wait(delay)
        LOGGER.info("Collector stopped")

    def _record_failure(self, stage: str, message: str) -> None:
        LOGGER.warning("Collection failed at %s: %s", stage, message)
        try:
            log_error(self.config.db_path, stage, message)
        except OSError:
            LOGGER.exception("Failed to persist collector error")


class RadiationCollector:
    def __init__(self, db_path: Path, interval_seconds: int = 2):
        self.db_path = db_path
        self.interval_seconds = interval_seconds
        self._gc = None

    def _connect(self):
        if self._gc is not None:
            return True
        try:
            import pygmc
            self._gc = pygmc.connect()
            LOGGER.info("Connected to Geiger counter")
            return True
        except Exception as exc:
            LOGGER.warning("Geiger counter connection attempt failed: %s", exc)
            return False

    def collect_once(self) -> bool:
        if not self._connect():
            return False
        try:
            cpm = self._gc.get_cpm()
            LOGGER.debug("Current CPM: %s", cpm)
            insert_radiation(self.db_path, int(cpm))
            return True
        except Exception as exc:
            LOGGER.warning("Geiger counter read failed, resetting connection: %s", exc)
            self._gc = None  # Force reconnect on next cycle
            return False

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        LOGGER.info("Radiation collector started interval=%ss", self.interval_seconds)
        while not stop_event.is_set():
            started = time.monotonic()
            self.collect_once()
            elapsed = time.monotonic() - started
            delay = max(0.1, self.interval_seconds - elapsed)
            stop_event.wait(delay)
        LOGGER.info("Radiation collector stopped")
