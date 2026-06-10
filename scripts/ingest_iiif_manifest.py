#!/usr/bin/env python3
"""CLI entry point for IIIF manifest normalization and database ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.db import connect
from src.ingestion.iiif_client import ManifestLoadError, fetch_manifest_url, load_manifest_file
from src.ingestion.iiif_ingest import ingest_manifest
from src.ingestion.iiif_normalizer import normalize_manifest


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Ingest a IIIF Presentation manifest into the Fragment Autocomplete database.")
  source = parser.add_mutually_exclusive_group(required=True)
  source.add_argument("--file", help="Path to a local IIIF manifest JSON file.")
  source.add_argument("--url", help="Remote IIIF manifest URL.")
  parser.add_argument("--repository", required=True, help="Repository/source name to register or reuse.")
  parser.add_argument("--dry-run", action="store_true", help="Parse and normalize the manifest without writing to the database.")
  return parser


def main() -> int:
  args = build_parser().parse_args()

  try:
    if args.file:
      manifest_json, source_identifier = load_manifest_file(args.file)
      fetch_headers = {}
    else:
      manifest_json, source_identifier, fetch_headers = fetch_manifest_url(args.url)
    manifest = normalize_manifest(manifest_json, source_identifier)
  except (ManifestLoadError, ValueError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1

  image_count = sum(len(canvas.images) for canvas in manifest.canvases)
  print(f"Manifest loaded: {manifest.label or manifest.manifest_id or manifest.source_identifier}")
  print(f"Source identifier: {manifest.source_identifier}")
  print(f"Canvases detected: {len(manifest.canvases)}")
  print(f"Image assets detected: {image_count}")

  if args.dry_run:
    print("Dry run: no database writes performed.")
    print(json.dumps({
      "manifest_id": manifest.manifest_id,
      "label": manifest.label,
      "rights_statement": manifest.rights_statement,
      "license": manifest.license,
      "attribution": manifest.attribution,
      "canvas_count": len(manifest.canvases),
      "image_asset_count": image_count,
    }, indent=2, sort_keys=True))
    return 0

  try:
    with connect() as conn:
      stats = ingest_manifest(conn, manifest, args.repository, fetch_headers)
      conn.commit()
  except Exception as exc:
    print(f"ERROR: database ingestion failed: {exc}", file=sys.stderr)
    return 1

  print("Database rows inserted/updated:")
  print(f"  repositories: {stats.repositories_inserted} inserted, {stats.repositories_updated} updated")
  print(f"  manuscripts: {stats.manuscripts_inserted} inserted, {stats.manuscripts_updated} updated")
  print(f"  manifest cache rows: {stats.manifests_inserted} inserted, {stats.manifests_updated} updated")
  print(f"  canvases: {stats.canvases_inserted} inserted, {stats.canvases_updated} updated")
  print(f"  image assets: {stats.image_assets_inserted} inserted, {stats.image_assets_updated} updated")
  for warning in stats.warnings:
    print(f"WARNING: {warning}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
