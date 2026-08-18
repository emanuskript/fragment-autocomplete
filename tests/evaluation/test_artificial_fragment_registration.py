from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image
import pytest
import yaml

from src.evaluation.artificial_fragment_registration import (
  SourceDatabaseContext,
  TaskRegistrationRecord,
  canonical_json,
  load_registration_records,
  register_records,
)


def _sha(path: Path) -> str:
  return sha256(path.read_bytes()).hexdigest()


def _artifact(root: Path, task_id: str, name: str, size: tuple[int, int]) -> dict:
  path = root / "outputs" / task_id / f"{name}.png"
  path.parent.mkdir(parents=True, exist_ok=True)
  Image.new("L", size, 255).save(path)
  return {
    "path": path.relative_to(root).as_posix(),
    "sha256": _sha(path),
    "dimensions_px": list(size),
  }


def _write_task(
  root: Path,
  *,
  task_id: str = "task_1",
  task_group: str = "core_pilot",
  seed: int = 42,
  source_canvas_id: str | None = None,
  source_image_asset_id: str | None = None,
) -> tuple[dict, dict]:
  source_canvas_id = source_canvas_id or str(uuid4())
  source_image_asset_id = source_image_asset_id or str(uuid4())
  segmentation_run_id = str(uuid4())
  source_path = root / "source.png"
  if not source_path.exists():
    Image.new("RGB", (4, 4), "white").save(source_path)
  source_sha256 = _sha(source_path)
  artifacts = {
    "fragment_image": _artifact(root, task_id, "fragment", (2, 2)),
    "observed_fragment_survival_mask": _artifact(root, task_id, "observed_mask", (2, 2)),
    "source_survival_mask": _artifact(root, task_id, "survival", (4, 4)),
    "source_damage_mask": _artifact(root, task_id, "damage", (4, 4)),
  }
  task = {
    "task_id": task_id,
    "task_group": task_group,
    "generation_version": "artificial_fragment_generator_v0_1_1",
    "generation_fingerprint_sha256": "f" * 64,
    "source_sample_id": "fp_test",
    "source_image_asset_id": source_image_asset_id,
    "source_canvas_id": source_canvas_id,
    "source_path": source_path.relative_to(root).as_posix(),
    "source_sha256": source_sha256,
    "source_sha256_after_generation": source_sha256,
    "source_integrity_verified": True,
    "original_image_dimensions_px": [4, 4],
    "generated_fragment_dimensions_px": [2, 2],
    "source_provenance": {"source": "fixture"},
    "mask_family": "rectangular",
    "random_seed": seed,
    "requested_severity": 0.5,
    "measured_severity": 0.5,
    "surviving_fraction": 0.5,
    "rotation_degrees": 0.0,
    "scale": 1.0,
    "mask_semantics": {
      "survival_mask": "255=survives",
      "damage_mask": "255=removed",
    },
    "artifacts": artifacts,
    "fragment_contour": {
      "source_page_xy_px": [[1, 1], [3, 1], [3, 3], [1, 3]],
      "observed_fragment_xy_px": [[0, 0], [2, 0], [2, 2], [0, 2]],
    },
    "fragment_bounding_box": {
      "source_page_bbox_xyxy_px": [1, 1, 3, 3],
      "observed_fragment_bbox_xyxy_px": [0, 0, 2, 2],
    },
    "crop_transform": {
      "source_bbox_xyxy_px": [1, 1, 3, 3],
      "source_to_observed_fragment_matrix": [[1, 0, -1], [0, 1, -1], [0, 0, 1]],
      "observed_fragment_to_source_matrix": [[1, 0, 1], [0, 1, 1], [0, 0, 1]],
    },
    "ground_truth_placement": {
      "coordinate_space": "source_page",
      "placement_is_known": True,
      "source_canvas_id": source_canvas_id,
      "source_image_asset_id": source_image_asset_id,
      "source_page_dimensions_px": [4, 4],
      "source_contour_xy_px": [[1, 1], [3, 1], [3, 3], [1, 3]],
      "source_bbox_xyxy_px": [1, 1, 3, 3],
    },
    "layout_survival_estimate": {
      "geometry_method": "segmentation_mask",
      "segmentation_run_provenance": {
        "db_segmentation_run_id": segmentation_run_id,
        "model_id": "best_emanuskript_segmentation",
      },
      "regions": [{"source_region_index": 0, "surviving_fraction": 0.5}],
      "summary": {"total_regions": 1, "geometry_method": "segmentation_mask"},
    },
    "degradation_profile": {
      "profile": "mask_crop_rotation_scale_only",
      "contains_inferred_or_reconstructed_content": False,
    },
    "split_name": "demo",
    "parameters": {
      "requested_severity": 0.5,
      "measured_severity": 0.5,
      "surviving_fraction": 0.5,
      "rotation_degrees": 0.0,
      "scale": 1.0,
      "mask_parameters": {"family": "rectangular", "seed": seed},
    },
  }
  metadata_path = root / "outputs" / task_id / "metadata.json"
  metadata_path.write_text(json.dumps(task), encoding="utf-8")
  metadata_artifact = {
    "path": metadata_path.relative_to(root).as_posix(),
    "sha256": _sha(metadata_path),
  }
  index = {
    name: deepcopy(task[name])
    for name in (
      "task_id",
      "task_group",
      "generation_version",
      "generation_fingerprint_sha256",
      "source_canvas_id",
      "source_image_asset_id",
      "source_sha256",
    )
  }
  index["artifacts"] = {"metadata": metadata_artifact}
  return index, task


