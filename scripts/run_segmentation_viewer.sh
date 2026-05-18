#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! bash scripts/db_start.sh; then
  echo "Database could not be started automatically. Run 'bash scripts/db_start.sh' and try again." >&2
  exit 1
fi

exec python3 -m streamlit run scripts/view_segmentation_results.py
