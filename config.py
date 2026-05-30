"""Runtime defaults for the air monitor service."""

from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Populate os.environ from a simple KEY=VALUE file (e.g. ac.env).

    Loaded so `python run.py run` picks up secrets/pins without needing the
    run.sh wrapper. Real environment variables take precedence (setdefault), so
    anything already exported on the command line wins over the file.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        # Strip an inline comment for unquoted values. The " #" (space-hash)
        # delimiter avoids cutting a '#' that is part of a token/password, since
        # those contain no spaces.
        if value[:1] not in ('"', "'"):
            cut = value.find(" #")
            if cut != -1:
                value = value[:cut].rstrip()
        os.environ.setdefault(key.strip(), value.strip('"').strip("'"))


# Load ./ac.env from the package directory (next to run.py), regardless of cwd.
_load_env_file(Path(__file__).with_name("ac.env"))


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


# --- Olimpia AC sidecar -----------------------------------------------------
# The AC client is a separate JVM service (cmunaro/Olimpia). air_monitor pins an
# exact released build, fetches that jar from the private repo's GitHub release
# at startup, verifies it, and launches it. Bumping the integration = editing the
# two pinned constants below (a deliberate, reviewed change).
# Enabled by default: `run` launches the AC sidecar. Set AIR_MONITOR_AC_ENABLED=0
# to disable. It still degrades gracefully if java/credentials/jar are missing.
AC_ENABLED = os.environ.get("AIR_MONITOR_AC_ENABLED", "1").lower() in ("1", "true", "yes")

# Pinned release: the asset is olimpia-server-<version>.jar on the v<version> tag,
# and AC_SERVER_SHA256 is its expected SHA-256 (the jar is rejected if it differs).
AC_SERVER_VERSION = os.environ.get("AIR_MONITOR_AC_VERSION", "1.0.0")
# Accept either a bare hash or a full "<hash>  <filename>" checksum-file line
# (what `sha256sum`/the Gradle task emit), so pasting either works.
_raw_sha = os.environ.get("AIR_MONITOR_AC_SHA256", "").strip().lower().split()
AC_SERVER_SHA256 = _raw_sha[0] if _raw_sha else ""
AC_SERVER_REPO = os.environ.get("AIR_MONITOR_AC_REPO", "cmunaro/Olimpia")

# Release asset base name; must match `releaseJarName` in Olimpia's
# server/build.gradle.kts. The fetched asset is <artifact>-<version>.jar.
AC_SERVER_ARTIFACT = os.environ.get("AIR_MONITOR_AC_ARTIFACT", "olimpia-client")

# Where the fetched jar is cached between runs.
AC_CACHE_DIR = Path(os.environ.get("AIR_MONITOR_AC_CACHE", "./data/ac-server"))

# Local port the sidecar listens on, and the base URL air_monitor talks to.
# Set AIR_MONITOR_AC_URL to an already-running server to skip fetch+launch
# entirely (e.g. the JVM runs as its own systemd service or on another box).
AC_PORT = int(os.environ.get("AIR_MONITOR_AC_PORT", "8090"))
AC_URL = os.environ.get("AIR_MONITOR_AC_URL", "").strip()

# Token with read access to the private repo's releases (fine-grained PAT with
# Contents:read on cmunaro/Olimpia is enough). GITHUB_TOKEN is a fallback.
AC_GH_TOKEN = (
    os.environ.get("OLIMPIA_GH_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or ""
).strip()
