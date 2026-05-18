#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.db import connect

DATASET_ID = "initial_sample_dataset_v0_1"
DEFAULT_CONFIG = Path("data/metadata/initial_sample_dataset.yaml")
DEFAULT_RESOLVED = Path("data/metadata/initial_sample_dataset_resolved.yaml")
DEFAULT_REPORT = Path("docs/04_initial_sample_dataset_report.md")

RIGHTS_DEFAULTS = {
  "rights_review_status": "pending_review",
  "training_allowed": False,
  "publication_allowed": False,
  "demo_allowed": False,
  "access_level": "internal",
}

EXPECTED_FULL_PAGES = [
  {
    "id": "fp_01_clean_simple",
    "category": "clean_simple",
    "source": "e-codices",
    "url": "https://www.e-codices.unifr.ch/en/csg/0300/5/0/",
    "purpose": "Simple full-page baseline for segmentation and artificial-fragment generation.",
  },
  {
    "id": "fp_02_clean_simple",
    "category": "clean_simple",
    "source": "e-codices",
    "url": "https://www.e-codices.unifr.ch/en/kba/Wett0004/9r",
    "purpose": "Simple full-page baseline for segmentation and artificial-fragment generation.",
  },
  {
    "id": "fp_03_complex_layout",
    "category": "complex_layout",
    "source": "e-codices",
    "url": "https://www.e-codices.unifr.ch/en/csg/0059/2",
    "purpose": "Complex page for testing glosses, initials, music, illustration, or multi-zone layout.",
  },
  {
    "id": "fp_04_complex_layout",
    "category": "complex_layout",
    "source": "e-codices",
    "url": "https://www.e-codices.unifr.ch/en/ubb/F-IX-0068/2r",
    "purpose": "Complex page for testing glosses, initials, music, illustration, or multi-column layout.",
  },
  {
    "id": "fp_05_iiif_rights",
    "category": "iiif_rights_metadata",
    "source": "e-codices",
    "url": "https://www.e-codices.unifr.ch/en/csg/0314/3",
    "purpose": "Validate IIIF manifest extraction, image service extraction, rights metadata, and attribution.",
  },
]

EXPECTED_FRAGMENTS = [
  {
    "id": "fr_01_binding_strip",
    "category": "binding_strip",
    "source": "Fragmentarium",
    "url": "https://fragmentarium.ms/view/page/F-cpkx/4139/43306",
    "purpose": "Real fragment case: binding strip or narrow reused fragment.",
  },
  {
    "id": "fr_02_text_block",
    "category": "text_block",
    "source": "Fragmentarium",
    "url": "https://fragmentarium.ms/view/page/F-sf5d/6321/54882",
    "purpose": "Real fragment case: visible main text block.",
  },
  {
    "id": "fr_03_marginal_gloss",
    "category": "marginal_gloss",
    "source": "Fragmentarium",
    "url": "https://fragmentarium.ms/view/page/F-0dfk/9908/72248",
    "purpose": "Real fragment case: marginal, gloss, or secondary text material.",
  },
  {
    "id": "fr_04_decoration_initial",
    "category": "decoration_initial",
    "source": "Fragmentarium",
    "url": "https://fragmentarium.ms/view/page/F-5el0/10778/77958",
    "purpose": "Real fragment case: decoration, initials, or visually distinctive layout element.",
  },
  {
    "id": "fr_05_damaged_irregular",
    "category": "damaged_irregular",
    "source": "Fragmentarium",
    "url": "https://fragmentarium.ms/view/page/F-knxa/11598/83378",
    "purpose": "Real fragment case: difficult damaged or irregular fragment.",
  },
]


@dataclass
class RegistrationStats:
  repositories_inserted: int = 0
  repositories_matched: int = 0
  manuscripts_inserted: int = 0
  manuscripts_matched: int = 0
  canvases_inserted: int = 0
  canvases_matched: int = 0
  image_assets_inserted: int = 0
  image_assets_matched: int = 0
  fragments_inserted: int = 0
  fragments_matched: int = 0
  iiif_resolved: int = 0
  iiif_unresolved: int = 0
  iiif_not_attempted: int = 0
  local_files_matched: int = 0
  warnings: list[str] = field(default_factory=list)


