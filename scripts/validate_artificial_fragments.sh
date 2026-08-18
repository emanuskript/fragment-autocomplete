#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m pytest -q tests/evaluation/test_artificial_fragments.py

"$PYTHON_BIN" - <<'PY'
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image, ImageChops
import yaml

ROOT = Path.cwd()
manifest_path = ROOT / "data/metadata/artificial_fragment_generation_results.yaml"
payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

if payload.get("generation_version") != "artificial_fragment_generator_v0_1_1":
  raise SystemExit("FAIL: unexpected generation version")
if payload.get("run_mode") != "pilot":
  raise SystemExit("FAIL: committed manifest is not the pilot run")
if payload.get("database_write") is not False:
  raise SystemExit("FAIL: generator must not write to the database")

core = payload.get("core_pilot_tasks", [])
sanity = payload.get("transformation_sanity_tasks", [])
if len(core) != 20 or payload.get("core_pilot_task_count") != 20:
  raise SystemExit(f"FAIL: expected 20 core tasks, found {len(core)}")
if len(sanity) != 3 or payload.get("transformation_sanity_task_count") != 3:
  raise SystemExit(f"FAIL: expected 3 transformation sanity tasks, found {len(sanity)}")

expected_fields = {
  "source_region_index", "source_region_identifier", "label", "class_id", "confidence",
  "original_bbox_xyxy", "original_rasterized_area_px", "surviving_area_px",
  "surviving_fraction", "completely_lost", "geometry_method", "segmentation_run_provenance",
  "mask_path", "mask_pixel_area", "mask_dimensions_px",
}
groups = {}
seeds = set()

def file_sha(path: Path) -> str:
  digest = sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()

for index_task in core + sanity:
  metadata_artifact = index_task["artifacts"]["metadata"]
  metadata_path = ROOT / metadata_artifact["path"]
  if file_sha(metadata_path) != metadata_artifact["sha256"]:
    raise SystemExit(f"FAIL: per-task metadata checksum mismatch for {index_task['task_id']}")
  task = json.loads(metadata_path.read_text(encoding="utf-8"))
  task["artifacts"]["metadata"] = metadata_artifact
  if task["random_seed"] in seeds:
    raise SystemExit(f"FAIL: duplicate recorded seed {task['random_seed']}")
  seeds.add(task["random_seed"])
  source_path = ROOT / task["source_path"]
  if file_sha(source_path) != task["source_sha256"] or not task.get("source_integrity_verified"):
    raise SystemExit(f"FAIL: source integrity mismatch for {task['task_id']}")
  if abs(task["requested_severity"] - task["measured_severity"]) > 0.02:
    raise SystemExit(f"FAIL: severity outside tolerance for {task['task_id']}")
  if abs((1.0 - task["measured_severity"]) - task["surviving_fraction"]) > 1e-8:
    raise SystemExit(f"FAIL: survival statistics inconsistent for {task['task_id']}")
  if task["degradation_profile"].get("contains_inferred_or_reconstructed_content") is not False:
    raise SystemExit(f"FAIL: inferred content flag invalid for {task['task_id']}")

  artifacts = task["artifacts"]
  for name, artifact in artifacts.items():
    path = ROOT / artifact["path"]
    if not path.exists():
      raise SystemExit(f"FAIL: missing {name}: {path}")
    if file_sha(path) != artifact["sha256"]:
      raise SystemExit(f"FAIL: checksum mismatch for {path}")

  survival_path = ROOT / artifacts["source_survival_mask"]["path"]
  damage_path = ROOT / artifacts["source_damage_mask"]["path"]
  observed_mask_path = ROOT / artifacts["observed_fragment_survival_mask"]["path"]
  with Image.open(survival_path) as survival, Image.open(damage_path) as damage, Image.open(observed_mask_path) as observed_mask:
    if survival.size != tuple(task["original_image_dimensions_px"]) or damage.size != survival.size:
      raise SystemExit(f"FAIL: source mask dimensions invalid for {task['task_id']}")
    if observed_mask.size != tuple(task["generated_fragment_dimensions_px"]):
      raise SystemExit(f"FAIL: observed mask dimensions invalid for {task['task_id']}")
    for mask in (survival, damage, observed_mask):
      colors = mask.getcolors(maxcolors=3)
      if colors is None or {value for _, value in colors} - {0, 255}:
        raise SystemExit(f"FAIL: non-binary mask for {task['task_id']}")
    if ImageChops.add(survival, damage).getextrema() != (255, 255):
      raise SystemExit(f"FAIL: damage and survival masks are not complements for {task['task_id']}")

  placement = task["ground_truth_placement"]
  width, height = task["original_image_dimensions_px"]
  x1, y1, x2, y2 = placement["source_bbox_xyxy_px"]
  if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
    raise SystemExit(f"FAIL: source placement outside page for {task['task_id']}")

  estimate = task["layout_survival_estimate"]
  if estimate.get("geometry_method") != "segmentation_mask":
    raise SystemExit(f"FAIL: layout geometry method missing for {task['task_id']}")
  regions = estimate.get("regions", [])
  summary = estimate.get("summary", {})
  if len(regions) != summary.get("total_regions"):
    raise SystemExit(f"FAIL: region summary count mismatch for {task['task_id']}")
  classified = sum(summary.get(key, 0) for key in ("completely_visible_count", "partially_visible_count", "completely_lost_count"))
  if classified != len(regions):
    raise SystemExit(f"FAIL: region visibility classes incomplete for {task['task_id']}")
  for region in regions:
    if not expected_fields.issubset(region):
      raise SystemExit(f"FAIL: incomplete region metadata for {task['task_id']}")
    if region.get("geometry_method") != "segmentation_mask":
      raise SystemExit(f"FAIL: incorrect region geometry method for {task['task_id']}")

for index_task in core:
  task = json.loads((ROOT / index_task["artifacts"]["metadata"]["path"]).read_text(encoding="utf-8"))
  if task["rotation_degrees"] != 0.0 or task["scale"] != 1.0:
    raise SystemExit(f"FAIL: core pilot transform is not neutral for {task['task_id']}")
  key = (task["source_sample_id"], task["mask_family"], task["requested_severity"])
  groups[key] = groups.get(key, 0) + 1

if len(groups) != 20 or any(count != 1 for count in groups.values()):
  raise SystemExit("FAIL: core pilot is not 5 pages x 2 masks x 2 severities")
sanity_metadata = [json.loads((ROOT / task["artifacts"]["metadata"]["path"]).read_text(encoding="utf-8")) for task in sanity]
if {task["rotation_degrees"] for task in sanity_metadata} != {12.0, -9.0, 0.0}:
  raise SystemExit("FAIL: transformation sanity rotations are incomplete")
if not any(task["scale"] != 1.0 for task in sanity_metadata):
  raise SystemExit("FAIL: transformation sanity scale case is missing")

print("PASS: artificial-fragment v0.1.1 unit tests and pilot artifacts are valid")
PY
