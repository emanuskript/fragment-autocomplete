"""Tests for controlled artificial-fragment generation helpers."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PIL import Image

from src.evaluation.artificial_fragments import (
  MASK_FAMILIES,
  build_tasks,
  source_pages_from_resolved_dataset,
  stable_seed,
)


def test_source_pages_preserve_registered_metadata():
  payload = {
    "full_pages": [
      {
        "id": "fp_test",
        "category": "clean_simple",
        "source": "e-codices",
        "url": "https://example.test/page",
        "local_path": "inputs/page.png",
        "registration_status": "registered",
        "rights_review_status": "pending_review",
        "access_level": "internal",
        "db_ids": {"canvas_id": "canvas-1", "image_asset_id": "image-1"},
      }
    ]
  }

  pages = source_pages_from_resolved_dataset(payload)

  assert len(pages) == 1
  assert pages[0].sample_id == "fp_test"
  assert pages[0].db_ids["image_asset_id"] == "image-1"
  assert pages[0].rights_review_status == "pending_review"
  assert pages[0].hsp_normalized_metadata == {}
  assert pages[0].source_metadata["purpose"] is None


def test_stable_seed_is_reproducible_and_family_specific():
  rectangular = stable_seed("dataset", "fp_01", "rectangular", 1)
  repeated = stable_seed("dataset", "fp_01", "rectangular", 1)
  irregular = stable_seed("dataset", "fp_01", "irregular", 1)

  assert rectangular == repeated
  assert rectangular != irregular


def test_build_tasks_writes_fragments_masks_and_ground_truth(tmp_path: Path):
  source_dir = tmp_path / "inputs"
  source_dir.mkdir()
  source_path = source_dir / "page.png"
  Image.new("RGB", (220, 180), color=(230, 220, 200)).save(source_path)
  page = source_pages_from_resolved_dataset(
    {
      "full_pages": [
        {
          "id": "fp_test",
          "category": "clean_simple",
          "source": "fixture",
          "url": "https://example.test/page",
          "local_path": "inputs/page.png",
          "registration_status": "registered",
          "rights_review_status": "pending_review",
          "access_level": "internal",
          "db_ids": {"canvas_id": "canvas-1", "image_asset_id": "image-1"},
          "hsp_normalized_metadata": {"object_form": "codex"},
        }
      ]
    }
  )[0]

  tasks = build_tasks(
    root=tmp_path,
    dataset_id="fixture_dataset",
    source_pages=[page],
    output_dir=Path("outputs/artificial_fragments"),
    base_seed=42,
  )

  assert [task.mask_family for task in tasks] == list(MASK_FAMILIES)
  for task in tasks:
    metadata = task.to_metadata()
    assert (tmp_path / task.fragment_path).exists()
    assert (tmp_path / task.mask_path).exists()
    assert metadata["ground_truth_placement"]["placement_is_known"] is True
    assert metadata["ground_truth_placement"]["source_image_asset_id"] == "image-1"
    assert metadata["degradation_profile"]["profile"] == "none"
    assert metadata["hsp_normalized_metadata"] == {"object_form": "codex"}
