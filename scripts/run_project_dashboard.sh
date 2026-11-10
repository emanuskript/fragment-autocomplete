#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
PORT="${FRAGMENT_WORKBENCH_PORT:-8503}"
PYTHON_BIN="${FRAGMENT_WORKBENCH_PYTHON:-$ROOT_DIR/.venv/bin/python}"
PROTOTYPE_MANIFEST="$ROOT_DIR/outputs/synthetic_data/damage_review_prototype_v2/prototype.json"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

if [[ -f "$PROTOTYPE_MANIFEST" ]]; then
  "$PYTHON_BIN" "$ROOT_DIR/scripts/build_damage_review_prototype.py" --validate-only
else
  "$PYTHON_BIN" "$ROOT_DIR/scripts/build_damage_review_prototype.py"
fi

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  npm --prefix "$WEB_DIR" install
fi

exec npm --prefix "$WEB_DIR" run dev -- --hostname 127.0.0.1 --port "$PORT"
