"""Utilities for preserving segmentation masks in source-image coordinates."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image


MASK_THRESHOLD = 128


def normalize_binary_mask(mask: Image.Image, threshold: int = MASK_THRESHOLD) -> Image.Image:
  """Return an 8-bit mask containing only 0 and 255."""
  if not 0 <= threshold <= 255:
    raise ValueError("threshold must be between 0 and 255")
  grayscale = mask.convert("L")
  return grayscale.point(lambda value: 255 if value >= threshold else 0, mode="L")


def validate_binary_mask(mask: Image.Image, expected_size: tuple[int, int] | None = None) -> None:
  """Validate mask mode, dimensions, and binary values."""
  if mask.mode != "L":
    raise ValueError("Segmentation mask must use Pillow mode L")
  if expected_size is not None and mask.size != expected_size:
    raise ValueError(f"Mask/source dimension mismatch: mask={mask.size}, source={expected_size}")
  colors = mask.getcolors(maxcolors=3)
  if colors is None or {value for _, value in colors} - {0, 255}:
    raise ValueError("Segmentation mask must contain only binary values 0 and 255")


def restore_mask_to_source(
  mask: Image.Image,
  *,
  inference_size: tuple[int, int],
  source_size: tuple[int, int],
) -> Image.Image:
  """Restore one model mask to the original source-image coordinate space.

  Ultralytics may return masks at a model-dependent raster size. The mask is
  first aligned to the actual inference image and then restored through the
  preprocessing resize to the original source dimensions. Nearest-neighbour
  resampling preserves categorical membership.
  """
  if min(*inference_size, *source_size) < 1:
    raise ValueError("Mask coordinate-space dimensions must be positive")
  restored = normalize_binary_mask(mask)
  if restored.size != inference_size:
    restored = restored.resize(inference_size, Image.Resampling.NEAREST)
  if inference_size != source_size:
    restored = restored.resize(source_size, Image.Resampling.NEAREST)
  restored = normalize_binary_mask(restored)
  validate_binary_mask(restored, source_size)
  return restored


def mask_pixel_area(mask: Image.Image) -> int:
  """Count surviving/foreground pixels in a validated binary mask."""
  validate_binary_mask(mask)
  return int(mask.histogram()[255])


def file_sha256(path: Path) -> str:
  """Hash a saved mask artifact."""
  digest = sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def save_binary_mask(mask: Image.Image, path: Path) -> str:
  """Save a deterministic binary PNG and return its SHA-256."""
  validate_binary_mask(mask)
  path.parent.mkdir(parents=True, exist_ok=True)
  mask.save(path, format="PNG", compress_level=9)
  return file_sha256(path)
