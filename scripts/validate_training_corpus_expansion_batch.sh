#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
SPEC="data/metadata/training_corpus_expansion_batch_01_spec.yaml"
MANIFEST="data/metadata/training_corpus_expansion_batch_01_manifest.yaml"
STATISTICS="data/metadata/training_corpus_expansion_batch_01_statistics.yaml"
REPORT="/tmp/training_corpus_expansion_batch_01_builder_report.md"

run_dry_build() {
  PYTHONPATH=. "$PYTHON_BIN" scripts/build_training_corpus.py \
    --spec "$SPEC" \
    --manifest "$MANIFEST" \
    --statistics "$STATISTICS" \
    --report "$REPORT" \
    --dry-run
}

PYTHONPATH=. "$PYTHON_BIN" -m pytest -q tests/ingestion/test_training_corpus.py
run_dry_build
FIRST_MANIFEST_SHA="$($PYTHON_BIN -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("data/metadata/training_corpus_expansion_batch_01_manifest.yaml").read_bytes()).hexdigest())')"
FIRST_STATISTICS_SHA="$($PYTHON_BIN -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("data/metadata/training_corpus_expansion_batch_01_statistics.yaml").read_bytes()).hexdigest())')"
run_dry_build
SECOND_MANIFEST_SHA="$($PYTHON_BIN -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("data/metadata/training_corpus_expansion_batch_01_manifest.yaml").read_bytes()).hexdigest())')"
SECOND_STATISTICS_SHA="$($PYTHON_BIN -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("data/metadata/training_corpus_expansion_batch_01_statistics.yaml").read_bytes()).hexdigest())')"

if [[ "$FIRST_MANIFEST_SHA" != "$SECOND_MANIFEST_SHA" || "$FIRST_STATISTICS_SHA" != "$SECOND_STATISTICS_SHA" ]]; then
  echo "FAIL: unchanged expansion dry runs were not byte-identical" >&2
  exit 1
fi

PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_expansion_batch.py
