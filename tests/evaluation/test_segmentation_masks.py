"""Tests for source-coordinate eManuSkript instance-mask preservation."""

from pathlib import Path
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.evaluation.segmentation_masks import (
  mask_pixel_area,
  restore_mask_to_source,
  save_binary_mask,
  validate_binary_mask,
)


def test_mask_coordinate_restoration_through_inference_resize():
  model_mask = Image.new("L", (2, 2), 0)
  model_mask.putpixel((0, 0), 255)

  restored = restore_mask_to_source(
    model_mask,
    inference_size=(4, 2),
    source_size=(8, 4),
  )

  assert restored.size == (8, 4)
  assert mask_pixel_area(restored) == 8
  assert restored.getpixel((0, 0)) == 255
  assert restored.getpixel((3, 1)) == 255
  assert restored.getpixel((4, 1)) == 0
  assert restored.getpixel((0, 2)) == 0


def test_restored_mask_is_binary_and_matches_source_dimensions():
  soft_mask = Image.new("L", (3, 2), 127)
  soft_mask.putpixel((1, 0), 128)
  restored = restore_mask_to_source(
    soft_mask,
    inference_size=(3, 2),
    source_size=(6, 4),
  )

  validate_binary_mask(restored, (6, 4))
  assert {value for _, value in restored.getcolors(maxcolors=3)} <= {0, 255}
  with pytest.raises(ValueError, match="dimension mismatch"):
    validate_binary_mask(restored, (7, 4))


def test_binary_mask_validation_rejects_non_binary_values():
  mask = Image.new("L", (4, 4), 64)
  with pytest.raises(ValueError, match="binary values"):
    validate_binary_mask(mask)


def test_mask_png_regeneration_is_deterministic(tmp_path: Path):
  mask = Image.new("L", (12, 10), 0)
  mask.paste(255, (2, 3, 9, 8))

  first_hash = save_binary_mask(mask, tmp_path / "first.png")
  second_hash = save_binary_mask(mask, tmp_path / "second.png")

  assert first_hash == second_hash
  assert (tmp_path / "first.png").read_bytes() == (tmp_path / "second.png").read_bytes()
