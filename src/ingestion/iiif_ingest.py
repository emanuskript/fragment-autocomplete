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
  value = (license_or_rights or "").lower()
  is_open_for_publication = any(token in value for token in ("creativecommons.org/publicdomain/zero", "creativecommons.org/publicdomain/mark", "creativecommons.org/licenses/by/"))
  # Training remains conservative even for open manifests until project policy is reviewed.
  return {
    "training_allowed": False,
    "publication_allowed": is_open_for_publication,
    "demo_allowed": is_open_for_publication,
    "access_level": "public" if is_open_for_publication else "internal",
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
  row = _execute_returning(
    conn,
    """
    INSERT INTO repository (name, short_name, repository_type, raw_metadata)
    VALUES (%s, %s, 'iiif_repository', %s)
    ON CONFLICT (name) DO UPDATE
    SET raw_metadata = repository.raw_metadata || EXCLUDED.raw_metadata,
        updated_at = now()
    RETURNING id, (xmax = 0) AS inserted
    """,
    (
      repository_name,
      repository_name,
      Jsonb({"source": "iiif_ingestion_poc", "source_identifier": source_identifier}),
    ),
  )
  if row["inserted"]:
    stats.repositories_inserted += 1
  else:
    stats.repositories_updated += 1
  return str(row["id"])


def upsert_manuscript(conn: Connection, repository_id: str, manifest: NormalizedManifest, stats: IngestStats) -> str:
  manifest_key = manifest.manifest_id or manifest.source_identifier
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
    "source": "iiif_ingestion_poc",
    "iiif_manifest_key": manifest_key,
    "manifest_id": manifest.manifest_id,
    "source_identifier": manifest.source_identifier,
    "metadata": manifest.metadata,
    "rights_statement": manifest.rights_statement,
    "license": manifest.license,
    "attribution": manifest.attribution,
  }
  params = (
    repository_id,
    metadata_lookup(manifest.metadata, ("shelfmark", "signatur", "call number")),
    manifest.label,
    metadata_lookup(manifest.metadata, ("place", "origin")),
    metadata_lookup(manifest.metadata, ("language",)),
    metadata_lookup(manifest.metadata, ("script",)),
    metadata_lookup(manifest.metadata, ("material",)),
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
          raw_metadata = raw_metadata || %s,
          updated_at = now()
      WHERE id = %s
      RETURNING id
      """,
      params[1:] + (existing["id"],),
    )
    stats.manuscripts_updated += 1
    return str(row["id"])

  row = _execute_returning(
    conn,
    """
    INSERT INTO manuscript (
      repository_id, shelfmark, title, place, language, script, material, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
    Jsonb({"source": "iiif_ingestion_poc", "raw_canvas": canvas.raw_metadata}),
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
      manuscript_id, iiif_manifest_cache_id, canvas_identifier, canvas_label, width_px, height_px, sequence_index, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
    manifest.rights_statement,
    manifest.license,
    manifest.attribution,
    rights["training_allowed"],
    rights["publication_allowed"],
    rights["demo_allowed"],
    rights["access_level"],
    Jsonb({"source": "iiif_ingestion_poc", "raw_image": image.raw_metadata}),
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
          rights_statement = %s,
          license = %s,
          attribution = %s,
          training_allowed = %s,
          publication_allowed = %s,
          demo_allowed = %s,
          access_level = %s,
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
      width_px, height_px, rights_statement, license, attribution,
      training_allowed, publication_allowed, demo_allowed, access_level, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
