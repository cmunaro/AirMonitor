# Air Monitor — Architecture

A small, self-contained service for a Raspberry Pi (or any LAN host) that polls a
local air-quality sensor endpoint and an attached Geiger counter, stores the
readings in SQLite, and serves a live dashboard over HTTP. No external services,
no frameworks — only the Python standard library plus the optional `pygmc` driver
for the radiation sensor.

## High-level overview

```
                    ┌──────────────────────── air_monitor process ────────────────────────┐
                    │                                                                      │
  Air sensor        │   ┌──────────────────┐                                               │
  HTTP/JSON ───────────▶│ AirDataCollector │──┐                                            │
  192.168.1.204      │   │ (thread, 10s)    │  │  insert_reading / log_error               │
                    │   └──────────────────┘  │                                            │
                    │                          ▼                                            │
  Geiger counter     │   ┌──────────────────┐ ┌──────────────┐                              │
  USB serial ───────────▶│ RadiationCollector│▶│  SQLite (WAL) │◀──── query_* ───┐          │
  (pygmc)            │   │ (thread, 2s)     │ │ air_monitor   │                  │          │
                    │   └──────────────────┘ │ .sqlite       │                  │          │
                    │                         └──────────────┘                  │          │
                    │   ┌──────────────────┐         ▲                ┌─────────┴────────┐ │
                    │   │ Maintenance       │─────────┘                │ ThreadingHTTPServer│ │
                    │   │ (thread, 1h)      │ compact_all_tables       │  AirMonitorHandler │ │
                    │   └──────────────────┘                          └─────────┬────────┘ │
                    │                                                            │          │
                    └────────────────────────────────────────────────────────────┼──────────┘
                                                                                  │ HTTP
                                                                                  ▼
                                                                    Browser dashboard
                                                                  (static/ + /api/*)
```

The whole thing runs as **one process with four threads** (under the `run`
command): three background producers/maintainers and the foreground HTTP server.

## Modules

| File | Responsibility |
|------|----------------|
| [`main.py`](main.py) | CLI entrypoint, argument parsing, thread orchestration, signal handling. |
| [`__main__.py`](__main__.py) | Allows `python -m air_monitor`; delegates to `main.main`. |
| [`config.py`](config.py) | Runtime defaults, all overridable via environment variables. |
| [`collector.py`](collector.py) | `AirDataCollector` (HTTP polling) and `RadiationCollector` (serial polling). |
| [`db.py`](db.py) | All SQLite access: schema, inserts, queries, dedup, and hourly compaction. |
| [`server.py`](server.py) | `ThreadingHTTPServer` + request handler exposing the JSON API and static files. |
| [`static/`](static/) | Vanilla HTML/CSS/JS dashboard — no build step, no dependencies. |

## Runtime / commands

`main.py` exposes four subcommands (`python -m air_monitor <cmd>`):

- **`run`** — the normal mode. Starts all collector threads, the maintenance
  thread, and the HTTP server in the foreground. Wires `SIGTERM`/`SIGINT` to a
  shared `threading.Event` so all threads shut down cleanly.
- **`serve`** — HTTP server only (read-only dashboard against an existing DB).
- **`collect-once`** — performs a single air-data fetch+store and prints the
  result; useful for cron or debugging.
- **`init-db`** — creates the SQLite schema and exits.

Shutdown is cooperative: the foreground server's signal handler sets `stop_event`
and calls `httpd.shutdown()`; the `finally` block joins the worker threads with
short timeouts ([`main.py:115`](main.py:115)).

## Configuration

All defaults live in [`config.py`](config.py) and read from the environment:

| Env var | Default | Meaning |
|---------|---------|---------|
| `AIR_MONITOR_ENDPOINT` | `http://192.168.1.204/air-data/latest` | Air sensor JSON endpoint. |
| `AIR_MONITOR_INTERVAL` | `10` | Air poll interval (seconds). |
| `AIR_MONITOR_DB` | `./data/air_monitor.sqlite` | SQLite file path. |
| `AIR_MONITOR_HOST` | `0.0.0.0` | HTTP bind host. |
| `AIR_MONITOR_PORT` | `8080` | HTTP bind port. |
| `AIR_MONITOR_TIMEOUT` | `5` | Air HTTP request timeout (seconds). |

CLI flags (`--endpoint`, `--interval`, `--db`, etc.) override these per-run.

## Data collection

### AirDataCollector ([`collector.py:29`](collector.py:29))
- `fetch_payload()` does a plain `urllib` GET, caps the read at 64 KiB, and parses
  JSON (warning, not failing, on unexpected `Content-Type`).
