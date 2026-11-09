#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
PORT="${FRAGMENT_WORKBENCH_PORT:-8503}"

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  npm --prefix "$WEB_DIR" install
fi

exec npm --prefix "$WEB_DIR" run dev -- --hostname 127.0.0.1 --port "$PORT"
