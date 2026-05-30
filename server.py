"""LAN HTTP server exposing the local UI and JSON API."""

from __future__ import annotations

import json
import logging
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import (
    count_radiation,
    count_readings,
    error_stats,
    init_db,
    latest_radiation,
    latest_reading,
    query_radiation,
    query_readings,
    recent_errors,
)

LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).with_name("static")


# Subclasses BaseHTTPRequestHandler, NOT SimpleHTTPRequestHandler: the latter
# ships do_HEAD/send_head that serve files from the process working directory,
# which would bypass do_GET's routing and the static/ sandbox (e.g. HEAD probing
# arbitrary files). All file access goes through _serve_static below instead.
class AirMonitorHandler(BaseHTTPRequestHandler):
    db_path: Path
    static_dir: Path = STATIC_DIR
    ac = None  # AcController, or None when the AC sidecar is unavailable

    server_version = "AirMonitorHTTP/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/readings":
            self._handle_readings(parsed.query)
        elif parsed.path == "/api/latest":
            self._json_response({"latest": latest_reading(self.db_path)})
        elif parsed.path == "/api/radiation/latest":
            self._json_response({"latest": latest_radiation(self.db_path)})
        elif parsed.path == "/api/radiation":
            self._handle_radiation(parsed.query)
        elif parsed.path == "/api/errors":
            params = parse_qs(parsed.query)
            limit = _first_int(params, "limit", 20)
            self._json_response(
                {
                    "stats": error_stats(self.db_path),
                    "errors": recent_errors(self.db_path, limit=limit),
                }
            )
        elif parsed.path == "/api/health":
            self._json_response(
                {
                    "ok": True,
                    "readings": count_readings(self.db_path),
                    "radiation_readings": count_radiation(self.db_path),
                    "latest": latest_reading(self.db_path),
                    "latest_radiation": latest_radiation(self.db_path),
                    "recent_errors": recent_errors(self.db_path, limit=10),
                }
            )
        elif parsed.path == "/api/ac":
            if self.ac is None:
                self._json_response({"available": False})
            else:
                self._json_response(self.ac.get_view())
        elif parsed.path == "/" or parsed.path == "/index.html":
            self._serve_static("index.html")
        elif parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        from .ac import AC_MODES, FAN_SPEEDS

        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/ac/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self.ac is None:
            self._json_response({"error": "AC unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return

        body = self._read_json()
        if body is None:
            return  # error already sent

        try:
            if parsed.path == "/api/ac/power":
                view = self.ac.set_power(bool(body["on"]))
            elif parsed.path == "/api/ac/control-mode":
                view = self.ac.set_control_mode(_require(body, "mode", ("auto", "manual")))
            elif parsed.path == "/api/ac/targets":
                view = self.ac.set_targets(body.get("humidity"), body.get("temperature"))
            elif parsed.path == "/api/ac/mode":
                view = self.ac.set_mode(_require(body, "mode", AC_MODES))
            elif parsed.path == "/api/ac/fan":
                view = self.ac.set_fan_speed(_require(body, "speed", FAN_SPEEDS))
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
        except (KeyError, ValueError) as exc:
            self._json_response({"error": f"bad request: {exc}"}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # sidecar/cloud failure
            self._json_response({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return
        self._json_response(view)

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._json_response({"error": "invalid JSON body"}, HTTPStatus.BAD_REQUEST)
            return None

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _handle_readings(self, query: str) -> None:
        params = parse_qs(query)
        hours = _first_float(params, "hours", 24)
        max_points = _first_int(params, "max_points", 1200)
        self._json_response(
            {
                "readings": query_readings(
                    self.db_path,
                    hours=hours,
                    max_points=max_points,
                )
            }
        )

    def _handle_radiation(self, query: str) -> None:
        params = parse_qs(query)
        hours = _first_float(params, "hours", 24)
        max_points = _first_int(params, "max_points", 1200)
        self._json_response(
            {
                "readings": query_radiation(
                    self.db_path,
                    hours=hours,
                    max_points=max_points,
                )
            }
        )

    def _serve_static(self, requested: str) -> None:
        requested_path = Path(requested)
        if requested_path.is_absolute() or ".." in requested_path.parts:
            self.send_error(HTTPStatus.BAD_REQUEST, "Bad path")
            return

        path = (self.static_dir / requested_path).resolve()
        try:
            path.relative_to(self.static_dir.resolve())
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Bad path")
            return

        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str, port: int, db_path: str | Path) -> ThreadingHTTPServer:
    db = Path(db_path)
    init_db(db)

    class ConfiguredHandler(AirMonitorHandler):
        pass

    ConfiguredHandler.db_path = db
    return ThreadingHTTPServer((host, port), ConfiguredHandler)


def serve(host: str, port: int, db_path: str | Path) -> None:
    httpd = make_server(host, port, db_path)
    LOGGER.info("Serving on http://%s:%s", host, port)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def _require(body: dict, key: str, allowed: tuple[str, ...]) -> str:
    value = body[key]
    if value not in allowed:
        raise ValueError(f"{key} must be one of {allowed}")
    return value


def _first_float(params: dict[str, list[str]], key: str, default: float) -> float:
    try:
        return float(params.get(key, [str(default)])[0])
    except ValueError:
        return default


def _first_int(params: dict[str, list[str]], key: str, default: int) -> int:
    try:
        return int(params.get(key, [str(default)])[0])
    except ValueError:
        return default
