"""Six distinct, calibrated synthetic material-loss mechanisms; no historical inference."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image
from scipy import ndimage

from .corpus_audit import digest

VERSION = "artificial_fragment_experiment_v0_3"
GENERATOR_VERSION = "structured_damage_generator_v0_3"
SEVERITIES = (0.30, 0.60)
SEVERITY_TOLERANCE = 0.005
MIN_DIMENSION = 16
CONNECTIVITY = 4
MIN_STRIP_NORMALIZED_ELONGATION = 1.25
MIN_TEAR_DEPTH_LEVELS = 3
MAX_PIECE_BBOX_FILL = 0.95
EDGES = ("top", "bottom", "left", "right")
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
TAXONOMY = {
  "edge_loss": "A straight boundary slab, inset one pixel from the two neighboring edges; exactly one edge touched.",
  "corner_loss": "A corner-anchored expanding rectangle, guarded from the two opposite edges; exactly two adjacent edges touched.",
  "internal_hole": "An expanding elliptical interior hole, with a one-pixel border guard; no page edge touched.",
  "edge_tear": "A connected boundary loss with a two-frequency depth profile, inset from neighboring edges; a varying inward front.",
  "strip_loss": "A full-span vertical or horizontal strip, positioned at the start, middle or end of the transverse axis.",
  "connected_piece_loss": "The expanding union of three overlapping elliptical lobes along a diagonal; one irregular connected lost piece, possibly edge-clipped.",
}
FAMILIES = tuple(TAXONOMY)


class DamageRejected(ValueError):
  """A deterministic scientific constraint failure; must be reported, never silently relaxed."""


def parameters(page_id, source_sha256, family, severity):
  if family not in TAXONOMY or not 0 < severity < 1:
    raise DamageRejected("unsupported_family_or_severity")
  key = digest({"version": VERSION, "page_id": page_id, "source_sha256": source_sha256,
                "family": family, "severity": severity})
  number = int(key[:16], 16)
  p = {"taxonomy_version": GENERATOR_VERSION, "family": family, "assignment_sha256": key,
       "seed": number % (2**31 - 1), "border_guard_px": 1,
       "calibration": "nearest_pixel_count; ascending_shape_score; row_major_ties; round_half_even"}
  if family in ("edge_loss", "edge_tear"):
    p["edge"] = EDGES[number % len(EDGES)]
  if family == "corner_loss":
    p.update(corner=CORNERS[number % len(CORNERS)], axis_ratio=0.90 + ((number >> 8) % 21) / 100)
  if family == "internal_hole":
    p.update(center_normalized=[0.48 + ((number >> 8) % 5) / 100, 0.48 + ((number >> 16) % 5) / 100],
             ellipse_axis_ratio=0.95 + ((number >> 24) % 11) / 100)
  if family == "edge_tear":
    p.update(phase_radians=((number >> 8) % 6284) / 1000,
             depth_base=0.85, depth_amplitudes=[0.15, 0.10], depth_frequencies=[2, 5])
  if family == "strip_loss":
    p.update(orientation=("vertical", "horizontal")[number % 2], placement=("start_edge", "interior", "end_edge")[(number >> 8) % 3])
  if family == "connected_piece_loss":
    p.update(diagonal=("descending", "ascending")[number % 2],
             centers_normalized=[[0.28, 0.31], [0.50, 0.49], [0.71, 0.69]],
             lobe_axis_ratios=[[1.0, 0.8], [0.85, 1.0], [1.0, 0.85]])
  return p


def _shape_score(size, p):
  w, h = size
  x, y = (np.arange(w, dtype=np.float64)[None, :] + .5) / w, (np.arange(h, dtype=np.float64)[:, None] + .5) / h
  family = p["family"]
  guard = np.zeros((h, w), dtype=bool)
  if family in ("edge_loss", "edge_tear"):
    edge = p["edge"]
    depth = y if edge == "top" else 1-y if edge == "bottom" else x if edge == "left" else 1-x
    transverse = x if edge in ("top", "bottom") else y
    profile = np.ones_like(transverse)
    if family == "edge_tear":
      profile = p["depth_base"] + sum(a * np.sin(2 * math.pi * f * transverse + p["phase_radians"])
                                      for a, f in zip(p["depth_amplitudes"], p["depth_frequencies"]))
    score = np.broadcast_to(depth / profile, (h, w)).copy()
    if edge in ("top", "bottom"):
      guard[:, [0, -1]] = True
      guard[-1 if edge == "top" else 0, :] = True
    else:
      guard[[0, -1], :] = True
      guard[:, -1 if edge == "left" else 0] = True
  elif family == "corner_loss":
    corner = p["corner"]
    u, v = (1-x if "right" in corner else x), (1-y if "bottom" in corner else y)
    ratio = p["axis_ratio"]
    score = np.maximum(u / ratio, v * ratio)
    guard[0 if "bottom" in corner else -1, :] = True
    guard[:, 0 if "right" in corner else -1] = True
  elif family == "internal_hole":
    cx, cy = p["center_normalized"]
    ratio = p["ellipse_axis_ratio"]
    score = ((x-cx)/ratio)**2 + ((y-cy)*ratio)**2
    guard[[0, -1], :] = True
    guard[:, [0, -1]] = True
  elif family == "strip_loss":
    transverse = x if p["orientation"] == "vertical" else y
    center = {"start_edge": 0., "interior": .5, "end_edge": 1.}[p["placement"]]
    score = np.broadcast_to(np.abs(transverse-center), (h, w)).copy()
  elif family == "connected_piece_loss":
    scores = []
    for (cx, cy), (rx, ry) in zip(p["centers_normalized"], p["lobe_axis_ratios"]):
      if p["diagonal"] == "ascending":
        cy = 1-cy
      scores.append(((x-cx)/rx)**2 + ((y-cy)/ry)**2)
    score = np.minimum.reduce(scores)
  else:
    raise DamageRejected("unknown_family")
  score[guard] = np.inf
  return score


def topology(mask, p):
  """Four-neighbor components; border and shape checks operate on the actual binary raster."""
  a = np.asarray(mask) > 0
  h, w = a.shape
  _, components = ndimage.label(a, structure=ndimage.generate_binary_structure(2, 1))
  touched = [edge for edge, values in (("top", a[0]), ("bottom", a[-1]), ("left", a[:, 0]), ("right", a[:, -1])) if values.any()]
  yy, xx = np.nonzero(a)
  bw, bh = (int(xx.max()-xx.min()+1), int(yy.max()-yy.min()+1)) if len(xx) else (0, 0)
  checks = {"nonempty": bool(a.any()), "not_entire_page": not bool(a.all()), "one_removed_component": int(components) == 1}
  details = {"connectivity": CONNECTIVITY, "removed_components": int(components), "touched_edges": touched,
             "removed_bbox_dimensions_px": [bw, bh], "bbox_fill_fraction": int(a.sum()) / (bw*bh) if bw*bh else None}
  family = p["family"]
  if family in ("edge_loss", "edge_tear"):
    checks["exactly_intended_edge"] = set(touched) == {p["edge"]}
    depths = a.sum(axis=0 if p["edge"] in ("top", "bottom") else 1)
    levels = len(np.unique(depths[depths > 0]))
    details["positive_depth_levels"] = levels
    if family == "edge_tear":
      checks["irregular_inward_front"] = levels >= MIN_TEAR_DEPTH_LEVELS
    else:
      checks["straight_front_with_pixel_rounding"] = levels <= 2
  elif family == "corner_loss":
    checks["exactly_intended_two_edges"] = set(touched) == set(p["corner"].split("_"))
  elif family == "internal_hole":
    checks["strictly_interior"] = not touched
  elif family == "strip_loss":
    vertical = p["orientation"] == "vertical"
    full_span, cross_fraction = (bh == h, bw/w) if vertical else (bw == w, bh/h)
    details["normalized_elongation"] = 1/cross_fraction if cross_fraction else None
    checks["full_orientation_span"] = full_span
    checks["normalized_strip_elongation"] = bool(cross_fraction and 1/cross_fraction >= MIN_STRIP_NORMALIZED_ELONGATION)
    expected = {"top", "bottom"} if vertical else {"left", "right"}
    if p["placement"] != "interior":
      expected.add(("left" if vertical else "top") if p["placement"] == "start_edge" else ("right" if vertical else "bottom"))
    checks["intended_strip_edges"] = set(touched) == expected
    # Every slice through the strip must be a single interval.
    arr = a if vertical else a.T
    checks["contiguous_cross_sections"] = bool(np.all(np.count_nonzero(np.diff(np.pad(arr, ((0, 0), (1, 1))), axis=1), axis=1) == 2))
  elif family == "connected_piece_loss":
    checks["nonrectangular_piece"] = bool(details["bbox_fill_fraction"] and details["bbox_fill_fraction"] < MAX_PIECE_BBOX_FILL)
  return {**details, "checks": checks, "passed": all(checks.values())}


def build_damage_mask(size, p, severity):
  w, h = size
  if min(size) < MIN_DIMENSION or not 0 < severity < 1:
    raise DamageRejected("dimensions_or_severity_outside_supported_domain")
  score = _shape_score(size, p)
  target = round(w*h*severity)
  capacity = int(np.isfinite(score).sum())
  if not 0 < target < w*h or target > capacity:
    raise DamageRejected("requested_area_exceeds_topological_capacity")
  # Deterministic calibration to nearest realizable pixel count, with explicit tie handling.
  threshold = float(np.partition(score.ravel(), target-1)[target-1])
  removed = score < threshold
  remainder = target - int(removed.sum())
  removed.ravel()[np.flatnonzero(score.ravel() == threshold)[:remainder]] = True
  damage = Image.fromarray(removed.astype(np.uint8) * 255)
  validation = topology(damage, p)
  actual = int(removed.sum()) / (w*h)
  error = abs(actual-severity)
  if error > SEVERITY_TOLERANCE:
    raise DamageRejected("severity_outside_tolerance")
  if not validation["passed"]:
    raise DamageRejected("topology_failed:" + ",".join(k for k, v in validation["checks"].items() if not v))
  stats = {"requested_severity": severity, "removed_pixels": int(removed.sum()), "total_pixels": w*h,
           "measured_severity": actual, "surviving_fraction": 1-actual, "absolute_severity_error": error,
           "severity_tolerance": SEVERITY_TOLERANCE, "calibrated_target_pixels": target,
           "shape_score_threshold": threshold, "topological_capacity_pixels": capacity,
           "topology": validation}
  return damage, stats
