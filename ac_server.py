"""Bootstrap for the Olimpia AC sidecar (cmunaro/Olimpia).

At startup air_monitor pins an exact released build of the JVM AC client,
fetches that jar from the private repo's GitHub release (verifying its SHA-256),
and launches it as a managed subprocess. air_monitor then talks to it over its
REST API. Everything here is stdlib-only; all the AC crypto/protocol stays in
the JVM.

The sidecar is optional and degrades gracefully: if disabled, if `java` is
missing, or if the jar can neither be fetched nor found in cache, AC features
are simply skipped and the rest of air_monitor runs normally.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.request import Request

from . import config

LOGGER = logging.getLogger(__name__)

_USER_AGENT = "air-monitor-ac-bootstrap"


class _AuthStrippingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Drops the Authorization header when a redirect crosses to another host.

    GitHub's release-asset endpoint 302-redirects to a signed storage URL on a
    different host that rejects requests carrying a second credential. urllib
    re-sends headers across redirects by default, so we strip Authorization when
    the host changes.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            old_host = urllib.parse.urlsplit(req.full_url).hostname
            new_host = urllib.parse.urlsplit(newurl).hostname
            if old_host != new_host:
                new.remove_header("Authorization")
        return new


class AcSidecar:
    """Owns the lifecycle of the AC server subprocess."""

    def __init__(self, base_url: str, process: subprocess.Popen | None):
        self.base_url = base_url
        self._process = process

    def stop(self, timeout: float = 5.0) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        LOGGER.info("Stopping AC sidecar")
        self._process.terminate()
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            LOGGER.warning("AC sidecar did not stop in %ss; killing", timeout)
            self._process.kill()


def maybe_start() -> AcSidecar | None:
    """Start the AC sidecar per config, or return None if it should be skipped.

    Never raises: any failure is logged and AC features are disabled.
    """
    try:
        return _start()
    except Exception:
        LOGGER.exception("AC sidecar failed to start; AC features disabled")
        return None


def _start() -> AcSidecar | None:
    if not config.AC_ENABLED:
        return None

    # An external server was supplied: use it directly, no fetch or launch.
    if config.AC_URL:
        LOGGER.info("Using external AC server at %s", config.AC_URL)
        return AcSidecar(base_url=config.AC_URL.rstrip("/"), process=None)

    if shutil.which("java") is None:
        LOGGER.warning("`java` not found on PATH; AC features disabled")
        return None

    jar = _ensure_jar()
    if jar is None:
        return None

    base_url = f"http://localhost:{config.AC_PORT}"
    process = _launch(jar, config.AC_PORT)
    if not _await_health(base_url, process):
        LOGGER.warning("AC sidecar did not become healthy; AC features disabled")
        AcSidecar(base_url, process).stop()
        return None

    LOGGER.info("AC sidecar ready at %s", base_url)
    return AcSidecar(base_url=base_url, process=process)


def _ensure_jar() -> Path | None:
    """Return a verified jar path, using cache when valid, else downloading it."""
    version = config.AC_SERVER_VERSION
    expected = config.AC_SERVER_SHA256
    jar_name = f"{config.AC_SERVER_ARTIFACT}-{version}.jar"
    cached = config.AC_CACHE_DIR / jar_name

    if not expected:
        LOGGER.warning(
            "AIR_MONITOR_AC_SHA256 is not set; refusing to run an unverified jar. "
            "Pin the SHA-256 of %s to enable the AC sidecar.",
            jar_name,
        )
        return None

    if cached.is_file() and _sha256(cached) == expected:
        LOGGER.info("Using cached %s", jar_name)
        return cached

    downloaded = _download_release_asset(jar_name, cached)
    if downloaded is None:
        # Fall back to a (mismatching/partial) cache only if it actually verifies.
        if cached.is_file() and _sha256(cached) == expected:
            return cached
        return None

    actual = _sha256(downloaded)
    if actual != expected:
        LOGGER.error(
            "Checksum mismatch for %s: expected %s, got %s; discarding",
            jar_name, expected, actual,
        )
        downloaded.unlink(missing_ok=True)
        return None

    config.AC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    downloaded.replace(cached)
    LOGGER.info("Fetched and verified %s", jar_name)
    return cached


def _download_release_asset(jar_name: str, cached: Path) -> Path | None:
    """Download the named asset from the v<version> release to a temp file."""
    token = config.AC_GH_TOKEN
    if not token:
        LOGGER.warning(
            "No GitHub token (OLIMPIA_GH_TOKEN/GITHUB_TOKEN) set; cannot fetch the "
            "private AC release. AC features disabled unless a verified jar is cached.",
        )
        return None

    repo = config.AC_SERVER_REPO
    tag = f"v{config.AC_SERVER_VERSION}"
    opener = urllib.request.build_opener(_AuthStrippingRedirectHandler())

    # 1) Resolve the release by tag and find the asset's API URL.
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    release_req = Request(
        api_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": _USER_AGENT,
        },
    )
    with opener.open(release_req, timeout=30) as resp:
        release = json.load(resp)

    asset_url = next(
        (a["url"] for a in release.get("assets", []) if a.get("name") == jar_name),
        None,
    )
    if asset_url is None:
        LOGGER.error("Release %s has no asset named %s", tag, jar_name)
        return None

    # 2) Download the asset bytes (octet-stream triggers the redirect to storage).
    config.AC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    asset_req = Request(
        asset_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/octet-stream",
            "User-Agent": _USER_AGENT,
        },
    )
    fd, tmp_name = tempfile.mkstemp(dir=config.AC_CACHE_DIR, suffix=".part")
    tmp = Path(tmp_name)
    try:
        with opener.open(asset_req, timeout=120) as resp, os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(resp, out)
    except (urllib.error.URLError, OSError) as exc:
        LOGGER.error("Failed to download %s: %s", jar_name, exc)
        tmp.unlink(missing_ok=True)
        return None
    return tmp


def _launch(jar: Path, port: int) -> subprocess.Popen:
    """Start `java -jar <jar>` forwarding PORT and the OLIMPIA_* credentials."""
    env = os.environ.copy()
    env["PORT"] = str(port)
    LOGGER.info("Launching AC sidecar: java -jar %s (PORT=%s)", jar.name, port)
    return subprocess.Popen(
        ["java", "-jar", str(jar)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _await_health(base_url: str, process: subprocess.Popen, timeout: float = 30.0) -> bool:
    """Poll /api/health until the server answers or the deadline/process dies."""
    deadline = time.monotonic() + timeout
    health_url = f"{base_url}/api/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            LOGGER.error("AC sidecar exited early with code %s", process.returncode)
            return False
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
