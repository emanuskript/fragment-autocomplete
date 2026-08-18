"""Generate deterministic artificial manuscript fragments from complete pages."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import ceil, cos, floor, radians, sin, sqrt
from pathlib import Path
import random
from typing import Any, Iterable

from PIL import Image, ImageDraw

from .layout_survival import estimate_layout_survival


GENERATION_VERSION = "artificial_fragment_generator_v0_1_1"
MASK_FAMILIES = ("rectangular", "irregular")
SEVERITY_TOLERANCE = 0.02


@dataclass(frozen=True)
class SourcePage:
  """Registered complete page eligible for artificial-fragment generation."""

  sample_id: str
  category: str
  source: str
  source_url: str | None
  local_path: str
  rights_review_status: str | None
  access_level: str | None
  db_ids: dict[str, Any]
  hsp_normalized_metadata: dict[str, Any]
  source_metadata: dict[str, Any]
  registered_source_record: dict[str, Any]


@dataclass(frozen=True)
class GenerationConfig:
  """Canonical parameters for one deterministic artificial-fragment task."""

  task_id: str
  mask_family: str
  requested_severity: float
  random_seed: int
  rotation_degrees: float = 0.0
  scale: float = 1.0
  task_group: str = "core_pilot"

  def validate(self) -> None:
    if self.mask_family not in MASK_FAMILIES:
      raise ValueError(f"Unsupported mask family: {self.mask_family}")
    if not 0.0 < self.requested_severity < 1.0:
      raise ValueError("requested_severity must be greater than 0 and less than 1")
    if not -180.0 <= self.rotation_degrees <= 180.0:
      raise ValueError("rotation_degrees must be between -180 and 180")
    if not 0.1 <= self.scale <= 4.0:
      raise ValueError("scale must be between 0.1 and 4.0")


@dataclass(frozen=True)
class ArtifactPaths:
  """Filesystem paths for one generated task."""

  fragment: Path
  observed_fragment_mask: Path
  source_survival_mask: Path
  source_damage_mask: Path
  metadata: Path


def canonical_json(value: Any) -> str:
  """Return a stable JSON representation for hashes and task fingerprints."""
  return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_file(path: Path) -> str:
  """Hash a file without mutating it."""
  digest = sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def stable_seed(
  dataset_id: str,
  sample_id: str,
  mask_family: str,
  base_seed: int,
  *,
  requested_severity: float | None = None,
  rotation_degrees: float = 0.0,
  scale: float = 1.0,
  variant: str = "core_pilot",
) -> int:
  """Derive a reproducible seed from source identity and canonical parameters."""
  values = {
    "base_seed": base_seed,
    "dataset_id": dataset_id,
    "mask_family": mask_family,
    "requested_severity": requested_severity,
    "rotation_degrees": rotation_degrees,
    "sample_id": sample_id,
    "scale": scale,
    "variant": variant,
  }
  digest = sha256(canonical_json(values).encode("utf-8")).hexdigest()
  return int(digest[:15], 16)


def source_pages_from_resolved_dataset(payload: dict[str, Any]) -> list[SourcePage]:
  """Load registered full pages while preserving their complete source records."""
  pages: list[SourcePage] = []
  for item in payload.get("full_pages", []):
    if item.get("registration_status") != "registered":
      continue
    pages.append(
      SourcePage(
        sample_id=item["id"],
        category=item["category"],
        source=item["source"],
        source_url=item.get("url"),
        local_path=item["local_path"],
        rights_review_status=item.get("rights_review_status"),
        access_level=item.get("access_level"),
        db_ids=dict(item.get("db_ids", {})),
        hsp_normalized_metadata=dict(item.get("hsp_normalized_metadata") or item.get("hsp_normalized") or {}),
        source_metadata={
          "purpose": item.get("purpose"),
          "sample_kind": item.get("sample_kind"),
          "category": item.get("category"),
          "iiif_manifest_url": item.get("iiif_manifest_url"),
          "iiif_image_service_url": item.get("iiif_image_service_url"),
          "iiif_resolution_status": item.get("iiif_resolution_status"),
          "rights_review_status": item.get("rights_review_status"),
          "training_allowed": item.get("training_allowed"),
          "publication_allowed": item.get("publication_allowed"),
          "demo_allowed": item.get("demo_allowed"),
          "access_level": item.get("access_level"),
        },
        registered_source_record=dict(item),
      )
    )
  return pages


def _mask_pixel_count(mask: Image.Image) -> int:
  return int(mask.histogram()[255])


def _assert_binary_mask(mask: Image.Image) -> None:
  extrema = mask.getextrema()
  if mask.mode != "L" or not isinstance(extrema, tuple) or set(extrema) - {0, 255}:
    raise ValueError("Mask must be an 8-bit binary image containing only 0 and 255")


def _rectangular_survival_mask(
  size: tuple[int, int],
  target_surviving_pixels: int,
  rng: random.Random,
) -> tuple[Image.Image, list[tuple[int, int]], dict[str, Any]]:
  width, height = size
  page_ratio = width / height
  aspect = page_ratio * rng.uniform(0.82, 1.18)
  rect_width = max(1, min(width, round(sqrt(target_surviving_pixels * aspect))))
  rect_height = max(1, min(height, round(target_surviving_pixels / rect_width)))
  if rect_width * rect_height < target_surviving_pixels and rect_height < height:
    rect_height += 1
  if rect_width * rect_height < target_surviving_pixels and rect_width < width:
    rect_width += 1
  x = rng.randint(0, width - rect_width)
  y = rng.randint(0, height - rect_height)
  mask = Image.new("L", size, 0)
  mask.paste(255, (x, y, x + rect_width, y + rect_height))
  contour = [(x, y), (x + rect_width, y), (x + rect_width, y + rect_height), (x, y + rect_height)]
  return mask, contour, {
    "rectangle_xywh_px": [x, y, rect_width, rect_height],
    "sampled_aspect_ratio": round(aspect, 8),
    "rasterization": "half_open_rectangle",
  }


def _normalized_irregular_polygon(rng: random.Random, steps: int = 7) -> list[tuple[float, float]]:
  points: list[tuple[float, float]] = []
  for step in range(steps):
    x = -0.5 + step / (steps - 1)
    points.append((x, -0.5 + rng.uniform(0.0, 0.055)))
  for step in range(1, steps):
    y = -0.5 + step / (steps - 1)
    points.append((0.5 - rng.uniform(0.0, 0.055), y))
  for step in range(steps - 2, -1, -1):
    x = -0.5 + step / (steps - 1)
    points.append((x, 0.5 - rng.uniform(0.0, 0.055)))
  for step in range(steps - 2, 0, -1):
    y = -0.5 + step / (steps - 1)
    points.append((-0.5 + rng.uniform(0.0, 0.055), y))
  return points


def _scale_polygon(
  normalized: Iterable[tuple[float, float]],
  size: tuple[int, int],
  scale_factor: float,
  center: tuple[float, float],
) -> list[tuple[int, int]]:
  width, height = size
  center_x, center_y = center
  return [
    (
      max(0, min(width - 1, round(center_x + x * width * scale_factor))),
      max(0, min(height - 1, round(center_y + y * height * scale_factor))),
    )
    for x, y in normalized
  ]


def _draw_polygon_mask(size: tuple[int, int], polygon: list[tuple[int, int]]) -> Image.Image:
  mask = Image.new("L", size, 0)
  ImageDraw.Draw(mask).polygon(polygon, fill=255)
  return mask


def _irregular_survival_mask(
  size: tuple[int, int],
  target_surviving_pixels: int,
  rng: random.Random,
) -> tuple[Image.Image, list[tuple[int, int]], dict[str, Any]]:
  width, height = size
  normalized = _normalized_irregular_polygon(rng)
  page_center = (width / 2.0, height / 2.0)
  low, high = 0.01, 1.0
  best_scale = high
  best_delta = width * height
  for _ in range(18):
    candidate_scale = (low + high) / 2.0
    polygon = _scale_polygon(normalized, size, candidate_scale, page_center)
    count = _mask_pixel_count(_draw_polygon_mask(size, polygon))
    delta = abs(count - target_surviving_pixels)
    if delta < best_delta:
      best_delta = delta
      best_scale = candidate_scale
    if count < target_surviving_pixels:
      low = candidate_scale
    else:
      high = candidate_scale

  half_width = width * best_scale / 2.0
  half_height = height * best_scale / 2.0
  center_x = rng.uniform(half_width, width - half_width) if width - half_width > half_width else width / 2.0
  center_y = rng.uniform(half_height, height - half_height) if height - half_height > half_height else height / 2.0
  polygon = _scale_polygon(normalized, size, best_scale, (center_x, center_y))
  mask = _draw_polygon_mask(size, polygon)
  return mask, polygon, {
    "normalized_control_points": [[round(x, 8), round(y, 8)] for x, y in normalized],
    "source_polygon_xy_px": [list(point) for point in polygon],
    "calibrated_scale_factor": round(best_scale, 10),
    "center_xy_px": [round(center_x, 6), round(center_y, 6)],
    "calibration_iterations": 18,
    "rasterization": "pillow_polygon_fill",
  }


def build_source_masks(
  size: tuple[int, int],
  mask_family: str,
  requested_severity: float,
  random_seed: int,
) -> tuple[Image.Image, Image.Image, list[tuple[int, int]], dict[str, Any], dict[str, Any]]:
  """Build source-coordinate survival/damage masks and measured statistics."""
  if mask_family not in MASK_FAMILIES:
    raise ValueError(f"Unsupported mask family: {mask_family}")
  if not 0.0 < requested_severity < 1.0:
    raise ValueError("requested_severity must be greater than 0 and less than 1")
  width, height = size
  total_pixels = width * height
  target_surviving_pixels = round((1.0 - requested_severity) * total_pixels)
  rng = random.Random(random_seed)
  if mask_family == "rectangular":
    survival_mask, contour, mask_parameters = _rectangular_survival_mask(size, target_surviving_pixels, rng)
  else:
    survival_mask, contour, mask_parameters = _irregular_survival_mask(size, target_surviving_pixels, rng)
  _assert_binary_mask(survival_mask)
  damage_mask = Image.eval(survival_mask, lambda value: 255 - value)
  _assert_binary_mask(damage_mask)
  surviving_pixels = _mask_pixel_count(survival_mask)
  damaged_pixels = total_pixels - surviving_pixels
  measured_severity = damaged_pixels / total_pixels
  statistics = {
    "requested_severity": requested_severity,
    "measured_severity": round(measured_severity, 10),
    "surviving_fraction": round(surviving_pixels / total_pixels, 10),
    "total_source_pixels": total_pixels,
    "surviving_source_pixels": surviving_pixels,
    "damaged_source_pixels": damaged_pixels,
    "absolute_severity_error": round(abs(measured_severity - requested_severity), 10),
    "severity_tolerance": SEVERITY_TOLERANCE,
  }
  if statistics["absolute_severity_error"] > SEVERITY_TOLERANCE:
    raise ValueError(
      f"Measured severity {measured_severity:.6f} exceeds tolerance for requested severity {requested_severity:.6f}"
    )
  return survival_mask, damage_mask, contour, mask_parameters, statistics


def _matrix_multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
  return [
    [sum(left[row][index] * right[index][column] for index in range(3)) for column in range(3)]
    for row in range(3)
  ]


def apply_transform(matrix: list[list[float]], point: tuple[float, float]) -> tuple[float, float]:
  """Apply a homogeneous 2D transform to one coordinate."""
  x, y = point
  return (
    matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
    matrix[1][0] * x + matrix[1][1] * y + matrix[1][2],
  )


def invert_affine(matrix: list[list[float]]) -> list[list[float]]:
  """Invert a 3x3 affine transform matrix."""
  a, b, tx = matrix[0]
  c, d, ty = matrix[1]
  determinant = a * d - b * c
  if abs(determinant) < 1e-12:
    raise ValueError("Affine transform is singular")
  return [
    [d / determinant, -b / determinant, (b * ty - d * tx) / determinant],
    [-c / determinant, a / determinant, (c * tx - a * ty) / determinant],
    [0.0, 0.0, 1.0],
  ]


def source_to_observed_transform(
  source_bbox: tuple[int, int, int, int],
  rotation_degrees: float,
  scale: float,
) -> tuple[list[list[float]], list[list[float]], tuple[int, int]]:
  """Build forward/inverse transforms using continuous pixel-boundary coordinates."""
  left, top, right, bottom = source_bbox
  crop_width = right - left
  crop_height = bottom - top
  translation = [[1.0, 0.0, -left], [0.0, 1.0, -top], [0.0, 0.0, 1.0]]
  angle = radians(rotation_degrees)
  cosine = cos(angle)
  sine = sin(angle)
  center_x = crop_width / 2.0
  center_y = crop_height / 2.0
  rotation_about_origin = [[cosine, sine, 0.0], [-sine, cosine, 0.0], [0.0, 0.0, 1.0]]
  to_center = [[1.0, 0.0, -center_x], [0.0, 1.0, -center_y], [0.0, 0.0, 1.0]]
  from_center = [[1.0, 0.0, center_x], [0.0, 1.0, center_y], [0.0, 0.0, 1.0]]
  centered_rotation = _matrix_multiply(from_center, _matrix_multiply(rotation_about_origin, to_center))
  corners = [(0.0, 0.0), (float(crop_width), 0.0), (float(crop_width), float(crop_height)), (0.0, float(crop_height))]
  rotated_corners = [apply_transform(centered_rotation, point) for point in corners]
  minimum_x = min(point[0] for point in rotated_corners)
  minimum_y = min(point[1] for point in rotated_corners)
  maximum_x = max(point[0] for point in rotated_corners)
  maximum_y = max(point[1] for point in rotated_corners)
  # Match Pillow's expand=True rule exactly: ceil(max) - floor(min), with the
  # rotated crop centered in the expanded canvas.
  expanded_width = ceil(maximum_x) - floor(minimum_x)
  expanded_height = ceil(maximum_y) - floor(minimum_y)
  expand_translation = [
    [1.0, 0.0, (expanded_width - crop_width) / 2.0],
    [0.0, 1.0, (expanded_height - crop_height) / 2.0],
    [0.0, 0.0, 1.0],
  ]
  output_width = max(1, round(expanded_width * scale))
  output_height = max(1, round(expanded_height * scale))
  effective_scale_x = output_width / expanded_width
  effective_scale_y = output_height / expanded_height
  scaling = [[effective_scale_x, 0.0, 0.0], [0.0, effective_scale_y, 0.0], [0.0, 0.0, 1.0]]
  forward = _matrix_multiply(scaling, _matrix_multiply(expand_translation, _matrix_multiply(centered_rotation, translation)))
  inverse = invert_affine(forward)
  expected_size = (output_width, output_height)
  return forward, inverse, expected_size


def _round_matrix(matrix: list[list[float]]) -> list[list[float]]:
  return [[round(value, 12) for value in row] for row in matrix]


def _relative(path: Path, root: Path) -> str:
  try:
    return path.resolve().relative_to(root.resolve()).as_posix()
  except ValueError:
    return path.resolve().as_posix()


def _save_image(image: Image.Image, path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  image.save(path, format="PNG", compress_level=9)


def _ensure_no_source_overwrite(source_path: Path, artifacts: ArtifactPaths) -> None:
  source_resolved = source_path.resolve()
  targets = [artifacts.fragment, artifacts.observed_fragment_mask, artifacts.source_survival_mask, artifacts.source_damage_mask, artifacts.metadata]
  if source_resolved in {target.resolve() for target in targets}:
    raise ValueError("Generated artifact paths must not overwrite the source image")


def generate_fragment_task(
  *,
  root: Path,
  source_page: SourcePage,
  config: GenerationConfig,
  artifacts: ArtifactPaths,
  layout_detections: list[dict[str, Any]],
  segmentation_run_provenance: dict[str, Any],
) -> dict[str, Any]:
  """Generate one observed fragment and preserve source-coordinate ground truth."""
  config.validate()
  source_path = root / source_page.local_path
  if not source_path.exists():
    raise FileNotFoundError(f"Source image missing: {source_path}")
  _ensure_no_source_overwrite(source_path, artifacts)
  source_sha256_before = sha256_file(source_path)

  with Image.open(source_path) as image:
    source = image.convert("RGBA")
  source_width, source_height = source.size
  segmentation_shape = segmentation_run_provenance.get("orig_shape")
  if segmentation_shape is not None and list(segmentation_shape) != [source_height, source_width]:
    raise ValueError(
      f"Segmentation/source dimension mismatch for {source_page.sample_id}: "
      f"segmentation={segmentation_shape}, source={[source_height, source_width]}"
    )
  survival_mask, damage_mask, source_contour, mask_parameters, mask_statistics = build_source_masks(
    source.size, config.mask_family, config.requested_severity, config.random_seed
  )
  source_bbox = survival_mask.getbbox()
  if source_bbox is None:
    raise ValueError("Generated survival mask is empty")
  left, top, right, bottom = source_bbox
  if not (0 <= left < right <= source_width and 0 <= top < bottom <= source_height):
    raise ValueError("Generated fragment lies outside source-page coordinate space")

  layout_estimates, layout_summary = estimate_layout_survival(
    layout_detections,
    survival_mask,
    segmentation_run_provenance,
    artifact_root=root,
  )
  observed = source.crop(source_bbox)
  observed_mask = survival_mask.crop(source_bbox)
  observed.putalpha(observed_mask)
  if config.rotation_degrees:
    observed = observed.rotate(config.rotation_degrees, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0))
    observed_mask = observed_mask.rotate(config.rotation_degrees, resample=Image.Resampling.NEAREST, expand=True, fillcolor=0)
  if config.scale != 1.0:
    scaled_size = (max(1, round(observed.width * config.scale)), max(1, round(observed.height * config.scale)))
    observed = observed.resize(scaled_size, Image.Resampling.BICUBIC)
    observed_mask = observed_mask.resize(scaled_size, Image.Resampling.NEAREST)
  _assert_binary_mask(observed_mask)
  observed.putalpha(observed_mask)

  forward, inverse, transform_expected_size = source_to_observed_transform(source_bbox, config.rotation_degrees, config.scale)
  observed_contour = [apply_transform(forward, (float(x), float(y))) for x, y in source_contour]
  _save_image(observed, artifacts.fragment)
  _save_image(observed_mask, artifacts.observed_fragment_mask)
  _save_image(survival_mask, artifacts.source_survival_mask)
  _save_image(damage_mask, artifacts.source_damage_mask)
  source_sha256_after = sha256_file(source_path)
  if source_sha256_before != source_sha256_after:
    raise RuntimeError(f"Source image changed during generation: {source_page.local_path}")

  artifact_metadata = {
    "fragment_image": {"path": _relative(artifacts.fragment, root), "sha256": sha256_file(artifacts.fragment), "coordinate_space": "observed_fragment", "dimensions_px": [observed.width, observed.height], "mode": observed.mode},
    "observed_fragment_survival_mask": {"path": _relative(artifacts.observed_fragment_mask, root), "sha256": sha256_file(artifacts.observed_fragment_mask), "coordinate_space": "observed_fragment", "dimensions_px": [observed_mask.width, observed_mask.height], "semantics": "255=observed source pixel survives; 0=missing"},
    "source_survival_mask": {"path": _relative(artifacts.source_survival_mask, root), "sha256": sha256_file(artifacts.source_survival_mask), "coordinate_space": "source_page", "dimensions_px": [source_width, source_height], "semantics": "255=observed source pixel survives; 0=missing"},
    "source_damage_mask": {"path": _relative(artifacts.source_damage_mask, root), "sha256": sha256_file(artifacts.source_damage_mask), "coordinate_space": "source_page", "dimensions_px": [source_width, source_height], "semantics": "255=source pixel removed; 0=survives"},
  }
  parameters = {
    "requested_severity": config.requested_severity,
    "measured_severity": mask_statistics["measured_severity"],
    "surviving_fraction": mask_statistics["surviving_fraction"],
    "rotation_degrees": config.rotation_degrees,
    "scale": config.scale,
    "mask_parameters": mask_parameters,
    "mask_statistics": mask_statistics,
    "coordinate_convention": "Continuous pixel-boundary coordinates; top-left origin; x right; y down.",
  }
  fingerprint = sha256(canonical_json({"generation_version": GENERATION_VERSION, "source_sha256": source_sha256_before, "mask_family": config.mask_family, "random_seed": config.random_seed, **parameters}).encode("utf-8")).hexdigest()
  metadata = {
    "task_id": config.task_id,
    "task_group": config.task_group,
    "generation_version": GENERATION_VERSION,
    "generation_fingerprint_sha256": fingerprint,
    "source_sample_id": source_page.sample_id,
    "source_image_asset_id": source_page.db_ids.get("image_asset_id"),
    "source_canvas_id": source_page.db_ids.get("canvas_id"),
    "source_path": source_page.local_path,
    "source_sha256": source_sha256_before,
    "source_sha256_after_generation": source_sha256_after,
    "source_integrity_verified": True,
    "original_image_dimensions_px": [source_width, source_height],
    "generated_fragment_dimensions_px": [observed.width, observed.height],
    "source_provenance": {
      "source": source_page.source,
      "source_url": source_page.source_url,
      "category": source_page.category,
      "database_ids": source_page.db_ids,
      "registered_source_record": source_page.registered_source_record,
      "source_metadata": source_page.source_metadata,
      "hsp_normalized_metadata": source_page.hsp_normalized_metadata,
      "hsp_normalized_metadata_availability": "present" if source_page.hsp_normalized_metadata else "not_present_in_resolved_source_registry",
      "rights_review_status": source_page.rights_review_status,
      "access_level": source_page.access_level,
    },
    "mask_family": config.mask_family,
    "random_seed": config.random_seed,
    "requested_severity": config.requested_severity,
    "measured_severity": mask_statistics["measured_severity"],
    "surviving_fraction": mask_statistics["surviving_fraction"],
    "rotation_degrees": config.rotation_degrees,
    "scale": config.scale,
    "mask_semantics": {
      "survival_mask": "1/255=observed source pixel survives; 0=missing",
      "damage_mask": "1/255=source pixel removed; 0=survives",
      "severity_definition": "damaged source pixels / total source-page pixels",
    },
    "artifacts": artifact_metadata,
    "fragment_contour": {"source_page_xy_px": [list(point) for point in source_contour], "observed_fragment_xy_px": [[round(x, 8), round(y, 8)] for x, y in observed_contour]},
    "fragment_bounding_box": {"source_page_bbox_xyxy_px": list(source_bbox), "observed_fragment_bbox_xyxy_px": [0, 0, observed.width, observed.height]},
    "crop_transform": {
      "source_bbox_xyxy_px": list(source_bbox),
      "source_bbox_xywh_px": [left, top, right - left, bottom - top],
      "rotation_degrees": config.rotation_degrees,
      "scale": config.scale,
      "source_to_observed_fragment_matrix": _round_matrix(forward),
      "observed_fragment_to_source_matrix": _round_matrix(inverse),
      "matrix_expected_dimensions_px": list(transform_expected_size),
      "exported_dimensions_px": [observed.width, observed.height],
    },
    "ground_truth_placement": {
      "coordinate_space": "source_page",
      "placement_is_known": True,
      "source_canvas_id": source_page.db_ids.get("canvas_id"),
      "source_image_asset_id": source_page.db_ids.get("image_asset_id"),
      "source_page_dimensions_px": [source_width, source_height],
      "source_contour_xy_px": [list(point) for point in source_contour],
      "source_bbox_xyxy_px": list(source_bbox),
      "source_survival_mask_path": artifact_metadata["source_survival_mask"]["path"],
      "source_damage_mask_path": artifact_metadata["source_damage_mask"]["path"],
      "scientific_role": "hidden_ground_truth",
    },
    "layout_survival_estimate": {
      "geometry_method": layout_summary["geometry_method"],
      "segmentation_run_provenance": segmentation_run_provenance,
      "regions": layout_estimates,
      "summary": layout_summary,
    },
    "degradation_profile": {"profile": "mask_crop_rotation_scale_only", "contains_inferred_or_reconstructed_content": False, "note": "The exported fragment contains only transformed observed pixels from the complete source page."},
    "split_name": "demo",
    "parameters": parameters,
    "artificial_fragment_task_mapping": {
      "source_canvas_id": source_page.db_ids.get("canvas_id"),
      "source_image_asset_id": source_page.db_ids.get("image_asset_id"),
      "generated_fragment_image_asset_id": None,
      "mask_path": artifact_metadata["source_survival_mask"]["path"],
      "mask_family": config.mask_family,
      "random_seed": config.random_seed,
      "crop_transform": "crop_transform",
      "degradation_profile": "degradation_profile",
      "ground_truth_placement": "ground_truth_placement",
      "split_name": "demo",
      "generation_version": GENERATION_VERSION,
      "parameters": "parameters",
      "database_write": False,
    },
  }
  artifacts.metadata.parent.mkdir(parents=True, exist_ok=True)
  artifacts.metadata.write_text(json.dumps(metadata, indent=2, sort_keys=False), encoding="utf-8")
  metadata["artifacts"]["metadata"] = {"path": _relative(artifacts.metadata, root), "sha256": sha256_file(artifacts.metadata), "coordinate_space": "not_applicable"}
  return metadata
