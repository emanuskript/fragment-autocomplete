#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/db/docker-compose.yml"
DB_NAME="${FRAGMENT_DB_NAME:-fragment}"
DB_USER="${FRAGMENT_DB_USER:-fragment}"
REPOSITORY_NAME="Fixture Repository"
failures=0

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

pass() {
  echo "  [PASS] $1"
}

fail() {
  echo "  [FAIL] $1"
  failures=$((failures + 1))
}

run_sql() {
  local sql="$1"
  compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atc "$sql"
}

check_count_at_least() {
  local label="$1"
  local sql="$2"
  local minimum="$3"
  local result
  if result="$(run_sql "$sql" 2>/dev/null)" && [ "$result" -ge "$minimum" ]; then
    pass "$label ($result >= $minimum)"
  else
    fail "$label"
  fi
}

cd "$ROOT_DIR"

echo "Validating IIIF ingestion proof of concept..."
echo

if command -v pytest >/dev/null 2>&1; then
  echo "Running IIIF normalizer tests..."
  if pytest tests/ingestion/test_iiif_normalizer.py; then
    pass "normalizer tests"
  else
    fail "normalizer tests"
  fi
else
  fail "pytest is not installed"
fi

echo
echo "Ensuring database is reachable..."
if bash scripts/db_start.sh >/dev/null && bash scripts/db_migrate.sh >/dev/null; then
  pass "database reachable and migrations applied"
else
  fail "database reachable and migrations applied"
fi

echo
echo "Running fixture ingestion..."
if python3 scripts/ingest_iiif_manifest.py --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json --repository "$REPOSITORY_NAME"; then
  pass "IIIF v3 fixture ingestion"
else
  fail "IIIF v3 fixture ingestion"
fi

if python3 scripts/ingest_iiif_manifest.py --file tests/ingestion/fixtures/iiif_v2_minimal_manifest.json --repository "$REPOSITORY_NAME"; then
  pass "IIIF v2 fixture ingestion"
else
  fail "IIIF v2 fixture ingestion"
fi

echo
echo "Checking database rows from fixture ingestion..."
check_count_at_least \
  "fixture manifest cache rows" \
  "SELECT count(*) FROM iiif_manifest_cache WHERE manifest_url LIKE '%iiif_v2_minimal_manifest.json' OR manifest_url LIKE '%iiif_v3_minimal_manifest.json';" \
  2
check_count_at_least \
  "fixture repository rows" \
  "SELECT count(*) FROM repository WHERE name = '$REPOSITORY_NAME';" \
  1
check_count_at_least \
  "fixture manuscript rows" \
  "SELECT count(*) FROM manuscript WHERE raw_metadata->>'source' = 'iiif_ingestion_poc' AND repository_id IN (SELECT id FROM repository WHERE name = '$REPOSITORY_NAME');" \
  2
check_count_at_least \
  "fixture canvas rows" \
  "SELECT count(*) FROM canvas WHERE canvas_identifier LIKE 'https://fixtures.example.org/iiif/%/canvas/%';" \
  2
check_count_at_least \
  "fixture image asset rows" \
  "SELECT count(*) FROM image_asset WHERE source_url LIKE 'https://fixtures.example.org/images/%';" \
  2

echo
if [ "$failures" -eq 0 ]; then
  echo "IIIF ingestion validation passed."
  exit 0
fi

echo "IIIF ingestion validation failed with $failures issue(s)."
exit 1
