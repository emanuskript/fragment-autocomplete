#!/usr/bin/env bash

set -euo pipefail

export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/db/docker-compose.yml"
CONFIRM="${1:-}"

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

if [ "$CONFIRM" != "--yes" ]; then
  echo "This will stop the local Fragment Autocomplete database and delete its Docker volume."
  printf "Type 'reset fragment database' to continue: "
  read -r answer
  if [ "$answer" != "reset fragment database" ]; then
    echo "Reset cancelled."
    exit 0
  fi
fi

echo "Stopping database and removing local volume..."
compose down -v

echo "Starting fresh database..."
bash "$ROOT_DIR/scripts/db_start.sh"

echo "Applying migrations and seed values..."
bash "$ROOT_DIR/scripts/db_migrate.sh"

echo "Database reset completed."
