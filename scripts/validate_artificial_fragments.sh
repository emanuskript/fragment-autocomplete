#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from pathlib import Path
import yaml

ROOT = Path.cwd()
metadata_path = ROOT / "data/metadata/artificial_fragment_generation_results.yaml"
report_path = ROOT / "docs/13_artificial_fragment_generator_report.md"

if not metadata_path.exists():
  raise SystemExit("FAIL: artificial fragment metadata is missing")
if not report_path.exists():
  raise SystemExit("FAIL: artificial fragment report is missing")

payload = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
tasks = payload.get("tasks", [])
if payload.get("generated_task_count") != 10 or len(tasks) != 10:
  raise SystemExit(f"FAIL: expected 10 generated tasks, found {len(tasks)}")
if payload.get("database_write") is not False:
  raise SystemExit("FAIL: generator should not write to the database in this milestone")

families_by_source: dict[str, set[str]] = {}
for task in tasks:
  source_id = task.get("source_sample_id")
  families_by_source.setdefault(source_id, set()).add(task.get("mask_family"))
  for key in ("fragment_path", "mask_path"):
    path = ROOT / task[key]
    if not path.exists():
      raise SystemExit(f"FAIL: generated file missing: {task[key]}")
  placement = task.get("ground_truth_placement", {})
  bbox = placement.get("bbox_xyxy_px")
  if not bbox or len(bbox) != 4:
    raise SystemExit(f"FAIL: missing ground-truth bbox for {task.get('task_id')}")
  if not placement.get("placement_is_known"):
    raise SystemExit(f"FAIL: placement is not marked as known for {task.get('task_id')}")
  if not task.get("source_db_ids", {}).get("image_asset_id"):
    raise SystemExit(f"FAIL: missing inherited source image_asset_id for {task.get('task_id')}")
  if "hsp_normalized_metadata" not in task:
    raise SystemExit(f"FAIL: missing HSP metadata inheritance field for {task.get('task_id')}")
  if not isinstance(task.get("source_metadata"), dict):
    raise SystemExit(f"FAIL: missing source metadata for {task.get('task_id')}")

for source_id, families in families_by_source.items():
  if families != {"rectangular", "irregular"}:
    raise SystemExit(f"FAIL: source {source_id} has mask families {sorted(families)}")

print("PASS: artificial fragment outputs and metadata are valid")
PY
