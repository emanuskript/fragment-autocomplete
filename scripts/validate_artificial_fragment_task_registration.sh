#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'PY'
from pathlib import Path

from psycopg.rows import dict_row

from src.evaluation.artificial_fragment_registration import (
  EXPECTED_CORE_TASKS,
  EXPECTED_SANITY_TASKS,
  REGISTRATION_VERSION,
  load_registration_records,
)
from src.ingestion.db import connect


ROOT = Path.cwd()
manifest_path = ROOT / "data/metadata/artificial_fragment_generation_results.yaml"
results_path = ROOT / "data/metadata/artificial_fragment_task_registration_results.yaml"
if not results_path.is_file():
  raise SystemExit("FAIL: artificial-fragment task registration results are missing")

# Loading the records revalidates every source, artifact path, checksum, and declared dimension.
records = load_registration_records(manifest_path, ROOT)
expected_count = EXPECTED_CORE_TASKS + EXPECTED_SANITY_TASKS
if len(records) != expected_count:
  raise SystemExit(f"FAIL: expected {expected_count} validated records, found {len(records)}")

json_fields = {"crop_transform", "degradation_profile", "ground_truth_placement", "parameters"}
with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
  cur.execute("SELECT COUNT(*) AS count FROM artificial_fragment_task")
  total_count = cur.fetchone()["count"]
  if total_count != expected_count:
    raise SystemExit(f"FAIL: expected {expected_count} total artificial_fragment_task rows, found {total_count}")

  cur.execute(
    """
    SELECT COUNT(*) AS count,
           COUNT(DISTINCT parameters->'task_identity'->>'sha256') AS identity_count
    FROM artificial_fragment_task
    WHERE parameters->>'registration_version' = %s
    """,
    (REGISTRATION_VERSION,),
  )
  counts = cur.fetchone()
  if counts["count"] != expected_count or counts["identity_count"] != expected_count:
    raise SystemExit(
      f"FAIL: expected {expected_count} unique task identities; "
      f"rows={counts['count']}, identities={counts['identity_count']}"
    )

  cur.execute(
    """
    SELECT COUNT(*) AS count
    FROM artificial_fragment_task task
    JOIN image_asset asset ON asset.id = task.source_image_asset_id
    JOIN canvas source_canvas ON source_canvas.id = task.source_canvas_id
    WHERE asset.canvas_id = source_canvas.id
      AND task.parameters->>'registration_version' = %s
    """,
    (REGISTRATION_VERSION,),
  )
  relationship_count = cur.fetchone()["count"]
  if relationship_count != expected_count:
    raise SystemExit(
      f"FAIL: source relationships resolve for {relationship_count}/{expected_count} tasks"
    )

  cur.execute(
    """
    SELECT COUNT(*) AS count
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'artificial_fragment_task'
      AND data_type = 'bytea'
    """
  )
  if cur.fetchone()["count"]:
    raise SystemExit("FAIL: artificial_fragment_task unexpectedly contains a binary column")

  core_mask_count = 0
  for record in records:
    cur.execute(
      """
      SELECT id::text AS id,
             source_canvas_id::text AS source_canvas_id,
             source_image_asset_id::text AS source_image_asset_id,
             generated_fragment_image_asset_id::text AS generated_fragment_image_asset_id,
             mask_path,
             mask_family,
             random_seed,
             crop_transform,
             degradation_profile,
             ground_truth_placement,
             split_name,
             generation_version,
             parameters
      FROM artificial_fragment_task
      WHERE id = %s
      """,
      (record.database_id,),
    )
    stored = cur.fetchone()
    if not stored:
      raise SystemExit(f"FAIL: database task is missing: {record.task_id}")
    expected = record.database_values()
    for name, expected_value in expected.items():
      stored_value = stored.get(name)
      if name in json_fields:
        matches = stored_value == expected_value
      else:
        matches = stored_value == expected_value
      if not matches:
        raise SystemExit(f"FAIL: stored field differs for {record.task_id}: {name}")
    if stored["generated_fragment_image_asset_id"] is not None:
      raise SystemExit(f"FAIL: generated binary image_asset was stored for {record.task_id}")
    parameters = stored["parameters"]
    if parameters.get("binary_data_stored_in_postgresql") is not False:
      raise SystemExit(f"FAIL: binary-storage declaration is invalid for {record.task_id}")
    if record.task_group == "core_pilot":
      if parameters.get("layout_geometry_method") != "segmentation_mask":
        raise SystemExit(f"FAIL: core task lacks segmentation_mask survival data: {record.task_id}")
      core_mask_count += 1

if core_mask_count != EXPECTED_CORE_TASKS:
  raise SystemExit(
    f"FAIL: expected {EXPECTED_CORE_TASKS} core segmentation_mask tasks, found {core_mask_count}"
  )

print(
  "PASS: 23 deterministic artificial-fragment tasks, source relationships, "
  "local artifact checksums, and segmentation-mask survival metadata are valid"
)
PY
