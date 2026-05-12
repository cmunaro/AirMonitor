"""SQLite storage for sensor readings and collector diagnostics."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


READING_FIELDS = (
    "score",
    "dew_point",
    "temp",
    "humid",
    "abs_humid",
    "co2",
    "co2_est",
    "co2_est_baseline",
    "voc",
    "voc_baseline",
    "voc_h2_raw",
    "voc_ethanol_raw",
    "pm25",
    "pm10_est",
)

ALL_READING_COLUMNS = ("timestamp",) + READING_FIELDS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL UNIQUE,
                fetched_at TEXT NOT NULL,
                score REAL NOT NULL,
                dew_point REAL NOT NULL,
                temp REAL NOT NULL,
                humid REAL NOT NULL,
                abs_humid REAL NOT NULL,
                co2 REAL NOT NULL,
                co2_est REAL NOT NULL,
                co2_est_baseline REAL NOT NULL,
                voc REAL NOT NULL,
                voc_baseline REAL NOT NULL,
                voc_h2_raw REAL NOT NULL,
                voc_ethanol_raw REAL NOT NULL,
                pm25 REAL NOT NULL,
                pm10_est REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_readings_fetched_at
                ON readings (fetched_at);

            CREATE INDEX IF NOT EXISTS idx_readings_timestamp
                ON readings (timestamp);

            CREATE TABLE IF NOT EXISTS collector_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_collector_errors_occurred_at
                ON collector_errors (occurred_at);
            """
        )


def normalize_reading(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in ALL_READING_COLUMNS if field not in payload]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")

    timestamp = payload["timestamp"]
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ValueError("timestamp must be a non-empty string")

    normalized: dict[str, Any] = {"timestamp": timestamp}
    for field in READING_FIELDS:
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric")
        normalized[field] = float(value)
    return normalized


def insert_reading(db_path: str | Path, payload: dict[str, Any]) -> bool:
    reading = normalize_reading(payload)
    fields_sql = ", ".join(("timestamp", "fetched_at") + READING_FIELDS)
    placeholders = ", ".join("?" for _ in ("timestamp", "fetched_at") + READING_FIELDS)
    values = [reading["timestamp"], utc_now_iso()]
    values.extend(reading[field] for field in READING_FIELDS)

    with connect(db_path) as conn:
        cur = conn.execute(
            f"INSERT OR IGNORE INTO readings ({fields_sql}) VALUES ({placeholders})",
            values,
        )
        return cur.rowcount == 1


def log_error(db_path: str | Path, stage: str, message: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO collector_errors (occurred_at, stage, message)
            VALUES (?, ?, ?)
            """,
            (utc_now_iso(), stage[:80], message[:1000]),
        )


def latest_reading(db_path: str | Path) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM readings ORDER BY timestamp DESC, id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def count_readings(db_path: str | Path) -> int:
    with connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM readings").fetchone()
    return int(row["count"])


def recent_errors(db_path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT occurred_at, stage, message
            FROM collector_errors
            ORDER BY occurred_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def query_readings(
    db_path: str | Path,
    hours: float = 24,
    max_points: int = 1200,
) -> list[dict[str, Any]]:
    hours = max(0.05, min(float(hours), 24 * 31))
    max_points = max(50, min(int(max_points), 5000))
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, fetched_at, score, dew_point, temp, humid, abs_humid,
                   co2, co2_est, co2_est_baseline, voc, voc_baseline,
                   voc_h2_raw, voc_ethanol_raw, pm25, pm10_est
            FROM readings
            WHERE fetched_at >= ?
            ORDER BY fetched_at ASC, id ASC
            """,
            (cutoff,),
        ).fetchall()

    data = [dict(row) for row in rows]
    if len(data) <= max_points:
        return data

    stride = len(data) / max_points
    sampled = [data[int(index * stride)] for index in range(max_points)]
    if sampled[-1]["id"] != data[-1]["id"]:
        sampled[-1] = data[-1]
    return sampled
