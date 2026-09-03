#!/usr/bin/env python3
"""Prepare a registered corpus for the existing eManuSkript segmentation runner."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.ingestion.training_corpus import segmentation_input_manifest  # noqa: E402


DEFAULT_SPEC = ROOT / "data/metadata/training_corpus_expansion_batch_01_segmentation_spec.yaml"


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Prepare selected registered corpus pages for the existing segmentation workflow."
  )
  parser.add_argument("--spec", default=str(DEFAULT_SPEC))
  return parser.parse_args()


def resolve(path: str | Path) -> Path:
  candidate = Path(path)
  return candidate if candidate.is_absolute() else ROOT / candidate


def load_yaml(path: Path) -> dict[str, Any]:
  payload = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"Expected a YAML mapping: {path}")
  return payload


def file_sha256(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def prepare(spec_path: Path) -> dict[str, Any]:
  spec = load_yaml(spec_path)
  corpus_path = resolve(spec["source"]["corpus_manifest"])
  output_path = resolve(spec["artifacts"]["inputs"])
  corpus = load_yaml(corpus_path)
  if corpus.get("corpus_id") != spec.get("corpus_id"):
    raise ValueError("Segmentation specification and corpus manifest IDs differ")
  if corpus.get("status") != "downloaded_and_registered":
    raise ValueError("Corpus manifest is not downloaded and registered")

  payload = segmentation_input_manifest(corpus, spec["model"]["path"])
  payload.update({
    "status": "prepared_for_inference",
    "segmentation_specification": {
      "path": spec_path.relative_to(ROOT).as_posix(),
      "sha256": file_sha256(spec_path),
      "version": spec.get("specification_version"),
    },
    "source_corpus_manifest": {
      "path": corpus_path.relative_to(ROOT).as_posix(),
      "sha256": file_sha256(corpus_path),
    },
    "expected_page_count": spec["expected"]["total_pages"],
    "expected_page_split_counts": spec["expected"]["page_split_counts"],
  })
  selected = payload.get("selected_inputs", [])
  expected = int(spec["expected"]["total_pages"])
  if len(selected) != expected:
    raise ValueError(f"Expected exactly {expected} selected inputs, found {len(selected)}")
  if any(not item.get("db_image_asset_id") or not item.get("db_canvas_id") for item in selected):
    raise ValueError("Every segmentation input must have registered image_asset and canvas IDs")
  if any(item.get("training_allowed") is not False for item in selected):
    raise ValueError("Segmentation preparation cannot include a training-approved Batch 01 page")

  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(
    yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
    encoding="utf-8",
  )
  return payload


def main() -> int:
  args = parse_args()
  spec_path = resolve(args.spec)
  payload = prepare(spec_path)
  print(
    f"Prepared {len(payload['selected_inputs'])} pages for existing eManuSkript runner: "
    f"{payload['dataset_id']}"
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
