from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from PIL import Image

from scripts import run_segmentation_pilot as runner
from scripts import store_segmentation_pilot_outputs as storage
from scripts import validate_training_corpus_expansion_batch_01_segmentation as validator
from src.evaluation.segmentation_masks import (
  file_sha256,
  mask_pixel_area,
  restore_mask_to_source,
  save_binary_mask,
  validate_binary_mask,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "data/metadata/training_corpus_expansion_batch_01_segmentation_spec.yaml"


def load_yaml(path: Path) -> dict:
  return yaml.safe_load(path.read_text(encoding="utf-8"))


def batch_payloads() -> tuple[dict, dict, dict, dict]:
  spec = load_yaml(SPEC_PATH)
  inputs = load_yaml(ROOT / spec["artifacts"]["inputs"])
  corpus = load_yaml(ROOT / spec["source"]["corpus_manifest"])
  frozen = load_yaml(ROOT / spec["source"]["frozen_validation_corpus_manifest"])
  return spec, inputs, corpus, frozen


def test_batch_page_enumeration_returns_exactly_acquired_pages():
  spec, inputs, corpus, frozen = batch_payloads()
  selected = validator.assert_corpus_scope(spec, corpus, frozen, inputs)

  assert len(selected) == 70
  assert {item["db_image_asset_id"] for item in inputs["selected_inputs"]} == set(selected)
  assert all(item["db_canvas_id"] and item["db_image_asset_id"] for item in inputs["selected_inputs"])


def test_frozen_validation_pages_and_manuscripts_are_excluded():
  _, inputs, corpus, frozen = batch_payloads()
  batch_canvases = {item["canvas_identifier"] for item in inputs["selected_inputs"]}
  frozen_canvases = validator.selected_canvas_identifiers(frozen)
  batch_manuscripts = {item["id"] for item in corpus["manuscripts"]}
  frozen_manuscripts = {item["id"] for item in frozen["manuscripts"]}

  assert batch_canvases.isdisjoint(frozen_canvases)
  assert batch_manuscripts.isdisjoint(frozen_manuscripts)


def test_existing_manuscript_splits_are_preserved():
  spec, inputs, _, _ = batch_payloads()
  page_splits = Counter(item["dataset_split"] for item in inputs["selected_inputs"])
  manuscript_splits: dict[str, set[str]] = defaultdict(set)
  for item in inputs["selected_inputs"]:
    manuscript_splits[item["manuscript_id"]].add(item["dataset_split"])

  assert dict(page_splits) == spec["expected"]["page_split_counts"]
  assert all(len(values) == 1 for values in manuscript_splits.values())


def test_segmentation_run_identity_is_deterministic(tmp_path: Path, monkeypatch):
  monkeypatch.setattr(runner, "ROOT", tmp_path)
  model = tmp_path / "model.pt"
  page = tmp_path / "page.jpg"
  model.write_bytes(b"model")
  page.write_bytes(b"page")
  payload = {"dataset_id": "batch", "pilot_run_id": "run", "model_id": "model"}
  sample = {
    "sample_id": "sample",
    "local_path": "page.jpg",
    "db_image_asset_id": "asset",
    "db_canvas_id": "canvas",
    "manuscript_id": "manuscript",
    "dataset_split": "train",
  }
  kwargs = {
    "device": "cpu",
    "conf": 0.25,
    "imgsz": 320,
    "software_versions": {"torch": "test", "ultralytics": "test"},
  }

  assert runner.build_run_identity(payload, [sample], model, **kwargs) == runner.build_run_identity(
    payload, [sample], model, **kwargs
  )


def test_prepared_source_checksums_and_rights_match_registered_manifest():
  _, inputs, corpus, _ = batch_payloads()
  selected = validator.selected_corpus_pages(corpus, 70)
  for item in inputs["selected_inputs"]:
    expected = selected[item["db_image_asset_id"]]
    assert item["source_sha256"] == expected["source_sha256"]
    assert item["rights_review_status"] == "pending_review"
    assert item["training_allowed"] is False


def test_downscaled_mask_restores_to_source_dimensions_and_stays_binary():
  model_mask = Image.new("L", (32, 20), 0)
  model_mask.paste(255, (4, 3, 20, 14))
  restored = restore_mask_to_source(
    model_mask,
    inference_size=(1600, 1000),
    source_size=(3200, 2000),
  )

  validate_binary_mask(restored, (3200, 2000))
  assert restored.size == (3200, 2000)
  assert mask_pixel_area(restored) > 0


def test_binary_mask_hash_area_and_dimensions_are_consistent(tmp_path: Path):
  mask = Image.new("L", (20, 12), 0)
  mask.paste(255, (2, 3, 9, 10))
  path = tmp_path / "mask.png"
  recorded_hash = save_binary_mask(mask, path)

  with Image.open(path) as stored:
    validate_binary_mask(stored, (20, 12))
    assert mask_pixel_area(stored) == 49
  assert file_sha256(path) == recorded_hash


def test_bbox_scaling_is_clipped_and_xywh_is_reconciled():
  detection = {
    "index": 0,
    "bbox_xyxy": [-2.0, 1.0, 102.0, 60.0],
    "bbox_xywh": [50.0, 30.5, 104.0, 59.0],
  }
  scaled = runner.scale_detections(
    [detection],
    scale_x=2.0,
    scale_y=2.0,
    source_size=(200, 100),
  )[0]

  assert scaled["bbox_xyxy"] == [0.0, 2.0, 200.0, 100.0]
  assert scaled["bbox_xywh"] == [100.0, 51.0, 200.0, 98.0]
  validator.validate_bbox(scaled, (200, 100), "sample")


def test_checksum_verified_segmentation_rerun_skips_subprocess(tmp_path: Path, monkeypatch):
  monkeypatch.setattr(runner, "ROOT", tmp_path)
  sample = {"sample_id": "sample", "sample_kind": "full_page", "local_path": "page.jpg"}
  output = tmp_path / "outputs"
  mask_path = output / "masks/sample/region_0000.png"
  mask_path.parent.mkdir(parents=True)
  mask = Image.new("L", (5, 4), 255)
  mask_hash = save_binary_mask(mask, mask_path)
  raw_path = output / "raw/sample.json"
  raw_path.parent.mkdir(parents=True)
  raw_path.write_text(json.dumps({
    "status": "success",
    "orig_shape": [4, 5],
    "segmentation_provenance": {"run_identity_sha256": "identity"},
    "detections": [{
      "index": 0,
      "mask_path": "outputs/masks/sample/region_0000.png",
      "mask_dimensions_px": [5, 4],
      "mask_sha256": mask_hash,
      "mask_pixel_area": 20,
    }],
  }), encoding="utf-8")
  overlay = output / "overlays/sample_overlay.jpg"
  overlay.parent.mkdir(parents=True)
  overlay.write_bytes(b"overlay")

  def unexpected_subprocess(*args, **kwargs):  # noqa: ARG001
    raise AssertionError("verified cache should be resolved before launching a subprocess")

  monkeypatch.setattr(runner.subprocess, "run", unexpected_subprocess)
  result = runner.run_sample_subprocess(
    sample,
    tmp_path / "inputs.yaml",
    output,
    "cpu",
    0.25,
    320,
    force=False,
    run_identity={"run_identity_sha256": "identity"},
  )

  assert result["status"] == "success"
  assert result["artifact_disposition"] == "reused_checksum_verified"


class FakeCursor:
  def __init__(self, row=None, rows=None):
    self.row = row
    self.rows = rows or []

  def execute(self, *args, **kwargs):  # noqa: ARG002
    return None

  def fetchone(self):
    return self.row

  def fetchall(self):
    return self.rows


def test_idempotent_storage_helpers_recognize_unchanged_run_and_regions():
  desired = {
    "image_asset_id": "asset",
    "fragment_id": None,
    "model_name": "model",
    "model_version": "1",
    "model_source": "model.pt",
    "parameters": {"run_identity_sha256": "identity"},
    "status": "completed",
    "output_path": "raw.json",
    "output_format": "ultralytics_segmentation_json_with_binary_masks",
    "confidence_summary": {"count": 1},
    "raw_output": {"sample_id": "sample"},
  }
  row = tuple(desired[key] for key in desired)
  detection = {"index": 0, "label": "Main script black"}

  assert storage.existing_run_content_matches(FakeCursor(row=row), "run", desired)
  assert storage.existing_layout_regions_match(FakeCursor(rows=[(detection,)]), "run", [detection])


def test_failure_outcome_records_required_provenance(tmp_path: Path, monkeypatch):
  monkeypatch.setattr(runner, "ROOT", tmp_path)
  image_path = tmp_path / "page.jpg"
  Image.new("RGB", (8, 6), "white").save(image_path)
  sample = {
    "sample_id": "sample",
    "sample_kind": "full_page",
    "local_path": "page.jpg",
    "manuscript_id": "ms",
    "db_image_asset_id": "asset",
  }
  error = runner.PageSegmentationError(ValueError("bad prediction"), {"strategy": "original"})

  result = runner.build_error_result(
    sample,
    tmp_path / "outputs",
    error,
    {"run_identity_sha256": "identity", "descriptor": {}},
  )
  raw = json.loads((tmp_path / result["raw_output_path"]).read_text(encoding="utf-8"))

  assert result["status"] == "failure"
  assert raw["failure"]["error_type"] == "ValueError"
  assert raw["failure"]["preprocessing_state"] == {"strategy": "original"}
  assert "retry_appropriate" in raw["failure"]


def test_batch_generated_binary_paths_are_git_ignored_and_untracked():
  candidates = [
    "outputs/training_corpus_segmentation/batch_01/masks/sample/region_0000.png",
    "outputs/training_corpus_segmentation/batch_01/overlays/sample_overlay.jpg",
    "outputs/training_corpus_segmentation/batch_01/raw/sample.json",
  ]
  ignored = subprocess.run(
    ["git", "check-ignore", *candidates],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  ).stdout.splitlines()
  tracked = subprocess.run(
    ["git", "ls-files", "outputs/training_corpus_segmentation/batch_01"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  ).stdout.splitlines()

  assert sorted(ignored) == sorted(candidates)
  assert tracked == []
