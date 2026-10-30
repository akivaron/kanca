#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Linux || ! -S /run/dbus/system_bus_socket ]]; then
  echo "Pemindaian ini memerlukan Linux dengan BlueZ dan system D-Bus." >&2
  exit 1
fi
docker compose -f compose.ble-scan.yaml run --rm scanner
