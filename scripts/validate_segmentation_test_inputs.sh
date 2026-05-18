#!/usr/bin/env bash

set -euo pipefail

export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="$ROOT_DIR/data/metadata/segmentation_test_inputs.yaml"
FAILURES=0

pass() {
  echo "  [PASS] $1"
}

fail() {
  echo "  [FAIL] $1"
  FAILURES=$((FAILURES + 1))
}

cd "$ROOT_DIR"

echo "Validating controlled segmentation test inputs..."
echo

if bash scripts/db_start.sh >/dev/null; then
  pass "database reachable"
else
  fail "database reachable"
fi

if python3 scripts/prepare_segmentation_test_inputs.py --verbose >/dev/null; then
  pass "segmentation test input preparation"
else
  fail "segmentation test input preparation"
fi

if [ -f "$OUTPUT_FILE" ]; then
  pass "segmentation_test_inputs.yaml exists"
else
  fail "segmentation_test_inputs.yaml exists"
fi

if python3 - <<'PY'
from pathlib import Path
import sys
import yaml

root = Path.cwd()
payload = yaml.safe_load((root / "data/metadata/segmentation_test_inputs.yaml").read_text(encoding="utf-8"))
errors = []

inputs = payload.get("selected_inputs", [])
if len(inputs) != 2:
  errors.append(f"expected 2 selected inputs, found {len(inputs)}")

kinds = sorted(item.get("sample_kind") for item in inputs)
if kinds != ["fragment", "full_page"]:
  errors.append(f"expected one fragment and one full_page, found {kinds}")

for item in inputs:
  local_path = item.get("local_path")
  if not local_path or not (root / local_path).exists():
    errors.append(f"missing local file for {item.get('sample_id')}")
  if not item.get("db_image_asset_id"):
    errors.append(f"missing image_asset id for {item.get('sample_id')}")
  if item.get("sample_kind") == "full_page" and not item.get("db_canvas_id"):
    errors.append(f"missing canvas id for {item.get('sample_id')}")
  if item.get("sample_kind") == "fragment" and not item.get("db_fragment_id"):
    errors.append(f"missing fragment id for {item.get('sample_id')}")

model_path = payload.get("model_path")
if not model_path or not (root / model_path).exists():
  errors.append("recommended model path is missing")

if payload.get("inference_run") is not False:
  errors.append("inference_run must be false")
if payload.get("segmentation_run") is not False:
  errors.append("segmentation_run must be false")

if errors:
  for error in errors:
    print(error)
  sys.exit(1)
PY
then
  pass "YAML content checks"
else
  fail "YAML content checks"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "Controlled segmentation test input validation passed."
  exit 0
fi

echo "Controlled segmentation test input validation failed with $FAILURES issue(s)."
exit 1
