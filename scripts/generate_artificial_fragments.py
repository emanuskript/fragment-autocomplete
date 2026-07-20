#!/usr/bin/env python3
"""Generate local artificial fragment tasks from registered complete pages."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.artificial_fragments import (  # noqa: E402
  GENERATION_VERSION,
  build_tasks,
  source_pages_from_resolved_dataset,
)


DEFAULT_RESOLVED = ROOT / "data/metadata/initial_sample_dataset_resolved.yaml"
DEFAULT_OUTPUT_DIR = Path("outputs/artificial_fragments")
DEFAULT_METADATA = ROOT / "data/metadata/artificial_fragment_generation_results.yaml"
DEFAULT_REPORT = ROOT / "docs/13_artificial_fragment_generator_report.md"


class NoAliasDumper(yaml.SafeDumper):
  """Write repeated metadata objects explicitly so manifests stay portable."""

  def ignore_aliases(self, data: Any) -> bool:
    return True


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Generate controlled artificial fragments from complete pages.")
  parser.add_argument("--resolved", default=DEFAULT_RESOLVED.as_posix())
  parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR.as_posix())
  parser.add_argument("--metadata", default=DEFAULT_METADATA.as_posix())
  parser.add_argument("--report", default=DEFAULT_REPORT.as_posix())
  parser.add_argument("--base-seed", type=int, default=20260720)
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args()


def now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
  if not path.exists():
    raise FileNotFoundError(f"Missing YAML file: {path}")
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"Expected YAML mapping in {path}")
  return data


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.dump(payload, Dumper=NoAliasDumper, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")


def build_report(payload: dict[str, Any]) -> str:
  rows = [
    "| Task | Source page | Mask family | Fragment | Mask |",
    "| --- | --- | --- | --- | --- |",
  ]
  for task in payload["tasks"]:
    rows.append(
      f"| `{task['task_id']}` | `{task['source_sample_id']}` | `{task['mask_family']}` | "
      f"`{task['fragment_path']}` | `{task['mask_path']}` |"
    )

  return "\n".join(
    [
      "# Fragment Autocomplete - Artificial Fragment Generator Report",
      "",
      "## Purpose",
      "",
      "Document the first reproducible local artificial-fragment generation pass for complete-page samples.",
      "",
      "## Scope",
      "",
      "This step generates controlled local crop/mask tasks for evaluation groundwork. It does not train a model, write to PostgreSQL, run reconstruction, infer missing manuscript content, or claim that generated fragments are historical evidence.",
      "",
      "## Summary",
      "",
      f"- Generation version: `{payload['generation_version']}`",
      f"- Dataset ID: `{payload['dataset_id']}`",
      f"- Source full pages: `{payload['source_full_page_count']}`",
      f"- Generated tasks: `{payload['generated_task_count']}`",
      f"- Output directory: `{payload['output_dir']}`",
      f"- Database write: `{str(payload['database_write']).lower()}`",
      "",
      "## Generated Tasks",
      "",
      *rows,
      "",
      "## Provenance and Ground Truth",
      "",
      "Each task records the source page, source database identifiers, source metadata, HSP-aligned normalized metadata when available, rights/access status, mask family, random seed, crop transform, and exact ground-truth placement on the source canvas. These records prepare for later insertion into `artificial_fragment_task`.",
      "",
      "## Known Limitations",
      "",
      "- Generated fragment PNGs and masks are local outputs and should not be committed.",
      "- The first pass uses simple rectangular and irregular crop masks only.",
      "- No degradation, reconstruction, retrieval, MSI, CoMMA workflow, or model training is implemented here.",
      "",
      "## Next Step",
      "",
      "Add PostgreSQL storage for `artificial_fragment_task` records after reviewing the local generation metadata.",
      "",
    ]
  )


def main() -> int:
  args = parse_args()
  resolved_path = Path(args.resolved)
  output_dir = Path(args.output_dir)
  metadata_path = Path(args.metadata)
  report_path = Path(args.report)

  resolved = load_yaml(resolved_path)
  dataset_id = resolved.get("dataset_id", "unknown_dataset")
  source_pages = source_pages_from_resolved_dataset(resolved)
  if len(source_pages) != 5:
    raise RuntimeError(f"Expected 5 registered full-page samples, found {len(source_pages)}")

  tasks = build_tasks(
    root=ROOT,
    dataset_id=dataset_id,
    source_pages=source_pages,
    output_dir=output_dir,
    base_seed=args.base_seed,
  )
  task_metadata = [task.to_metadata() for task in tasks]
  payload = {
    "generated_at": now_iso(),
    "generation_version": GENERATION_VERSION,
    "status": "generated",
    "dataset_id": dataset_id,
    "source_resolved_dataset": resolved_path.relative_to(ROOT).as_posix(),
    "source_full_page_count": len(source_pages),
    "generated_task_count": len(task_metadata),
    "mask_families": ["rectangular", "irregular"],
    "base_seed": args.base_seed,
    "output_dir": output_dir.as_posix(),
    "database_write": False,
    "tasks": task_metadata,
  }
  write_yaml(metadata_path, payload)
  write_text(report_path, build_report(payload))

  if args.verbose:
    print(f"Generated {len(task_metadata)} artificial fragment tasks")
    print(f"Metadata: {metadata_path.relative_to(ROOT)}")
    print(f"Report: {report_path.relative_to(ROOT)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
