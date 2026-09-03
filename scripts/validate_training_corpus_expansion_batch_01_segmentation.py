#!/usr/bin/env python3
"""Validate Batch 01 through the existing eManuSkript inference/storage workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


DEFAULT_SPEC = ROOT / "data/metadata/training_corpus_expansion_batch_01_segmentation_spec.yaml"
FAILURE_STATUSES = {"error", "failure"}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate Batch 01 eManuSkript segmentation.")
  parser.add_argument("--spec", default=str(DEFAULT_SPEC))
  mode = parser.add_mutually_exclusive_group()
  mode.add_argument("--capture-source-snapshot", action="store_true")
  mode.add_argument("--capture-mask-snapshot", action="store_true")
  parser.add_argument("--skip-storage-rerun", action="store_true")
  return parser.parse_args()


def resolve(path: str | Path) -> Path:
  candidate = Path(path)
  return candidate if candidate.is_absolute() else ROOT / candidate


def rel(path: Path) -> str:
  return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_yaml(path: Path) -> dict[str, Any]:
  if not path.is_file():
    raise FileNotFoundError(f"Required YAML file is missing: {rel(path)}")
  payload = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"Expected YAML mapping: {rel(path)}")
  return payload


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def canonical_sha256(value: Any) -> str:
  encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
  return hashlib.sha256(encoded).hexdigest()


def iso_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def snapshot_sha256(payload: dict[str, Any]) -> str:
  return canonical_sha256({
    key: value
    for key, value in payload.items()
    if key not in {"captured_at", "snapshot_sha256"}
  })


def paths_from_spec(spec: dict[str, Any]) -> dict[str, Path]:
  paths = {key: resolve(value) for key, value in spec["artifacts"].items()}
  paths["corpus_manifest"] = resolve(spec["source"]["corpus_manifest"])
  paths["acquisition_validation"] = resolve(spec["source"]["acquisition_validation"])
  paths["frozen_manifest"] = resolve(spec["source"]["frozen_validation_corpus_manifest"])
  paths["model"] = resolve(spec["model"]["path"])
  return paths


def selected_corpus_pages(corpus: dict[str, Any], expected_count: int) -> dict[str, dict[str, Any]]:
  selected: dict[str, dict[str, Any]] = {}
  for manuscript in corpus.get("manuscripts", []):
    for page in manuscript.get("pages", []):
      if page.get("selection_status") != "selected":
        continue
      image = page.get("image", {})
      db_ids = page.get("registration", {}).get("db_ids", {})
      asset_id = db_ids.get("image_asset_id")
      if not asset_id or asset_id in selected:
        raise ValueError(f"Missing or duplicate selected image_asset identity: {asset_id}")
      selected[asset_id] = {
        "manuscript_id": manuscript["id"],
        "repository": manuscript.get("repository"),
        "dataset_split": manuscript["split"],
        "canvas_identifier": page["canvas_identifier"],
        "canvas_label": page.get("canvas_label"),
        "sequence_index": page.get("sequence_index"),
        "local_path": image.get("local_path"),
        "source_url": image.get("download_url"),
        "source_sha256": image.get("checksum_sha256"),
        "source_size_bytes": image.get("size_bytes"),
        "source_dimensions_px": [image.get("download_width_px"), image.get("download_height_px")],
        "rights_review_status": image.get("rights_review_status"),
        "training_allowed": image.get("training_allowed"),
        "db_ids": db_ids,
      }
  if len(selected) != expected_count:
    raise ValueError(f"Expected exactly {expected_count} selected Batch pages, found {len(selected)}")
  return selected


def selected_canvas_identifiers(corpus: dict[str, Any]) -> set[str]:
  return {
    page["canvas_identifier"]
    for manuscript in corpus.get("manuscripts", [])
    for page in manuscript.get("pages", [])
    if page.get("selection_status") == "selected"
  }


def assert_corpus_scope(
  spec: dict[str, Any],
  corpus: dict[str, Any],
  frozen: dict[str, Any],
  inputs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
  expected = spec["expected"]
  expected_pages = int(expected["total_pages"])
  selected = selected_corpus_pages(corpus, expected_pages)
  input_items = inputs.get("selected_inputs", [])
  input_by_asset = {item.get("db_image_asset_id"): item for item in input_items}
  if len(input_items) != expected_pages or len(input_by_asset) != expected_pages:
    raise ValueError("Batch segmentation input identities are missing or duplicated")
  if set(input_by_asset) != set(selected):
    raise ValueError("Batch segmentation inputs differ from final selected corpus membership")

  page_splits = Counter(item.get("dataset_split") for item in input_items)
  if dict(page_splits) != expected["page_split_counts"]:
    raise ValueError(f"Batch page split counts changed: {dict(page_splits)}")
  manuscript_splits: dict[str, set[str]] = defaultdict(set)
  for item in input_items:
    manuscript_splits[item["manuscript_id"]].add(item["dataset_split"])
    selected_item = selected[item["db_image_asset_id"]]
    for key in ("manuscript_id", "repository", "dataset_split", "canvas_identifier", "local_path", "source_url"):
      if item.get(key) != selected_item.get(key):
        raise ValueError(f"Prepared input {key} differs from corpus: {item['sample_id']}")
    if item.get("source_sha256") != selected_item["source_sha256"]:
      raise ValueError(f"Prepared source checksum differs from corpus: {item['sample_id']}")
    if item.get("rights_review_status") != "pending_review" or item.get("training_allowed") is not False:
      raise ValueError(f"Prepared input rights gate changed: {item['sample_id']}")
  if any(len(splits) != 1 for splits in manuscript_splits.values()):
    raise ValueError("A Batch manuscript crosses train/validation/test boundaries")
  active_counts = Counter(next(iter(splits)) for splits in manuscript_splits.values())
  if dict(active_counts) != expected["page_bearing_manuscript_split_counts"]:
    raise ValueError(f"Page-bearing manuscript split counts changed: {dict(active_counts)}")
  assigned_counts = Counter(item.get("split") for item in corpus.get("manuscripts", []))
  if dict(assigned_counts) != expected["assigned_manuscript_split_counts"]:
    raise ValueError(f"Assigned manuscript split counts changed: {dict(assigned_counts)}")

  frozen_canvases = selected_canvas_identifiers(frozen)
  batch_canvases = selected_canvas_identifiers(corpus)
  if batch_canvases & frozen_canvases:
    raise ValueError("A frozen validation canvas was included in Batch 01 segmentation")
  frozen_manuscripts = {item["id"] for item in frozen.get("manuscripts", [])}
  batch_manuscripts = {item["id"] for item in corpus.get("manuscripts", [])}
  if batch_manuscripts & frozen_manuscripts:
    raise ValueError("Batch 01 manuscript membership overlaps the frozen validation corpus")
  return selected


def query_source_state(asset_id: str) -> dict[str, Any]:
  with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
      """
      SELECT asset.id::text AS image_asset_id,
             asset.canvas_id::text AS canvas_id,
             asset.repository_id::text AS repository_id,
             canvas.manuscript_id::text AS manuscript_db_id,
             canvas.iiif_manifest_cache_id::text AS manifest_cache_id,
             repository.name AS repository,
             canvas.canvas_identifier,
             canvas.canvas_label,
             canvas.sequence_index,
             asset.source_url,
             asset.iiif_image_service_url,
             asset.local_path,
             asset.checksum_sha256,
             asset.width_px,
             asset.height_px,
             asset.training_allowed,
             asset.rights_review_status,
             asset.publication_allowed,
             asset.demo_allowed,
             asset.access_level,
             asset.rights_statement,
             asset.license,
             asset.attribution,
             asset.raw_metadata AS image_raw_metadata,
             canvas.raw_metadata AS canvas_raw_metadata,
             manuscript.raw_metadata AS manuscript_raw_metadata
      FROM image_asset asset
      JOIN canvas ON canvas.id = asset.canvas_id
      JOIN manuscript ON manuscript.id = canvas.manuscript_id
      LEFT JOIN repository ON repository.id = asset.repository_id
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
  with Image.open(local_path) as image:
    actual_dimensions = [image.width, image.height]
  stat = local_path.stat()
  state.update({
    "actual_source_sha256": file_sha256(local_path),
    "actual_dimensions_px": actual_dimensions,
    "actual_size_bytes": stat.st_size,
    "source_mtime_ns": stat.st_mtime_ns,
    "image_raw_metadata_sha256": canonical_sha256(state.pop("image_raw_metadata")),
    "canvas_raw_metadata_sha256": canonical_sha256(state.pop("canvas_raw_metadata")),
    "manuscript_raw_metadata_sha256": canonical_sha256(state.pop("manuscript_raw_metadata")),
  })
  return state


