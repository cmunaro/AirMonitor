# AirMonitor

AirMonitor collects readings from an air-quality monitor, saves them to a local SQLite database, and displays them in a small Phoenix LiveView dashboard.

The umbrella contains four applications:

- `air_monitor_core` contains the application logic and calculates the air-quality score.
- `air_monitor_fetcher` fetches a new reading every few seconds.
- `air_monitor_storage` reads and writes the SQLite database through Ecto.
- `air_monitor_web` contains the LiveView dashboard and the JSON API.

## Running it

The first time you run the project, create the SQLite database and apply its migrations:

```bash
mix ecto.create -r AirMonitorStorage.Repository
mix ecto.migrate -r AirMonitorStorage.Repository
```

Then start everything from the root of the project:

```bash
mix phx.server
```

The dashboard will be available at [http://localhost:4000](http://localhost:4000).

## Endpoints

`GET /` shows the LiveView dashboard with the latest readings.

`GET /api/readings` returns the readings as JSON. It accepts an optional `limit` between 1 and 200 (20 by default) and an optional ISO 8601 `before` cursor for pagination.

`GET /dev/dashboard` opens Phoenix LiveDashboard when development routes are enabled.
