#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker tidak ditemukan." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon tidak dapat diakses. Jalankan Docker Desktop dan periksa akses Anda." >&2
  exit 1
fi

docker compose -f compose.yaml -f compose.gateways.yaml --profile '*' down
echo "Kanca dihentikan; volume data tetap tersimpan."
