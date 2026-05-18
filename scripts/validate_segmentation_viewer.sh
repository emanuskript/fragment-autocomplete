#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/validate_segmentation_viewer_data.py

for path in \
  scripts/view_segmentation_results.py \
  scripts/run_segmentation_viewer.sh \
  docs/10_minimal_segmentation_viewer.md
do
  if [ ! -f "$path" ]; then
    echo "FAIL: missing required viewer file: $path" >&2
    exit 1
  fi
done

python3 - <<'PY'
import importlib.util
import sys

for name in ("streamlit", "pandas"):
    if importlib.util.find_spec(name) is None:
        print(f"FAIL: missing Python dependency: {name}")
        sys.exit(1)
print("PASS: minimal segmentation viewer files and dependencies are present")
PY
