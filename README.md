# Air Monitor

A small, self-contained service for a Raspberry Pi (or any LAN host) that polls a
local air-quality sensor and an attached Geiger counter, stores the readings in
SQLite, and serves a live dashboard over HTTP. It can optionally drive an Olimpia
air conditioner (humidistat/thermostat automation) through a bundled JVM sidecar.

No external services and no web framework — just the Python standard library, plus
the optional [`pygmc`](https://pypi.org/project/pygmc/) driver for the radiation
sensor and a `java` runtime if you use the AC integration.

## Features

- **Air-quality logging** — polls a JSON sensor endpoint every 10s (temperature,
  humidity, CO2, VOC, particulates, score, …) and stores it in SQLite.
- **Radiation logging** — reads CPM from a USB Geiger counter every ~2s via `pygmc`.
- **Live dashboard** — a dependency-free HTML/JS page with hand-drawn charts,
  selectable metric groups and time windows, and a health/errors view.
- **AC control (optional)** — manual power/mode/fan control plus an automatic mode
  that regulates the unit against humidity/temperature targets using the latest
  sensor readings.
- **Self-maintaining** — old data is compacted hourly to keep the DB small.
- **Graceful degradation** — runs fine with no Geiger counter and no AC; those
  features simply turn themselves off.

## Requirements

- Python 3.9+ (standard library only for the core service).
- Optional: [`pygmc`](https://pypi.org/project/pygmc/) for the radiation collector.
- Optional: a Java runtime (`java` on `PATH`) for the Olimpia AC sidecar.

## Quick start

```bash
git clone <this-repo> AirMonitor
cd AirMonitor

# Create and activate a virtualenv (the systemd unit expects ./.venv).
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Optional: install the radiation-sensor driver (the core service needs no deps).
pip install pygmc

# Run the full service: collectors + dashboard (+ AC sidecar if configured).
python run.py run
```

Then open the dashboard at **http://localhost:8080** (it also listens on the LAN).

The core service is standard-library only, so the virtualenv is optional for a
bare run — but [`deploy/air-monitor.service`](deploy/air-monitor.service) launches
`./.venv/bin/python`, so create the venv at the project root if you deploy via
systemd (and that's also where `pygmc` is installed when you use a Geiger counter).

> The package uses relative imports. `run.py` is a convenience wrapper that puts
> the parent directory on `sys.path` and runs the package; it is equivalent to
> `python -m air_monitor` from the parent directory.

## Commands

`run.py` (and `python -m air_monitor`) exposes four subcommands:

| Command | What it does |
|---------|--------------|
| `run` | Normal mode. Starts the air + radiation collectors, the hourly maintenance task, the HTTP dashboard, and (if enabled) the AC sidecar — all in one process. |
| `serve` | Dashboard only, read-only against an existing DB. No collectors, no AC. |
| `collect-once` | Performs a single air-data fetch + store, prints the result, and exits. Handy for cron or debugging. |
| `init-db` | Creates the SQLite schema and exits. |

Common flags: `--db`, `--host`, `--port`, `--endpoint`, `--interval`, `--timeout`,
`--log-level`. CLI flags override environment variables per run.

```bash
python run.py serve --port 9000
python run.py collect-once --endpoint http://192.168.1.204/air-data/latest
python run.py init-db --db ./data/air_monitor.sqlite
```

## Configuration

All defaults live in [`config.py`](config.py) and are overridable via environment
variables (or an `ac.env` file in the project root — see below).

### Core

| Env var | Default | Meaning |
|---------|---------|---------|
| `AIR_MONITOR_ENDPOINT` | `http://192.168.1.204/air-data/latest` | Air sensor JSON endpoint. |
| `AIR_MONITOR_INTERVAL` | `10` | Air poll interval (seconds). |
| `AIR_MONITOR_DB` | `./data/air_monitor.sqlite` | SQLite file path. |
| `AIR_MONITOR_HOST` | `0.0.0.0` | HTTP bind host. |
| `AIR_MONITOR_PORT` | `8080` | HTTP bind port. |
| `AIR_MONITOR_TIMEOUT` | `5` | Air HTTP request timeout (seconds). |

### AC sidecar (optional)

| Env var | Default | Meaning |
|---------|---------|---------|
| `AIR_MONITOR_AC_ENABLED` | `1` | Set `0` to disable the AC sidecar. |
| `AIR_MONITOR_AC_VERSION` | `1.0.0` | Pinned Olimpia release to fetch (`v<version>` tag). |
| `AIR_MONITOR_AC_SHA256` | — | **Required** SHA-256 of the jar; the jar is rejected if it differs. Without it the sidecar refuses to run. |
| `AIR_MONITOR_AC_REPO` | `cmunaro/Olimpia` | GitHub repo to fetch the release from. |
| `AIR_MONITOR_AC_ARTIFACT` | `olimpia-client` | Release asset base name (`<artifact>-<version>.jar`). |
| `AIR_MONITOR_AC_CACHE` | `./data/ac-server` | Where the fetched jar is cached. |
| `AIR_MONITOR_AC_PORT` | `8090` | Local port the sidecar listens on. |
| `AIR_MONITOR_AC_URL` | — | Point at an already-running AC server; skips fetch + launch. |
| `AIR_MONITOR_AC_POLL` | `30` | How often the controller polls the AC and runs the auto loop (seconds). |
| `AIR_MONITOR_AC_TARGET_HUM` / `AIR_MONITOR_AC_TARGET_TEMP` | `50` / `24` | Default auto-mode setpoints. |
| `AIR_MONITOR_AC_HUM_HYST` / `AIR_MONITOR_AC_TEMP_HYST` | `3` / `1` | Hysteresis (deadband) around the targets so the controller doesn't flap. |
| `OLIMPIA_GH_TOKEN` (or `GITHUB_TOKEN`) | — | Token with `Contents:read` on the private release repo. |
| `OLIMPIA_ACCOUNT` / `OLIMPIA_PASSWORD` | — | Olimpia/Midea cloud credentials, forwarded to the AC client JVM. |

#### `ac.env`

On startup [`config.py`](config.py) loads a `KEY=VALUE` file named `ac.env` from
the project directory, if present. Real environment variables take precedence over
file values. This is where AC secrets and the pinned release live.

> **Do not commit `ac.env`** — it holds a GitHub token and cloud credentials.
> Copy `ac.env.example` to `ac.env`, fill it in, and keep `ac.env` gitignored.

The AC integration degrades gracefully: if it's disabled, if `java` is missing, if
no token is set, or if the jar can't be fetched/verified, AC features are skipped
and the rest of the service runs normally.

## HTTP API

All read endpoints are `GET`; AC commands are `POST` with a JSON body.

| Path | Method | Returns |
|------|--------|---------|
| `/api/readings?hours=&max_points=` | GET | Downsampled air-quality series. |
| `/api/radiation?hours=&max_points=` | GET | Downsampled CPM series. |
| `/api/latest` | GET | Most recent air reading. |
| `/api/radiation/latest` | GET | Most recent CPM reading. |
| `/api/errors?limit=` | GET | Collector error stats + recent errors. |
| `/api/health` | GET | Row counts, latest values, last 10 errors. |
| `/api/ac` | GET | AC view: control mode, targets, current state, power/mode/fan. `{"available": false}` when the sidecar is down. |
| `/api/ac/power` | POST | `{"on": true\|false}` |
| `/api/ac/mode` | POST | `{"mode": "Cool"\|"Dry"\|"Fan"\|"Auto"}` |
| `/api/ac/fan` | POST | `{"speed": "Low"\|"High"\|"Auto"}` |
| `/api/ac/control-mode` | POST | `{"mode": "auto"\|"manual"}` |
| `/api/ac/targets` | POST | `{"humidity": <n>, "temperature": <n>}` |
| `/`, `/index.html`, `/static/*` | GET | Dashboard assets. |

## Running as a service (Raspberry Pi)

A systemd unit is provided in [`deploy/air-monitor.service`](deploy/air-monitor.service).
Adjust `User`/`WorkingDirectory` to match where you cloned the repo, then:

```bash
sudo cp deploy/air-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now air-monitor
```

The unit restarts on crash and on boot, waits for the network (needed for the AC
release fetch), and gives `run.py` time to stop the JVM child cleanly on shutdown.
Secrets are loaded by `config.py` from `ac.env` in the working directory, so no
`EnvironmentFile` is needed.

Alternatively, `run.sh` is a small launcher that sources `ac.env`, enables the AC
sidecar by default, and execs `run.py`.

## Project layout

```
main.py        CLI entrypoint, thread orchestration, signal handling
__main__.py    `python -m air_monitor` shim
run.py         convenience entrypoint (`python run.py ...`)
run.sh         launcher that sources ac.env and enables the AC sidecar
config.py      runtime defaults + ac.env loader
collector.py   AirDataCollector (HTTP) and RadiationCollector (serial)
db.py          all SQLite access: schema, inserts, queries, compaction
server.py      ThreadingHTTPServer + request handler (JSON API + static files)
ac_server.py   fetches/verifies/launches the Olimpia JVM sidecar
ac.py          AC REST client + controller (auto humidistat/thermostat loop)
static/        vanilla HTML/CSS/JS dashboard (no build step)
deploy/        systemd unit
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deeper design walkthrough.
