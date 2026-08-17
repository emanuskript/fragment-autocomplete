#!/usr/bin/env python3
"""Generate deterministic artificial fragments from registered complete pages."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.artificial_fragments import (  # noqa: E402
  ArtifactPaths,
  GENERATION_VERSION,
  GenerationConfig,
  MASK_FAMILIES,
  SourcePage,
  generate_fragment_task,
  source_pages_from_resolved_dataset,
  stable_seed,
)


DEFAULT_RESOLVED = ROOT / "data/metadata/initial_sample_dataset_resolved.yaml"
DEFAULT_SEGMENTATION_RESULTS = ROOT / "data/metadata/segmentation_pilot_results.yaml"
DEFAULT_SEGMENTATION_STORAGE = ROOT / "data/metadata/segmentation_pilot_storage_results.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "outputs/artificial_fragments/v0_1_1"
DEFAULT_METADATA = ROOT / "data/metadata/artificial_fragment_generation_results.yaml"
CORE_SEVERITIES = (0.30, 0.60)


class NoAliasDumper(yaml.SafeDumper):
  """Write repeated metadata explicitly so manifests remain self-contained."""

  def ignore_aliases(self, data: Any) -> bool:
    return True


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Generate controlled artificial fragments from complete pages.")
  parser.add_argument("--resolved", default=DEFAULT_RESOLVED.as_posix())
  parser.add_argument("--segmentation-results", default=DEFAULT_SEGMENTATION_RESULTS.as_posix())
  parser.add_argument("--segmentation-storage", default=DEFAULT_SEGMENTATION_STORAGE.as_posix())
  parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR.as_posix())
  parser.add_argument("--metadata", default=DEFAULT_METADATA.as_posix())
  parser.add_argument("--base-seed", type=int, default=20260817)
  parser.add_argument("--sample")
  parser.add_argument("--mask", choices=MASK_FAMILIES)
  parser.add_argument("--severity", type=float)
  parser.add_argument("--seed", type=int)
  parser.add_argument("--rotation", type=float, default=0.0)
  parser.add_argument("--scale", type=float, default=1.0)
  parser.add_argument(
    "--skip-transform-sanity",
    action="store_true",
    help="Generate only the 20 core pilot tasks when running without --sample.",
  )
  parser.add_argument("--verbose", action="store_true")
  args = parser.parse_args()
  single_values = (args.mask, args.severity, args.seed)
  if args.sample and any(value is None for value in single_values):
    parser.error("--sample requires --mask, --severity, and --seed")
  if not args.sample and any(value is not None for value in single_values):
    parser.error("--mask, --severity, and --seed may only be used with --sample")
  return args


def load_yaml(path: Path) -> dict[str, Any]:
  if not path.exists():
    raise FileNotFoundError(f"Missing YAML file: {path}")
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"Expected YAML mapping in {path}")
  return data


def load_json(path: Path) -> dict[str, Any]:
  if not path.exists():
    raise FileNotFoundError(f"Missing JSON file: {path}")
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"Expected JSON object in {path}")
  return data


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(
    yaml.dump(payload, Dumper=NoAliasDumper, sort_keys=False, allow_unicode=False),
    encoding="utf-8",
  )


def now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def artifact_paths(output_dir: Path, config: GenerationConfig) -> ArtifactPaths:
  group_dir = output_dir / config.task_group
  return ArtifactPaths(
    fragment=group_dir / "fragments" / f"{config.task_id}.png",
    observed_fragment_mask=group_dir / "observed_masks" / f"{config.task_id}_observed_survival.png",
    source_survival_mask=group_dir / "source_survival_masks" / f"{config.task_id}_survival.png",
    source_damage_mask=group_dir / "source_damage_masks" / f"{config.task_id}_damage.png",
    metadata=group_dir / "metadata" / f"{config.task_id}.json",
  )


def build_layout_sources(
  segmentation_results: dict[str, Any],
  segmentation_storage: dict[str, Any],
) -> dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]:
  storage_by_sample = {item["sample_id"]: item for item in segmentation_storage.get("samples", [])}
  sources: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
  for result in segmentation_results.get("results", []):
    if result.get("sample_kind") != "full_page" or result.get("status") != "success":
      continue
    sample_id = result["sample_id"]
    raw_path = ROOT / result["raw_output_path"]
    raw = load_json(raw_path)
    storage = storage_by_sample.get(sample_id, {})
    provenance = {
      "sample_id": sample_id,
      "pilot_run_id": segmentation_results.get("pilot_run_id"),
      "dataset_id": segmentation_results.get("dataset_id"),
      "model_id": segmentation_results.get("model_id"),
      "model_path": segmentation_results.get("model_path"),
      "confidence_threshold": segmentation_results.get("confidence_threshold"),
      "imgsz": segmentation_results.get("imgsz"),
      "raw_output_path": result["raw_output_path"],
      "db_segmentation_run_id": storage.get("db_segmentation_run_id"),
      "orig_shape": raw.get("orig_shape"),
      "geometry_method": "rasterized_bbox_xyxy",
      "interpretation": "layout_survival_estimate",
    }
    detections = raw.get("detections", [])
    if len(detections) != result.get("detected_region_count"):
      raise ValueError(f"Segmentation detection count mismatch for {sample_id}")
    sources[sample_id] = (detections, provenance)
  return sources


def core_pilot_configs(dataset_id: str, page: SourcePage, base_seed: int) -> list[GenerationConfig]:
  configs: list[GenerationConfig] = []
  for mask_family in MASK_FAMILIES:
    for severity in CORE_SEVERITIES:
      severity_code = round(severity * 100)
      seed = stable_seed(
        dataset_id,
        page.sample_id,
        mask_family,
        base_seed,
        requested_severity=severity,
        variant="core_pilot",
      )
      configs.append(
        GenerationConfig(
          task_id=f"af_{page.sample_id}_{mask_family}_s{severity_code:03d}",
          mask_family=mask_family,
          requested_severity=severity,
          random_seed=seed,
          rotation_degrees=0.0,
          scale=1.0,
          task_group="core_pilot",
        )
      )
  return configs


def transform_sanity_configs(dataset_id: str, page: SourcePage, base_seed: int) -> list[GenerationConfig]:
  cases = (
    ("positive_rotation", 12.0, 1.0),
    ("negative_rotation", -9.0, 1.0),
    ("non_unit_scale", 0.0, 0.80),
  )
  configs: list[GenerationConfig] = []
  for name, rotation, scale in cases:
    seed = stable_seed(
      dataset_id,
      page.sample_id,
      "irregular",
      base_seed,
      requested_severity=0.45,
      rotation_degrees=rotation,
      scale=scale,
      variant=name,
    )
    configs.append(
      GenerationConfig(
        task_id=f"af_{page.sample_id}_sanity_{name}",
        mask_family="irregular",
        requested_severity=0.45,
        random_seed=seed,
        rotation_degrees=rotation,
        scale=scale,
        task_group="transformation_sanity",
      )
    )
  return configs


def single_config(args: argparse.Namespace) -> GenerationConfig:
  severity_code = round(args.severity * 100)
  rotation_code = str(args.rotation).replace("-", "m").replace(".", "p")
  scale_code = str(args.scale).replace(".", "p")
  return GenerationConfig(
    task_id=f"af_{args.sample}_{args.mask}_s{severity_code:03d}_r{rotation_code}_sc{scale_code}_seed{args.seed}",
    mask_family=args.mask,
    requested_severity=args.severity,
    random_seed=args.seed,
    rotation_degrees=args.rotation,
    scale=args.scale,
    task_group="single",
  )


def manifest_task_record(task: dict[str, Any]) -> dict[str, Any]:
  """Build a compact committed index record; full region metadata stays in per-task JSON."""
  metadata_artifact = task["artifacts"]["metadata"]
  return {
    "task_id": task["task_id"],
    "task_group": task["task_group"],
    "generation_version": task["generation_version"],
    "generation_fingerprint_sha256": task["generation_fingerprint_sha256"],
    "source_sample_id": task["source_sample_id"],
    "source_image_asset_id": task["source_image_asset_id"],
    "source_canvas_id": task["source_canvas_id"],
    "source_path": task["source_path"],
    "source_sha256": task["source_sha256"],
    "source_integrity_verified": task["source_integrity_verified"],
    "original_image_dimensions_px": task["original_image_dimensions_px"],
    "generated_fragment_dimensions_px": task["generated_fragment_dimensions_px"],
    "mask_family": task["mask_family"],
    "random_seed": task["random_seed"],
    "requested_severity": task["requested_severity"],
    "measured_severity": task["measured_severity"],
    "surviving_fraction": task["surviving_fraction"],
    "rotation_degrees": task["rotation_degrees"],
    "scale": task["scale"],
    "artifacts": task["artifacts"],
    "crop_transform": task["crop_transform"],
    "ground_truth_placement": task["ground_truth_placement"],
    "layout_survival_estimate": {
      "geometry_method": task["layout_survival_estimate"]["geometry_method"],
      "segmentation_run_provenance": task["layout_survival_estimate"]["segmentation_run_provenance"],
      "summary": task["layout_survival_estimate"]["summary"],
      "full_region_metadata_path": metadata_artifact["path"],
    },
    "artificial_fragment_task_mapping": task["artificial_fragment_task_mapping"],
  }


def generate(
  *,
  page: SourcePage,
  config: GenerationConfig,
  output_dir: Path,
  layout_sources: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]],
  verbose: bool,
) -> dict[str, Any]:
  if page.sample_id not in layout_sources:
    raise ValueError(f"No successful stored segmentation output for {page.sample_id}")
  detections, provenance = layout_sources[page.sample_id]
  if verbose:
    print(
      f"Generating {config.task_id}: mask={config.mask_family} severity={config.requested_severity:.2f} "
      f"seed={config.random_seed} rotation={config.rotation_degrees:g} scale={config.scale:g}"
    )
  return generate_fragment_task(
    root=ROOT,
    source_page=page,
    config=config,
    artifacts=artifact_paths(output_dir, config),
    layout_detections=detections,
    segmentation_run_provenance=provenance,
  )


def main() -> int:
  args = parse_args()
  resolved_path = Path(args.resolved).resolve()
  segmentation_results_path = Path(args.segmentation_results).resolve()
  segmentation_storage_path = Path(args.segmentation_storage).resolve()
  output_dir = Path(args.output_dir).resolve()
  metadata_path = Path(args.metadata).resolve()
  resolved = load_yaml(resolved_path)
  segmentation_results = load_yaml(segmentation_results_path)
  segmentation_storage = load_yaml(segmentation_storage_path)
  pages = source_pages_from_resolved_dataset(resolved)
  if len(pages) != 5:
    raise RuntimeError(f"Expected 5 registered full-page samples, found {len(pages)}")
  pages_by_id = {page.sample_id: page for page in pages}
  layout_sources = build_layout_sources(segmentation_results, segmentation_storage)
  if set(layout_sources) != set(pages_by_id):
    raise RuntimeError("Stored full-page segmentation outputs do not match the five registered source pages")

  core_tasks: list[dict[str, Any]] = []
  sanity_tasks: list[dict[str, Any]] = []
  if args.sample:
    if args.sample not in pages_by_id:
      raise ValueError(f"Unknown registered full-page sample: {args.sample}")
    core_tasks.append(
      generate(
        page=pages_by_id[args.sample],
        config=single_config(args),
        output_dir=output_dir,
        layout_sources=layout_sources,
        verbose=args.verbose,
      )
    )
    run_mode = "single"
  else:
    for page in pages:
      for config in core_pilot_configs(resolved["dataset_id"], page, args.base_seed):
        core_tasks.append(
          generate(page=page, config=config, output_dir=output_dir, layout_sources=layout_sources, verbose=args.verbose)
        )
    if not args.skip_transform_sanity:
      sanity_page = pages_by_id["fp_01_clean_simple"]
      for config in transform_sanity_configs(resolved["dataset_id"], sanity_page, args.base_seed):
        sanity_tasks.append(
          generate(page=sanity_page, config=config, output_dir=output_dir, layout_sources=layout_sources, verbose=args.verbose)
        )
    run_mode = "pilot"

  payload = {
    "generated_at": now_iso(),
    "generation_version": GENERATION_VERSION,
    "status": "generated",
    "run_mode": run_mode,
    "dataset_id": resolved.get("dataset_id"),
    "source_resolved_dataset": resolved_path.relative_to(ROOT).as_posix(),
    "segmentation_results": segmentation_results_path.relative_to(ROOT).as_posix(),
    "segmentation_storage_results": segmentation_storage_path.relative_to(ROOT).as_posix(),
    "source_full_page_count": len(pages),
    "core_pilot_task_count": len(core_tasks) if run_mode == "pilot" else 0,
    "transformation_sanity_task_count": len(sanity_tasks),
    "generated_task_count": len(core_tasks) + len(sanity_tasks),
    "mask_families": list(MASK_FAMILIES),
    "core_severities": list(CORE_SEVERITIES),
    "base_seed": args.base_seed if run_mode == "pilot" else None,
    "output_dir": output_dir.relative_to(ROOT).as_posix() if output_dir.is_relative_to(ROOT) else output_dir.as_posix(),
    "database_write": False,
    "scientific_roles": {
      "generated_fragment": "observed_evidence",
      "complete_source_page": "hidden_ground_truth",
      "contains_inferred_or_reconstructed_content": False,
    },
    "metadata_storage_note": (
      "This committed manifest is a compact index. Full per-region metadata is stored in the checksummed "
      "per-task JSON referenced by each task."
    ),
    "core_pilot_tasks": [manifest_task_record(task) for task in core_tasks],
    "transformation_sanity_tasks": [manifest_task_record(task) for task in sanity_tasks],
  }
  write_yaml(metadata_path, payload)
  print(f"Generated {len(core_tasks)} core/single tasks and {len(sanity_tasks)} transformation sanity tasks.")
  print(f"Metadata: {metadata_path}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
