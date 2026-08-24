#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

PYTHONPATH=. "$PYTHON_BIN" -m pytest \
  tests/ingestion/test_iiif_normalizer.py \
  tests/ingestion/test_training_corpus.py

"$PYTHON_BIN" - <<'PY'
from pathlib import Path

import yaml
from psycopg.rows import dict_row

from src.ingestion.db import connect
from src.ingestion.training_corpus import sha256_file


ROOT = Path.cwd()
manifest_path = ROOT / "data/metadata/training_corpus_validation_manifest.yaml"
statistics_path = ROOT / "data/metadata/training_corpus_validation_statistics.yaml"
report_path = ROOT / "docs/14_training_corpus_builder_report.md"
segmentation_inputs_path = ROOT / "data/metadata/training_corpus_segmentation_inputs.yaml"
for path in (manifest_path, statistics_path, report_path, segmentation_inputs_path):
  if not path.is_file():
    raise SystemExit(f"FAIL: required validation artifact is missing: {path.relative_to(ROOT)}")

manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
statistics = yaml.safe_load(statistics_path.read_text(encoding="utf-8"))
segmentation_inputs = yaml.safe_load(segmentation_inputs_path.read_text(encoding="utf-8"))
manuscripts = manifest.get("manuscripts", [])
if len(manuscripts) != 5:
  raise SystemExit(f"FAIL: expected 5 validation manuscripts, found {len(manuscripts)}")
if manifest.get("status") != "downloaded_and_registered":
  raise SystemExit(f"FAIL: corpus registration status is {manifest.get('status')!r}")

manifest_urls: set[str] = set()
canvas_ids: set[str] = set()
selected_count = 0
split_by_manuscript: dict[str, str] = {}
with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
  for manuscript in manuscripts:
    manuscript_id = manuscript["id"]
    split_name = manuscript["split"]
    split_by_manuscript[manuscript_id] = split_name
    if manuscript["manifest_url"] in manifest_urls:
      raise SystemExit(f"FAIL: duplicate manuscript manifest: {manuscript['manifest_url']}")
    manifest_urls.add(manuscript["manifest_url"])
    selected = [page for page in manuscript["pages"] if page["selection_status"] == "selected"]
    if not 1 <= len(selected) <= 3:
      raise SystemExit(f"FAIL: {manuscript_id} selected page count is {len(selected)}")
    for page in manuscript["pages"]:
      if not page.get("selection_reasons"):
        raise SystemExit(f"FAIL: page decision lacks reasons: {page['canvas_identifier']}")
      if page["canvas_identifier"] in canvas_ids:
        raise SystemExit(f"FAIL: duplicate page/canvas: {page['canvas_identifier']}")
      canvas_ids.add(page["canvas_identifier"])
    for page in selected:
      selected_count += 1
      image = page["image"]
      if image.get("training_allowed") is not False:
        raise SystemExit(f"FAIL: training permission was enabled: {page['canvas_identifier']}")
      if image.get("rights_review_status") != "pending_review":
        raise SystemExit(f"FAIL: rights review status changed: {page['canvas_identifier']}")
      local_path = ROOT / image["local_path"]
      if not local_path.is_file():
        raise SystemExit(f"FAIL: downloaded page is missing: {image['local_path']}")
      if sha256_file(local_path) != image["checksum_sha256"]:
        raise SystemExit(f"FAIL: checksum mismatch: {image['local_path']}")
      db_ids = page.get("registration", {}).get("db_ids", {})
      cur.execute(
        """
        SELECT asset.checksum_sha256,
               asset.local_path,
               asset.training_allowed,
               asset.rights_review_status,
               canvas.manuscript_id::text AS manuscript_id
        FROM image_asset asset
        JOIN canvas ON canvas.id = asset.canvas_id
        WHERE asset.id = %s AND canvas.id = %s
        """,
        (db_ids.get("image_asset_id"), db_ids.get("canvas_id")),
      )
      stored = cur.fetchone()
      if stored is None:
        raise SystemExit(f"FAIL: registered database page is missing: {page['canvas_identifier']}")
      if stored["checksum_sha256"] != image["checksum_sha256"] or stored["local_path"] != image["local_path"]:
        raise SystemExit(f"FAIL: database source provenance differs: {page['canvas_identifier']}")
      if stored["training_allowed"] is not False or stored["rights_review_status"] != "pending_review":
        raise SystemExit(f"FAIL: database rights state differs: {page['canvas_identifier']}")

if selected_count != 15:
  raise SystemExit(f"FAIL: expected 15 selected validation pages, found {selected_count}")
if statistics.get("manuscript_count") != 5 or statistics.get("selected_page_count") != 15:
  raise SystemExit("FAIL: statistics counts do not match the validation corpus")
if statistics.get("training_allowed_true_count") != 0:
  raise SystemExit("FAIL: statistics report an explicitly training-allowed source")
if sum(statistics["split_counts"]["manuscripts"].values()) != 5:
  raise SystemExit("FAIL: manuscript split counts do not cover the validation corpus")
if sum(statistics["split_counts"]["pages"].values()) != 15:
  raise SystemExit("FAIL: page split counts do not cover the validation corpus")
prepared_inputs = segmentation_inputs.get("selected_inputs", [])
if len(prepared_inputs) != 15:
  raise SystemExit(f"FAIL: expected 15 prepared eManuSkript inputs, found {len(prepared_inputs)}")
if segmentation_inputs.get("segmentation_run") is not False or segmentation_inputs.get("inference_run") is not False:
  raise SystemExit("FAIL: optional eManuSkript inputs incorrectly claim that inference ran")
for item in prepared_inputs:
  if not item.get("db_image_asset_id") or not item.get("db_canvas_id"):
    raise SystemExit(f"FAIL: prepared eManuSkript input lacks database provenance: {item.get('sample_id')}")
  if split_by_manuscript.get(item.get("manuscript_id")) != item.get("dataset_split"):
    raise SystemExit(f"FAIL: prepared eManuSkript split differs from its manuscript: {item.get('sample_id')}")

print(
  "PASS: 5 manuscripts and 15 selected complete pages are deterministic, checksummed, "
  "manuscript-split-isolated, conservatively rights-gated, and registered through the existing IIIF schema"
)
PY
