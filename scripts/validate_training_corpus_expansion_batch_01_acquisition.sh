#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SPEC="data/metadata/training_corpus_expansion_batch_01_spec.yaml"
MANIFEST="data/metadata/training_corpus_expansion_batch_01_manifest.yaml"
STATISTICS="data/metadata/training_corpus_expansion_batch_01_statistics.yaml"
REVIEW="data/metadata/training_corpus_expansion_readiness_review.yaml"
REPORT="/tmp/training_corpus_expansion_batch_01_acquisition_builder_report.md"
STATE_FILE="$(mktemp /tmp/training_corpus_expansion_batch_01_acquisition.XXXXXX.json)"
trap 'rm -f "$STATE_FILE"' EXIT

build_batch() {
  "$PYTHON_BIN" scripts/build_training_corpus.py \
    --spec "$SPEC" \
    --manifest "$MANIFEST" \
    --statistics "$STATISTICS" \
    --report "$REPORT" \
    --manual-review "$REVIEW" \
    "$@"
}

validate_phase() {
  PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_expansion_batch_01_acquisition.py \
    --phase "$1" \
    --state "$STATE_FILE"
}

# The existing builder remains the sole acquisition and registration path.
PYTHON_BIN="$PYTHON_BIN" bash scripts/validate_training_corpus_expansion_batch.sh
validate_phase capture-preflight

build_batch
validate_phase capture-initial

build_batch --register
validate_phase capture-registration

build_batch --register
validate_phase validate-rerun
