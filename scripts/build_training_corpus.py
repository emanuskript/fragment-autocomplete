#!/usr/bin/env python3
"""Build and optionally register a deterministic e-codices source corpus."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.training_corpus import (  # noqa: E402
  build_corpus,
  load_yaml,
  manual_page_decisions_for_corpus,
  manuscript_suitability_decisions_for_corpus,
  replacement_page_reviews_for_corpus,
  sha256_file,
  segmentation_input_manifest,
  write_yaml,
)


DEFAULT_SPEC = ROOT / "data/metadata/training_corpus_validation_spec.yaml"
DEFAULT_MANIFEST = ROOT / "data/metadata/training_corpus_validation_manifest.yaml"
DEFAULT_STATISTICS = ROOT / "data/metadata/training_corpus_validation_statistics.yaml"
DEFAULT_REPORT = ROOT / "docs/14_training_corpus_builder_report.md"
DEFAULT_SEGMENTATION_INPUTS = ROOT / "data/metadata/training_corpus_segmentation_inputs.yaml"
DEFAULT_SEGMENTATION_RESULTS = ROOT / "data/metadata/training_corpus_segmentation_results.yaml"
DEFAULT_SEGMENTATION_OUTPUTS = ROOT / "outputs/training_corpus_segmentation"
DEFAULT_MODEL_PATH = "model weights/best_emanuskript_segmentation.pt"


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build the provenance-preserving Training Corpus Builder v0.1 source corpus.")
  parser.add_argument("--spec", default=str(DEFAULT_SPEC))
  parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
  parser.add_argument("--statistics", default=str(DEFAULT_STATISTICS))
  parser.add_argument("--report", default=str(DEFAULT_REPORT))
  parser.add_argument("--limit-manuscripts", type=int)
  parser.add_argument("--max-pages", type=int)
  parser.add_argument("--timeout", type=int, default=120)
  parser.add_argument(
    "--manual-review",
    help="Versioned review YAML containing explicit page and manuscript suitability decisions.",
  )
  parser.add_argument("--dry-run", action="store_true", help="Harvest and select only; do not download or register.")
  parser.add_argument("--register", action="store_true", help="Register downloaded selected pages with the existing IIIF database model.")
  parser.add_argument("--prepare-segmentation", action="store_true", help="Prepare inputs for the existing eManuSkript workflow.")
  parser.add_argument("--run-segmentation", action="store_true", help="Invoke the existing eManuSkript runner after preparing inputs.")
  parser.add_argument("--segmentation-inputs", default=str(DEFAULT_SEGMENTATION_INPUTS))
  parser.add_argument("--segmentation-results", default=str(DEFAULT_SEGMENTATION_RESULTS))
  parser.add_argument("--segmentation-output-dir", default=str(DEFAULT_SEGMENTATION_OUTPUTS))
  parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
  parser.add_argument("--device", default="cpu")
  parser.add_argument("--conf", type=float, default=0.25)
  parser.add_argument("--imgsz", type=int, default=320)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args()


def resolved_path(value: str) -> Path:
  path = Path(value)
  return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
  try:
    return path.relative_to(ROOT).as_posix()
  except ValueError:
    return path.as_posix()


def main() -> int:
  args = parse_args()
  spec_path = resolved_path(args.spec)
  manifest_path = resolved_path(args.manifest)
  statistics_path = resolved_path(args.statistics)
  report_path = resolved_path(args.report)
  spec = load_yaml(spec_path)
  manual_page_decisions = None
  manuscript_suitability_decisions = None
  replacement_page_reviews = None
  manual_review_artifact = None
  if args.manual_review:
    review_path = resolved_path(args.manual_review)
    review = load_yaml(review_path)
    manual_page_decisions = manual_page_decisions_for_corpus(review, spec["corpus_id"])
    manuscript_suitability_decisions = manuscript_suitability_decisions_for_corpus(review, spec["corpus_id"])
    replacement_page_reviews = replacement_page_reviews_for_corpus(review, spec["corpus_id"])
    manual_review_artifact = {
      "path": review_path.resolve().relative_to(ROOT.resolve()).as_posix(),
      "sha256": sha256_file(review_path),
      "review_version": review.get("review_version"),
    }
  payload = build_corpus(
    spec,
    root=ROOT,
    specification_path=spec_path,
    output_manifest_path=manifest_path,
    statistics_yaml_path=statistics_path,
    statistics_report_path=report_path,
    limit_manuscripts=args.limit_manuscripts,
    max_pages_override=args.max_pages,
    dry_run=args.dry_run,
    register=args.register,
    timeout_seconds=args.timeout,
    manual_page_decisions=manual_page_decisions,
    manuscript_suitability_decisions=manuscript_suitability_decisions,
    replacement_page_reviews=replacement_page_reviews,
    manual_review_artifact=manual_review_artifact,
  )
  selected_count = payload["statistics"]["selected_page_count"]
  print(f"Built {payload['corpus_id']}: {len(payload['manuscripts'])} manuscripts, {selected_count} selected pages")
  print(f"Manifest: {display_path(manifest_path)}")
  print(f"Statistics: {display_path(statistics_path)}")
  print(f"Report: {display_path(report_path)}")

  if args.prepare_segmentation or args.run_segmentation:
    if args.dry_run or not args.register:
      raise ValueError("Segmentation preparation requires downloaded, registered source pages")
    segmentation_path = resolved_path(args.segmentation_inputs)
    segmentation_payload = segmentation_input_manifest(payload, args.model_path)
    write_yaml(segmentation_path, segmentation_payload)
    print(f"Segmentation inputs: {display_path(segmentation_path)}")

    if args.run_segmentation:
      command = [
        sys.executable,
        str(ROOT / "scripts/run_segmentation_pilot.py"),
        "--inputs",
        str(segmentation_path),
        "--results",
        str(resolved_path(args.segmentation_results)),
        "--output-dir",
        str(resolved_path(args.segmentation_output_dir)),
        "--device",
        args.device,
        "--conf",
        str(args.conf),
        "--imgsz",
        str(args.imgsz),
      ]
      if args.verbose:
        command.append("--verbose")
      subprocess.run(command, cwd=ROOT, check=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
