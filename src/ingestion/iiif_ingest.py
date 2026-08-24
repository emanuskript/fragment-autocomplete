"""Persist normalized IIIF manifest data into the local PostgreSQL schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .iiif_manifest import NormalizedCanvas, NormalizedImageAsset, NormalizedManifest
from .iiif_normalizer import metadata_lookup


@dataclass
class IngestStats:
  """Track insert/update counts and soft warnings emitted during ingestion."""
  repositories_inserted: int = 0
  repositories_updated: int = 0
  manuscripts_inserted: int = 0
  manuscripts_updated: int = 0
  manifests_inserted: int = 0
  manifests_updated: int = 0
  canvases_inserted: int = 0
  canvases_updated: int = 0
  image_assets_inserted: int = 0
  image_assets_updated: int = 0
  warnings: list[str] = field(default_factory=list)


def open_rights_policy(license_or_rights: str | None) -> dict[str, bool | str]:
  """Apply the project's conservative open-rights policy to a manifest value."""
  value = (license_or_rights or "").lower()
  is_open_for_publication = any(token in value for token in ("creativecommons.org/publicdomain/zero", "creativecommons.org/publicdomain/mark", "creativecommons.org/licenses/by/"))
  # Training remains conservative even for open manifests until project policy is reviewed.
  return {
    "training_allowed": False,
    "publication_allowed": is_open_for_publication,
    "demo_allowed": is_open_for_publication,
    "access_level": "public" if is_open_for_publication else "internal",
  }


def _metadata_value(manifest: NormalizedManifest, names: tuple[str, ...]) -> str | None:
  return metadata_lookup(manifest.metadata, names)


def _normalized_yes_no(value: str | None) -> str | None:
  if value is None:
    return None
  lowered = value.strip().lower()
  if lowered in {"yes", "ja", "true", "1"}:
    return "yes"
  if lowered in {"no", "nein", "false", "0"}:
    return "no"
  return None


def _material_types(value: str | None) -> list[str]:
  if not value:
    return []
  lowered = value.lower()
  material_map = {
    "parchment": ("parchment", "pergament"),
    "paper": ("paper", "papier"),
    "papyrus": ("papyrus",),
    "linen": ("linen", "leinen"),
    "palm": ("palm",),
  }
  return [name for name, tokens in material_map.items() if any(token in lowered for token in tokens)]


def _object_form(value: str | None) -> str | None:
  if not value:
    return None
  lowered = value.strip().lower()
  form_map = {
    "codex": ("codex", "kode", "handschrift"),
    "fragment": ("fragment",),
    "composite": ("composite", "zusammengesetzt"),
    "collection": ("collection", "sammlung"),
    "scroll": ("scroll", "rolle"),
    "singleSheet": ("singlesheet", "single sheet", "einzelblatt"),
  }
  for normalized, tokens in form_map.items():
    if any(token in lowered for token in tokens):
      return normalized
  return None


def _object_status(value: str | None) -> str | None:
  if not value:
    return None
  lowered = value.strip().lower()
  allowed = {"existent", "missing", "destroyed", "displaced", "dismembered", "unknown"}
  return lowered if lowered in allowed else None


def normalized_hsp_metadata(manifest: NormalizedManifest) -> dict[str, Any]:
  """Map selected IIIF metadata labels into the HSP-aligned manuscript fields."""
  material = _metadata_value(manifest, ("material", "support"))
  place = _metadata_value(manifest, ("place", "origin", "provenance"))
  form_value = _metadata_value(manifest, ("form", "object type", "object form"))
  script = _metadata_value(manifest, ("script", "script type"))
  return {
    "hsp_id": _metadata_value(manifest, ("hsp-id", "hsp id")),
    "mxml_id": _metadata_value(manifest, ("mxml-id", "mxml id")),
    "corpus_id": _metadata_value(manifest, ("corpus", "corpus id")),
    "object_status": _object_status(_metadata_value(manifest, ("status",))),
    "object_form": _object_form(form_value),
    "material_type": _material_types(material),
    "orig_date_display": _metadata_value(manifest, ("date", "origdate", "origin date")),
    "orig_place_norm": [{"display": place, "role": "origin"}] if place else [],
    "script_type_display": script,
    "decoration": _normalized_yes_no(_metadata_value(manifest, ("decoration",))),
    "music_notation": _normalized_yes_no(_metadata_value(manifest, ("musicnotation", "music notation"))),
  }


