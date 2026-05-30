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
        elif parsed.path == "/" or parsed.path == "/index.html":
            self._serve_static("index.html")
        elif parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

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