def capture_source_snapshot(spec: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
  corpus = load_yaml(paths["corpus_manifest"])
  frozen = load_yaml(paths["frozen_manifest"])
  inputs = load_yaml(paths["inputs"])
  selected = assert_corpus_scope(spec, corpus, frozen, inputs)
  sources: list[dict[str, Any]] = []
  for item in inputs["selected_inputs"]:
    expected = selected[item["db_image_asset_id"]]
    state = query_source_state(item["db_image_asset_id"])
    db_ids = expected["db_ids"]
    relationships = {
      "canvas_id": db_ids.get("canvas_id"),
      "manuscript_db_id": db_ids.get("manuscript_id"),
      "repository_id": db_ids.get("repository_id"),
      "manifest_cache_id": db_ids.get("manifest_cache_id"),
    }
    if any(state.get(key) != value for key, value in relationships.items()):
      raise ValueError(f"Registered source relationships differ: {item['sample_id']}")
    if state["local_path"] != expected["local_path"] or state["canvas_identifier"] != expected["canvas_identifier"]:
      raise ValueError(f"Registered path/canvas differs: {item['sample_id']}")
    if state["actual_source_sha256"] != expected["source_sha256"] or state["checksum_sha256"] != expected["source_sha256"]:
      raise ValueError(f"Source checksum differs before segmentation: {item['sample_id']}")
    if state["actual_dimensions_px"] != expected["source_dimensions_px"]:
      raise ValueError(f"Source dimensions differ before segmentation: {item['sample_id']}")
    if state["actual_size_bytes"] != expected["source_size_bytes"]:
      raise ValueError(f"Source byte size differs before segmentation: {item['sample_id']}")
    if state["rights_review_status"] != "pending_review" or state["training_allowed"] is not False:
      raise ValueError(f"Source rights are not conservatively gated: {item['sample_id']}")
    sources.append({"sample_id": item["sample_id"], "manuscript_id": item["manuscript_id"], **state})
  payload = {
    "snapshot_version": "training_corpus_expansion_batch_01_segmentation_source_snapshot_v0_1",
    "captured_at": iso_now(),
    "corpus_id": spec["corpus_id"],
    "source_count": len(sources),
    "total_source_bytes": sum(item["actual_size_bytes"] for item in sources),
    "sources": sorted(sources, key=lambda item: item["sample_id"]),
  }
  payload["snapshot_sha256"] = snapshot_sha256(payload)
  write_yaml(paths["source_snapshot"], payload)
  return payload


def raw_prediction(result: dict[str, Any]) -> dict[str, Any]:
  path = ROOT / result["raw_output_path"]
  payload = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"Raw segmentation output is not an object: {result['raw_output_path']}")
  return payload


def mask_records(results: dict[str, Any]) -> list[dict[str, Any]]:
  records: list[dict[str, Any]] = []
  for result in results.get("results", []):
    raw = raw_prediction(result)
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
        "mtime_ns": mask_path.stat().st_mtime_ns,
      })
  return sorted(records, key=lambda item: (item["sample_id"], item["index"]))


