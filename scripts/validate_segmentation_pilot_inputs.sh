#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from pathlib import Path
import yaml

ROOT = Path.cwd()
path = ROOT / "data/metadata/segmentation_pilot_inputs.yaml"
if not path.exists():
    raise SystemExit("FAIL: segmentation_pilot_inputs.yaml is missing")
payload = yaml.safe_load(path.read_text(encoding="utf-8"))
items = payload.get("selected_inputs", [])
if len(items) != 10:
    raise SystemExit(f"FAIL: expected 10 pilot inputs, found {len(items)}")
full_pages = [item for item in items if item.get("sample_kind") == "full_page"]
fragments = [item for item in items if item.get("sample_kind") == "fragment"]
if len(full_pages) != 5:
    raise SystemExit(f"FAIL: expected 5 full-page inputs, found {len(full_pages)}")
if len(fragments) != 5:
    raise SystemExit(f"FAIL: expected 5 fragment inputs, found {len(fragments)}")
model_path = ROOT / payload["model_path"]
if not model_path.exists():
    raise SystemExit(f"FAIL: model path missing: {payload['model_path']}")
for item in items:
    local_path = ROOT / item["local_path"]
    if not local_path.exists():
        raise SystemExit(f"FAIL: local image missing for {item['sample_id']}: {item['local_path']}")
    if not item.get("db_image_asset_id"):
        raise SystemExit(f"FAIL: missing db_image_asset_id for {item['sample_id']}")
    if item["sample_kind"] == "full_page" and not item.get("db_canvas_id"):
        raise SystemExit(f"FAIL: missing db_canvas_id for {item['sample_id']}")
    if item["sample_kind"] == "fragment" and not item.get("db_fragment_id"):
        raise SystemExit(f"FAIL: missing db_fragment_id for {item['sample_id']}")
print("PASS: pilot segmentation inputs are ready")
PY
