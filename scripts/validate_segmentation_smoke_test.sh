#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_FILE="$ROOT_DIR/data/metadata/segmentation_smoke_test_results.yaml"
REPORT_FILE="$ROOT_DIR/docs/08_segmentation_smoke_test_report.md"
FAILURES=0

pass() {
  echo "  [PASS] $1"
}

fail() {
  echo "  [FAIL] $1"
  FAILURES=$((FAILURES + 1))
}

cd "$ROOT_DIR"

echo "Validating segmentation smoke test outputs..."
echo

if [ -f "$RESULTS_FILE" ]; then
  pass "results YAML exists"
else
  fail "results YAML exists"
fi

if [ -f "$REPORT_FILE" ]; then
  pass "smoke test report exists"
else
  fail "smoke test report exists"
fi

if python3 - <<'PY'
from pathlib import Path
import sys
import yaml

root = Path.cwd()
payload = yaml.safe_load((root / "data/metadata/segmentation_smoke_test_results.yaml").read_text(encoding="utf-8"))
errors = []

results = payload.get("results", [])
if len(results) != 2:
  errors.append(f"expected 2 results, found {len(results)}")

if payload.get("inference_run") is not True:
  errors.append("inference_run must be true")
if payload.get("segmentation_run") is not True:
  errors.append("segmentation_run must be true")

for result in results:
  raw_path = result.get("raw_output_path")
  overlay_path = result.get("overlay_path")
  if not raw_path or not (root / raw_path).exists():
    errors.append(f"missing raw output for {result.get('sample_id')}")
  if not overlay_path or not (root / overlay_path).exists():
    errors.append(f"missing overlay output for {result.get('sample_id')}")

if errors:
  for error in errors:
    print(error)
  sys.exit(1)
PY
then
  pass "results YAML content checks"
else
  fail "results YAML content checks"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "Segmentation smoke test validation passed."
  exit 0
fi

echo "Segmentation smoke test validation failed with $FAILURES issue(s)."
exit 1
