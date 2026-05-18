#!/usr/bin/env bash

set -euo pipefail

export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/db/docker-compose.yml"
DB_NAME="${FRAGMENT_DB_NAME:-fragment}"
DB_USER="${FRAGMENT_DB_USER:-fragment}"
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

check_zero() {
  local label="$1"
  local sql="$2"
  local result
  if result="$(run_sql "$sql" 2>/dev/null)" && [ "$result" -eq 0 ]; then
    pass "$label"
  else
    fail "$label"
  fi
}

cd "$ROOT_DIR"

echo "Validating initial sample dataset registration..."
echo

if bash scripts/db_start.sh >/dev/null && bash scripts/db_migrate.sh >/dev/null; then
  pass "database reachable and migrations applied"
else
  fail "database reachable and migrations applied"
fi

if python3 scripts/register_initial_sample_dataset.py --verbose; then
  pass "sample dataset registration script"
else
  fail "sample dataset registration script"
fi

echo
echo "Checking registered database records..."
check_count_at_least \
  "sample repositories" \
  "SELECT count(*) FROM repository WHERE name IN ('e-codices', 'Fragmentarium');" \
  2
check_count_at_least \
  "full-page canvases" \
  "SELECT count(*) FROM canvas WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1' AND raw_metadata->>'sample_kind' = 'full_page';" \
  5
check_count_at_least \
  "full-page image assets" \
  "SELECT count(*) FROM image_asset WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1' AND raw_metadata->>'sample_kind' = 'full_page';" \
  5
check_count_at_least \
  "fragment records" \
  "SELECT count(*) FROM fragment WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1' AND raw_metadata->>'sample_kind' = 'fragment';" \
  5
check_count_at_least \
  "fragment image assets" \
  "SELECT count(*) FROM image_asset WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1' AND raw_metadata->>'sample_kind' = 'fragment';" \
  5
check_count_at_least \
  "all sample IDs represented in image assets" \
  "SELECT count(DISTINCT raw_metadata->>'sample_id') FROM image_asset WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1';" \
  10
check_zero \
  "training_allowed remains conservative on sample image assets" \
  "SELECT count(*) FROM image_asset WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1' AND training_allowed IS TRUE;"
check_zero \
  "training_allowed remains conservative on sample fragments" \
  "SELECT count(*) FROM fragment WHERE raw_metadata->>'sample_dataset_id' = 'initial_sample_dataset_v0_1' AND training_allowed IS TRUE;"

echo
if [ "$failures" -eq 0 ]; then
  echo "Initial sample dataset validation passed."
  exit 0
fi

echo "Initial sample dataset validation failed with $failures issue(s)."
exit 1
