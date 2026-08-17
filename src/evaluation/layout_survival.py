"""Estimate source-layout survival from rasterized bounding-box geometry."""

from __future__ import annotations

from collections import defaultdict
from math import ceil, floor
from typing import Any

from PIL import Image


GEOMETRY_METHOD = "rasterized_bbox_xyxy"


def clip_bbox_xyxy(
  bbox_xyxy: list[float] | tuple[float, float, float, float],
  width: int,
  height: int,
) -> tuple[int, int, int, int]:
  """Clip a floating-point bbox to a half-open integer pixel rectangle."""
  if len(bbox_xyxy) != 4:
    raise ValueError("bbox_xyxy must contain exactly four values")
  x1, y1, x2, y2 = (float(value) for value in bbox_xyxy)
  left = max(0, min(width, floor(x1)))
  top = max(0, min(height, floor(y1)))
  right = max(0, min(width, ceil(x2)))
  bottom = max(0, min(height, ceil(y2)))
  if right < left:
    right = left
  if bottom < top:
    bottom = top
  return left, top, right, bottom


def _surviving_pixels(mask: Image.Image, bbox: tuple[int, int, int, int]) -> int:
  left, top, right, bottom = bbox
  if right <= left or bottom <= top:
    return 0
  histogram = mask.crop(bbox).histogram()
  return int(histogram[255])


def estimate_layout_survival(
  detections: list[dict[str, Any]],
  survival_mask: Image.Image,
  segmentation_run_provenance: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
  """Estimate how much of each bbox-based source layout region survives.

  This deliberately uses the stored detection bounding boxes. It is a layout
  survival estimate, not pixel-accurate segmentation-mask survival.
  """
  if survival_mask.mode != "L":
    raise ValueError("survival_mask must use Pillow mode L")
  width, height = survival_mask.size
  if set(survival_mask.getextrema()) - {0, 255}:
    raise ValueError("survival_mask must be binary (0 or 255)")

  estimates: list[dict[str, Any]] = []
  for position, detection in enumerate(detections):
    original_bbox = detection.get("bbox_xyxy")
    if not isinstance(original_bbox, (list, tuple)) or len(original_bbox) != 4:
      raise ValueError(f"Layout region {position} is missing bbox_xyxy")
    clipped_bbox = clip_bbox_xyxy(original_bbox, width, height)
    left, top, right, bottom = clipped_bbox
    original_area = max(0, right - left) * max(0, bottom - top)
    surviving_area = _surviving_pixels(survival_mask, clipped_bbox)
    surviving_fraction = surviving_area / original_area if original_area else 0.0
    estimates.append(
      {
        "source_region_index": detection.get("index", position),
        "source_region_identifier": f"{segmentation_run_provenance.get('sample_id', 'unknown')}:{detection.get('index', position)}",
        "label": detection.get("label", "unknown"),
        "class_id": detection.get("class_id"),
        "confidence": detection.get("confidence"),
        "original_bbox_xyxy": [float(value) for value in original_bbox],
        "clipped_raster_bbox_xyxy": list(clipped_bbox),
        "original_rasterized_area_px": original_area,
        "surviving_area_px": surviving_area,
        "surviving_fraction": round(surviving_fraction, 8),
        "completely_lost": original_area > 0 and surviving_area == 0,
        "geometry_method": GEOMETRY_METHOD,
        "segmentation_run_provenance": dict(segmentation_run_provenance),
      }
    )

  return estimates, summarize_layout_survival(estimates)


def summarize_layout_survival(estimates: list[dict[str, Any]]) -> dict[str, Any]:
  """Build per-fragment counts and area-weighted summaries by region label."""
  visible = [item for item in estimates if item["original_rasterized_area_px"] > 0 and item["surviving_area_px"] == item["original_rasterized_area_px"]]
  lost = [item for item in estimates if item["completely_lost"]]
  partial = [
    item
    for item in estimates
    if item["original_rasterized_area_px"] > 0
    and 0 < item["surviving_area_px"] < item["original_rasterized_area_px"]
  ]

  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for item in estimates:
    grouped[str(item["label"])].append(item)

  by_label: dict[str, dict[str, Any]] = {}
  labels_completely_lost: list[str] = []
  for label in sorted(grouped):
    items = grouped[label]
    original_area = sum(int(item["original_rasterized_area_px"]) for item in items)
    surviving_area = sum(int(item["surviving_area_px"]) for item in items)
    completely_lost_count = sum(bool(item["completely_lost"]) for item in items)
    if items and completely_lost_count == len(items):
      labels_completely_lost.append(label)
    by_label[label] = {
      "region_count": len(items),
      "original_rasterized_area_px": original_area,
      "surviving_area_px": surviving_area,
      "area_weighted_surviving_fraction": round(surviving_area / original_area, 8) if original_area else 0.0,
      "completely_lost_region_count": completely_lost_count,
    }

  return {
    "metric_name": "layout_survival_estimate",
    "geometry_method": GEOMETRY_METHOD,
    "total_regions": len(estimates),
    "completely_visible_count": len(visible),
    "partially_visible_count": len(partial),
    "completely_lost_count": len(lost),
    "labels_completely_lost": labels_completely_lost,
    "labels_with_completely_lost_regions": sorted({str(item["label"]) for item in lost}),
    "surviving_fractions_by_label": by_label,
    "interpretation_note": (
      "Calculated from rasterized source-region bounding boxes; this is not pixel-accurate segmentation-mask survival."
    ),
  }
