#!/usr/bin/env python3
"""Validate the 15-page corpus-to-eManuSkript integration and emit statistics."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from PIL import Image
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.evaluation.segmentation_masks import (  # noqa: E402
  file_sha256,
  mask_pixel_area,
  validate_binary_mask,
)
from src.ingestion.db import connect  # noqa: E402


INPUTS = ROOT / "data/metadata/training_corpus_segmentation_inputs.yaml"
CORPUS_MANIFEST = ROOT / "data/metadata/training_corpus_validation_manifest.yaml"
RESULTS = ROOT / "data/metadata/training_corpus_segmentation_results.yaml"
STORAGE = ROOT / "data/metadata/training_corpus_segmentation_storage_results.yaml"
SOURCE_SNAPSHOT = ROOT / "data/metadata/training_corpus_segmentation_source_snapshot.yaml"
MASK_SNAPSHOT = ROOT / "data/metadata/training_corpus_segmentation_mask_snapshot.yaml"
STATISTICS = ROOT / "data/metadata/training_corpus_segmentation_statistics.yaml"
VALIDATION = ROOT / "data/metadata/training_corpus_segmentation_validation.yaml"
REPORT = ROOT / "docs/15_training_corpus_segmentation_integration.md"
STORAGE_REPORT = ROOT / "outputs/training_corpus_segmentation/storage_report.md"
EXPECTED_SPLITS = {"train": 9, "validation": 3, "test": 3}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate training-corpus eManuSkript integration.")
  mode = parser.add_mutually_exclusive_group()
  mode.add_argument("--capture-source-snapshot", action="store_true")
  mode.add_argument("--capture-mask-snapshot", action="store_true")
  parser.add_argument("--skip-storage-rerun", action="store_true")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
  if not path.is_file():
    raise FileNotFoundError(f"Required YAML file is missing: {path.relative_to(ROOT)}")
  payload = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"Expected YAML mapping: {path.relative_to(ROOT)}")
  return payload


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def canonical_sha256(value: Any) -> str:
  encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
  return hashlib.sha256(encoded).hexdigest()


def selected_corpus_pages(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
  selected: dict[str, dict[str, Any]] = {}
  for manuscript in corpus.get("manuscripts", []):
    for page in manuscript.get("pages", []):
      if page.get("selection_status") != "selected":
        continue
      db_ids = page.get("registration", {}).get("db_ids", {})
      asset_id = db_ids.get("image_asset_id")
      if not asset_id or asset_id in selected:
        raise ValueError(f"Missing or duplicate selected image_asset identity: {asset_id}")
      selected[asset_id] = {
        "sample_manuscript_id": manuscript["id"],
        "dataset_split": manuscript["split"],
        "canvas_identifier": page["canvas_identifier"],
        "local_path": page["image"]["local_path"],
        "source_sha256": page["image"]["checksum_sha256"],
        "rights_review_status": page["image"]["rights_review_status"],
        "training_allowed": page["image"]["training_allowed"],
        "db_ids": db_ids,
      }
  if len(selected) != 15:
    raise ValueError(f"Expected exactly 15 selected corpus pages, found {len(selected)}")
  return selected


def query_source_state(asset_id: str) -> dict[str, Any]:
  with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
      """
      SELECT asset.id::text AS image_asset_id,
             asset.canvas_id::text AS canvas_id,
             canvas.manuscript_id::text AS manuscript_db_id,
             asset.local_path,
             asset.checksum_sha256,
             asset.training_allowed,
             asset.rights_review_status,
             asset.publication_allowed,
             asset.demo_allowed,
             asset.rights_statement,
             asset.license,
             asset.attribution,
             asset.raw_metadata AS image_raw_metadata,
             canvas.raw_metadata AS canvas_raw_metadata,
             manuscript.raw_metadata AS manuscript_raw_metadata
      FROM image_asset asset
      JOIN canvas ON canvas.id = asset.canvas_id
      JOIN manuscript ON manuscript.id = canvas.manuscript_id
      WHERE asset.id = %s
      """,
      (asset_id,),
    )
    row = cur.fetchone()
  if row is None:
    raise ValueError(f"Source image_asset does not resolve: {asset_id}")
  state = dict(row)
  local_path = ROOT / state["local_path"]
  if not local_path.is_file():
    raise FileNotFoundError(f"Registered source file is missing: {state['local_path']}")
  state["actual_source_sha256"] = file_sha256(local_path)
  state["image_raw_metadata_sha256"] = canonical_sha256(state.pop("image_raw_metadata"))
  state["canvas_raw_metadata_sha256"] = canonical_sha256(state.pop("canvas_raw_metadata"))
  state["manuscript_raw_metadata_sha256"] = canonical_sha256(state.pop("manuscript_raw_metadata"))
  return state


def capture_source_snapshot() -> dict[str, Any]:
  corpus = load_yaml(CORPUS_MANIFEST)
  inputs = load_yaml(INPUTS)
  selected = selected_corpus_pages(corpus)
  source_states: list[dict[str, Any]] = []
  seen: set[str] = set()
  for item in inputs.get("selected_inputs", []):
    asset_id = item.get("db_image_asset_id")
    if asset_id in seen or asset_id not in selected:
      raise ValueError(f"Prepared input is duplicated or not selected by the corpus: {asset_id}")
    seen.add(asset_id)
    expected = selected[asset_id]
    if item.get("manuscript_id") != expected["sample_manuscript_id"] or item.get("dataset_split") != expected["dataset_split"]:
      raise ValueError(f"Prepared split/manuscript differs from corpus manifest: {item['sample_id']}")
    state = query_source_state(asset_id)
    if state["canvas_id"] != item.get("db_canvas_id") or state["local_path"] != item.get("local_path"):
      raise ValueError(f"Prepared source relationship differs from database: {item['sample_id']}")
    if state["checksum_sha256"] != expected["source_sha256"] or state["actual_source_sha256"] != expected["source_sha256"]:
      raise ValueError(f"Source checksum differs before segmentation: {item['sample_id']}")
    if state["training_allowed"] is not False or state["rights_review_status"] != "pending_review":
      raise ValueError(f"Source rights are not conservatively gated: {item['sample_id']}")
    source_states.append({"sample_id": item["sample_id"], **state})
  if len(source_states) != 15:
    raise ValueError(f"Expected 15 source states, found {len(source_states)}")
  payload = {
    "snapshot_version": "training_corpus_segmentation_source_snapshot_v0_1",
    "corpus_id": inputs.get("dataset_id"),
    "source_count": len(source_states),
    "sources": sorted(source_states, key=lambda item: item["sample_id"]),
  }
  payload["snapshot_sha256"] = canonical_sha256(payload)
  write_yaml(SOURCE_SNAPSHOT, payload)
  return payload


def mask_records(results: dict[str, Any]) -> list[dict[str, Any]]:
  records: list[dict[str, Any]] = []
  for result in results.get("results", []):
    raw_path = ROOT / result["raw_output_path"]
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    for detection in raw.get("detections", []):
      mask_path = ROOT / detection["mask_path"]
      records.append({
        "sample_id": result["sample_id"],
        "index": detection["index"],
        "path": detection["mask_path"],
        "sha256": file_sha256(mask_path),
        "recorded_sha256": detection.get("mask_sha256"),
        "dimensions_px": detection.get("mask_dimensions_px"),
        "size_bytes": mask_path.stat().st_size,
      })
  return sorted(records, key=lambda item: (item["sample_id"], item["index"]))


def capture_mask_snapshot() -> dict[str, Any]:
  results = load_yaml(RESULTS)
  records = mask_records(results)
  if not records:
    raise ValueError("Cannot capture mask snapshot: no mask artifacts were produced")
  if any(item["sha256"] != item["recorded_sha256"] for item in records):
    raise ValueError("Cannot capture mask snapshot: a mask hash differs from raw detection metadata")
  payload = {
    "snapshot_version": "training_corpus_segmentation_mask_snapshot_v0_1",
    "run_identity_sha256": results.get("run_identity_sha256"),
    "model_sha256": results.get("model_sha256"),
    "mask_count": len(records),
    "masks": records,
  }
  payload["snapshot_sha256"] = canonical_sha256(payload)
  write_yaml(MASK_SNAPSHOT, payload)
  return payload


def database_run_snapshot(run_identity: str) -> dict[str, Any]:
  with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
      """
      SELECT id::text AS run_id,
             image_asset_id::text AS image_asset_id,
             status,
             parameters,
             output_format
      FROM segmentation_run
      WHERE parameters->>'run_identity_sha256' = %s
      ORDER BY parameters->>'sample_id'
      """,
      (run_identity,),
    )
    runs = [dict(row) for row in cur.fetchall()]
    snapshots: dict[str, Any] = {}
    for run in runs:
      sample_id = run["parameters"].get("sample_id")
      if sample_id in snapshots:
        raise ValueError(f"Duplicate segmentation_run for run identity/sample: {sample_id}")
      cur.execute(
        """
        SELECT label, label_id, confidence, reading_order_index, region_area_px,
               mask_path, raw_region
        FROM layout_region
        WHERE segmentation_run_id = %s
        ORDER BY reading_order_index, label, confidence
        """,
        (run["run_id"],),
      )
      regions = [dict(row) for row in cur.fetchall()]
      snapshots[sample_id] = {
        **run,
        "regions": regions,
        "region_count": len(regions),
        "region_signature_sha256": canonical_sha256(regions),
      }
  return snapshots


def rerun_storage() -> None:
  subprocess.run(
    [
      sys.executable,
      str(ROOT / "scripts/store_segmentation_pilot_outputs.py"),
      "--results",
      str(RESULTS),
      "--inputs",
      str(INPUTS),
      "--output",
      str(STORAGE),
      "--report",
      str(STORAGE_REPORT),
    ],
    cwd=ROOT,
    check=True,
  )


def build_statistics(
  inputs: dict[str, Any],
  results: dict[str, Any],
  raw_by_sample: dict[str, dict[str, Any]],
  masks: list[dict[str, Any]],
) -> dict[str, Any]:
  input_by_sample = {item["sample_id"]: item for item in inputs["selected_inputs"]}
  successful = [item for item in results["results"] if item.get("status") != "error"]
  failed = [item for item in results["results"] if item.get("status") == "error"]
  region_counts = [len(raw_by_sample[item["sample_id"]].get("detections", [])) for item in results["results"]]
  labels: Counter[str] = Counter()
  confidences: list[float] = []
  split_stats = {
    name: {"attempted_pages": 0, "successful_pages": 0, "failed_pages": 0, "detected_regions": 0}
    for name in ("train", "validation", "test")
  }
  for result in results["results"]:
    sample_id = result["sample_id"]
    split_name = input_by_sample[sample_id]["dataset_split"]
    detections = raw_by_sample[sample_id].get("detections", [])
    split_stats[split_name]["attempted_pages"] += 1
    split_stats[split_name]["detected_regions"] += len(detections)
    status_key = "failed_pages" if result.get("status") == "error" else "successful_pages"
    split_stats[split_name][status_key] += 1
    for detection in detections:
      labels[detection.get("label", "unknown")] += 1
      if detection.get("confidence") is not None:
        confidences.append(float(detection["confidence"]))
  return {
    "corpus_id": results.get("dataset_id"),
    "run_identity_sha256": results.get("run_identity_sha256"),
    "model_id": results.get("model_id"),
    "model_sha256": results.get("model_sha256"),
    "attempted_pages": len(results["results"]),
    "successful_pages": len(successful),
    "failed_pages": len(failed),
    "failures": [
      {"sample_id": item["sample_id"], "errors": item.get("errors", [])}
      for item in failed
    ],
    "total_detected_regions": sum(region_counts),
    "regions_per_page": {
      "minimum": min(region_counts, default=0),
      "maximum": max(region_counts, default=0),
      "mean": round(statistics.mean(region_counts), 4) if region_counts else 0.0,
      "median": round(statistics.median(region_counts), 4) if region_counts else 0.0,
      "values": region_counts,
    },
    "label_distribution": dict(sorted(labels.items())),
    "confidence_distribution": {
      "count": len(confidences),
      "minimum": round(min(confidences), 6) if confidences else None,
      "maximum": round(max(confidences), 6) if confidences else None,
      "mean": round(statistics.mean(confidences), 6) if confidences else None,
      "median": round(statistics.median(confidences), 6) if confidences else None,
    },
    "split_counts": split_stats,
    "mask_artifacts": {
      "count": len(masks),
      "total_size_bytes": sum(item["size_bytes"] for item in masks),
      "minimum_size_bytes": min((item["size_bytes"] for item in masks), default=0),
      "maximum_size_bytes": max((item["size_bytes"] for item in masks), default=0),
    },
  }


def write_report(statistics_payload: dict[str, Any], validation_payload: dict[str, Any]) -> None:
  regions = statistics_payload["regions_per_page"]
  confidence = statistics_payload["confidence_distribution"]
  masks = statistics_payload["mask_artifacts"]
  lines = [
    "# Training Corpus → eManuSkript Integration Validation",
    "",
    "## Scope",
    "",
    "The existing eManuSkript/Ultralytics inference, source-dimension mask restoration, mask serialization, and PostgreSQL `segmentation_run`/`layout_region` storage paths were run against exactly the 15 selected validation-corpus pages. No segmentation logic was added to the corpus builder, and no model training, artificial-fragment generation, reconstruction, retrieval, LLM, e-rara, HisFrag20, UI, or database migration work was performed.",
    "",
    "Source manuscript splits and rights remain evidence from corpus registration, not segmentation inference. Mask and region outputs are model-derived layout evidence rather than manual ground truth.",
    "",
    "## Reproducible identity",
    "",
    f"- Corpus: `{statistics_payload['corpus_id']}`",
    f"- Run identity SHA-256: `{statistics_payload['run_identity_sha256']}`",
    f"- Model: `{statistics_payload['model_id']}`",
    f"- Model SHA-256: `{statistics_payload['model_sha256']}`",
    "- Configuration identity includes the 15 source image checksums/DB identities, manuscript splits, model checksum, device, confidence threshold, image size, software versions, retina-mask setting, and source-dimension restoration method.",
    "",
    "## Validation result",
    "",
    f"- Attempted pages: {statistics_payload['attempted_pages']}",
    f"- Successful pages: {statistics_payload['successful_pages']}",
    f"- Failed pages: {statistics_payload['failed_pages']}",
    f"- Detected regions: {statistics_payload['total_detected_regions']}",
    f"- Regions/page: min {regions['minimum']}, max {regions['maximum']}, mean {regions['mean']}, median {regions['median']}",
    f"- Confidence: min {confidence['minimum']}, max {confidence['maximum']}, mean {confidence['mean']}, median {confidence['median']}",
    f"- Source-sized mask artifacts: {masks['count']} files, {masks['total_size_bytes']} bytes",
    f"- Stable segmentation runs after storage rerun: {validation_payload['idempotency']['stable_run_count']}",
    f"- Stable region sets after storage rerun: {validation_payload['idempotency']['stable_region_set_count']}",
    "",
    "## Manuscript-isolated split statistics",
    "",
  ]
  for split_name, values in statistics_payload["split_counts"].items():
    lines.append(
      f"- {split_name}: {values['attempted_pages']} attempted, {values['successful_pages']} successful, "
      f"{values['failed_pages']} failed, {values['detected_regions']} regions"
    )
  lines.extend(["", "## Label distribution", ""])
  lines.extend(f"- {label}: {count}" for label, count in statistics_payload["label_distribution"].items())
  if statistics_payload["failures"]:
    lines.extend(["", "## Explicit failures", ""])
    for failure in statistics_payload["failures"]:
      lines.append(f"- `{failure['sample_id']}`: {'; '.join(failure['errors'])}")
  else:
    lines.extend(["", "## Explicit failures", "", "No page failed in this validation run."])
  lines.extend([
    "",
    "## Invariants confirmed",
    "",
    "- All successful detections retain class ID, label, confidence, bbox, source-sized binary mask path, mask SHA-256, mask area, and model/run provenance.",
    "- Every stored mask matches its registered source-image dimensions and remains an ignored local PNG artifact.",
    "- Every stored run resolves to its original `image_asset`, `canvas`, and manuscript; the same run identity reuses the same 15 `segmentation_run` rows and replaces rather than duplicates their regions.",
    "- Source image checksums, source metadata hashes, `training_allowed`, `rights_review_status`, `publication_allowed`, and manuscript split assignments match the pre-inference snapshot.",
    "",
    "## Next engineering step",
    "",
    "Expand the source corpus toward approximately 100 manuscripts / 500 selected pages in bounded batches while preserving manuscript-level train/validation/test isolation, checksum-resumable assets, and `pending_review` rights until explicit approval. Do not begin model training as part of acquisition.",
    "",
  ])
  REPORT.write_text("\n".join(lines), encoding="utf-8")


def validate_integration(skip_storage_rerun: bool = False) -> dict[str, Any]:
  inputs = load_yaml(INPUTS)
  corpus = load_yaml(CORPUS_MANIFEST)
  results = load_yaml(RESULTS)
  storage = load_yaml(STORAGE)
  source_snapshot = load_yaml(SOURCE_SNAPSHOT)
  mask_snapshot = load_yaml(MASK_SNAPSHOT)
  selected = selected_corpus_pages(corpus)
  input_items = inputs.get("selected_inputs", [])
  result_items = results.get("results", [])
  storage_items = storage.get("samples", [])
  if len(input_items) != 15 or len(result_items) != 15 or len(storage_items) != 15:
    raise ValueError(
      f"Exactly 15 pages are required: inputs={len(input_items)}, results={len(result_items)}, storage={len(storage_items)}"
    )
  input_by_sample = {item["sample_id"]: item for item in input_items}
  result_by_sample = {item["sample_id"]: item for item in result_items}
  storage_by_sample = {item["sample_id"]: item for item in storage_items}
  if len(input_by_sample) != 15 or set(input_by_sample) != set(result_by_sample) or set(input_by_sample) != set(storage_by_sample):
    raise ValueError("Input/result/storage sample identities are duplicated or differ")
  split_counts = Counter(item.get("dataset_split") for item in input_items)
  if dict(split_counts) != EXPECTED_SPLITS:
    raise ValueError(f"Manuscript split counts changed: {dict(split_counts)}")
  manuscript_splits: dict[str, set[str]] = {}
  for item in input_items:
    manuscript_splits.setdefault(item["manuscript_id"], set()).add(item["dataset_split"])
  if any(len(splits) != 1 for splits in manuscript_splits.values()):
    raise ValueError("A manuscript occurs in more than one dataset split")
  run_identity = results.get("run_identity_sha256")
  if not run_identity or storage.get("run_identity_sha256") != run_identity:
    raise ValueError("Run identity is missing or differs between inference and storage")
  if mask_snapshot.get("run_identity_sha256") != run_identity:
    raise ValueError("Mask reproducibility snapshot belongs to a different run identity")
  model_path = ROOT / results["model_path"]
  if file_sha256(model_path) != results.get("model_sha256"):
    raise ValueError("Model checksum differs from run provenance")

  snapshot_by_sample = {item["sample_id"]: item for item in source_snapshot["sources"]}
  if len(snapshot_by_sample) != 15 or set(snapshot_by_sample) != set(input_by_sample):
    raise ValueError("Pre-inference source snapshot does not contain exactly the selected 15 pages")
  descriptor_sources = {
    item["sample_id"]: item
    for item in results.get("run_identity_descriptor", {}).get("source_assets", [])
  }
  raw_by_sample: dict[str, dict[str, Any]] = {}
  for sample_id, item in input_by_sample.items():
    asset_id = item["db_image_asset_id"]
    expected = selected.get(asset_id)
    if expected is None:
      raise ValueError(f"Input is no longer a selected corpus page: {sample_id}")
    if item["manuscript_id"] != expected["sample_manuscript_id"] or item["dataset_split"] != expected["dataset_split"]:
      raise ValueError(f"Corpus manuscript split changed: {sample_id}")
    current_source = query_source_state(asset_id)
    frozen_source = {key: value for key, value in snapshot_by_sample[sample_id].items() if key != "sample_id"}
    if current_source != frozen_source:
      raise ValueError(f"Registered source metadata/rights changed during segmentation: {sample_id}")
    if descriptor_sources.get(sample_id, {}).get("source_sha256") != expected["source_sha256"]:
      raise ValueError(f"Run identity source checksum differs from corpus: {sample_id}")
    result = result_by_sample[sample_id]
    if result.get("run_identity_sha256") != run_identity:
      raise ValueError(f"Per-page run identity differs: {sample_id}")
    raw_path = ROOT / result["raw_output_path"]
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw_by_sample[sample_id] = raw
    if raw.get("segmentation_provenance", {}).get("run_identity_sha256") != run_identity:
      raise ValueError(f"Raw prediction provenance differs: {sample_id}")
    if result.get("status") == "error":
      if not result.get("errors") or raw.get("detections"):
        raise ValueError(f"Failed page is not explicitly recorded: {sample_id}")
      continue
    source_path = ROOT / item["local_path"]
    with Image.open(source_path) as source_image:
      source_size = source_image.size
    for detection in raw.get("detections", []):
      required = ("bbox_xyxy", "bbox_xywh", "class_id", "label", "confidence", "mask_path", "mask_sha256")
      if any(detection.get(field) is None for field in required):
        raise ValueError(f"Detection provenance is incomplete: {sample_id} region {detection.get('index')}")
      mask_path = ROOT / detection["mask_path"]
      with Image.open(mask_path) as mask:
        binary = mask.convert("L")
        validate_binary_mask(binary, source_size)
        if mask_pixel_area(binary) != detection.get("mask_pixel_area"):
          raise ValueError(f"Mask area differs: {detection['mask_path']}")
      if file_sha256(mask_path) != detection["mask_sha256"]:
        raise ValueError(f"Mask checksum differs: {detection['mask_path']}")

  current_masks = mask_records(results)
  if current_masks != mask_snapshot.get("masks"):
    raise ValueError("Mask hashes/dimensions/sizes changed on the unchanged inference rerun")
  before = database_run_snapshot(run_identity)
  if len(before) != 15:
    raise ValueError(f"Expected exactly 15 database runs for identity, found {len(before)}")
  if not skip_storage_rerun:
    rerun_storage()
  after = database_run_snapshot(run_identity)
  if set(before) != set(after):
    raise ValueError("Storage rerun changed segmentation_run sample identities")
  stable_runs = 0
  stable_regions = 0
  for sample_id in before:
    if before[sample_id]["run_id"] != after[sample_id]["run_id"]:
      raise ValueError(f"Storage rerun created a duplicate run: {sample_id}")
    stable_runs += 1
    if (
      before[sample_id]["region_count"] != after[sample_id]["region_count"]
      or before[sample_id]["region_signature_sha256"] != after[sample_id]["region_signature_sha256"]
    ):
      raise ValueError(f"Storage rerun changed region content/count: {sample_id}")
    stable_regions += 1
    params = after[sample_id]["parameters"]
    source_expected = descriptor_sources[sample_id]
    input_expected = input_by_sample[sample_id]
    storage_expected = storage_by_sample[sample_id]
    if after[sample_id]["image_asset_id"] != input_expected["db_image_asset_id"]:
      raise ValueError(f"Stored segmentation_run does not resolve to the source image_asset: {sample_id}")
    if params.get("db_canvas_id") != input_expected["db_canvas_id"]:
      raise ValueError(f"Stored segmentation_run does not resolve to the source canvas: {sample_id}")
    if params.get("manuscript_id") != input_expected["manuscript_id"]:
      raise ValueError(f"Stored segmentation_run does not resolve to the source manuscript: {sample_id}")
    if storage_expected.get("db_segmentation_run_id") != after[sample_id]["run_id"]:
      raise ValueError(f"Storage result references a different segmentation_run: {sample_id}")
    if params.get("source_sha256") != source_expected["source_sha256"]:
      raise ValueError(f"Stored source checksum provenance differs: {sample_id}")
    if params.get("dataset_split") != input_by_sample[sample_id]["dataset_split"]:
      raise ValueError(f"Stored manuscript split differs: {sample_id}")
    expected_status = "failed" if result_by_sample[sample_id].get("status") == "error" else "completed"
    if after[sample_id]["status"] != expected_status:
      raise ValueError(f"Stored run status differs: {sample_id}")
    if after[sample_id]["region_count"] != len(raw_by_sample[sample_id].get("detections", [])):
      raise ValueError(f"Stored region count differs from raw inference: {sample_id}")
    stored_regions = after[sample_id]["regions"]
    raw_detections = raw_by_sample[sample_id].get("detections", [])
    for stored_region, detection in zip(stored_regions, raw_detections):
      if stored_region["reading_order_index"] != detection["index"]:
        raise ValueError(f"Stored region ordering differs from inference: {sample_id}")
      if stored_region["label"] != detection["label"] or stored_region["label_id"] != detection["class_id"]:
        raise ValueError(f"Stored region class/label differs from inference: {sample_id}")
      if float(stored_region["confidence"]) != float(detection["confidence"]):
        raise ValueError(f"Stored region confidence differs from inference: {sample_id}")
      if stored_region["mask_path"] != detection["mask_path"]:
        raise ValueError(f"Stored region mask path differs from inference: {sample_id}")
      if stored_region["raw_region"].get("mask_sha256") != detection["mask_sha256"]:
        raise ValueError(f"Stored region mask checksum differs from inference: {sample_id}")
      if stored_region["raw_region"].get("bbox_xyxy") != detection["bbox_xyxy"]:
        raise ValueError(f"Stored region bbox differs from inference: {sample_id}")

  statistics_payload = build_statistics(inputs, results, raw_by_sample, current_masks)
  validation_payload = {
    "validation_version": "training_corpus_emanuskript_integration_validation_v0_1",
    "status": "passed",
    "corpus_id": results.get("dataset_id"),
    "run_identity_sha256": run_identity,
    "source_snapshot_sha256": source_snapshot.get("snapshot_sha256"),
    "mask_snapshot_sha256": mask_snapshot.get("snapshot_sha256"),
    "attempted_page_count": 15,
    "source_invariants_unchanged": True,
    "manuscript_splits_unchanged": True,
    "mask_hashes_reproducible": True,
    "database_relationships_resolve": True,
    "idempotency": {
      "storage_rerun_performed": not skip_storage_rerun,
      "stable_run_count": stable_runs,
      "stable_region_set_count": stable_regions,
      "duplicate_run_count": 0,
    },
    "statistics_path": STATISTICS.relative_to(ROOT).as_posix(),
    "report_path": REPORT.relative_to(ROOT).as_posix(),
  }
  write_yaml(STATISTICS, statistics_payload)
  write_yaml(VALIDATION, validation_payload)
  write_report(statistics_payload, validation_payload)
  return validation_payload


def main() -> int:
  args = parse_args()
  if args.capture_source_snapshot:
    payload = capture_source_snapshot()
    print(f"Captured {payload['source_count']} pre-inference source invariants: {SOURCE_SNAPSHOT.relative_to(ROOT)}")
    return 0
  if args.capture_mask_snapshot:
    payload = capture_mask_snapshot()
    print(f"Captured {payload['mask_count']} mask hashes after first inference: {MASK_SNAPSHOT.relative_to(ROOT)}")
    return 0
  payload = validate_integration(skip_storage_rerun=args.skip_storage_rerun)
  print(
    "PASS: 15 corpus pages flowed through existing eManuSkript inference/storage; "
    f"run identity {payload['run_identity_sha256']} is idempotent"
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