def rel(path: Path) -> str:
  return path.relative_to(ROOT).as_posix()


def load_yaml(path: Path) -> dict[str, Any]:
  return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, data: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def build_config(dataset_root: Path) -> dict[str, Any]:
  return {
    "dataset_id": DATASET_ID,
    "status": "registered",
    "purpose": "Initial pilot dataset for IIIF registration, eManuSkript segmentation testing, artificial-fragment preparation, and real-fragment workflow validation.",
    "created_from": dataset_root.as_posix(),
    "rights_policy": "conservative_pending_review",
    "full_pages": [sample_item("full_page", item) for item in EXPECTED_FULL_PAGES],
    "fragments": [sample_item("fragment", item) for item in EXPECTED_FRAGMENTS],
  }


def sample_item(kind: str, item: dict[str, str]) -> dict[str, Any]:
  return {
    **item,
    "local_path": None,
    "local_file_mapping_status": "missing",
    "iiif_manifest_url": None,
    "iiif_image_service_url": None,
    "iiif_resolution_status": "not_attempted",
    **RIGHTS_DEFAULTS,
    "sample_kind": kind,
  }


def ensure_config(path: Path, dataset_root: Path) -> dict[str, Any]:
  if path.exists():
    return load_yaml(path)
  config = build_config(dataset_root)
  write_yaml(path, config)
  return config


