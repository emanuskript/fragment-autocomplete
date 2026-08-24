#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUTS="data/metadata/training_corpus_segmentation_inputs.yaml"
RESULTS="data/metadata/training_corpus_segmentation_results.yaml"
STORAGE="data/metadata/training_corpus_segmentation_storage_results.yaml"
OUTPUT_DIR="outputs/training_corpus_segmentation"

PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_segmentation.py --capture-source-snapshot

PYTHONPATH=. "$PYTHON_BIN" scripts/run_segmentation_pilot.py \
  --inputs "$INPUTS" \
  --results "$RESULTS" \
  --output-dir "$OUTPUT_DIR" \
  --device cpu \
  --conf 0.25 \
  --imgsz 320 \
  --verbose

PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_segmentation.py --capture-mask-snapshot

# An unchanged rerun must reuse only artifacts whose corpus/model/config identity and hashes match.
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

# The validator reruns the same existing storage command and proves stable run IDs/region sets.
PYTHONPATH=. "$PYTHON_BIN" scripts/validate_training_corpus_segmentation.py
