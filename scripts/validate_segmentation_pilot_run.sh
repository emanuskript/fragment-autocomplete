#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
from PIL import Image
import yaml

from src.evaluation.segmentation_masks import file_sha256, mask_pixel_area, validate_binary_mask

ROOT = Path.cwd()
path = ROOT / "data/metadata/segmentation_pilot_results.yaml"
if not path.exists():
    raise SystemExit("FAIL: segmentation_pilot_results.yaml is missing")
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
results = payload.get("results", [])
if len(results) != 10:
    raise SystemExit(f"FAIL: expected 10 pilot results, found {len(results)}")
expected = {
    "fp_01_clean_simple",
    "fp_02_clean_simple",
    "fp_03_complex_layout",
    "fp_04_complex_layout",
    "fp_05_iiif_rights",
    "fr_01_binding_strip",
    "fr_02_text_block",
    "fr_03_marginal_gloss",
    "fr_04_decoration_initial",
    "fr_05_damaged_irregular",
}
seen = set()
for result in results:
    sample_id = result["sample_id"]
    seen.add(sample_id)
    if sample_id not in expected:
        raise SystemExit(f"FAIL: unexpected non-pilot sample processed: {sample_id}")
    raw_path = ROOT / result["raw_output_path"]
    overlay_path = ROOT / result["overlay_path"]
    if not raw_path.exists():
        raise SystemExit(f"FAIL: raw output missing for {sample_id}: {result['raw_output_path']}")
    if not overlay_path.exists():
        raise SystemExit(f"FAIL: overlay missing for {sample_id}: {result['overlay_path']}")
    if result.get("status") not in {"success", "warning", "error"}:
        raise SystemExit(f"FAIL: invalid status for {sample_id}: {result.get('status')}")
    if result.get("sample_kind") == "full_page" and result.get("status") == "success":
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        height, width = raw["orig_shape"]
        detections = raw.get("detections", [])
        if result.get("mask_region_count") != len(detections) or not result.get("mask_geometry_available"):
            raise SystemExit(f"FAIL: full-page masks incomplete for {sample_id}")
        for detection in detections:
            mask_path = ROOT / detection["mask_path"]
            if not mask_path.exists():
                raise SystemExit(f"FAIL: missing region mask for {sample_id}: {mask_path}")
            with Image.open(mask_path) as mask:
                binary = mask.convert("L")
                validate_binary_mask(binary, (width, height))
                if mask_pixel_area(binary) != detection.get("mask_pixel_area"):
                    raise SystemExit(f"FAIL: mask area mismatch for {mask_path}")
            if file_sha256(mask_path) != detection.get("mask_sha256"):
                raise SystemExit(f"FAIL: mask checksum mismatch for {mask_path}")
missing = expected - seen
if missing:
    raise SystemExit(f"FAIL: missing expected pilot samples: {sorted(missing)}")
print("PASS: pilot segmentation results are present for all 10 samples")
PY
