#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/db/docker-compose.yml"
MIGRATIONS_DIR="$ROOT_DIR/infra/db/migrations"
SEED_DIR="$ROOT_DIR/infra/db/seed"
DB_NAME="${FRAGMENT_DB_NAME:-fragment}"
DB_USER="${FRAGMENT_DB_USER:-fragment}"

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

apply_sql_file() {
  local file="$1"
  local display_path="${file#$ROOT_DIR/}"
  echo "Applying $display_path..."
  compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$file"
}

echo "Checking database connection..."
compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null

shopt -s nullglob
migration_files=("$MIGRATIONS_DIR"/*.sql)
seed_files=("$SEED_DIR"/*.sql)

if [ "${#migration_files[@]}" -eq 0 ]; then
  echo "No migration files found in $MIGRATIONS_DIR" >&2
  exit 1
fi

echo "Applying database migrations..."
for file in "${migration_files[@]}"; do
  apply_sql_file "$file"
done

if [ "${#seed_files[@]}" -gt 0 ]; then
  echo "Applying seed files..."
  for file in "${seed_files[@]}"; do
    apply_sql_file "$file"
  done
fi

echo "Database migrations and seed values applied successfully."
