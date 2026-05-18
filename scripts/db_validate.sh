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

check_true() {
  local label="$1"
  local sql="$2"
  local result
  if result="$(run_sql "$sql" 2>/dev/null)" && [ "$result" = "t" ]; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_count_at_least() {
  local label="$1"
  local sql="$2"
  local minimum="$3"
  local result
  if result="$(run_sql "$sql" 2>/dev/null)" && [ "$result" -ge "$minimum" ]; then
    pass "$label"
  else
    fail "$label"
  fi
}

echo "Validating Fragment Autocomplete database schema..."
echo

if compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
  pass "database connection"
else
  fail "database connection"
fi

check_count_at_least "PostGIS extension enabled" "SELECT count(*) FROM pg_extension WHERE extname = 'postgis';" 1
check_count_at_least "pgcrypto extension enabled" "SELECT count(*) FROM pg_extension WHERE extname = 'pgcrypto';" 1

echo
echo "Checking required tables..."
required_tables=(
  repository
  manuscript
  witness
  iiif_manifest_cache
  canvas
  image_asset
  msi_asset
  fragment
  annotation
  segmentation_run
  layout_region
  artificial_fragment_task
  reconstruction_job
  reconstruction_candidate
  retrieval_embedding
  text_witness_link
  evaluation_run
  export_bundle
)

for table in "${required_tables[@]}"; do
  check_true "table exists: $table" "SELECT to_regclass('public.$table') IS NOT NULL;"
done

echo
echo "Checking required geometry columns..."
geometry_columns=(
  "fragment:contour_geom:POLYGON"
  "fragment:bbox_geom:POLYGON"
  "annotation:geometry_geom:GEOMETRY"
  "layout_region:region_geom:POLYGON"
  "layout_region:bbox_geom:POLYGON"
  "reconstruction_candidate:estimated_canvas_geom:POLYGON"
  "reconstruction_candidate:estimated_fragment_geom:POLYGON"
)

for item in "${geometry_columns[@]}"; do
  IFS=":" read -r table column geom_type <<< "$item"
  check_count_at_least \
    "geometry column exists: $table.$column" \
    "SELECT count(*) FROM public.geometry_columns WHERE f_table_schema = 'public' AND f_table_name = '$table' AND f_geometry_column = '$column' AND srid = 0 AND type = '$geom_type';" \
    1
done

echo
echo "Checking rights/access columns..."
rights_tables=(image_asset msi_asset fragment export_bundle)
rights_columns=(rights_statement license attribution access_level)

for table in "${rights_tables[@]}"; do
  for column in "${rights_columns[@]}"; do
    check_count_at_least \
      "rights column exists: $table.$column" \
      "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '$table' AND column_name = '$column';" \
      1
  done
done

for table in image_asset msi_asset fragment; do
  for column in training_allowed publication_allowed demo_allowed; do
    check_count_at_least \
      "permission column exists: $table.$column" \
      "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '$table' AND column_name = '$column';" \
      1
  done
done

echo
echo "Checking important indexes..."
required_indexes=(
  idx_repository_name
  idx_manuscript_shelfmark
  idx_witness_external_source_identifier
  idx_iiif_manifest_cache_manifest_url
  idx_canvas_canvas_identifier
  idx_image_asset_source_url
  idx_image_asset_checksum_sha256
  idx_fragment_shelfmark
  idx_segmentation_run_model
  idx_layout_region_label
  idx_reconstruction_candidate_fragment_id
  idx_reconstruction_candidate_reconstruction_job_id
  idx_reconstruction_candidate_candidate_rank
  idx_retrieval_embedding_target
  idx_text_witness_link_external_source_identifier
  idx_fragment_contour_geom
  idx_layout_region_region_geom
  idx_reconstruction_candidate_estimated_canvas_geom
)

for index in "${required_indexes[@]}"; do
  check_true "index exists: $index" "SELECT to_regclass('public.$index') IS NOT NULL;"
done

echo
echo "Checking first-class reconstruction candidate support..."
check_true "reconstruction_candidate table exists" "SELECT to_regclass('public.reconstruction_candidate') IS NOT NULL;"
check_count_at_least \
  "reconstruction_candidate has score/uncertainty/provenance" \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'reconstruction_candidate' AND column_name IN ('score', 'uncertainty', 'provenance');" \
  3

echo
if [ "$failures" -eq 0 ]; then
  echo "Database validation passed."
  exit 0
fi

echo "Database validation failed with $failures issue(s)."
exit 1
