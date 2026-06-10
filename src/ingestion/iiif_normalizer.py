"""Normalize IIIF Presentation v2/v3 payloads into a shared internal shape."""

from __future__ import annotations

from typing import Any

from .iiif_manifest import NormalizedCanvas, NormalizedImageAsset, NormalizedManifest


def _first(value: Any) -> Any:
  if isinstance(value, list):
    return value[0] if value else None
  return value


def text_value(value: Any) -> str | None:
  """Flatten common IIIF multilingual/value containers into a readable string."""
  if value is None:
    return None
  if isinstance(value, str):
    return value
  if isinstance(value, (int, float)):
    return str(value)
  if isinstance(value, list):
    parts = [text_value(item) for item in value]
    return "; ".join(part for part in parts if part) or None
  if isinstance(value, dict):
    if "@value" in value:
      return text_value(value.get("@value"))
    if "value" in value and not isinstance(value.get("value"), (dict, list)):
      return text_value(value.get("value"))
    if "none" in value:
      return text_value(value.get("none"))
    if "en" in value:
      return text_value(value.get("en"))
    for item in value.values():
      rendered = text_value(item)
      if rendered:
        return rendered
  return str(value)


def _identifier(data: dict[str, Any]) -> str | None:
  return data.get("id") or data.get("@id")


def _type(data: dict[str, Any]) -> str | None:
  return data.get("type") or data.get("@type")


def _int_value(value: Any) -> int | None:
  if value is None:
    return None
  try:
    return int(value)
  except (TypeError, ValueError):
    return None


def normalize_metadata(metadata: Any) -> list[dict[str, Any]]:
  """Convert raw IIIF metadata lists into label/value records with provenance."""
  normalized: list[dict[str, Any]] = []
  if not isinstance(metadata, list):
    return normalized
  for item in metadata:
    if not isinstance(item, dict):
      continue
    label = text_value(item.get("label"))
    value = text_value(item.get("value"))
    if label or value:
      normalized.append({"label": label, "value": value, "raw": item})
  return normalized


def metadata_lookup(metadata: list[dict[str, Any]], names: tuple[str, ...]) -> str | None:
  """Find the first metadata value whose label matches one of the requested names."""
  lowered = tuple(name.lower() for name in names)
  for item in metadata:
    label = (item.get("label") or "").lower()
    if any(name in label for name in lowered):
      return item.get("value")
  return None


def _service_url(service: Any) -> str | None:
  service_data = _first(service)
  if isinstance(service_data, dict):
    return _identifier(service_data)
  if isinstance(service_data, str):
    return service_data
  return None


def _v2_image_from_resource(resource: dict[str, Any]) -> NormalizedImageAsset:
  return NormalizedImageAsset(
    source_url=_identifier(resource),
    iiif_image_service_url=_service_url(resource.get("service")),
    media_type=resource.get("format"),
    width_px=_int_value(resource.get("width")),
    height_px=_int_value(resource.get("height")),
    raw_metadata=resource,
  )


def _v3_image_from_body(body: dict[str, Any]) -> NormalizedImageAsset | None:
  body_type = _type(body)
  if body_type and body_type.lower() not in {"image", "dctypes:image"}:
    return None
  return NormalizedImageAsset(
    source_url=_identifier(body),
    iiif_image_service_url=_service_url(body.get("service")),
    media_type=body.get("format"),
    width_px=_int_value(body.get("width")),
    height_px=_int_value(body.get("height")),
    raw_metadata=body,
  )


def _normalize_v2_canvas(canvas: dict[str, Any], sequence_index: int) -> NormalizedCanvas:
  images: list[NormalizedImageAsset] = []
  for annotation in canvas.get("images") or []:
    if not isinstance(annotation, dict):
      continue
    resource = annotation.get("resource")
    if isinstance(resource, dict):
      images.append(_v2_image_from_resource(resource))

  return NormalizedCanvas(
    canvas_identifier=_identifier(canvas) or f"unknown-v2-canvas-{sequence_index}",
    canvas_label=text_value(canvas.get("label")),
    width_px=_int_value(canvas.get("width")),
    height_px=_int_value(canvas.get("height")),
    sequence_index=sequence_index,
    raw_metadata=canvas,
    images=images,
  )