- `collect_once()` maps each failure class — `HTTPError`, `URLError`,
  `TimeoutError`, payload/`OSError` — to a labeled `stage` and records it via
  `log_error` into the `collector_errors` table, so the dashboard's health view
  can surface them.
- `run_forever()` loops on a `stop_event`, subtracting elapsed time from the
  interval so cadence stays even.

### RadiationCollector ([`collector.py:107`](collector.py:107))
- Lazily connects to the Geiger counter through the optional `pygmc` library, with
  a 1s stabilization delay after connect.
- Reads CPM every ~2s; retries once on a transient serial glitch, and on a hard
  failure drops the handle (`self._gc = None`) so the next cycle reconnects.
- `pygmc` is imported inside `_connect()`, so the rest of the app runs fine on
  machines with no sensor attached.

## Storage ([`db.py`](db.py))

SQLite with `WAL` journaling and `synchronous=NORMAL` — good fit for a
single-writer-per-table, many-reader workload on a Pi.

**Tables**
- `readings` — air-quality samples. `timestamp` is `UNIQUE`; columns are the 12
  numeric fields in `READING_FIELDS` (temp, humid, co2, voc, pm25, score, …) plus
  `fetched_at`.
- `radiation_readings` — `timestamp` + integer `cpm`.
- `collector_errors` — `occurred_at`, `stage`, `message` for diagnostics.

Indexes exist on the timestamp/`fetched_at` columns of each table.

**Key behaviors**
- **Schema self-heal**: `init_db` detects a legacy `co2_est_baseline` column and
  drops/recreates the `readings` table ([`db.py:47`](db.py:47)).
- **Deduplication**: `insert_reading` compares all sensor fields against the latest
  row and skips inserts where every value is unchanged (`< 1e-7`), avoiding flat
  runs of identical samples ([`db.py:124`](db.py:124)).
- **Downsampling on read**: `query_readings` / `query_radiation` clamp `hours`
  (≤ 31 days) and `max_points`, then stride-sample to at most `max_points` while
  always keeping the final point ([`db.py:205`](db.py:205)).
- **Hourly compaction**: `compact_all_tables` (run by the maintenance thread)
  collapses each *completed* past hour that has > 20 rows down to 20 averaged
  points per table, keeping the DB small over long retention windows
  ([`db.py:287`](db.py:287)).

## HTTP server & API ([`server.py`](server.py))

A `ThreadingHTTPServer` with a `SimpleHTTPRequestHandler` subclass. `make_server`
calls `init_db` then binds the handler with the configured `db_path` as a class
attribute. Static files are served from `static/` with explicit path-traversal
guards (rejecting absolute paths and `..`, and verifying the resolved path stays
under `static/`).

**Endpoints (all GET)**

| Path | Returns |
|------|---------|
| `/api/readings?hours=&max_points=` | Downsampled air-quality series. |
| `/api/radiation?hours=&max_points=` | Downsampled CPM series. |
| `/api/latest` | Most recent air reading. |
| `/api/radiation/latest` | Most recent CPM reading. |
| `/api/health` | Row counts, latest values, last 10 errors. |
| `/`, `/index.html`, `/static/*` | Dashboard assets. |

JSON is emitted compact with `Cache-Control: no-cache`.

## Frontend ([`static/`](static/))

A single dependency-free page that renders charts on a `<canvas>` by hand
([`static/app.js`](static/app.js)):

- Metrics are organized into **groups** (Comfort, CO2, VOC, Particulates, Score,
  Radiation), each with its own field list, labels, units, and colors.
- Switching group/time-window calls the appropriate API (`/api/readings` for air,
  `/api/radiation` for the radiation tab) and redraws.
- The dashboard polls every 10s. It always fetches both `/api/latest` and
  `/api/radiation/latest` (via `Promise.allSettled`) so the "Recent Values" grid
  and the top latest-pills stay current regardless of the active tab.
- Charting is fully custom: axis/grid drawing, multi-series lines, and an
  interactive hover tooltip with collision-avoiding labels and a clamped timestamp
  badge.

## Design notes & trade-offs

- **Stdlib-only by intent.** Easy to deploy on a Pi — no pip install beyond the
  optional `pygmc` driver, no build tooling for the frontend.
- **One process, shared `stop_event`.** Simple lifecycle; collectors are daemon
  threads so a stuck worker can't block process exit.
- **DB as the integration point.** Collectors only write; the server only reads.
  They never call each other, which keeps coupling low and makes `serve`/`run`
  separable.
- **Compaction trades fidelity for footprint.** Older data is averaged to 20
  points/hour, so long-window charts are smoothed approximations, not raw samples.
