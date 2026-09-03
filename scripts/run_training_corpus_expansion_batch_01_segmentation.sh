#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SPEC="data/metadata/training_corpus_expansion_batch_01_segmentation_spec.yaml"
INPUTS="data/metadata/training_corpus_expansion_batch_01_segmentation_inputs.yaml"
RESULTS="data/metadata/training_corpus_expansion_batch_01_segmentation_results.yaml"
STORAGE="data/metadata/training_corpus_expansion_batch_01_segmentation_storage_results.yaml"
OUTPUT_DIR="outputs/training_corpus_segmentation/batch_01"

PYTHONPATH=. "$PYTHON_BIN" scripts/prepare_training_corpus_segmentation_inputs.py --spec "$SPEC"

PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_expansion_batch_01_segmentation.py \
  --spec "$SPEC" \
  --capture-source-snapshot

PYTHONPATH=. "$PYTHON_BIN" scripts/run_segmentation_pilot.py \
  --inputs "$INPUTS" \
  --results "$RESULTS" \
  --output-dir "$OUTPUT_DIR" \
  --device cpu \
  --conf 0.25 \
  --imgsz 320 \
  --verbose

PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_expansion_batch_01_segmentation.py \
  --spec "$SPEC" \
  --capture-mask-snapshot

# The unchanged rerun must resolve every successful page from verified local artifacts
# before model loading and must preserve raw, overlay, mask, and result-manifest bytes/mtimes.
PYTHONPATH=. "$PYTHON_BIN" scripts/run_segmentation_pilot.py \
  --inputs "$INPUTS" \
  --results "$RESULTS" \
  --output-dir "$OUTPUT_DIR" \
  --device cpu \
  --conf 0.25 \
  --imgsz 320

PYTHONPATH=. "$PYTHON_BIN" scripts/store_segmentation_pilot_outputs.py \
  --results "$RESULTS" \
  --inputs "$INPUTS" \
  --output "$STORAGE" \
  --report "$OUTPUT_DIR/storage_report.md" \
  --verbose

# The validator performs one more unchanged storage reconciliation and requires exact
# segmentation_run/layout_region row IDs, content, and timestamps to remain stable.
PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_expansion_batch_01_segmentation.py \
  --spec "$SPEC"
