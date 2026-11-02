#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -f certs/server.key ]; then
  mkdir -p certs
  openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/server.key -out certs/ca.crt -days 365 -subj '/CN=Kanca simulator'
  cp certs/ca.crt certs/server.crt
  chmod 600 certs/server.key
fi
docker compose -f compose.yaml up -d --force-recreate
