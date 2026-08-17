"""Tests for deterministic artificial-fragment generation and ground truth."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.evaluation.artificial_fragments import (
  ArtifactPaths,
  GenerationConfig,
  SEVERITY_TOLERANCE,
  apply_transform,
  build_source_masks,
  generate_fragment_task,
  sha256_file,
  source_pages_from_resolved_dataset,
  source_to_observed_transform,
)
from src.evaluation.layout_survival import clip_bbox_xyxy, estimate_layout_survival


def source_page(local_path: str = "inputs/page.png"):
  return source_pages_from_resolved_dataset(
    {
      "full_pages": [
        {
          "id": "fp_test",
          "category": "clean_simple",
          "source": "fixture",
          "url": "https://example.test/page",
          "local_path": local_path,
          "registration_status": "registered",
          "rights_review_status": "pending_review",
          "training_allowed": False,
          "publication_allowed": False,
          "demo_allowed": False,
          "access_level": "internal",
          "sample_kind": "full_page",
          "db_ids": {"canvas_id": "canvas-1", "image_asset_id": "image-1"},
          "hsp_normalized_metadata": {"object_form": "codex"},
        }
      ]
    }
  )[0]


def paths(root: Path, name: str) -> ArtifactPaths:
  output = root / "outputs" / name
  return ArtifactPaths(
    fragment=output / "fragment.png",
    observed_fragment_mask=output / "observed_mask.png",
    source_survival_mask=output / "survival.png",
    source_damage_mask=output / "damage.png",
    metadata=output / "metadata.json",
  )


def provenance(shape: tuple[int, int] = (80, 100)) -> dict:
  height, width = shape
  return {
    "sample_id": "fp_test",
    "pilot_run_id": "pilot-test",
    "db_segmentation_run_id": "run-test",
    "model_id": "emanuskript-test",
    "orig_shape": [height, width],
    "geometry_method": "rasterized_bbox_xyxy",
  }


def detections() -> list[dict]:
  return [
    {
      "index": 0,
      "class_id": 4,
      "label": "Main script black",
      "confidence": 0.9,
      "bbox_xyxy": [10.0, 10.0, 40.0, 30.0],
    },
    {
      "index": 1,
      "class_id": 11,
      "label": "Embellished",
      "confidence": 0.8,
      "bbox_xyxy": [70.0, 50.0, 95.0, 75.0],
    },
  ]


def make_source(root: Path) -> Path:
  source = root / "inputs" / "page.png"
  source.parent.mkdir(parents=True)
  image = Image.new("RGB", (100, 80), (230, 220, 200))
  for x in range(100):
    image.putpixel((x, x % 80), (x, 20, 30))
  image.save(source)
  return source


@pytest.mark.parametrize("mask_family", ["rectangular", "irregular"])
@pytest.mark.parametrize("severity", [0.30, 0.60])
def test_masks_are_binary_complementary_and_within_severity_tolerance(mask_family: str, severity: float):
  survival, damage, _, _, statistics = build_source_masks((120, 90), mask_family, severity, 42)

  assert set(survival.getdata()) <= {0, 255}
  assert set(damage.getdata()) <= {0, 255}
  assert all(surviving + damaged == 255 for surviving, damaged in zip(survival.getdata(), damage.getdata()))
  assert abs(statistics["measured_severity"] - severity) <= SEVERITY_TOLERANCE
  assert statistics["surviving_fraction"] == pytest.approx(1.0 - statistics["measured_severity"])


def test_generation_is_deterministic_and_source_remains_untouched(tmp_path: Path):
  source = make_source(tmp_path)
  before = sha256_file(source)
  config = GenerationConfig("task", "irregular", 0.60, 1234)

  first = generate_fragment_task(
    root=tmp_path,
    source_page=source_page(),
    config=config,
    artifacts=paths(tmp_path, "first"),
    layout_detections=detections(),
    segmentation_run_provenance=provenance(),
  )
  second = generate_fragment_task(
    root=tmp_path,
    source_page=source_page(),
    config=config,
    artifacts=paths(tmp_path, "second"),
    layout_detections=detections(),
    segmentation_run_provenance=provenance(),
  )

  assert first["generation_fingerprint_sha256"] == second["generation_fingerprint_sha256"]
  for artifact in ("fragment_image", "observed_fragment_survival_mask", "source_survival_mask", "source_damage_mask"):
    assert first["artifacts"][artifact]["sha256"] == second["artifacts"][artifact]["sha256"]
  assert sha256_file(source) == before
  assert first["source_integrity_verified"] is True


def test_bbox_clipping_is_safe_and_half_open():
  assert clip_bbox_xyxy([-4.2, -2.1, 10.2, 8.8], 100, 80) == (0, 0, 11, 9)
  assert clip_bbox_xyxy([95.1, 75.2, 120.0, 100.0], 100, 80) == (95, 75, 100, 80)
  assert clip_bbox_xyxy([110.0, 90.0, 120.0, 100.0], 100, 80) == (100, 80, 100, 80)


def test_known_region_survival_and_completely_lost_region():
  mask = Image.new("L", (100, 80), 0)
  mask.paste(255, (0, 0, 50, 80))
  regions = [
    {"index": 2, "class_id": 4, "label": "Main", "confidence": 0.9, "bbox_xyxy": [25, 10, 75, 30]},
    {"index": 3, "class_id": 11, "label": "Lost", "confidence": 0.8, "bbox_xyxy": [60, 10, 80, 30]},
    {"index": 4, "class_id": 3, "label": "Visible", "confidence": 0.7, "bbox_xyxy": [-10, 5, 10, 15]},
  ]

  estimates, summary = estimate_layout_survival(regions, mask, provenance())

  assert estimates[0]["original_rasterized_area_px"] == 1000
  assert estimates[0]["surviving_area_px"] == 500
  assert estimates[0]["surviving_fraction"] == 0.5
  assert estimates[1]["completely_lost"] is True
  assert estimates[2]["original_bbox_xyxy"] == [-10.0, 5.0, 10.0, 15.0]
  assert estimates[2]["clipped_raster_bbox_xyxy"] == [0, 5, 10, 15]
  assert summary["partially_visible_count"] == 1
  assert summary["completely_lost_count"] == 1
  assert summary["completely_visible_count"] == 1
  assert summary["labels_completely_lost"] == ["Lost"]
  assert summary["geometry_method"] == "rasterized_bbox_xyxy"


@pytest.mark.parametrize("rotation,scale", [(12.0, 1.0), (-9.0, 1.0), (0.0, 0.8)])
def test_coordinate_forward_inverse_round_trip(rotation: float, scale: float):
  forward, inverse, dimensions = source_to_observed_transform((10, 20, 90, 70), rotation, scale)
  source_point = (37.25, 44.75)
  observed_point = apply_transform(forward, source_point)
  recovered = apply_transform(inverse, observed_point)

  assert recovered[0] == pytest.approx(source_point[0], abs=1e-8)
  assert recovered[1] == pytest.approx(source_point[1], abs=1e-8)
  assert dimensions[0] > 0 and dimensions[1] > 0


@pytest.mark.parametrize("rotation,scale", [(12.0, 1.0), (-9.0, 1.0), (0.0, 0.8)])
def test_rotation_and_scale_generation_sanity(tmp_path: Path, rotation: float, scale: float):
  make_source(tmp_path)
  result = generate_fragment_task(
    root=tmp_path,
    source_page=source_page(),
    config=GenerationConfig("sanity", "irregular", 0.45, 99, rotation, scale, "transformation_sanity"),
    artifacts=paths(tmp_path, f"sanity-{rotation}-{scale}"),
    layout_detections=detections(),
    segmentation_run_provenance=provenance(),
  )

  assert result["rotation_degrees"] == rotation
  assert result["scale"] == scale
  assert result["generated_fragment_dimensions_px"][0] > 0
  assert result["generated_fragment_dimensions_px"] == result["artifacts"]["observed_fragment_survival_mask"]["dimensions_px"]
  assert result["generated_fragment_dimensions_px"] == result["crop_transform"]["matrix_expected_dimensions_px"]


def test_source_overwrite_is_rejected_before_writing(tmp_path: Path):
  source = make_source(tmp_path)
  artifact = paths(tmp_path, "overwrite")
  artifact = ArtifactPaths(
    fragment=source,
    observed_fragment_mask=artifact.observed_fragment_mask,
    source_survival_mask=artifact.source_survival_mask,
    source_damage_mask=artifact.source_damage_mask,
    metadata=artifact.metadata,
  )
  before = sha256_file(source)

  with pytest.raises(ValueError, match="must not overwrite"):
    generate_fragment_task(
      root=tmp_path,
      source_page=source_page(),
      config=GenerationConfig("overwrite", "rectangular", 0.30, 1),
      artifacts=artifact,
      layout_detections=detections(),
      segmentation_run_provenance=provenance(),
    )

  assert sha256_file(source) == before


def test_segmentation_dimension_mismatch_is_rejected(tmp_path: Path):
  make_source(tmp_path)
  with pytest.raises(ValueError, match="dimension mismatch"):
    generate_fragment_task(
      root=tmp_path,
      source_page=source_page(),
      config=GenerationConfig("mismatch", "rectangular", 0.30, 1),
      artifacts=paths(tmp_path, "mismatch"),
      layout_detections=detections(),
      segmentation_run_provenance=provenance((81, 100)),
    )


def test_registered_source_and_normalized_metadata_are_preserved():
  page = source_page()
  assert page.db_ids["image_asset_id"] == "image-1"
  assert page.hsp_normalized_metadata == {"object_form": "codex"}
  assert page.registered_source_record["rights_review_status"] == "pending_review"
