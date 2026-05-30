#!/usr/bin/env bash
# Launch air_monitor. Usage: ./run.sh run        (collectors + dashboard + AC sidecar)
#                            ./run.sh serve       (dashboard only)
#
# The Olimpia AC client is started automatically by the `run` command when
# AIR_MONITOR_AC_ENABLED=1. Secrets and the pinned release live in ./ac.env
# (gitignored) — copy ac.env.example to ac.env and fill it in. `java` must be on
# PATH for the sidecar to launch; without it, AC features are skipped.
set -euo pipefail

cd "$(dirname "$0")"

# Load local secrets/pins (token, credentials, version+sha) if present.
if [ -f ./ac.env ]; then
  set -a
  . ./ac.env
  set +a
fi

# Enable the AC sidecar by default for this launcher (override in ac.env).
export AIR_MONITOR_AC_ENABLED="${AIR_MONITOR_AC_ENABLED:-1}"

exec python3 run.py "$@"