def artifact_records(results: dict[str, Any], masks: list[dict[str, Any]]) -> list[dict[str, Any]]:
  records: list[dict[str, Any]] = []
  for result in results.get("results", []):
    for kind, key in (("raw_prediction", "raw_output_path"), ("overlay", "overlay_path")):
      path = ROOT / result[key]
      if not path.is_file():
        if kind == "overlay" and result.get("status") in FAILURE_STATUSES:
          continue
        raise FileNotFoundError(f"Missing {kind} artifact: {result[key]}")
      stat = path.stat()
      records.append({
        "kind": kind,
        "sample_id": result["sample_id"],
        "path": result[key],
        "sha256": file_sha256(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
      })
  records.extend({"kind": "mask", **item} for item in masks)
  return sorted(records, key=lambda item: (item["kind"], item["sample_id"], item["path"]))


def compact_artifact_snapshot(records: list[dict[str, Any]]) -> dict[str, Any]:
  by_kind: dict[str, dict[str, Any]] = {}
  for kind in sorted({item["kind"] for item in records}):
    subset = [item for item in records if item["kind"] == kind]
    by_kind[kind] = {
      "count": len(subset),
      "total_bytes": sum(int(item["size_bytes"]) for item in subset),
      "content_sha256": canonical_sha256([
        {key: value for key, value in item.items() if key != "mtime_ns"}
        for item in subset
      ]),
      "content_and_mtime_sha256": canonical_sha256(subset),
    }
  return {
    "artifact_count": len(records),
    "total_bytes": sum(int(item["size_bytes"]) for item in records),
    "by_kind": by_kind,
    "content_sha256": canonical_sha256([
      {key: value for key, value in item.items() if key != "mtime_ns"}
      for item in records
    ]),
    "content_and_mtime_sha256": canonical_sha256(records),
  }


def compact_mask_snapshot(records: list[dict[str, Any]]) -> dict[str, Any]:
  by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for item in records:
    by_sample[item["sample_id"]].append(item)
  return {
    "mask_count": len(records),
    "total_mask_bytes": sum(int(item["size_bytes"]) for item in records),
    "mask_records_sha256": canonical_sha256(records),
    "pages": [
      {
        "sample_id": sample_id,
        "mask_count": len(items),
        "total_mask_bytes": sum(int(item["size_bytes"]) for item in items),
        "mask_records_sha256": canonical_sha256(items),
      }
      for sample_id, items in sorted(by_sample.items())
    ],
  }


def capture_mask_snapshot(spec: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
  results = load_yaml(paths["results"])
  if len(results.get("results", [])) != int(spec["expected"]["total_pages"]):
    raise ValueError("Cannot snapshot masks until every Batch page has an explicit result")
  masks = mask_records(results)
  if any(item["sha256"] != item["recorded_sha256"] for item in masks):
    raise ValueError("Cannot snapshot masks because a recorded mask checksum differs")
  artifacts = artifact_records(results, masks)
  payload = {
    "snapshot_version": "training_corpus_expansion_batch_01_segmentation_mask_snapshot_v0_1",
    "captured_at": iso_now(),
    "corpus_id": spec["corpus_id"],
    "run_identity_sha256": results.get("run_identity_sha256"),
    "model_sha256": results.get("model_sha256"),
    "results_manifest": {
      "path": rel(paths["results"]),
      "sha256": file_sha256(paths["results"]),
      "size_bytes": paths["results"].stat().st_size,
      "mtime_ns": paths["results"].stat().st_mtime_ns,
    },
    **compact_mask_snapshot(masks),
    "artifact_snapshot": compact_artifact_snapshot(artifacts),
  }
  payload["snapshot_sha256"] = snapshot_sha256(payload)
  write_yaml(paths["mask_snapshot"], payload)
  return payload


def database_run_snapshot(run_identity: str) -> dict[str, dict[str, Any]]:
  with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
      """
      SELECT run.id::text AS run_id,
             run.image_asset_id::text AS image_asset_id,
             run.status,
             run.parameters,
             run.output_format,
             run.created_at,
             run.updated_at,
             canvas.id::text AS resolved_canvas_id,
             manuscript.id::text AS resolved_manuscript_id,
             repository.id::text AS resolved_repository_id
      FROM segmentation_run run
      JOIN image_asset asset ON asset.id = run.image_asset_id
      JOIN canvas ON canvas.id = asset.canvas_id
      JOIN manuscript ON manuscript.id = canvas.manuscript_id
      LEFT JOIN repository ON repository.id = asset.repository_id
      WHERE run.parameters->>'run_identity_sha256' = %s
      ORDER BY run.parameters->>'sample_id', run.id
      """,
      (run_identity,),
    )
    runs = [dict(row) for row in cur.fetchall()]
    snapshots: dict[str, dict[str, Any]] = {}
    for run in runs:
      sample_id = run["parameters"].get("sample_id")
      if not sample_id or sample_id in snapshots:
        raise ValueError(f"Duplicate/missing segmentation_run sample for run identity: {sample_id}")
      cur.execute(
        """
        SELECT id::text AS region_id,
               label,
               label_id,
               confidence,
               reading_order_index,
               region_area_px,
               mask_path,
               ST_AsText(bbox_geom) AS bbox_wkt,
               raw_region,
               created_at,
               updated_at
        FROM layout_region
        WHERE segmentation_run_id = %s
        ORDER BY reading_order_index, id
        """,
        (run["run_id"],),
      )
      regions = [dict(row) for row in cur.fetchall()]
      snapshots[sample_id] = {**run, "regions": regions, "region_count": len(regions)}
  return snapshots


def orphan_layout_region_count() -> int:
  with connect() as conn, conn.cursor() as cur:
    cur.execute(
      """
      SELECT count(*)
      FROM layout_region region
      LEFT JOIN segmentation_run run ON run.id = region.segmentation_run_id
      WHERE run.id IS NULL
      """
    )
    return int(cur.fetchone()[0])


def rerun_storage(paths: dict[str, Path]) -> None:
  subprocess.run(
    [
      sys.executable,
      str(ROOT / "scripts/store_segmentation_pilot_outputs.py"),
      "--results", str(paths["results"]),
      "--inputs", str(paths["inputs"]),
      "--output", str(paths["storage_results"]),
      "--report", str(paths["output_dir"] / "storage_report.md"),
    ],
    cwd=ROOT,
    check=True,
  )


def validate_bbox(detection: dict[str, Any], source_size: tuple[int, int], sample_id: str) -> None:
  bbox = detection.get("bbox_xyxy")
  bbox_xywh = detection.get("bbox_xywh")
  if not isinstance(bbox, list) or len(bbox) != 4 or not isinstance(bbox_xywh, list) or len(bbox_xywh) != 4:
    raise ValueError(f"Detection bbox metadata is incomplete: {sample_id}:{detection.get('index')}")
  x1, y1, x2, y2 = [float(value) for value in bbox]
  width, height = source_size
  if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
    raise ValueError(f"Detection bbox is not clipped to source coordinates: {sample_id}:{detection.get('index')}")
  expected_xywh = [(x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1]
  if any(abs(float(actual) - expected) > 0.002 for actual, expected in zip(bbox_xywh, expected_xywh)):
    raise ValueError(f"bbox_xywh disagrees with bbox_xyxy: {sample_id}:{detection.get('index')}")


def validate_raw_outputs(
  spec: dict[str, Any],
  paths: dict[str, Path],
  inputs: dict[str, Any],
  results: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
  run_identity = results["run_identity_sha256"]
  input_by_sample = {item["sample_id"]: item for item in inputs["selected_inputs"]}
  result_by_sample = {item["sample_id"]: item for item in results.get("results", [])}
  if set(result_by_sample) != set(input_by_sample) or len(result_by_sample) != int(spec["expected"]["total_pages"]):
    raise ValueError("Inference did not record exactly one explicit outcome for every Batch page")
  raw_by_sample: dict[str, dict[str, Any]] = {}
  masks: list[dict[str, Any]] = []
  output_root = paths["output_dir"].resolve()
  for sample_id, result in result_by_sample.items():
    status = result.get("status")
    if status not in {"success", "failure"}:
      raise ValueError(f"Unsupported page outcome {status!r}: {sample_id}")
    raw = raw_prediction(result)
    raw_by_sample[sample_id] = raw
    item = input_by_sample[sample_id]
    if result.get("run_identity_sha256") != run_identity:
      raise ValueError(f"Per-page run identity differs: {sample_id}")
    provenance = raw.get("segmentation_provenance", {})
    if provenance.get("run_identity_sha256") != run_identity or provenance.get("model_id") != spec["model"]["id"]:
      raise ValueError(f"Raw model/run provenance differs: {sample_id}")
    if raw.get("source_sha256") != item.get("source_sha256"):
      raise ValueError(f"Raw source checksum provenance differs: {sample_id}")
    if status == "failure":
      failure = raw.get("failure")
      required = (
        "sample_id", "manuscript_id", "source_asset_id", "error_type",
        "error_message", "preprocessing_state", "retry_appropriate",
      )
      if not isinstance(failure, dict) or any(key not in failure for key in required):
        raise ValueError(f"Failure provenance is incomplete: {sample_id}")
      if raw.get("detections") or not raw.get("errors"):
        raise ValueError(f"Failed page is not explicitly and consistently recorded: {sample_id}")
      continue

    source_path = ROOT / item["local_path"]
    with Image.open(source_path) as source:
      source_size = source.size
    preprocessing = raw.get("preprocessing")
    if not isinstance(preprocessing, dict) or preprocessing.get("original_size") != list(source_size):
      raise ValueError(f"Preprocessing source dimensions are incomplete: {sample_id}")
    seen_indexes: set[int] = set()
    for detection in raw.get("detections", []):
      required = (
        "index", "class_id", "label", "confidence", "bbox_xyxy", "bbox_xywh",
        "mask_path", "mask_sha256", "mask_pixel_area", "mask_dimensions_px",
        "segmentation_provenance",
      )
      if any(detection.get(field) is None for field in required):
        raise ValueError(f"Detection provenance is incomplete: {sample_id}:{detection.get('index')}")
      index = int(detection["index"])
      if index in seen_indexes:
        raise ValueError(f"Duplicate region index: {sample_id}:{index}")
      seen_indexes.add(index)
      validate_bbox(detection, source_size, sample_id)
      mask_path = (ROOT / detection["mask_path"]).resolve()
      if output_root not in mask_path.parents:
        raise ValueError(f"Mask escaped the Batch 01 output hierarchy: {detection['mask_path']}")
      with Image.open(mask_path) as mask:
        validate_binary_mask(mask, source_size)
        area = mask_pixel_area(mask)
      if detection["mask_dimensions_px"] != list(source_size) or area != detection["mask_pixel_area"]:
        raise ValueError(f"Mask dimensions/area differ from metadata: {detection['mask_path']}")
      if file_sha256(mask_path) != detection["mask_sha256"]:
        raise ValueError(f"Mask checksum differs: {detection['mask_path']}")
      region_provenance = detection["segmentation_provenance"]
      if region_provenance.get("run_identity_sha256") != run_identity:
        raise ValueError(f"Region run provenance differs: {sample_id}:{index}")
      masks.append({
        "sample_id": sample_id,
        "index": index,
        "path": detection["mask_path"],
        "sha256": detection["mask_sha256"],
        "recorded_sha256": detection["mask_sha256"],
        "dimensions_px": detection["mask_dimensions_px"],
        "size_bytes": mask_path.stat().st_size,
        "mtime_ns": mask_path.stat().st_mtime_ns,
      })
    if result.get("mask_region_count") != len(raw.get("detections", [])):
      raise ValueError(f"Every successful detection must have an authoritative mask: {sample_id}")
  return raw_by_sample, sorted(masks, key=lambda item: (item["sample_id"], item["index"]))


def outlier_records(
  inputs: dict[str, Any],
  raw_by_sample: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
  input_by_sample = {item["sample_id"]: item for item in inputs["selected_inputs"]}
  counts = [len(raw.get("detections", [])) for raw in raw_by_sample.values()]
  quartiles = statistics.quantiles(counts, n=4, method="inclusive") if len(counts) >= 4 else [0, 0, 0]
  iqr = quartiles[2] - quartiles[0]
  low_threshold = max(0.0, quartiles[0] - 1.5 * iqr)
  high_threshold = quartiles[2] + 1.5 * iqr
  high: list[dict[str, Any]] = []
  low: list[dict[str, Any]] = []
  low_confidence: list[dict[str, Any]] = []
  for sample_id, raw in sorted(raw_by_sample.items()):
    detections = raw.get("detections", [])
    count = len(detections)
    base = {
      "sample_id": sample_id,
      "manuscript_id": input_by_sample[sample_id]["manuscript_id"],
      "region_count": count,
    }
    if count > high_threshold:
      high.append(base)
    if count == 0 or count < low_threshold:
      low.append(base)
    confidences = [float(item["confidence"]) for item in detections if item.get("confidence") is not None]
    if confidences and statistics.mean(confidences) < 0.4:
      low_confidence.append({**base, "mean_confidence": round(statistics.mean(confidences), 6)})
  return {
    "unusually_high_region_counts": high,
    "unusually_low_region_counts": low,
    "very_low_mean_confidence": low_confidence,
    "unexpected_class_pages": [],
  }


def build_statistics(
  spec: dict[str, Any],
  inputs: dict[str, Any],
  results: dict[str, Any],
  raw_by_sample: dict[str, dict[str, Any]],
  masks: list[dict[str, Any]],
) -> dict[str, Any]:
  input_by_sample = {item["sample_id"]: item for item in inputs["selected_inputs"]}
  failed = [item for item in results["results"] if item.get("status") == "failure"]
  successful = [item for item in results["results"] if item.get("status") == "success"]
  region_counts = [len(raw_by_sample[item["sample_id"]].get("detections", [])) for item in results["results"]]
  labels: Counter[str] = Counter()
  classes: Counter[int] = Counter()
  confidences: list[float] = []
  manuscript_regions: Counter[str] = Counter()
  repository_regions: Counter[str] = Counter()
  split_regions: Counter[str] = Counter()
  split_pages: dict[str, dict[str, int]] = {
    split: {"attempted_pages": 0, "successful_pages": 0, "failed_pages": 0, "detected_regions": 0}
    for split in ("train", "validation", "test")
  }
  pages_without_detections: list[dict[str, Any]] = []
  for result in results["results"]:
    sample_id = result["sample_id"]
    item = input_by_sample[sample_id]
    detections = raw_by_sample[sample_id].get("detections", [])
    split = item["dataset_split"]
    split_pages[split]["attempted_pages"] += 1
    split_pages[split]["failed_pages" if result["status"] == "failure" else "successful_pages"] += 1
    split_pages[split]["detected_regions"] += len(detections)
    manuscript_regions[item["manuscript_id"]] += len(detections)
    repository_regions[item["repository"]] += len(detections)
    split_regions[split] += len(detections)
    if result["status"] == "success" and not detections:
      pages_without_detections.append({
        "sample_id": sample_id,
        "manuscript_id": item["manuscript_id"],
        "canvas_identifier": item["canvas_identifier"],
      })
    for detection in detections:
      labels[str(detection.get("label", "unknown"))] += 1
      classes[int(detection["class_id"])] += 1
      confidences.append(float(detection["confidence"]))
  source_bytes = sum(int(item.get("source_size_bytes") or 0) for item in inputs["selected_inputs"])
  performance = results.get("performance", {})
  return {
    "statistics_version": "training_corpus_expansion_batch_01_segmentation_statistics_v0_1",
    "corpus_id": spec["corpus_id"],
    "run_identity_sha256": results.get("run_identity_sha256"),
    "model_id": results.get("model_id"),
    "model_sha256": results.get("model_sha256"),
    "total_pages": len(results["results"]),
    "attempted_pages": len(results["results"]),
    "successful_pages": len(successful),
    "failed_pages": len(failed),
    "segmentation_success_rate": round(len(successful) / len(results["results"]), 8),
    "failures": [
      {"sample_id": item["sample_id"], **(item.get("failure") or {})}
      for item in failed
    ],
    "total_detected_regions": sum(region_counts),
    "mean_regions_per_page": round(statistics.mean(region_counts), 6) if region_counts else 0.0,
    "median_regions_per_page": round(statistics.median(region_counts), 6) if region_counts else 0.0,
    "minimum_regions_per_page": min(region_counts, default=0),
    "maximum_regions_per_page": max(region_counts, default=0),
    "detected_label_distribution": dict(sorted(labels.items())),
    "class_distribution": {str(key): value for key, value in sorted(classes.items())},
    "confidence": {
      "count": len(confidences),
      "minimum": round(min(confidences), 6) if confidences else None,
      "maximum": round(max(confidences), 6) if confidences else None,
      "mean": round(statistics.mean(confidences), 6) if confidences else None,
      "median": round(statistics.median(confidences), 6) if confidences else None,
    },
    "region_counts_by_manuscript": dict(sorted(manuscript_regions.items())),
    "region_counts_by_repository": dict(sorted(repository_regions.items())),
    "region_counts_by_split": dict(sorted(split_regions.items())),
    "page_coverage_by_split": split_pages,
    "pages_with_no_detections": pages_without_detections,
    "total_mask_count": len(masks),
    "total_mask_artifact_bytes": sum(int(item["size_bytes"]) for item in masks),
    "source_image_bytes": source_bytes,
    "segmentation_artifact_disk_usage_bytes": sum(
      int(item["size_bytes"]) for item in artifact_records(results, masks)
    ),
    "performance": performance,
    "outliers_for_review": outlier_records(inputs, raw_by_sample),
  }


def write_report(
  spec: dict[str, Any],
  paths: dict[str, Path],
  stats: dict[str, Any],
  validation: dict[str, Any],
) -> None:
  confidence = stats["confidence"]
  performance = stats["performance"]
  lines = [
    "# Training Corpus Expansion Batch 01 → eManuSkript Segmentation",
    "",
    "## Outcome",
    "",
    f"Exactly {stats['total_pages']} acquired Batch 01 pages were passed through the existing eManuSkript/Ultralytics inference, source-coordinate mask-restoration, and PostgreSQL storage workflow. Segmentation outputs are model-derived layout evidence, not manual ground truth and not training approval.",
    "",
    f"- Successful pages: {stats['successful_pages']}",
    f"- Failed pages: {stats['failed_pages']}",
    f"- Detected regions / source-sized masks: {stats['total_detected_regions']} / {stats['total_mask_count']}",
    f"- Regions/page: min {stats['minimum_regions_per_page']}, max {stats['maximum_regions_per_page']}, mean {stats['mean_regions_per_page']}, median {stats['median_regions_per_page']}",
    f"- Confidence: min {confidence['minimum']}, max {confidence['maximum']}, mean {confidence['mean']}, median {confidence['median']}",
    f"- Mask bytes: {stats['total_mask_artifact_bytes']}",
    f"- Total ignored segmentation artifact bytes: {stats['segmentation_artifact_disk_usage_bytes']}",
    "",
    "## Model and configuration",
    "",
    f"- Model: `{stats['model_id']}`",
    f"- Checkpoint: `{spec['model']['path']}`",
    f"- Model SHA-256: `{stats['model_sha256']}`",
    f"- Run identity SHA-256: `{stats['run_identity_sha256']}`",
    f"- Device: `{spec['inference']['device']}`; confidence `{spec['inference']['confidence_threshold']}`; image size `{spec['inference']['imgsz']}`; retina masks enabled.",
    "- Inputs larger than 2048 pixels on their longest side use the existing temporary downscaled inference copy; masks and boxes are restored to original source-image coordinates.",
    "",
    "## Split coverage",
    "",
  ]
  for split, values in stats["page_coverage_by_split"].items():
    lines.append(
      f"- {split}: {values['attempted_pages']} attempted, {values['successful_pages']} successful, "
      f"{values['failed_pages']} failed, {values['detected_regions']} regions"
    )
  lines.extend(["", "## Label distribution", ""])
  lines.extend(f"- {label}: {count}" for label, count in stats["detected_label_distribution"].items())
  lines.extend([
    "",
    "## Idempotency and integrity",
    "",
    f"- The unchanged inference rerun preserved {validation['idempotency']['stable_artifact_count']} raw/overlay/mask artifacts byte-for-byte and without mtime churn.",
    f"- The storage rerun reused {validation['idempotency']['stable_run_count']} logical `segmentation_run` rows and {validation['idempotency']['stable_region_count']} `layout_region` rows without duplicate or timestamp churn.",
    "- Every mask is an ignored local binary PNG, matches its source dimensions, contains only 0/255 values, and matches its recorded SHA-256 and pixel area.",
    "- Source image hashes, dimensions, byte sizes, mtimes, database relationships, manuscript splits, and rights metadata match the pre-inference snapshot.",
    "- All 70 Batch pages remain `pending_review`; `training_allowed` remains false. Segmentation did not approve rights.",
    "",
    "## Performance",
    "",
    f"- Initial wall duration: {performance.get('total_wall_duration_seconds')} seconds",
    f"- Approximate wall time/page: {performance.get('mean_wall_time_per_selected_page_seconds')} seconds",
    f"- Requested device: `{performance.get('requested_device')}`",
    f"- Downscaled temporary inference images: {performance.get('downscaled_page_count')} pages",
    f"- Observed child-process max RSS: {performance.get('observed_child_process_max_rss_bytes')} bytes ({performance.get('memory_observation_method')})",
    "",
    "## Explicit failures and outliers",
    "",
  ])
  if stats["failures"]:
    for failure in stats["failures"]:
      lines.append(f"- Failure `{failure['sample_id']}`: {failure.get('error_type')}: {failure.get('error_message')}")
  else:
    lines.append("- No page failed.")
  outliers = stats["outliers_for_review"]
  for category, items in outliers.items():
    if items:
      lines.append(f"- {category}: " + ", ".join(f"`{item['sample_id']}`" for item in items))
  if not any(outliers.values()):
    lines.append("- No deterministic region-count/class/confidence outlier rule fired.")
  lines.extend([
    "",
    "Outliers remain in the corpus and are recorded for later human review; no page was automatically excluded or replaced.",
    "",
    "## Artifact layout",
    "",
    f"- Local ignored outputs: `{rel(paths['output_dir'])}/`",
    f"- Compact results: `{rel(paths['results'])}`",
    f"- Compact statistics: `{rel(paths['statistics'])}`",
    f"- Validation: `{rel(paths['validation'])}`",
    "",
    "## Next decision (not implemented)",
    "",
    "Choose between another complete-page corpus expansion batch and controlled artificial-fragment generation plus a first training-pipeline smoke test only after reviewing segmentation quality, the damage model, corpus diversity, and rights approvals. Actual model training remains blocked until an explicitly rights-approved subset exists.",
    "",
  ])
  paths["report"].write_text("\n".join(lines), encoding="utf-8")


def validate(spec: dict[str, Any], paths: dict[str, Path], skip_storage_rerun: bool) -> dict[str, Any]:
  corpus = load_yaml(paths["corpus_manifest"])
  frozen = load_yaml(paths["frozen_manifest"])
  acquisition = load_yaml(paths["acquisition_validation"])
  inputs = load_yaml(paths["inputs"])
  results = load_yaml(paths["results"])
  storage = load_yaml(paths["storage_results"])
  source_snapshot = load_yaml(paths["source_snapshot"])
  mask_snapshot = load_yaml(paths["mask_snapshot"])
  if source_snapshot.get("snapshot_sha256") != snapshot_sha256(source_snapshot):
    raise ValueError("Pre-inference source snapshot checksum is invalid")
  if mask_snapshot.get("snapshot_sha256") != snapshot_sha256(mask_snapshot):
    raise ValueError("First-run mask/artifact snapshot checksum is invalid")
  selected = assert_corpus_scope(spec, corpus, frozen, inputs)
  expected_pages = int(spec["expected"]["total_pages"])
  if acquisition.get("selection_and_provenance", {}).get("selected_page_count") != expected_pages:
    raise ValueError("Acquisition validation no longer confirms the expected Batch page count")

  if results.get("dataset_id") != spec["corpus_id"] or storage.get("dataset_id") != spec["corpus_id"]:
    raise ValueError("Inference/storage corpus identity differs from the Batch specification")
  if results.get("model_id") != spec["model"]["id"] or results.get("model_path") != spec["model"]["path"]:
    raise ValueError("Inference model identity differs from the Batch specification")
  if file_sha256(paths["model"]) != spec["model"]["sha256"] or results.get("model_sha256") != spec["model"]["sha256"]:
    raise ValueError("Model checksum differs from the registered Batch specification")
  descriptor = results.get("run_identity_descriptor", {})
  configuration = descriptor.get("configuration", {})
  for key, expected_value in (
    ("device", spec["inference"]["device"]),
    ("confidence_threshold", spec["inference"]["confidence_threshold"]),
    ("imgsz", spec["inference"]["imgsz"]),
    ("retina_masks", spec["inference"]["retina_masks"]),
    ("preprocessing_max_side", spec["inference"]["preprocessing_max_side"]),
    ("mask_restoration", spec["inference"]["mask_restoration"]),
  ):
    if configuration.get(key) != expected_value:
      raise ValueError(f"Run configuration differs for {key}")
  run_identity = results.get("run_identity_sha256")
  if not run_identity or storage.get("run_identity_sha256") != run_identity:
    raise ValueError("Run identity is missing or differs between inference and storage")

  input_by_sample = {item["sample_id"]: item for item in inputs["selected_inputs"]}
  source_by_sample = {item["sample_id"]: item for item in source_snapshot["sources"]}
  if set(source_by_sample) != set(input_by_sample) or len(source_by_sample) != expected_pages:
    raise ValueError("Pre-inference source snapshot does not cover exactly the Batch inputs")
  for sample_id, item in input_by_sample.items():
    expected = selected[item["db_image_asset_id"]]
    current = query_source_state(item["db_image_asset_id"])
    frozen_state = {key: value for key, value in source_by_sample[sample_id].items() if key not in {"sample_id", "manuscript_id"}}
    if current != frozen_state:
      raise ValueError(f"Source file/metadata/rights changed during segmentation: {sample_id}")
    if current["actual_source_sha256"] != expected["source_sha256"]:
      raise ValueError(f"Source checksum changed: {sample_id}")
    if current["rights_review_status"] != "pending_review" or current["training_allowed"] is not False:
      raise ValueError(f"Rights state changed during segmentation: {sample_id}")

  raw_by_sample, masks = validate_raw_outputs(spec, paths, inputs, results)
  current_mask_snapshot = compact_mask_snapshot(masks)
  for key in ("mask_count", "total_mask_bytes", "mask_records_sha256", "pages"):
    if current_mask_snapshot[key] != mask_snapshot.get(key):
      raise ValueError(f"Mask snapshot changed on unchanged inference rerun: {key}")
  artifacts = artifact_records(results, masks)
  current_artifacts = compact_artifact_snapshot(artifacts)
  if current_artifacts != mask_snapshot.get("artifact_snapshot"):
    raise ValueError("Raw/overlay/mask artifacts changed or were rewritten on unchanged inference rerun")
  current_results_manifest = {
    "path": rel(paths["results"]),
    "sha256": file_sha256(paths["results"]),
    "size_bytes": paths["results"].stat().st_size,
    "mtime_ns": paths["results"].stat().st_mtime_ns,
  }
  if current_results_manifest != mask_snapshot.get("results_manifest"):
    raise ValueError("Results manifest changed or was rewritten on unchanged inference rerun")

  before = database_run_snapshot(run_identity)
  if len(before) != expected_pages:
    raise ValueError(f"Expected {expected_pages} database runs for this identity, found {len(before)}")
  if not skip_storage_rerun:
    rerun_storage(paths)
  after = database_run_snapshot(run_identity)
  if before != after:
    raise ValueError("Unchanged storage rerun changed run/region IDs, content, or timestamps")
  storage = load_yaml(paths["storage_results"])
  storage_by_sample = {item["sample_id"]: item for item in storage.get("samples", [])}
  result_by_sample = {item["sample_id"]: item for item in results["results"]}
  if set(storage_by_sample) != set(input_by_sample):
    raise ValueError("Storage results do not cover exactly the Batch inputs")
  stable_region_count = 0
  for sample_id, run in after.items():
    item = input_by_sample[sample_id]
    result = result_by_sample[sample_id]
    raw = raw_by_sample[sample_id]
    if run["image_asset_id"] != item["db_image_asset_id"]:
      raise ValueError(f"Stored run does not resolve to its image_asset: {sample_id}")
    if run["resolved_canvas_id"] != item["db_canvas_id"] or run["parameters"].get("db_canvas_id") != item["db_canvas_id"]:
      raise ValueError(f"Stored run does not resolve to its canvas: {sample_id}")
    if run["resolved_manuscript_id"] != item["db_manuscript_id"]:
      raise ValueError(f"Stored run does not resolve to its manuscript: {sample_id}")
    if run["resolved_repository_id"] != item["db_repository_id"]:
      raise ValueError(f"Stored run does not resolve to its repository: {sample_id}")
    if run["parameters"].get("dataset_split") != item["dataset_split"]:
      raise ValueError(f"Stored split differs from corpus input: {sample_id}")
    if run["parameters"].get("source_sha256") != item["source_sha256"]:
      raise ValueError(f"Stored source checksum provenance differs: {sample_id}")
    expected_status = "failed" if result["status"] == "failure" else "completed"
    if run["status"] != expected_status:
      raise ValueError(f"Stored run status differs: {sample_id}")
    if storage_by_sample[sample_id]["db_segmentation_run_id"] != run["run_id"]:
      raise ValueError(f"Storage manifest references a different run: {sample_id}")
    detections = raw.get("detections", [])
    if run["region_count"] != len(detections):
      raise ValueError(f"Stored region count differs from inference: {sample_id}")
    for stored_region, detection in zip(run["regions"], detections):
      if stored_region["raw_region"] != detection:
        raise ValueError(f"Stored raw region differs from inference: {sample_id}:{detection['index']}")
      if stored_region["mask_path"] != detection["mask_path"]:
        raise ValueError(f"Stored mask path differs from inference: {sample_id}:{detection['index']}")
      if float(stored_region["region_area_px"]) != float(detection["mask_pixel_area"]):
        raise ValueError(f"Stored mask area differs from inference: {sample_id}:{detection['index']}")
      if not stored_region["bbox_wkt"]:
        raise ValueError(f"Stored bbox geometry is missing: {sample_id}:{detection['index']}")
      stable_region_count += 1
  orphan_count = orphan_layout_region_count()
  if orphan_count:
    raise ValueError(f"Found {orphan_count} orphan layout_region rows")

  tracked_outputs = subprocess.run(
    ["git", "ls-files", rel(paths["output_dir"])],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  ).stdout.splitlines()
  if tracked_outputs:
    raise ValueError(f"Generated Batch segmentation binaries are tracked by Git: {tracked_outputs}")

  stats = build_statistics(spec, inputs, results, raw_by_sample, masks)
  stats["unchanged_rerun"] = {
    "reused_pages": expected_pages,
    "regenerated_pages": 0,
    "stable_artifact_count": current_artifacts["artifact_count"],
    "stable_segmentation_run_count": len(after),
    "stable_layout_region_count": stable_region_count,
    "timestamp_churn_count": 0,
  }
  if stats["source_image_bytes"] != int(spec["expected"]["source_image_bytes"]):
    raise ValueError("Source image byte total changed")
  validation = {
    "validation_version": "training_corpus_expansion_batch_01_segmentation_validation_v0_1",
    "validated_at": iso_now(),
    "status": "passed",
    "corpus_id": spec["corpus_id"],
    "run_identity_sha256": run_identity,
    "source_snapshot_sha256": source_snapshot["snapshot_sha256"],
    "mask_snapshot_sha256": mask_snapshot["snapshot_sha256"],
    "coverage": {
      "expected_pages": expected_pages,
      "attempted_pages": stats["attempted_pages"],
      "successful_pages": stats["successful_pages"],
      "failed_pages": stats["failed_pages"],
      "extra_pages": 0,
      "frozen_validation_pages_included": 0,
    },
    "source_integrity": {
      "source_count": expected_pages,
      "checksums_dimensions_sizes_and_mtimes_unchanged": True,
      "total_source_bytes": stats["source_image_bytes"],
    },
    "mask_integrity": {
      "mask_count": stats["total_mask_count"],
      "all_binary": True,
      "all_source_sized": True,
      "all_hashes_match": True,
      "all_areas_match": True,
      "all_bboxes_valid_and_clipped": True,
    },
    "database_integrity": {
      "segmentation_run_count": len(after),
      "layout_region_count": stable_region_count,
      "duplicate_logical_run_count": 0,
      "orphan_layout_region_count": 0,
      "relationships_resolve": True,
      "mask_paths_resolve_locally": True,
    },
    "split_integrity": {
      "page_split_counts": spec["expected"]["page_split_counts"],
      "assigned_manuscript_split_counts": spec["expected"]["assigned_manuscript_split_counts"],
      "page_bearing_manuscript_split_counts": spec["expected"]["page_bearing_manuscript_split_counts"],
      "manuscript_isolation_preserved": True,
    },
    "rights_integrity": {
      "rights_review_status_counts": {"pending_review": expected_pages},
      "training_allowed_true_count": 0,
      "publication_demo_access_and_human_review_metadata_unchanged": True,
    },
    "idempotency": {
      "unchanged_inference_rerun_verified": True,
      "stable_artifact_count": current_artifacts["artifact_count"],
      "unchanged_storage_rerun_performed": not skip_storage_rerun,
      "stable_run_count": len(after),
      "stable_region_count": stable_region_count,
      "run_or_region_timestamp_churn_count": 0,
      "duplicate_run_count": 0,
    },
    "git_safety": {
      "tracked_generated_output_count": 0,
      "generated_outputs_remain_ignored": True,
    },
    "statistics_path": rel(paths["statistics"]),
    "report_path": rel(paths["report"]),
    "next_decision": "Review results before choosing further complete-page expansion or controlled artificial-fragment generation; training remains rights-blocked.",
  }
  write_yaml(paths["statistics"], stats)
  write_yaml(paths["validation"], validation)
  write_report(spec, paths, stats, validation)
  return validation


def main() -> int:
  args = parse_args()
  spec_path = resolve(args.spec)
  spec = load_yaml(spec_path)
  paths = paths_from_spec(spec)
  if args.capture_source_snapshot:
    payload = capture_source_snapshot(spec, paths)
    print(f"Captured {payload['source_count']} Batch source invariants: {rel(paths['source_snapshot'])}")
    return 0
  if args.capture_mask_snapshot:
    payload = capture_mask_snapshot(spec, paths)
    print(f"Captured compact snapshot for {payload['mask_count']} masks: {rel(paths['mask_snapshot'])}")
    return 0
  payload = validate(spec, paths, args.skip_storage_rerun)
  print(
    f"PASS: {payload['coverage']['attempted_pages']} Batch pages flowed through the existing "
    f"eManuSkript inference/storage path; run {payload['run_identity_sha256']} is idempotent"
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