def _write_manifest(root: Path, core: list[dict], sanity: list[dict]) -> Path:
  path = root / "manifest.yaml"
  path.write_text(
    yaml.safe_dump(
      {
        "generated_task_count": len(core) + len(sanity),
        "core_pilot_tasks": core,
        "transformation_sanity_tasks": sanity,
      },
      sort_keys=False,
    ),
    encoding="utf-8",
  )
  return path


class FakeStore:
  def __init__(self, record: TaskRegistrationRecord, *, include_source: bool = True):
    self.sources = {}
    if include_source:
      self.sources[record.source_image_asset_id] = SourceDatabaseContext(
        image_asset_id=record.source_image_asset_id,
        canvas_id=record.source_canvas_id,
        local_path=record.source_path,
        checksum_sha256=record.source_sha256,
        width_px=record.source_dimensions_px[0],
        height_px=record.source_dimensions_px[1],
      )
    self.runs = {record.segmentation_run_id: record.source_image_asset_id}
    self.tasks: dict[str, dict] = {}

  def source_context(self, image_asset_id: str):
    return self.sources.get(image_asset_id)

  def segmentation_run_image_asset_id(self, segmentation_run_id: str):
    return self.runs.get(segmentation_run_id)

  def upsert_task(self, record: TaskRegistrationRecord) -> str:
    values = record.database_values()
    existing = self.tasks.get(record.database_id)
    if existing is None:
      self.tasks[record.database_id] = deepcopy(values)
      return "inserted"
    if canonical_json(existing) == canonical_json(values):
      return "matched"
    self.tasks[record.database_id] = deepcopy(values)
    return "updated"


def _one_record(tmp_path: Path) -> TaskRegistrationRecord:
  index, _ = _write_task(tmp_path)
  manifest = _write_manifest(tmp_path, [index], [])
  return load_registration_records(
    manifest,
    tmp_path,
    expected_core_tasks=1,
    expected_sanity_tasks=0,
  )[0]


def test_first_insertion_and_idempotent_rerun(tmp_path: Path):
  record = _one_record(tmp_path)
  store = FakeStore(record)
  first = register_records(store, [record])
  first_state = deepcopy(store.tasks)
  second = register_records(store, [record])
  assert first == {"inserted": 1, "updated": 0, "matched": 0, "validated": 1}
  assert second == {"inserted": 0, "updated": 0, "matched": 1, "validated": 1}
  assert store.tasks == first_state


def test_bad_source_id_is_rejected(tmp_path: Path):
  record = _one_record(tmp_path)
  with pytest.raises(ValueError, match="Source image_asset is missing"):
    register_records(FakeStore(record, include_source=False), [record])


def test_missing_artifact_is_rejected(tmp_path: Path):
  index, task = _write_task(tmp_path)
  (tmp_path / task["artifacts"]["fragment_image"]["path"]).unlink()
  manifest = _write_manifest(tmp_path, [index], [])
  with pytest.raises(FileNotFoundError, match="fragment_image"):
    load_registration_records(manifest, tmp_path, expected_core_tasks=1, expected_sanity_tasks=0)


def test_checksum_mismatch_is_rejected(tmp_path: Path):
  index, task = _write_task(tmp_path)
  path = tmp_path / task["artifacts"]["source_damage_mask"]["path"]
  path.write_bytes(path.read_bytes() + b"changed")
  manifest = _write_manifest(tmp_path, [index], [])
  with pytest.raises(ValueError, match="Checksum mismatch"):
    load_registration_records(manifest, tmp_path, expected_core_tasks=1, expected_sanity_tasks=0)


def test_duplicate_scientific_configuration_is_rejected(tmp_path: Path):
  shared_canvas = str(uuid4())
  shared_asset = str(uuid4())
  first, _ = _write_task(
    tmp_path,
    task_id="task_1",
    seed=99,
    source_canvas_id=shared_canvas,
    source_image_asset_id=shared_asset,
  )
  second, _ = _write_task(
    tmp_path,
    task_id="task_2",
    seed=99,
    source_canvas_id=shared_canvas,
    source_image_asset_id=shared_asset,
  )
  manifest = _write_manifest(tmp_path, [first, second], [])
  with pytest.raises(ValueError, match="Duplicate scientific task configuration"):
    load_registration_records(manifest, tmp_path, expected_core_tasks=2, expected_sanity_tasks=0)


def test_database_json_serialization_preserves_required_metadata(tmp_path: Path):
  record = _one_record(tmp_path)
  serialized = json.loads(json.dumps(record.database_values()))
  parameters = serialized["parameters"]
  assert parameters["requested_severity"] == 0.5
  assert parameters["fragment_artifact"]["sha256"]
  assert parameters["survival_mask_artifact"]["path"].endswith("survival.png")
  assert parameters["damage_mask_artifact"]["path"].endswith("damage.png")
  assert parameters["source_space_contour_xy_px"]
  assert parameters["source_to_fragment_transform"]
  assert parameters["fragment_to_source_transform"]
  assert parameters["segmentation_run_provenance"]["db_segmentation_run_id"]
  assert parameters["layout_survival_measurements"][0]["source_region_index"] == 0
  assert parameters["layout_survival_summary"]["total_regions"] == 1
  assert parameters["binary_data_stored_in_postgresql"] is False
