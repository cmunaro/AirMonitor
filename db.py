"""SQLite storage for sensor readings and collector diagnostics."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


READING_FIELDS = (
    "score",
    "dew_point",
    "temp",
    "humid",
    "abs_humid",
    "co2",
    "co2_est",
    "voc",
    "voc_h2_raw",
    "voc_ethanol_raw",
    "pm25",
    "pm10_est",
)

ALL_READING_COLUMNS = ("timestamp",) + READING_FIELDS

# Columns with INTEGER affinity, so averaged compaction values are rounded back
# to ints instead of being stored as REAL.
INTEGER_FIELDS = frozenset({"cpm"})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a configured connection, commit/rollback, and always close it.

    Used as ``with connect(path) as conn:``. The inner ``with conn`` gives the
    usual sqlite3 transaction semantics (commit on success, rollback on error);
    the outer ``finally`` guarantees the connection is closed -- a bare
    ``with sqlite3.connect(...)`` commits but never closes, leaking the handle.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Multiple writer threads (collectors + maintenance) contend for the write
    # lock; wait instead of failing immediately with "database is locked".
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        # Check for schema mismatch (legacy columns)
        table_info = conn.execute("PRAGMA table_info(readings)").fetchall()
        column_names = {row["name"] for row in table_info}
        
        if column_names and "co2_est_baseline" in column_names:
            LOGGER.warning("Schema mismatch detected, recreating readings table...")
            conn.execute("DROP TABLE readings")
            # We don't drop radiation_readings as it's new/independent

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
                voc REAL NOT NULL,
                voc_h2_raw REAL NOT NULL,
                voc_ethanol_raw REAL NOT NULL,
                pm25 REAL NOT NULL,
                pm10_est REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_readings_fetched_at
                ON readings (fetched_at);

            CREATE INDEX IF NOT EXISTS idx_readings_timestamp
                ON readings (timestamp);

            CREATE TABLE IF NOT EXISTS radiation_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpm INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_radiation_readings_timestamp
                ON radiation_readings (timestamp);

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
    
    # Deduplication: Check if values changed compared to the last entry
    latest = latest_reading(db_path)
    if latest:
        is_duplicate = all(
            abs(float(latest[field]) - float(reading[field])) < 1e-7
            for field in READING_FIELDS
        )
        if is_duplicate:
            return False

    fields_sql = ", ".join(("timestamp", "fetched_at") + READING_FIELDS)
    placeholders = ", ".join("?" for _ in ("timestamp", "fetched_at") + READING_FIELDS)
    values = [reading["timestamp"], utc_now_iso()]
    values.extend(reading[field] for field in READING_FIELDS)

    with connect(db_path) as conn:
        cur = conn.execute(
            f"INSERT OR REPLACE INTO readings ({fields_sql}) VALUES ({placeholders})",
            values,
        )
        # rowcount is 1 for new insert, 1 or 2 for replace
        return cur.rowcount >= 1


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
    # Order by fetched_at, not id: compaction re-inserts historical rows with
    # fresh autoincrement ids, so the highest id is not necessarily the newest.
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM readings ORDER BY fetched_at DESC, id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def count_radiation(db_path: str | Path) -> int:
    with connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM radiation_readings").fetchone()
    return int(row["count"])


def latest_radiation(db_path: str | Path) -> dict[str, Any] | None:
    # Order by timestamp, not id: compaction re-inserts historical rows with
    # fresh autoincrement ids, so the highest id is not necessarily the newest.
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM radiation_readings ORDER BY timestamp DESC, id DESC LIMIT 1"
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
                   co2, co2_est, voc,
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
def insert_radiation(db_path: str | Path, cpm: int) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO radiation_readings (timestamp, cpm) VALUES (?, ?)",
            (utc_now_iso(), cpm),
        )


def query_radiation(
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
            SELECT id, timestamp, cpm
            FROM radiation_readings
            WHERE timestamp >= ?
            ORDER BY timestamp ASC, id ASC
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


def compact_all_tables(db_path: str | Path) -> None:
    """Run compaction for all sensor tables."""
    # Compact air quality readings
    compact_table(db_path, "readings", READING_FIELDS)
    # Compact radiation readings
    compact_table(db_path, "radiation_readings", ("cpm",))


def compact_table(db_path: str | Path, table: str, fields: tuple[str, ...]) -> None:
    """Collapses hours older than the current one into 20 representative points."""
    # 1. Identify "full" hours in the past
    current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
    
    with connect(db_path) as conn:
        # Group by hour string (YYYY-MM-DDTHH:00:00Z)
        hours_rows = conn.execute(
            f"""
            SELECT substr(timestamp, 1, 14) || '00:00Z' as hour_key, COUNT(*) as count
            FROM {table}
            WHERE timestamp < ?
            GROUP BY hour_key
            HAVING count > 20
            """,
            (current_hour,),
        ).fetchall()

    # Compact each hour in its own transaction so the write lock is released
    # between hours. A single transaction spanning every historical hour would
    # block the collectors for the whole run (worst on the first run after a
    # backlog builds up); per-hour commits keep that window to one hour's rows.
    for row in hours_rows:
        hour_key = row["hour_key"]
        # Air readings carry a sensor-supplied timestamp; if it is not the
        # expected ISO "YYYY-MM-DDTHH:..." UTC form the hour bucketing is
        # meaningless, so skip rather than collapse unrelated rows together.
        if not _is_iso_hour_key(hour_key):
            LOGGER.warning("Skipping compaction for malformed hour key %r in %s", hour_key, table)
            continue
        with connect(db_path) as conn:
            _compact_hour(conn, table, fields, hour_key)


def _is_iso_hour_key(hour_key: str) -> bool:
    try:
        datetime.strptime(hour_key, "%Y-%m-%dT%H:00:00Z")
        return True
    except (ValueError, TypeError):
        return False


def _compact_hour(conn: sqlite3.Connection, table: str, fields: tuple[str, ...], hour_key: str) -> None:
    """Reduces a single hour's data to 20 averaged points."""
    # Fetch all data for this hour
    # We use a pattern match because substr in SQLite is sensitive to format
    pattern = hour_key[:13] + "%"
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE timestamp LIKE ? ORDER BY timestamp ASC",
        (pattern,),
    ).fetchall()
    
    if len(rows) <= 20:
        return

    data = [dict(r) for r in rows]
    chunk_size = len(data) / 20.0
    collapsed = []

    for i in range(20):
        start = int(i * chunk_size)
        end = int((i + 1) * chunk_size)
        if i == 19: end = len(data) # Ensure last chunk reaches the end
        
        chunk = data[start:end]
        if not chunk: continue

        # Average the values
        new_point = {
            "timestamp": chunk[len(chunk)//2]["timestamp"], # Use middle timestamp
        }
        if "fetched_at" in chunk[0]:
            new_point["fetched_at"] = chunk[len(chunk)//2]["fetched_at"]
        for field in fields:
            vals = [c[field] for c in chunk if c[field] is not None]
            average = sum(vals) / len(vals) if vals else 0.0
            new_point[field] = round(average) if field in INTEGER_FIELDS else average

        collapsed.append(new_point)

    # Replace original data with collapsed data in a transaction
    conn.execute(f"DELETE FROM {table} WHERE timestamp LIKE ?", (pattern,))
    
    placeholders = ", ".join("?" for _ in collapsed[0].keys())
    columns = ", ".join(collapsed[0].keys())
    conn.executemany(
        f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
        [tuple(p.values()) for p in collapsed]
    )
    LOGGER.info("Compacted hour %s in %s (from %s to 20 points)", hour_key, table, len(rows))
