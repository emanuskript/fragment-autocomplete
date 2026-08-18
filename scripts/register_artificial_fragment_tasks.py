#!/usr/bin/env python3
"""Register generated artificial-fragment task metadata in PostgreSQL."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import yaml
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.evaluation.artificial_fragment_registration import (  # noqa: E402
  REGISTRATION_VERSION,
  SourceDatabaseContext,
  TaskRegistrationRecord,
  load_registration_records,
  register_records,
)
from src.ingestion.db import connect  # noqa: E402


DEFAULT_MANIFEST = ROOT / "data/metadata/artificial_fragment_generation_results.yaml"
DEFAULT_OUTPUT = ROOT / "data/metadata/artificial_fragment_task_registration_results.yaml"
JSON_FIELDS = ("crop_transform", "degradation_profile", "ground_truth_placement", "parameters")


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Idempotently register the 23-task artificial-fragment pilot in PostgreSQL."
  )
  parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
  parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args()


def iso_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: Path) -> str:
  return path.resolve().relative_to(ROOT.resolve()).as_posix()


class PostgresArtificialFragmentTaskStore:
  """Small PostgreSQL adapter used by the validation-first registration core."""

  def __init__(self, cursor: Any):
    self.cursor = cursor
    self.actions: dict[str, str] = {}

  def source_context(self, image_asset_id: str) -> SourceDatabaseContext | None:
    self.cursor.execute(
      """
      SELECT id::text AS image_asset_id,
             canvas_id::text AS canvas_id,
             local_path,
             checksum_sha256,
             width_px,
             height_px
      FROM image_asset
      WHERE id = %s
      """,
      (image_asset_id,),
    )
    row = self.cursor.fetchone()
    if not row:
      return None
    return SourceDatabaseContext(**row)

  def segmentation_run_image_asset_id(self, segmentation_run_id: str) -> str | None:
    self.cursor.execute(
      "SELECT image_asset_id::text FROM segmentation_run WHERE id = %s",
      (segmentation_run_id,),
    )
    row = self.cursor.fetchone()
    return str(row["image_asset_id"]) if row and row["image_asset_id"] else None

  def _fetch_task(self, database_id: str) -> dict[str, Any] | None:
    self.cursor.execute(
      """
      SELECT id::text AS id,
             source_canvas_id::text AS source_canvas_id,
             source_image_asset_id::text AS source_image_asset_id,
             generated_fragment_image_asset_id::text AS generated_fragment_image_asset_id,
             mask_path,
             mask_family,
             random_seed,
             crop_transform,
             degradation_profile,
             ground_truth_placement,
             split_name,
             generation_version,
             parameters
      FROM artificial_fragment_task
      WHERE id = %s
      """,
      (database_id,),
    )
    return self.cursor.fetchone()

  @staticmethod
  def _same(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    for name, expected_value in expected.items():
      existing_value = existing.get(name)
      if name in JSON_FIELDS:
        # PostgreSQL JSONB normalizes numerically equivalent values such as 0.0
        # and 0. Python's structural equality preserves that semantic equality.
        if existing_value != expected_value:
          return False
      elif existing_value != expected_value:
        return False
    return True

  def _insert(self, values: dict[str, Any]) -> bool:
    self.cursor.execute(
      """
      INSERT INTO artificial_fragment_task (
        id,
        source_canvas_id,
        source_image_asset_id,
        generated_fragment_image_asset_id,
        mask_path,
        mask_family,
        random_seed,
        crop_transform,
        degradation_profile,
        ground_truth_placement,
        split_name,
        generation_version,
        parameters
      ) VALUES (
        %(id)s,
        %(source_canvas_id)s,
        %(source_image_asset_id)s,
        %(generated_fragment_image_asset_id)s,
        %(mask_path)s,
        %(mask_family)s,
        %(random_seed)s,
        %(crop_transform)s,
        %(degradation_profile)s,
        %(ground_truth_placement)s,
        %(split_name)s,
        %(generation_version)s,
        %(parameters)s
      )
      ON CONFLICT (id) DO NOTHING
      """,
      {
        **values,
        "crop_transform": Jsonb(values["crop_transform"]),
        "degradation_profile": Jsonb(values["degradation_profile"]),
        "ground_truth_placement": Jsonb(values["ground_truth_placement"]),
        "parameters": Jsonb(values["parameters"]),
      },
    )
    return self.cursor.rowcount == 1

  def _update(self, values: dict[str, Any]) -> None:
    self.cursor.execute(
      """
      UPDATE artificial_fragment_task
      SET source_canvas_id = %(source_canvas_id)s,
          source_image_asset_id = %(source_image_asset_id)s,
          generated_fragment_image_asset_id = %(generated_fragment_image_asset_id)s,
          mask_path = %(mask_path)s,
          mask_family = %(mask_family)s,
          random_seed = %(random_seed)s,
          crop_transform = %(crop_transform)s,
          degradation_profile = %(degradation_profile)s,
          ground_truth_placement = %(ground_truth_placement)s,
          split_name = %(split_name)s,
          generation_version = %(generation_version)s,
          parameters = %(parameters)s,
          updated_at = now()
      WHERE id = %(id)s
      """,
      {
        **values,
        "crop_transform": Jsonb(values["crop_transform"]),
        "degradation_profile": Jsonb(values["degradation_profile"]),
        "ground_truth_placement": Jsonb(values["ground_truth_placement"]),
        "parameters": Jsonb(values["parameters"]),
      },
    )

  def upsert_task(self, record: TaskRegistrationRecord) -> str:
    values = record.database_values()
    self.cursor.execute(
      """
      SELECT id::text AS id
      FROM artificial_fragment_task
      WHERE parameters->'task_identity'->>'sha256' = %s
      """,
      (record.identity_sha256,),
    )
    identity_rows = self.cursor.fetchall()
    conflicting_ids = [row["id"] for row in identity_rows if row["id"] != record.database_id]
    if conflicting_ids:
      raise ValueError(
        f"Duplicate scientific task identity already stored for {record.task_id}: "
        f"{', '.join(conflicting_ids)}"
      )
    existing = self._fetch_task(record.database_id)
    if existing is None:
      if self._insert(values):
        self.actions[record.task_id] = "inserted"
        return "inserted"
      existing = self._fetch_task(record.database_id)
      if existing is None:
        raise RuntimeError(f"Could not read task after insert conflict: {record.database_id}")

    existing_identity = existing.get("parameters", {}).get("task_identity", {}).get("sha256")
    if existing_identity != record.identity_sha256:
      raise ValueError(
        f"Deterministic task UUID collision for {record.task_id}: "
        f"database identity={existing_identity}, expected={record.identity_sha256}"
      )
    if self._same(existing, values):
      self.actions[record.task_id] = "matched"
      return "matched"
    self._update(values)
    self.actions[record.task_id] = "updated"
    return "updated"


def write_results(
  path: Path,
  *,
  manifest_path: Path,
  records: list[TaskRegistrationRecord],
  stats: dict[str, int],
  actions: dict[str, str],
  dry_run: bool,
) -> None:
  payload = {
    "generated_at": iso_now(),
    "registration_version": REGISTRATION_VERSION,
    "registration_status": "dry_run" if dry_run else "stored",
    "database_write": not dry_run,
    "binary_data_stored_in_postgresql": False,
    "source_manifest": relative(manifest_path),
    "expected_task_count": 23,
    "registered_task_count": len(records),
    "core_pilot_task_count": sum(record.task_group == "core_pilot" for record in records),
    "transformation_sanity_task_count": sum(record.task_group == "transformation_sanity" for record in records),
    "summary": stats,
    "tasks": [
      {
        "task_id": record.task_id,
        "task_group": record.task_group,
        "db_artificial_fragment_task_id": record.database_id,
        "task_identity_sha256": record.identity_sha256,
        "source_canvas_id": record.source_canvas_id,
        "source_image_asset_id": record.source_image_asset_id,
        "mask_path": record.mask_path,
        "fragment_artifact_path": record.parameters["fragment_artifact"]["path"],
        "layout_geometry_method": record.parameters["layout_geometry_method"],
        "status": "validated" if dry_run else actions[record.task_id],
      }
      for record in records
    ],
  }
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main() -> int:
  args = parse_args()
  manifest_path = Path(args.manifest).resolve()
  output_path = Path(args.output).resolve()
  records = load_registration_records(manifest_path, ROOT)

  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    store = PostgresArtificialFragmentTaskStore(cursor)
    stats = register_records(store, records, dry_run=args.dry_run)
    if args.dry_run:
      conn.rollback()
    else:
      conn.commit()
    actions = dict(store.actions)

  write_results(
    output_path,
    manifest_path=manifest_path,
    records=records,
    stats=stats,
    actions=actions,
    dry_run=args.dry_run,
  )
  print(
    f"Validated {stats['validated']} tasks; "
    f"inserted={stats['inserted']}, updated={stats['updated']}, matched={stats['matched']}."
  )
  print("PostgreSQL binary storage: disabled (paths, checksums, dimensions, and JSON metadata only).")
  print(f"Results: {relative(output_path)}")
  if args.verbose:
    for record in records:
      print(f"{record.task_id}: {'validated' if args.dry_run else actions[record.task_id]} -> {record.database_id}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
