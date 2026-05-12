"""Command-line entrypoint for the air monitor service."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path

from .collector import AirDataCollector, CollectorConfig, RadiationCollector
from .config import (
    DEFAULT_DB_PATH,
    DEFAULT_ENDPOINT,
    DEFAULT_HOST,
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_SECONDS,
)
from .db import init_db
from .server import make_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Raspberry Pi air monitor")
    subcommands = parser.add_subparsers(dest="command", required=True)

    for command in ("run", "serve", "collect-once", "init-db"):
        sub = subcommands.add_parser(command)
        sub.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
        if command in {"run", "collect-once"}:
            sub.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
            sub.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS)
            sub.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
        if command in {"run", "serve"}:
            sub.add_argument("--host", default=DEFAULT_HOST)
            sub.add_argument("--port", type=int, default=DEFAULT_PORT)
        sub.add_argument("--log-level", default="INFO")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "init-db":
        init_db(args.db)
        print(f"Initialized database at {args.db}")
        return 0

    if args.command == "collect-once":
        collector = AirDataCollector(_collector_config(args))
        result = collector.collect_once()
        print(result)
        return 0 if result.get("ok") else 1

    if args.command == "serve":
        return _serve(args.host, args.port, args.db)

    if args.command == "run":
        return _run(args)

    return 2


def _run(args: argparse.Namespace) -> int:
    stop_event = threading.Event()
    collector = AirDataCollector(_collector_config(args))
    collector_thread = threading.Thread(
        target=collector.run_forever,
        args=(stop_event,),
        name="air-monitor-collector",
        daemon=True,
    )
    collector_thread.start()
    
    rad_collector = RadiationCollector(args.db)
    rad_thread = threading.Thread(
        target=rad_collector.run_forever,
        args=(stop_event,),
        name="radiation-collector",
        daemon=True,
    )
    rad_thread.start()

    def stop(_signum: int, _frame: object) -> None:
        stop_event.set()
        httpd.shutdown()

    httpd = make_server(args.host, args.port, args.db)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        httpd.serve_forever()
    finally:
        stop_event.set()
        collector_thread.join(timeout=5)
        rad_thread.join(timeout=5)
        httpd.server_close()
    return 0


def _serve(host: str, port: int, db_path: Path) -> int:
    httpd = make_server(host, port, db_path)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def _collector_config(args: argparse.Namespace) -> CollectorConfig:
    return CollectorConfig(
        endpoint=args.endpoint,
        db_path=args.db,
        interval_seconds=args.interval,
        timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
