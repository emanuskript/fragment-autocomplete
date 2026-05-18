#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from pathlib import Path
import yaml

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
missing = expected - seen
if missing:
    raise SystemExit(f"FAIL: missing expected pilot samples: {sorted(missing)}")
print("PASS: pilot segmentation results are present for all 10 samples")
PY