def _fetch_one(conn: Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
  with conn.cursor(row_factory=dict_row) as cur:
    cur.execute(query, params)
    return cur.fetchone()


def _execute_returning(conn: Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
  with conn.cursor(row_factory=dict_row) as cur:
    cur.execute(query, params)
    row = cur.fetchone()
    if row is None:
      raise RuntimeError("Expected INSERT/UPDATE statement to return a row")
    return row


def upsert_repository(conn: Connection, repository_name: str, source_identifier: str, stats: IngestStats) -> str:
  """Insert or update the source repository row for a manifest."""
  row = _execute_returning(
    conn,
    """
    INSERT INTO repository (name, short_name, repository_type, metadata_review_status, raw_metadata)
    VALUES (%s, %s, 'iiif_repository', 'machine_extracted', %s)
    ON CONFLICT (name) DO UPDATE
    SET raw_metadata = repository.raw_metadata || EXCLUDED.raw_metadata,
        metadata_review_status = 'machine_extracted',
        updated_at = now()
    RETURNING id, (xmax = 0) AS inserted
    """,
    (
      repository_name,
      repository_name,
      Jsonb({"source": "iiif_ingestion", "source_identifier": source_identifier}),
    ),
  )
  if row["inserted"]:
    stats.repositories_inserted += 1
  else:
    stats.repositories_updated += 1
  return str(row["id"])


def upsert_manuscript(conn: Connection, repository_id: str, manifest: NormalizedManifest, stats: IngestStats) -> str:
  """Insert or update the manuscript row that groups the manifest canvases."""
  manifest_key = manifest.manifest_id or manifest.source_identifier
  hsp_metadata = normalized_hsp_metadata(manifest)
  existing = _fetch_one(
    conn,
    """
    SELECT id FROM manuscript
    WHERE repository_id = %s AND raw_metadata->>'iiif_manifest_key' = %s
    LIMIT 1
    """,
    (repository_id, manifest_key),
  )
  raw_metadata = {
    "source": "iiif_ingestion",
    "iiif_manifest_key": manifest_key,
    "manifest_id": manifest.manifest_id,
    "source_identifier": manifest.source_identifier,
    "metadata": manifest.metadata,
    "rights_statement": manifest.rights_statement,
    "license": manifest.license,
    "attribution": manifest.attribution,
    "hsp_normalized": hsp_metadata,
    "ingestion": manifest.ingestion_metadata,
  }
  params = (
    repository_id,
    metadata_lookup(manifest.metadata, ("shelfmark", "signatur", "call number")),
    _metadata_value(manifest, ("title",)) or manifest.label,
    metadata_lookup(manifest.metadata, ("place", "origin")),
    metadata_lookup(manifest.metadata, ("language",)),
    metadata_lookup(manifest.metadata, ("script",)),
    metadata_lookup(manifest.metadata, ("material",)),
    hsp_metadata.get("hsp_id"),
    hsp_metadata.get("mxml_id"),
    hsp_metadata.get("corpus_id"),
    hsp_metadata.get("object_status"),
    hsp_metadata.get("object_form"),
    Jsonb(hsp_metadata.get("material_type", [])),
    hsp_metadata.get("orig_date_display"),
    Jsonb(hsp_metadata.get("orig_place_norm", [])),
    hsp_metadata.get("script_type_display"),
    hsp_metadata.get("decoration"),
    hsp_metadata.get("music_notation"),
    Jsonb(raw_metadata),
  )

  if existing:
    row = _execute_returning(
      conn,
      """
      UPDATE manuscript
      SET shelfmark = COALESCE(%s, shelfmark),
          title = COALESCE(%s, title),
          place = COALESCE(%s, place),
          language = COALESCE(%s, language),
          script = COALESCE(%s, script),
          material = COALESCE(%s, material),
          hsp_id = COALESCE(%s, hsp_id),
          mxml_id = COALESCE(%s, mxml_id),
          corpus_id = COALESCE(%s, corpus_id),
          object_status = COALESCE(%s, object_status),
          object_form = COALESCE(%s, object_form),
          material_type = CASE WHEN jsonb_array_length(%s::jsonb) > 0 THEN %s::jsonb ELSE material_type END,
          orig_date_display = COALESCE(%s, orig_date_display),
          orig_place_norm = CASE WHEN jsonb_array_length(%s::jsonb) > 0 THEN %s::jsonb ELSE orig_place_norm END,
          script_type_display = COALESCE(%s, script_type_display),
          decoration = COALESCE(%s, decoration),
          music_notation = COALESCE(%s, music_notation),
          metadata_review_status = 'machine_extracted',
          raw_metadata = raw_metadata || %s,
          updated_at = now()
      WHERE id = %s
      RETURNING id
      """,
      (
        params[1],
        params[2],
        params[3],
        params[4],
        params[5],
        params[6],
        params[7],
        params[8],
        params[9],
        params[10],
        params[11],
        params[12],
        params[12],
        params[13],
        params[14],
        params[14],
        params[15],
        params[16],
        params[17],
        params[18],
        existing["id"],
      ),
    )
    stats.manuscripts_updated += 1
    return str(row["id"])

  row = _execute_returning(
    conn,
    """
    INSERT INTO manuscript (
      repository_id, shelfmark, title, place, language, script, material,
      hsp_id, mxml_id, corpus_id, object_status, object_form, material_type,
      orig_date_display, orig_place_norm, script_type_display, decoration,
      music_notation, metadata_review_status, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'machine_extracted', %s)
    RETURNING id
    """,
    params,
  )
  stats.manuscripts_inserted += 1
  return str(row["id"])


def upsert_manifest_cache(
  conn: Connection,
  repository_id: str,
  manuscript_id: str,
  manifest: NormalizedManifest,
  fetch_headers: dict[str, str | None],
  stats: IngestStats,
) -> str:
  """Upsert the cached raw manifest payload plus fetch metadata."""
  existing = _fetch_one(conn, "SELECT id FROM iiif_manifest_cache WHERE manifest_url = %s", (manifest.source_identifier,))
  row = _execute_returning(
    conn,
    """
    INSERT INTO iiif_manifest_cache (
      repository_id, manuscript_id, manifest_url, manifest_json, fetched_at, etag, last_modified, fetch_status, error_message
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', NULL)
    ON CONFLICT (manifest_url) DO UPDATE
    SET repository_id = EXCLUDED.repository_id,
        manuscript_id = EXCLUDED.manuscript_id,
        manifest_json = EXCLUDED.manifest_json,
        fetched_at = EXCLUDED.fetched_at,
        etag = EXCLUDED.etag,
        last_modified = EXCLUDED.last_modified,
        fetch_status = 'completed',
        error_message = NULL,
        updated_at = now()
    RETURNING id
    """,
    (
      repository_id,
      manuscript_id,
      manifest.source_identifier,
      Jsonb(manifest.raw_metadata),
      datetime.now(timezone.utc),
      fetch_headers.get("etag"),
      fetch_headers.get("last_modified"),
    ),
  )
  if existing:
    stats.manifests_updated += 1
  else:
    stats.manifests_inserted += 1
  return str(row["id"])


def upsert_canvas(conn: Connection, manuscript_id: str, manifest_cache_id: str, canvas: NormalizedCanvas, stats: IngestStats) -> str:
  """Insert or update one normalized canvas row."""
  existing = _fetch_one(
    conn,
    """
    SELECT id FROM canvas
    WHERE iiif_manifest_cache_id = %s AND canvas_identifier = %s
    LIMIT 1
    """,
    (manifest_cache_id, canvas.canvas_identifier),
  )
  params = (
    manuscript_id,
    manifest_cache_id,
    canvas.canvas_identifier,
    canvas.canvas_label,
    canvas.width_px,
    canvas.height_px,
    canvas.sequence_index,
    Jsonb({"source": "iiif_ingestion", "raw_canvas": canvas.raw_metadata, "ingestion": canvas.raw_metadata.get("training_corpus", {})}),
  )
  if existing:
    row = _execute_returning(
      conn,
      """
      UPDATE canvas
      SET manuscript_id = %s,
          iiif_manifest_cache_id = %s,
          canvas_identifier = %s,
          canvas_label = %s,
          width_px = %s,
          height_px = %s,
          sequence_index = %s,
          metadata_review_status = 'machine_extracted',
          raw_metadata = %s,
          updated_at = now()
      WHERE id = %s
      RETURNING id
      """,
      params + (existing["id"],),
    )
    stats.canvases_updated += 1
    return str(row["id"])

  row = _execute_returning(
    conn,
    """
    INSERT INTO canvas (
      manuscript_id, iiif_manifest_cache_id, canvas_identifier, canvas_label,
      width_px, height_px, sequence_index, metadata_review_status, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, 'machine_extracted', %s)
    RETURNING id
    """,
    params,
  )
  stats.canvases_inserted += 1
  return str(row["id"])


def upsert_image_asset(
  conn: Connection,
  repository_id: str,
  canvas_id: str,
  image: NormalizedImageAsset,
  manifest: NormalizedManifest,
  stats: IngestStats,
) -> str:
  """Insert or update one normalized image asset row for a canvas."""
  rights = open_rights_policy(manifest.license or manifest.rights_statement)
  existing = _fetch_one(
    conn,
    """
    SELECT id FROM image_asset
    WHERE canvas_id = %s
      AND source_url IS NOT DISTINCT FROM %s
      AND iiif_image_service_url IS NOT DISTINCT FROM %s
    LIMIT 1
    """,
    (canvas_id, image.source_url, image.iiif_image_service_url),
  )
  params = (
    canvas_id,
    repository_id,
    "iiif_image",
    image.source_url,
    image.iiif_image_service_url,
    image.media_type,
    image.width_px,
    image.height_px,
    image.local_path,
    image.checksum_sha256,
    manifest.rights_statement,
    manifest.license,
    manifest.attribution,
    rights["training_allowed"],
    rights["publication_allowed"],
    rights["demo_allowed"],
    rights["access_level"],
    manifest.license or manifest.rights_statement,
    image.rights_review_status,
    Jsonb({"source": "iiif_ingestion", "raw_image": image.raw_metadata, "ingestion": image.raw_metadata.get("training_corpus", {})}),
  )
  if existing:
    row = _execute_returning(
      conn,
      """
      UPDATE image_asset
      SET canvas_id = %s,
          repository_id = %s,
          asset_type = %s,
          source_url = %s,
          iiif_image_service_url = %s,
          media_type = %s,
          width_px = %s,
          height_px = %s,
          local_path = COALESCE(%s, local_path),
          checksum_sha256 = COALESCE(%s, checksum_sha256),
          rights_statement = %s,
          license = %s,
          attribution = %s,
          training_allowed = %s,
          publication_allowed = %s,
          demo_allowed = %s,
          access_level = %s,
          rights_uri = %s,
          rights_review_status = %s,
          metadata_review_status = 'machine_extracted',
          raw_metadata = %s,
          updated_at = now()
      WHERE id = %s
      RETURNING id
      """,
      params + (existing["id"],),
    )
    stats.image_assets_updated += 1
    return str(row["id"])

  row = _execute_returning(
    conn,
    """
    INSERT INTO image_asset (
      canvas_id, repository_id, asset_type, source_url, iiif_image_service_url, media_type,
      width_px, height_px, local_path, checksum_sha256, rights_statement, license, attribution,
      training_allowed, publication_allowed, demo_allowed, access_level,
      rights_uri, rights_review_status, metadata_review_status, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'machine_extracted', %s)
    RETURNING id
    """,
    params,
  )
  stats.image_assets_inserted += 1
  return str(row["id"])


def ingest_manifest(
  conn: Connection,
  manifest: NormalizedManifest,
  repository_name: str,
  fetch_headers: dict[str, str | None] | None = None,
) -> IngestStats:
  """Persist a normalized manifest and all dependent rows in one transaction."""
  stats = IngestStats()
  fetch_headers = fetch_headers or {}
  repository_id = upsert_repository(conn, repository_name, manifest.source_identifier, stats)
  manuscript_id = upsert_manuscript(conn, repository_id, manifest, stats)
  manifest_cache_id = upsert_manifest_cache(conn, repository_id, manuscript_id, manifest, fetch_headers, stats)

  for canvas in manifest.canvases:
    if canvas.width_px is None or canvas.height_px is None:
      stats.warnings.append(f"Canvas missing dimensions: {canvas.canvas_identifier}")
    if not canvas.images:
      stats.warnings.append(f"Canvas has no image assets: {canvas.canvas_identifier}")
    canvas_id = upsert_canvas(conn, manuscript_id, manifest_cache_id, canvas, stats)
    for image in canvas.images:
      if not image.iiif_image_service_url:
        stats.warnings.append(f"Image missing IIIF service URL: {image.source_url or canvas.canvas_identifier}")
      if not image.width_px or not image.height_px:
        stats.warnings.append(f"Image missing dimensions: {image.source_url or canvas.canvas_identifier}")
      if not (manifest.license or manifest.rights_statement):
        stats.warnings.append(f"Manifest missing rights/license: {manifest.source_identifier}")
      upsert_image_asset(conn, repository_id, canvas_id, image, manifest, stats)

  return stats
