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

run_sql() {
  local sql="$1"
  compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atc "$sql"
}

pass() {
  echo "  [PASS] $1"
}

fail() {
  echo "  [FAIL] $1"
  failures=$((failures + 1))
}

check_eq() {
  local label="$1"
  local sql="$2"
  local expected="$3"
  local result
  if result="$(run_sql "$sql" 2>/dev/null)" && [ "$result" = "$expected" ]; then
    pass "$label"
  else
    fail "$label (expected $expected, got ${result:-ERROR})"
  fi
}

check_true() {
  local label="$1"
  local sql="$2"
  check_eq "$label" "$sql" "t"
}

echo "Validating HSP/German normdata metadata alignment..."

if compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
  pass "database connection"
else
  fail "database connection"
fi

if pytest "$ROOT_DIR/tests/metadata/test_hsp_normdata.py"; then
  pass "HSP normdata YAML tests"
else
  fail "HSP normdata YAML tests"
fi

if python3 "$ROOT_DIR/scripts/import_hsp_normdata.py" --verbose; then
  pass "normdata import"
else
  fail "normdata import"
fi

check_true "controlled_vocabulary table exists" "SELECT to_regclass('public.controlled_vocabulary') IS NOT NULL;"
check_true "controlled_term table exists" "SELECT to_regclass('public.controlled_term') IS NOT NULL;"
check_true "metadata assignment table exists" "SELECT to_regclass('public.metadata_controlled_term_assignment') IS NOT NULL;"
check_true "fragment_location table exists" "SELECT to_regclass('public.fragment_location') IS NOT NULL;"

check_eq "SCRP term count" "SELECT count(*) FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'SCRP';" "116"
check_eq "FORM term count" "SELECT count(*) FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'FORM';" "92"
check_eq "CODC term count" "SELECT count(*) FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'CODC';" "73"
check_eq "BNDG term count" "SELECT count(*) FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'BNDG';" "240"
check_eq "HSP_SIMPLIFIED term count" "SELECT count(*) FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'HSP_SIMPLIFIED';" "18"

check_true "known SCRP term exists" "SELECT EXISTS (SELECT 1 FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'SCRP' AND ct.notation LIKE 'SCRP-%');"
check_true "known CODC-A366 term exists" "SELECT EXISTS (SELECT 1 FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'CODC' AND ct.notation = 'CODC-A366');"
check_true "known HSP form term exists" "SELECT EXISTS (SELECT 1 FROM controlled_term ct JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id WHERE cv.code = 'HSP_SIMPLIFIED' AND ct.notation = 'form');"

check_true "repository HSP columns exist" "SELECT count(*) = 9 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'repository' AND column_name IN ('hsp_key', 'gnd_uri', 'institution', 'institution_key', 'settlement', 'settlement_key', 'settlement_ref', 'repo_access_level', 'metadata_review_status');"
check_true "manuscript HSP columns exist" "SELECT count(*) = 27 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'manuscript' AND column_name IN ('hsp_id', 'mxml_id', 'corpus_id', 'former_shelfmarks', 'object_status', 'object_form', 'object_form_notation', 'material_type', 'material_notation', 'format', 'format_notation', 'orig_date_display', 'orig_date_type', 'orig_date_precision', 'orig_place_norm', 'script_type_display', 'script_type_notation', 'script_type_uuid', 'script_grade', 'layout_class', 'column_count_notation', 'ruling_technique', 'decoration', 'music_notation', 'persons', 'organisations', 'metadata_review_status');"
check_true "canvas page observation columns exist" "SELECT count(*) = 6 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'canvas' AND column_name IN ('written_area_height_mm', 'written_area_width_mm', 'lines_per_page', 'lines_per_column', 'ruling_visible', 'metadata_review_status');"
check_true "image_asset metadata columns exist" "SELECT count(*) = 3 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'image_asset' AND column_name IN ('rights_uri', 'binarisation_method', 'metadata_review_status');"
check_true "fragment HSP extension columns exist" "SELECT count(*) = 11 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'fragment' AND column_name IN ('parent_manuscript_id', 'host_volume', 'damage_zone', 'damage_extent_pct', 'orig_width_mm', 'orig_height_mm', 'completeness_pct', 'lines_visible', 'columns_visible', 'margin_visible', 'metadata_review_status');"

if [ "$failures" -eq 0 ]; then
  echo "HSP metadata alignment validation passed."
  exit 0
fi

echo "HSP metadata alignment validation failed with $failures issue(s)."
exit 1
