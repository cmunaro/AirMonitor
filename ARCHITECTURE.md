# Air Monitor — Architecture

A small, self-contained service for a Raspberry Pi (or any LAN host) that polls a
local air-quality sensor endpoint and an attached Geiger counter, stores the
readings in SQLite, and serves a live dashboard over HTTP. It can optionally drive
an Olimpia air conditioner through a bundled JVM sidecar. No web framework — only
the Python standard library, plus the optional `pygmc` driver for the radiation
sensor and a `java` runtime for the AC integration.

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
                    │   └──────────────────┘                          └────┬────────┬──────┘ │
                    │                                                       │        │ HTTP   │
                    │   ┌──────────────────┐   set_*/snapshot              │        ▼        │
  Olimpia AC ◀──REST────│ AcController      │◀──────────────────────────────┘  Browser dash  │
  (Midea cloud)      │  │ (thread, 30s)    │      get_view                  (static/ + /api/*)│
                    │   └────────┬─────────┘                                                  │
                    │            │ launches/supervises                                        │
                    │   ┌────────▼─────────┐                                                  │
                    │   │ AcSidecar (JVM)   │  java -jar olimpia-client.jar (subprocess)       │
                    │   │ ac-supervisor thr │                                                  │
                    │   └──────────────────┘                                                  │
                    └──────────────────────────────────────────────────────────────────────────┘
```

Under the `run` command the whole thing is **one Python process** of cooperating
threads — the air, radiation, and maintenance workers, the foreground HTTP server,
and (when the AC integration is enabled) the AC controller plus a supervisor for
the JVM sidecar, which itself runs as a managed child subprocess.

## Modules

| File | Responsibility |
|------|----------------|
| [`main.py`](main.py) | CLI entrypoint, argument parsing, thread orchestration, signal handling. |
| [`__main__.py`](__main__.py) | Allows `python -m air_monitor`; delegates to `main.main`. |
| [`config.py`](config.py) | Runtime defaults, all overridable via environment variables. |
| [`collector.py`](collector.py) | `AirDataCollector` (HTTP polling) and `RadiationCollector` (serial polling). |
| [`db.py`](db.py) | All SQLite access: schema, inserts, queries, dedup, and hourly compaction. |
| [`server.py`](server.py) | `ThreadingHTTPServer` + request handler exposing the JSON API and static files. |
| [`ac_server.py`](ac_server.py) | Bootstraps the Olimpia AC sidecar: fetches the pinned jar from a private GitHub release, verifies its SHA-256, launches and supervises the JVM. |
| [`ac.py`](ac.py) | `AcClient` (REST wrapper over the sidecar) and `AcController` (caches state, owns the auto/manual settings, runs the regulation loop). |
| [`static/`](static/) | Vanilla HTML/CSS/JS dashboard — no build step, no dependencies. |
| [`deploy/`](deploy/) | systemd unit for running on a Pi. |

## Runtime / commands

`main.py` exposes four subcommands (`python -m air_monitor <cmd>`):

- **`run`** — the normal mode. Starts all collector threads, the maintenance
  thread, and the HTTP server in the foreground. Wires `SIGTERM`/`SIGINT`/`SIGBREAK`
  to a shared `threading.Event` so all threads shut down cleanly. After the
  dashboard is serving, it best-effort starts the AC sidecar (non-essential, so it
  comes up last) and attaches an `AcController` to the live handler.
- **`serve`** — HTTP server only (read-only dashboard against an existing DB).
- **`collect-once`** — performs a single air-data fetch+store and prints the
  result; useful for cron or debugging.
- **`init-db`** — creates the SQLite schema and exits.

Shutdown is cooperative: the signal handler sets `stop_event`, then the main
thread calls `httpd.shutdown()` (from a *different* thread than `serve_forever()`,
which would otherwise deadlock) and the `finally` block joins the worker threads
with short timeouts and stops the AC sidecar ([`main.py`](main.py)).

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

The AC sidecar adds its own `AIR_MONITOR_AC_*` and `OLIMPIA_*` variables (pinned
release, port, poll interval, auto setpoints/hysteresis, GitHub token, and cloud
credentials) — see the AC integration section below and the README. These are
loaded from an `ac.env` file in the project directory if present;
[`config.py`](config.py) reads it with `os.environ.setdefault`, so anything already
exported on the command line wins.

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
| `/api/errors?limit=` | Collector error stats + recent errors. |
| `/api/health` | Row counts, latest values, last 10 errors. |
| `/api/ac` | AC view (control mode, targets, current state); `{"available": false}` when the sidecar is down. |
| `/`, `/index.html`, `/static/*` | Dashboard assets. |

**AC commands (POST `/api/ac/*`)** — `power` `{on}`, `mode` `{mode}`, `fan`
`{speed}`, `control-mode` `{mode: auto|manual}`, `targets` `{humidity, temperature}`.
The handler validates enums via `_require`, returns `503` when AC is unavailable,
`400` on bad input, and `502` on a sidecar/cloud failure, otherwise echoing the
fresh AC view.

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

## AC integration (optional)

The Olimpia AC support is split between a Python control plane and a JVM data
plane, joined by a small REST API. All the device crypto/protocol lives in the
JVM; air_monitor stays stdlib-only.

### Bootstrap ([`ac_server.py`](ac_server.py))
- `maybe_start()` never raises — any failure is logged and AC features are simply
  disabled.
- If `AIR_MONITOR_AC_URL` is set, it points at an already-running server and skips
  fetch + launch. Otherwise it needs `java` on `PATH`.
- `_ensure_jar()` fetches `<artifact>-<version>.jar` from the `v<version>` GitHub
  release of the (private) `AC_SERVER_REPO`, **verifying its SHA-256** against the
  pinned `AC_SERVER_SHA256` — an unset or mismatching hash is refused, so an
  unverified jar is never executed. A verified copy is cached under `data/ac-server`.
- `_AuthStrippingRedirectHandler` drops the `Authorization` header when GitHub
  302-redirects the asset download to a different storage host.
- `_launch()` runs `java -jar <jar>` with `PORT` and the `OLIMPIA_*` credentials
  forwarded via the environment; `_await_health()` polls `/api/health` until ready.
- `AcSidecar.supervise()` relaunches the JVM if it exits unexpectedly (a no-op for
  an external URL); `stop()` terminates then kills the child on shutdown.

### Control ([`ac.py`](ac.py))
- `AcClient` is a thin JSON wrapper over the sidecar's `/api/ac/*` REST routes.
- `AcController` runs its own thread (`AC_POLL_SECONDS`, default 30s): it caches
  the latest snapshot under a lock and, in **auto** control mode, regulates the
  running unit. `_desired_mode()` compares the latest humidity/temperature reading
  against the saved targets with a hysteresis deadband (`*_HYST`) and picks
  `Dry`/`Cool`/`Fan`, leaving the mode untouched inside the band. It never forces
  power on.
- Control mode and targets are persisted in the `ac_settings` table, so they
  survive restarts. The HTTP handler holds the controller as a class attribute
  (`AirMonitorHandler.ac`) and delegates the `/api/ac` routes to it.

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
- **AC is a sidecar, not a dependency.** The device protocol lives in a separate
  JVM that air_monitor pins, verifies, and supervises — keeping the Python side
  stdlib-only and letting AC fail (no `java`, no token, jar mismatch) without
  touching the rest of the service.
- **Pinned + checksummed releases.** The exact AC jar version and its SHA-256 are
  committed constants; bumping the integration is a deliberate, reviewed edit, and
  a hash mismatch refuses to run rather than executing an unexpected binary.
