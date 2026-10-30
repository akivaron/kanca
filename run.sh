#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker tidak ditemukan. Instal Docker Desktop terlebih dahulu." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose tidak tersedia." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon tidak dapat diakses. Jalankan Docker Desktop dan periksa akses Anda." >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "File .env belum ada. Salin .env.example ke .env dan isi konfigurasi terlebih dahulu." >&2
  exit 1
fi

docker compose up --build -d
echo "Kanca dimulai. Buka http://localhost:8765"
echo "Dokumentasi API: http://localhost:8765/docs"
echo "Lihat log: docker compose logs -f"
echo "Hentikan: ./stop.sh"
