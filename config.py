"""Runtime defaults for the air monitor service."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_ENDPOINT = os.environ.get(
    "AIR_MONITOR_ENDPOINT", "http://192.168.1.204/air-data/latest"
)
DEFAULT_INTERVAL_SECONDS = int(os.environ.get("AIR_MONITOR_INTERVAL", "10"))
DEFAULT_DB_PATH = Path(
    os.environ.get("AIR_MONITOR_DB", "./data/air_monitor.sqlite")
)
DEFAULT_HOST = os.environ.get("AIR_MONITOR_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("AIR_MONITOR_PORT", "8080"))
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("AIR_MONITOR_TIMEOUT", "5"))