def map_local_files(config: dict[str, Any], dataset_root: Path) -> None:
  files = sorted(path for path in (ROOT / dataset_root).glob("**/*") if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"})
  by_parent = {path.parent.name: path for path in files}
  for section in ("full_pages", "fragments"):
    for item in config.get(section, []):
      path = by_parent.get(item["id"])
      if path:
        item["local_path"] = rel(path)
        item["local_file_mapping_status"] = "matched"
      else:
        item["local_path"] = None
        item["local_file_mapping_status"] = "missing"


def attempt_iiif_resolution(item: dict[str, Any], timeout_seconds: int = 10) -> tuple[str, str | None, str | None, str | None]:
  try:
    response = requests.get(item["url"], timeout=timeout_seconds, headers={"Accept": "text/html,application/xhtml+xml"})
    response.raise_for_status()
  except requests.RequestException as exc:
    return "unresolved", None, None, f"Could not fetch source page: {exc}"

  html = response.text
  manifest_patterns = [
    r'https?://[^"\']+?manifest[^"\']*?\.json',
    r'https?://[^"\']+?/iiif/[^"\']+?/manifest[^"\']*',
  ]
  service_patterns = [
    r'https?://[^"\']+?/iiif/[^"\']+',
  ]
  manifest_url = first_regex_match(manifest_patterns, html)
  service_url = first_regex_match(service_patterns, html)
  if manifest_url or service_url:
    return "resolved", manifest_url, service_url, None
  return "unresolved", None, None, "No obvious IIIF manifest or image service URL found in page HTML."


def first_regex_match(patterns: list[str], text: str) -> str | None:
  for pattern in patterns:
    match = re.search(pattern, text)
    if match:
      return match.group(0).replace("\\/", "/")
  return None


def annotate_iiif_status(config: dict[str, Any], attempt_resolution: bool, stats: RegistrationStats) -> None:
  for section in ("full_pages", "fragments"):
    for item in config.get(section, []):
      if not attempt_resolution:
        item["iiif_resolution_status"] = "not_attempted"
        stats.iiif_not_attempted += 1
        continue
      status, manifest_url, service_url, warning = attempt_iiif_resolution(item)
      item["iiif_resolution_status"] = status
      item["iiif_manifest_url"] = manifest_url
      item["iiif_image_service_url"] = service_url
      if status == "resolved":
        stats.iiif_resolved += 1
      else:
        stats.iiif_unresolved += 1
      if warning:
        stats.warnings.append(f"{item['id']}: {warning}")


def fetch_one(conn: Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
  with conn.cursor(row_factory=dict_row) as cursor:
    cursor.execute(query, params)
    return cursor.fetchone()


def execute_returning(conn: Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
  with conn.cursor(row_factory=dict_row) as cursor:
    cursor.execute(query, params)
    row = cursor.fetchone()
    if not row:
      raise RuntimeError("Expected database statement to return a row")
    return row


def upsert_repository(conn: Connection, name: str, stats: RegistrationStats) -> str:
  existing = fetch_one(conn, "SELECT id FROM repository WHERE name = %s", (name,))
  row = execute_returning(
    conn,
    """
    INSERT INTO repository (name, short_name, repository_type, raw_metadata)
    VALUES (%s, %s, 'sample_source', %s)
    ON CONFLICT (name) DO UPDATE
    SET raw_metadata = repository.raw_metadata || EXCLUDED.raw_metadata,
        updated_at = now()
    RETURNING id
    """,
    (name, name, Jsonb({"source": "initial_sample_dataset_registration", "dataset_id": DATASET_ID})),
  )
  if existing:
    stats.repositories_matched += 1
  else:
    stats.repositories_inserted += 1
  return str(row["id"])


def raw_metadata(item: dict[str, Any]) -> dict[str, Any]:
  return {
    "sample_dataset_id": DATASET_ID,
    "sample_id": item["id"],
    "sample_kind": item["sample_kind"],
    "category": item["category"],
    "purpose": item["purpose"],
    "source": item["source"],
    "source_url": item["url"],
    "local_path": item.get("local_path"),
    "local_file_mapping_status": item.get("local_file_mapping_status"),
    "iiif_manifest_url": item.get("iiif_manifest_url"),
    "iiif_image_service_url": item.get("iiif_image_service_url"),
    "iiif_resolution_status": item.get("iiif_resolution_status"),
    "rights_review_status": item.get("rights_review_status"),
    "registration_source": "register_initial_sample_dataset.py",
  }


def upsert_manuscript(conn: Connection, repository_id: str, item: dict[str, Any], stats: RegistrationStats) -> str:
  existing = fetch_one(
    conn,
    "SELECT id FROM manuscript WHERE raw_metadata->>'sample_dataset_id' = %s AND raw_metadata->>'sample_id' = %s",
    (DATASET_ID, item["id"]),
  )
  metadata = raw_metadata(item)
  if existing:
    row = execute_returning(
      conn,
      """
      UPDATE manuscript
      SET repository_id = %s,
          shelfmark = %s,
          title = %s,
          description = %s,
          raw_metadata = %s,
          updated_at = now()
      WHERE id = %s
      RETURNING id
      """,
      (repository_id, item["id"], item["id"], item["purpose"], Jsonb(metadata), existing["id"]),
    )
    stats.manuscripts_matched += 1
  else:
    row = execute_returning(
      conn,
      """
      INSERT INTO manuscript (repository_id, shelfmark, title, description, raw_metadata)
      VALUES (%s, %s, %s, %s, %s)
      RETURNING id
      """,
      (repository_id, item["id"], item["id"], item["purpose"], Jsonb(metadata)),
    )
    stats.manuscripts_inserted += 1
  return str(row["id"])


def upsert_canvas(conn: Connection, manuscript_id: str, item: dict[str, Any], index: int, stats: RegistrationStats) -> str:
  existing = fetch_one(
    conn,
    "SELECT id FROM canvas WHERE raw_metadata->>'sample_dataset_id' = %s AND raw_metadata->>'sample_id' = %s",
    (DATASET_ID, item["id"]),
  )
  metadata = raw_metadata(item)
  canvas_identifier = item.get("iiif_manifest_url") or item["url"]
  if existing:
    row = execute_returning(
      conn,
      """
      UPDATE canvas
      SET manuscript_id = %s,
          canvas_identifier = %s,
          canvas_label = %s,
          sequence_index = %s,
          raw_metadata = %s,
          updated_at = now()
      WHERE id = %s
      RETURNING id
      """,
      (manuscript_id, canvas_identifier, item["id"], index, Jsonb(metadata), existing["id"]),
    )
    stats.canvases_matched += 1
  else:
    row = execute_returning(
      conn,
      """
      INSERT INTO canvas (manuscript_id, canvas_identifier, canvas_label, sequence_index, raw_metadata)
      VALUES (%s, %s, %s, %s, %s)
      RETURNING id
      """,
      (manuscript_id, canvas_identifier, item["id"], index, Jsonb(metadata)),
    )
    stats.canvases_inserted += 1
  return str(row["id"])


def upsert_image_asset(conn: Connection, repository_id: str, canvas_id: str | None, item: dict[str, Any], stats: RegistrationStats) -> str:
  existing = fetch_one(
    conn,
    "SELECT id FROM image_asset WHERE raw_metadata->>'sample_dataset_id' = %s AND raw_metadata->>'sample_id' = %s",
    (DATASET_ID, item["id"]),
  )
  metadata = raw_metadata(item)
  params = (
    canvas_id,
    repository_id,
    item["sample_kind"],
    item["url"],
    item.get("iiif_image_service_url"),
    item.get("local_path"),
    "image/jpeg" if item.get("local_path", "").lower().endswith((".jpg", ".jpeg")) else None,
    None,
    None,
    None,
    False,
    False,
    False,
    "internal",
    Jsonb(metadata),
  )
  if existing:
    row = execute_returning(
      conn,
      """
      UPDATE image_asset
      SET canvas_id = %s,
          repository_id = %s,
          asset_type = %s,
          source_url = %s,
          iiif_image_service_url = %s,
          local_path = %s,
          media_type = %s,
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
    stats.image_assets_matched += 1
  else:
    row = execute_returning(
      conn,
      """
      INSERT INTO image_asset (
        canvas_id, repository_id, asset_type, source_url, iiif_image_service_url, local_path,
        media_type, rights_statement, license, attribution,
        training_allowed, publication_allowed, demo_allowed, access_level, raw_metadata
      )
      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
      RETURNING id
      """,
      params,
    )
    stats.image_assets_inserted += 1
  return str(row["id"])


def upsert_fragment(conn: Connection, repository_id: str, image_asset_id: str, item: dict[str, Any], stats: RegistrationStats) -> str:
  del repository_id
  existing = fetch_one(
    conn,
    "SELECT id FROM fragment WHERE raw_metadata->>'sample_dataset_id' = %s AND raw_metadata->>'sample_id' = %s",
    (DATASET_ID, item["id"]),
  )
  metadata = raw_metadata(item)
  params = (
    image_asset_id,
    item["id"],
    item["id"],
    item["category"],
    item["purpose"],
    None,
    None,
    None,
    False,
    False,
    False,
    "internal",
    Jsonb(metadata),
  )
  if existing:
    row = execute_returning(
      conn,
      """
      UPDATE fragment
      SET image_asset_id = %s,
          shelfmark = %s,
          fragment_label = %s,
          fragment_type = %s,
          description = %s,
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
    stats.fragments_matched += 1
  else:
    row = execute_returning(
      conn,
      """
      INSERT INTO fragment (
        image_asset_id, shelfmark, fragment_label, fragment_type, description,
        rights_statement, license, attribution,
        training_allowed, publication_allowed, demo_allowed, access_level, raw_metadata
      )
      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
      RETURNING id
      """,
      params,
    )
    stats.fragments_inserted += 1
  return str(row["id"])


def register_dataset(config: dict[str, Any], dry_run: bool) -> tuple[dict[str, Any], RegistrationStats]:
  stats = RegistrationStats()
  resolved = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "dataset_id": config["dataset_id"],
    "status": "dry_run" if dry_run else "registered",
    "full_pages": [],
    "fragments": [],
    "summary": {},
  }

  for section in ("full_pages", "fragments"):
    for item in config.get(section, []):
      if item.get("local_file_mapping_status") == "matched":
        stats.local_files_matched += 1

  if dry_run:
    for section in ("full_pages", "fragments"):
      resolved[section] = [{**item, "registration_status": "dry_run"} for item in config.get(section, [])]
    resolved["summary"] = stats.__dict__
    return resolved, stats

  with connect() as conn:
    repositories = {source: upsert_repository(conn, source, stats) for source in sorted({item["source"] for item in config["full_pages"] + config["fragments"]})}
    for index, item in enumerate(config["full_pages"]):
      repository_id = repositories[item["source"]]
      manuscript_id = upsert_manuscript(conn, repository_id, item, stats)
      canvas_id = upsert_canvas(conn, manuscript_id, item, index, stats)
      image_asset_id = upsert_image_asset(conn, repository_id, canvas_id, item, stats)
      resolved["full_pages"].append({**item, "registration_status": "registered", "db_ids": {"repository_id": repository_id, "manuscript_id": manuscript_id, "canvas_id": canvas_id, "image_asset_id": image_asset_id}})
    for item in config["fragments"]:
      repository_id = repositories[item["source"]]
      image_asset_id = upsert_image_asset(conn, repository_id, None, item, stats)
      fragment_id = upsert_fragment(conn, repository_id, image_asset_id, item, stats)
      resolved["fragments"].append({**item, "registration_status": "registered", "db_ids": {"repository_id": repository_id, "image_asset_id": image_asset_id, "fragment_id": fragment_id}})
    conn.commit()

  resolved["summary"] = stats.__dict__
  return resolved, stats


def write_report(resolved: dict[str, Any], path: Path) -> None:
  full_pages = resolved.get("full_pages", [])
  fragments = resolved.get("fragments", [])
  summary = resolved.get("summary", {})
  lines = [
    "# Fragment Autocomplete — Initial Sample Dataset Report",
    "",
    "## 1. Purpose",
    "",
    "This report documents registration of the initial pilot sample dataset from `autocomplete-test-dataset/`. It prepares metadata and database records for later eManuSkript segmentation testing.",
    "",
    "This is a pilot sample dataset, not the full 5,000-10,000-page project dataset. eManuSkript has not been run, and model weights have not been loaded.",
    "",
    "## 2. Dataset summary",
    "",
    f"- Dataset ID: `{resolved.get('dataset_id')}`",
    f"- Full-page samples: {len(full_pages)}",
    f"- Fragment samples: {len(fragments)}",
    f"- Local files mapped: {summary.get('local_files_matched', 0)}",
    "",
    "## 3. Full-page samples",
    "",
    "| ID | Category | Source | Local mapping | IIIF status | Purpose |",
    "| --- | --- | --- | --- | --- | --- |",
  ]
  for item in full_pages:
    lines.append(f"| `{item['id']}` | {item['category']} | {item['source']} | {item['local_file_mapping_status']} | {item['iiif_resolution_status']} | {item['purpose']} |")
  lines.extend(["", "## 4. Fragment samples", "", "| ID | Category | Source | Local mapping | IIIF status | Purpose |", "| --- | --- | --- | --- | --- | --- |"])
  for item in fragments:
    lines.append(f"| `{item['id']}` | {item['category']} | {item['source']} | {item['local_file_mapping_status']} | {item['iiif_resolution_status']} | {item['purpose']} |")
  lines.extend([
    "",
    "## 5. Local file mapping",
    "",
    "Local images were matched by expected sample directory name. Unmatched items would be marked `missing` or `needs_review` in the resolved metadata.",
    "",
    "## 6. IIIF resolution status",
    "",
    f"- Resolved: {summary.get('iiif_resolved', 0)}",
    f"- Unresolved: {summary.get('iiif_unresolved', 0)}",
    f"- Not attempted: {summary.get('iiif_not_attempted', 0)}",
    "",
    "Human viewer URLs were preserved for all samples. IIIF resolution can be repeated later with `--attempt-iiif-resolution`; unresolved viewer URLs do not block local registration.",
    "",
    "## 7. Database registration summary",
    "",
    f"- Repositories inserted/matched: {summary.get('repositories_inserted', 0)} / {summary.get('repositories_matched', 0)}",
    f"- Manuscripts inserted/matched: {summary.get('manuscripts_inserted', 0)} / {summary.get('manuscripts_matched', 0)}",
    f"- Canvases inserted/matched: {summary.get('canvases_inserted', 0)} / {summary.get('canvases_matched', 0)}",
    f"- Image assets inserted/matched: {summary.get('image_assets_inserted', 0)} / {summary.get('image_assets_matched', 0)}",
    f"- Fragments inserted/matched: {summary.get('fragments_inserted', 0)} / {summary.get('fragments_matched', 0)}",
    "",
    "## 8. Rights and access status",
    "",
    "Rights are conservatively marked `pending_review`. Training, publication, and demo flags are false by default, and access level is `internal`.",
    "",
    "## 9. Known issues / unresolved items",
    "",
    "- Source URLs are human viewer URLs and may need further IIIF manifest resolution.",
    "- Rights require explicit review before publication, demo use, or training use.",
    "- Local file checksums are available in `data/metadata/local_assets_manifest.yaml`.",
    "",
    "## 10. Readiness for eManuSkript segmentation test",
    "",
    "The registered sample records are ready for model compatibility inspection and a controlled first eManuSkript segmentation test. No segmentation has been run yet.",
    "",
    "## 11. Next steps",
    "",
    "Inspect model weights compatibility and prepare the eManuSkript segmentation test.",
    "",
  ])
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Register the initial Fragment Autocomplete sample dataset.")
  parser.add_argument("--config", default=DEFAULT_CONFIG.as_posix())
  parser.add_argument("--dataset-root", default="autocomplete-test-dataset")
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--attempt-iiif-resolution", action="store_true")
  parser.add_argument("--no-iiif-resolution", action="store_true")
  parser.add_argument("--verbose", action="store_true")
  return parser


def main() -> int:
  args = build_parser().parse_args()
  config_path = Path(args.config)
  dataset_root = Path(args.dataset_root)
  config = ensure_config(config_path, dataset_root)
  map_local_files(config, dataset_root)
  stats = RegistrationStats()
  attempt_resolution = args.attempt_iiif_resolution and not args.no_iiif_resolution
  annotate_iiif_status(config, attempt_resolution, stats)
  write_yaml(config_path, config)
  resolved, registration_stats = register_dataset(config, args.dry_run)
  for field_name in ("iiif_resolved", "iiif_unresolved", "iiif_not_attempted"):
    setattr(registration_stats, field_name, getattr(stats, field_name))
  registration_stats.warnings.extend(stats.warnings)
  resolved["summary"] = registration_stats.__dict__
  write_yaml(DEFAULT_RESOLVED, resolved)
  write_report(resolved, DEFAULT_REPORT)

  print(f"Dataset root: {dataset_root}")
  print(f"Full pages: {len(config.get('full_pages', []))}")
  print(f"Fragments: {len(config.get('fragments', []))}")
  print(f"Local files matched: {registration_stats.local_files_matched}")
  print(f"IIIF resolved/unresolved/not_attempted: {registration_stats.iiif_resolved}/{registration_stats.iiif_unresolved}/{registration_stats.iiif_not_attempted}")
  print(f"Repositories inserted/matched: {registration_stats.repositories_inserted}/{registration_stats.repositories_matched}")
  print(f"Manuscripts inserted/matched: {registration_stats.manuscripts_inserted}/{registration_stats.manuscripts_matched}")
  print(f"Canvases inserted/matched: {registration_stats.canvases_inserted}/{registration_stats.canvases_matched}")
  print(f"Image assets inserted/matched: {registration_stats.image_assets_inserted}/{registration_stats.image_assets_matched}")
  print(f"Fragments inserted/matched: {registration_stats.fragments_inserted}/{registration_stats.fragments_matched}")
  if args.dry_run:
    print("Dry run: no database writes performed.")
  if args.verbose:
    for warning in registration_stats.warnings:
      print(f"WARNING: {warning}")
  print(f"Wrote {config_path}")
  print(f"Wrote {DEFAULT_RESOLVED}")
  print(f"Wrote {DEFAULT_REPORT}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
