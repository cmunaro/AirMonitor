"""AC client + controller.

`AcClient` is a thin stdlib wrapper over the Olimpia sidecar's REST API.
`AcController` caches the latest snapshot, owns the auto/manual control settings,
and runs the automatic-mode regulation loop (humidistat/thermostat) using the
latest sensor readings. The dashboard's /api/ac routes delegate to the controller.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request

from . import config
from .db import get_ac_settings, latest_reading, save_ac_settings

LOGGER = logging.getLogger(__name__)

# What the UI/automation may request, mapped to the sidecar's enum spellings.
AC_MODES = ("Cool", "Dry", "Fan", "Auto")
FAN_SPEEDS = ("Low", "High", "Auto")


class AcClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def snapshot(self) -> dict:
        return self._get("/api/ac/snapshot")

    def set_power(self, on: bool) -> dict:
        return self._post("/api/ac/power", {"on": on})

    def set_mode(self, mode: str) -> dict:
        return self._post("/api/ac/mode", {"mode": mode})

    def set_fan_speed(self, speed: str) -> dict:
        return self._post("/api/ac/fanSpeed", {"speed": speed})

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(self.base_url + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read() or b"{}")

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read() or b"{}")


class AcController:
    def __init__(self, base_url: str, db_path):
        self.client = AcClient(base_url)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._snapshot: dict | None = None
        self._error: str | None = None
        self._last_auto_mode: str | None = None  # last mode the auto loop applied

    # --- lifecycle ----------------------------------------------------------
    def start(self, stop_event: threading.Event) -> None:
        threading.Thread(
            target=self._run, args=(stop_event,), name="ac-controller", daemon=True
        ).start()

    def _run(self, stop_event: threading.Event) -> None:
        LOGGER.info("AC controller started (poll=%ss)", config.AC_POLL_SECONDS)
        while not stop_event.is_set():
            try:
                self._poll_once()
            except Exception:
                LOGGER.exception("AC controller cycle failed")
            stop_event.wait(config.AC_POLL_SECONDS)

    def _poll_once(self) -> None:
        try:
            snap = self.client.snapshot()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            with self._lock:
                self._error = str(exc)
            return
        with self._lock:
            self._snapshot = snap
            self._error = None
        self._auto_regulate(snap)

    # --- automatic regulation ----------------------------------------------
    def _auto_regulate(self, snap: dict) -> None:
        settings = get_ac_settings(self.db_path)
        if settings["control_mode"] != "auto":
            self._last_auto_mode = None
            return

        state = (snap or {}).get("state") or {}
        if state.get("power") != "On":
            # Auto only regulates the running unit; it never forces power.
            self._last_auto_mode = None
            return

        latest = latest_reading(self.db_path)
        if not latest:
            return
        humid = latest.get("humid")
        temp = latest.get("temp")
        if humid is None or temp is None:
            return

        desired = self._desired_mode(humid, temp, settings)
        if desired and desired != self._last_auto_mode and desired != state.get("mode"):
            LOGGER.info(
                "Auto: humid=%.1f/%.0f temp=%.1f/%.0f -> %s",
                humid, settings["target_humidity"], temp, settings["target_temp"], desired,
            )
            try:
                self.client.set_mode(desired)
                self._last_auto_mode = desired
                self._refresh()
            except (urllib.error.URLError, OSError, ValueError) as exc:
                LOGGER.warning("Auto set_mode(%s) failed: %s", desired, exc)

    @staticmethod
    def _desired_mode(humid: float, temp: float, settings: dict) -> str | None:
        target_h = settings["target_humidity"]
        target_t = settings["target_temp"]
        hh = config.AC_AUTO_HUMIDITY_HYST
        ht = config.AC_AUTO_TEMP_HYST
        if humid > target_h + hh:
            return "Dry"
        if temp > target_t + ht:
            return "Cool"
        if humid < target_h - hh and temp < target_t - ht:
            return "Fan"
        return None  # deadband: leave current mode untouched

    # --- view + commands (called by the HTTP handler) ----------------------
    def get_view(self) -> dict:
        with self._lock:
            snap = self._snapshot
            error = self._error
        settings = get_ac_settings(self.db_path)
        state = (snap or {}).get("state") or {}
        latest = latest_reading(self.db_path) or {}
        return {
            "available": snap is not None,
            "error": error,
            "control_mode": settings["control_mode"],
            "targets": {
                "humidity": settings["target_humidity"],
                "temperature": settings["target_temp"],
            },
            "power": state.get("power"),
            "mode": state.get("mode"),
            "fan_speed": state.get("fanSpeed"),
            "current": {"humidity": latest.get("humid"), "temperature": latest.get("temp")},
        }

    def set_power(self, on: bool) -> dict:
        self.client.set_power(on)
        self._refresh()
        return self.get_view()

    def set_control_mode(self, mode: str) -> dict:
        save_ac_settings(self.db_path, control_mode=mode)
        # Re-run regulation immediately so switching to auto takes effect at once.
        with self._lock:
            snap = self._snapshot
        if snap is not None:
            self._auto_regulate(snap)
        return self.get_view()

    def set_targets(self, humidity: float | None, temperature: float | None) -> dict:
        save_ac_settings(self.db_path, target_humidity=humidity, target_temp=temperature)
        with self._lock:
            snap = self._snapshot
        if snap is not None:
            self._auto_regulate(snap)
        return self.get_view()

    def set_mode(self, mode: str) -> dict:
        self.client.set_mode(mode)
        self._refresh()
        return self.get_view()

    def set_fan_speed(self, speed: str) -> dict:
        self.client.set_fan_speed(speed)
        self._refresh()
        return self.get_view()

    def _refresh(self) -> None:
        """Best-effort snapshot refresh so the UI reflects a command quickly."""
        try:
            snap = self.client.snapshot()
            with self._lock:
                self._snapshot = snap
                self._error = None
        except (urllib.error.URLError, OSError, ValueError):
            pass