def _normalize_v3_canvas(canvas: dict[str, Any], sequence_index: int) -> NormalizedCanvas:
  images: list[NormalizedImageAsset] = []
  for annotation_page in canvas.get("items") or []:
    if not isinstance(annotation_page, dict):
      continue
    for annotation in annotation_page.get("items") or []:
      if not isinstance(annotation, dict):
        continue
      bodies = annotation.get("body")
      body_list = bodies if isinstance(bodies, list) else [bodies]
      for body in body_list:
        if isinstance(body, dict):
          image = _v3_image_from_body(body)
          if image:
            images.append(image)

  return NormalizedCanvas(
    canvas_identifier=_identifier(canvas) or f"unknown-v3-canvas-{sequence_index}",
    canvas_label=text_value(canvas.get("label")),
    width_px=_int_value(canvas.get("width")),
    height_px=_int_value(canvas.get("height")),
    sequence_index=sequence_index,
    raw_metadata=canvas,
    images=images,
  )


def _normalize_v2(manifest: dict[str, Any], source_identifier: str) -> NormalizedManifest:
  sequences = manifest.get("sequences") or []
  canvases_raw = []
  if sequences and isinstance(sequences[0], dict):
    canvases_raw = sequences[0].get("canvases") or []

  metadata = normalize_metadata(manifest.get("metadata"))
  canvases = [
    _normalize_v2_canvas(canvas, index)
    for index, canvas in enumerate(canvases_raw)
    if isinstance(canvas, dict)
  ]

  return NormalizedManifest(
    source_identifier=source_identifier,
    manifest_id=_identifier(manifest),
    label=text_value(manifest.get("label")),
    metadata=metadata,
    rights_statement=manifest.get("license"),
    license=manifest.get("license"),
    attribution=text_value(manifest.get("attribution")),
    raw_metadata=manifest,
    canvases=canvases,
  )


def _normalize_v3(manifest: dict[str, Any], source_identifier: str) -> NormalizedManifest:
  metadata = normalize_metadata(manifest.get("metadata"))
  canvases = [
    _normalize_v3_canvas(canvas, index)
    for index, canvas in enumerate(manifest.get("items") or [])
    if isinstance(canvas, dict)
  ]

  required_statement = manifest.get("requiredStatement")
  attribution = text_value(required_statement.get("value")) if isinstance(required_statement, dict) else None
  if not attribution:
    providers = manifest.get("provider") or []
    provider = _first(providers)
    if isinstance(provider, dict):
      attribution = text_value(provider.get("label"))

  return NormalizedManifest(
    source_identifier=source_identifier,
    manifest_id=_identifier(manifest),
    label=text_value(manifest.get("label")),
    metadata=metadata,
    rights_statement=manifest.get("rights"),
    license=manifest.get("rights"),
    attribution=attribution,
    raw_metadata=manifest,
    canvases=canvases,
  )


def normalize_manifest(manifest: dict[str, Any], source_identifier: str) -> NormalizedManifest:
  """Normalize a IIIF Presentation manifest regardless of v2/v3 wire format."""
  manifest_type = (_type(manifest) or "").lower()
  if manifest_type == "manifest":
    return _normalize_v3(manifest, source_identifier)
  if manifest_type in {"sc:manifest", "manifest"} or "sequences" in manifest:
    return _normalize_v2(manifest, source_identifier)
  if "items" in manifest:
    return _normalize_v3(manifest, source_identifier)
  raise ValueError("Unsupported or unrecognized IIIF Presentation manifest")
