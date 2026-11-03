#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker Compose is unavailable or Docker is not running." >&2; exit 1
fi
if [[ ! -f config.json ]]; then python3 setup.py; fi
if python3 -c 'import json; c=json.load(open("config.json")); raise SystemExit(0 if any(s.get("type")=="ble" for s in c.get("sources",[])) else 1)'; then
  if [[ "$(uname -s)" != Linux || ! -S /run/dbus/system_bus_socket ]]; then
    echo "Bluetooth sources require a Linux mini PC with BlueZ and system D-Bus." >&2; exit 1
  fi
  docker compose -f compose.yaml -f compose.ble.yaml up -d --build
else
  docker compose up -d --build
fi
echo "Gateway dimulai. Lihat status: docker compose logs -f"
