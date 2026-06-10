"""Typed normalized IIIF manifest records shared across ingestion steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedImageAsset:
  """Normalized image asset metadata extracted from a IIIF canvas."""
  source_url: str | None
  iiif_image_service_url: str | None
  media_type: str | None
  width_px: int | None
  height_px: int | None
  raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedCanvas:
  """Normalized IIIF canvas metadata with attached image assets."""
  canvas_identifier: str
  canvas_label: str | None
  width_px: int | None
  height_px: int | None
  sequence_index: int
  raw_metadata: dict[str, Any]
  images: list[NormalizedImageAsset]


@dataclass(frozen=True)
class NormalizedManifest:
  """Normalized IIIF manifest record used by downstream database ingestion."""
  source_identifier: str
  manifest_id: str | None
  label: str | None
  metadata: list[dict[str, Any]]
  rights_statement: str | None
  license: str | None
  attribution: str | None
  raw_metadata: dict[str, Any]
  canvases: list[NormalizedCanvas]
