"""Generate controlled artificial manuscript fragments from complete pages."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


GENERATION_VERSION = "artificial_fragment_generator_v0_1"
MASK_FAMILIES = ("rectangular", "irregular")


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


@dataclass(frozen=True)
class FragmentTask:
  """Metadata for one generated artificial fragment task."""

  task_id: str
  source_page: SourcePage
  mask_family: str
  random_seed: int
  source_width_px: int
  source_height_px: int
  bbox_xywh: tuple[int, int, int, int]
  fragment_path: str
  mask_path: str

  def to_metadata(self) -> dict[str, Any]:
    """Return a database-ready metadata record for this generated task."""
    x, y, width, height = self.bbox_xywh
    return {
      "task_id": self.task_id,
      "generation_version": GENERATION_VERSION,
      "source_sample_id": self.source_page.sample_id,
      "source_category": self.source_page.category,
      "source": self.source_page.source,
      "source_url": self.source_page.source_url,
      "source_local_path": self.source_page.local_path,
      "source_db_ids": self.source_page.db_ids,
      "source_metadata": self.source_page.source_metadata,
      "hsp_normalized_metadata": self.source_page.hsp_normalized_metadata,
      "rights_review_status": self.source_page.rights_review_status,
      "access_level": self.source_page.access_level,
      "mask_family": self.mask_family,
      "random_seed": self.random_seed,
      "split_name": "demo",
      "fragment_path": self.fragment_path,
      "mask_path": self.mask_path,
      "crop_transform": {
        "type": "source_page_crop",
        "bbox_xywh_px": [x, y, width, height],
        "rotation_degrees": 0,
        "scale": 1,
      },
      "ground_truth_placement": {
        "source_canvas_id": self.source_page.db_ids.get("canvas_id"),
        "source_image_asset_id": self.source_page.db_ids.get("image_asset_id"),
        "source_page_width_px": self.source_width_px,
        "source_page_height_px": self.source_height_px,
        "bbox_xyxy_px": [x, y, x + width, y + height],
        "placement_is_known": True,
      },
      "degradation_profile": {
        "profile": "none",
        "note": "The output is a controlled crop/mask task, not a claim about a real damaged fragment.",
      },
      "parameters": {
        "source": "initial_sample_dataset_resolved",
        "mask_family": self.mask_family,
        "generator_version": GENERATION_VERSION,
      },
    }


def stable_seed(dataset_id: str, sample_id: str, mask_family: str, base_seed: int) -> int:
  """Derive a reproducible per-task seed from stable identifiers."""
  digest = sha256(f"{dataset_id}:{sample_id}:{mask_family}:{base_seed}".encode("utf-8")).hexdigest()
  return int(digest[:12], 16)


def source_pages_from_resolved_dataset(payload: dict[str, Any]) -> list[SourcePage]:
  """Load registered full pages while preserving source and normalized metadata links."""
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
        db_ids=item.get("db_ids", {}),
        hsp_normalized_metadata=item.get("hsp_normalized_metadata") or item.get("hsp_normalized") or {},
        source_metadata={
          "purpose": item.get("purpose"),
          "iiif_manifest_url": item.get("iiif_manifest_url"),
          "iiif_image_service_url": item.get("iiif_image_service_url"),
          "iiif_resolution_status": item.get("iiif_resolution_status"),
        },
      )
    )
  return pages


def choose_crop_box(width: int, height: int, rng: random.Random, mask_family: str) -> tuple[int, int, int, int]:
  """Choose a reproducible crop box large enough for layout evaluation."""
  if width < 64 or height < 64:
    raise ValueError("Source image is too small for artificial-fragment generation")

  if mask_family == "rectangular":
    crop_w = max(32, int(width * rng.uniform(0.32, 0.46)))
    crop_h = max(32, int(height * rng.uniform(0.32, 0.48)))
  elif mask_family == "irregular":
    crop_w = max(32, int(width * rng.uniform(0.38, 0.58)))
    crop_h = max(32, int(height * rng.uniform(0.30, 0.52)))
  else:
    raise ValueError(f"Unsupported mask family: {mask_family}")

  crop_w = min(crop_w, width)
  crop_h = min(crop_h, height)
  x = rng.randint(0, width - crop_w)
  y = rng.randint(0, height - crop_h)
  return x, y, crop_w, crop_h


def irregular_polygon(width: int, height: int, rng: random.Random) -> list[tuple[int, int]]:
  """Create a torn-edge polygon in crop-local coordinates."""
  margin_x = max(3, int(width * 0.07))
  margin_y = max(3, int(height * 0.07))
  points: list[tuple[int, int]] = []

  for step in range(5):
    x = round(step * (width - 1) / 4)
    points.append((x, rng.randint(0, margin_y)))
  for step in range(1, 5):
    y = round(step * (height - 1) / 4)
    points.append((width - 1 - rng.randint(0, margin_x), y))
  for step in range(3, -1, -1):
    x = round(step * (width - 1) / 4)
    points.append((x, height - 1 - rng.randint(0, margin_y)))
  for step in range(3, 0, -1):
    y = round(step * (height - 1) / 4)
    points.append((rng.randint(0, margin_x), y))
  return points


def build_mask(size: tuple[int, int], mask_family: str, rng: random.Random) -> Image.Image:
  """Build a binary alpha mask for the requested fragment family."""
  width, height = size
  mask = Image.new("L", size, 0)
  draw = ImageDraw.Draw(mask)
  if mask_family == "rectangular":
    draw.rectangle((0, 0, width - 1, height - 1), fill=255)
  elif mask_family == "irregular":
    draw.polygon(irregular_polygon(width, height, rng), fill=255)
  else:
    raise ValueError(f"Unsupported mask family: {mask_family}")
  return mask


def generate_fragment_files(
  source_path: Path,
  fragment_path: Path,
  mask_path: Path,
  mask_family: str,
  random_seed: int,
) -> tuple[int, int, tuple[int, int, int, int]]:
  """Generate one transparent PNG fragment and matching mask from a source page."""
  if not source_path.exists():
    raise FileNotFoundError(f"Source image missing: {source_path}")
  if source_path.resolve() in {fragment_path.resolve(), mask_path.resolve()}:
    raise ValueError("Output paths must not overwrite the source image")

  rng = random.Random(random_seed)
  with Image.open(source_path) as image:
    source = image.convert("RGBA")
    source_width, source_height = source.size
    x, y, crop_w, crop_h = choose_crop_box(source_width, source_height, rng, mask_family)
    crop = source.crop((x, y, x + crop_w, y + crop_h))
    mask = build_mask((crop_w, crop_h), mask_family, rng)
    crop.putalpha(mask)

  fragment_path.parent.mkdir(parents=True, exist_ok=True)
  mask_path.parent.mkdir(parents=True, exist_ok=True)
  crop.save(fragment_path)
  mask.save(mask_path)
  return source_width, source_height, (x, y, crop_w, crop_h)


def build_tasks(
  *,
  root: Path,
  dataset_id: str,
  source_pages: list[SourcePage],
  output_dir: Path,
  base_seed: int,
) -> list[FragmentTask]:
  """Generate rectangular and irregular artificial fragments for each source page."""
  tasks: list[FragmentTask] = []
  for page in source_pages:
    source_path = root / page.local_path
    for mask_family in MASK_FAMILIES:
      random_seed = stable_seed(dataset_id, page.sample_id, mask_family, base_seed)
      task_id = f"af_{page.sample_id}_{mask_family}"
      fragment_rel = output_dir / "fragments" / f"{task_id}.png"
      mask_rel = output_dir / "masks" / f"{task_id}_mask.png"
      source_width, source_height, bbox = generate_fragment_files(
        source_path=source_path,
        fragment_path=root / fragment_rel,
        mask_path=root / mask_rel,
        mask_family=mask_family,
        random_seed=random_seed,
      )
      tasks.append(
        FragmentTask(
          task_id=task_id,
          source_page=page,
          mask_family=mask_family,
          random_seed=random_seed,
          source_width_px=source_width,
          source_height_px=source_height,
          bbox_xywh=bbox,
          fragment_path=fragment_rel.as_posix(),
          mask_path=mask_rel.as_posix(),
        )
      )
  return tasks
