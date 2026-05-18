#!/usr/bin/env bash

set -euo pipefail

export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/db/docker-compose.yml"
DB_NAME="${FRAGMENT_DB_NAME:-fragment}"
DB_USER="${FRAGMENT_DB_USER:-fragment}"
DB_PORT="${FRAGMENT_DB_PORT:-55432}"

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "$COMPOSE_FILE" "$@"
  else
    echo "Docker Compose is required but was not found." >&2
    exit 1
  fi
}

echo "Starting Fragment Autocomplete PostgreSQL/PostGIS database..."
compose up -d db

echo "Waiting for PostgreSQL to become ready..."
for attempt in $(seq 1 60); do
  if compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    echo "Database is ready."
    echo
    echo "Connection info:"
    echo "  host: localhost"
    echo "  port: $DB_PORT"
    echo "  database: $DB_NAME"
    echo "  user: $DB_USER"
    echo "  password: fragment_dev_password"
    echo
    echo "Override the host port with FRAGMENT_DB_PORT=<port> if needed."
    exit 0
  fi
  sleep 1
done

echo "Database did not become ready within 60 seconds." >&2
compose ps
exit 1
