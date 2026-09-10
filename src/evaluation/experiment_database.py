"""Existing PostgreSQL schema adapters for read-only audit and guarded v0.2 storage."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

from psycopg import sql

from .artificial_fragments import canonical_json
from .artificial_fragment_experiment import EXPERIMENT_VERSION


def verify_database(cursor, pages):
  """Cross-check source relationships, frozen splits, rights, and declared runs."""
  cursor.execute("""SELECT to_jsonb(a) AS asset, to_jsonb(c) AS canvas, to_jsonb(m) AS manuscript
    FROM image_asset a JOIN canvas c ON c.id=a.canvas_id JOIN manuscript m ON m.id=c.manuscript_id
    WHERE a.raw_metadata->'ingestion'->>'corpus_id' = ANY(%s) ORDER BY a.id""",
    (sorted({p["corpus_id"] for p in pages}),))
  rows = {r["asset"]["id"]: r for r in cursor.fetchall()}
  if set(rows) != {p["db_ids"]["image_asset_id"] for p in pages}:
    raise ValueError("database_corpus_asset_set_differs_from_manifests")
  cursor.execute("SELECT to_jsonb(r) AS run FROM segmentation_run r WHERE image_asset_id = ANY(%s::uuid[]) ORDER BY id", (sorted(rows),))
  runs = {r["run"]["id"]: r["run"] for r in cursor.fetchall()}
  cursor.execute("""SELECT id::text, segmentation_run_id::text, reading_order_index, label, label_id,
    mask_path, raw_region FROM layout_region WHERE segmentation_run_id = ANY(%s::uuid[]) ORDER BY id""", (sorted(runs),))
  region_runs = {}
  for r in cursor.fetchall():
    region_runs.setdefault(r["segmentation_run_id"], []).append(r)
  for p in pages:
    row = rows[p["db_ids"]["image_asset_id"]]
    asset, canvas, manuscript = (row[k] for k in ("asset", "canvas", "manuscript"))
    ingestion = asset["raw_metadata"]["ingestion"]
    expected = {"local_path": p["source_path"], "checksum_sha256": p["source_sha256"],
      "canvas_id": p["db_ids"]["canvas_id"], "repository_id": p["db_ids"]["repository_id"],
      "width_px": p["source_record"]["image"].get("width_px"), "height_px": p["source_record"]["image"].get("height_px")}
    for name, value in expected.items():
      if asset[name] != value:
        raise ValueError(f"database_source_mismatch:{p['page_id']}:{name}")
    for name in ("rights_review_status", "training_allowed", "rights_statement", "license", "attribution"):
      if asset.get(name) != p["source_record"]["image"].get(name):
        raise ValueError(f"database_rights_mismatch:{p['page_id']}:{name}")
    if canvas["manuscript_id"] != p["db_ids"]["manuscript_id"]:
      raise ValueError("database_manuscript_relationship_mismatch")
    if ingestion["manuscript_split"] != p["split"] or ingestion["manuscript_spec_id"] != p["manuscript_id"]:
      raise ValueError("database_split_mismatch")
    for entity in (canvas, manuscript):
      provenance = entity["raw_metadata"].get("ingestion", {})
      if provenance.get("manuscript_split") != p["split"]:
        raise ValueError("database_canvas_or_manuscript_split_mismatch")
    p["database_asset"] = deepcopy(asset)
    p["database_dimensions_px"] = [asset["width_px"], asset["height_px"]]
    run_id = p["stored_run"].get("db_segmentation_run_id")
    run = runs.get(run_id)
    if not run or run["image_asset_id"] != asset["id"] or run["status"] != "completed":
      p["errors"].append("database_segmentation_missing_or_invalid")
      continue
    if run["parameters"].get("dataset_split") != p["split"] or run["parameters"].get("run_identity_sha256") != p["model"]["run_identity_sha256"]:
      p["errors"].append("database_segmentation_provenance_mismatch")
    registered = region_runs.get(run_id, [])
    if "detections" not in p:
      if len(registered) != p["result"].get("detected_region_count"):
        raise ValueError("database_uninspected_region_count_mismatch")
      continue
    by_index = {r["reading_order_index"]: r for r in registered}
    if len(by_index) != len(registered) or set(by_index) != {d["index"] for d in p["detections"]}:
      p["errors"].append("database_region_set_mismatch")
      continue
    for d in p["detections"]:
      r = by_index[d["index"]]
      if r["mask_path"] != d.get("mask_path") or r["label"] != d["label"] or r["label_id"] != d["class_id"]:
        p["errors"].append("database_region_geometry_or_class_mismatch")
      raw = r["raw_region"]
      if raw.get("mask_sha256") != d.get("mask_sha256") or raw.get("mask_pixel_area") != d.get("mask_pixel_area"):
        p["errors"].append("database_mask_provenance_mismatch")
      d["db_layout_region_id"] = r["id"]
    p["errors"] = sorted(set(p["errors"]))
  return {"corpus_asset_count": len(rows), "total_segmentation_runs": len(runs),
          "total_layout_regions": sum(len(r) for r in region_runs.values()),
          "verified_source_rights_splits_and_relationships": True}


def database_snapshot(cursor, *, experiment=False, experiment_version=EXPERIMENT_VERSION):
  """Hash complete rows including timestamps; binaries are never read from/written to DB."""
  tables = ("image_asset", "canvas", "manuscript", "repository", "iiif_manifest_cache", "segmentation_run", "layout_region", "artificial_fragment_task")
  snapshots = {}
  for table in tables:
    if experiment and table != "artificial_fragment_task":
      continue
    query = sql.SQL("SELECT to_jsonb(t) AS value FROM {} t").format(sql.Identifier(table))
    params = ()
    if table == "artificial_fragment_task":
      query += sql.SQL(" WHERE parameters->>'task_group' = %s" if experiment else " WHERE parameters->>'task_group' IS DISTINCT FROM %s")
      params = (experiment_version,)
    query += sql.SQL(" ORDER BY id")
    cursor.execute(query, params)
    h, count = sha256(), 0
    for row in cursor:
      h.update(canonical_json(row["value"]).encode())
      h.update(b"\n")
      count += 1
    snapshots[table] = {"count": count, "rows_sha256": h.hexdigest()}
  return snapshots


def assert_registration_sources(records, pages):
  """Registration cannot trust a generated split or source provenance assertion alone."""
  by_asset = {p["db_ids"]["image_asset_id"]: p for p in pages}
  for record in records:
    p = by_asset[record.source_image_asset_id]
    if p["split"] != "validation" or p["errors"]:
      raise ValueError("registration_source_not_valid_validation_page")
    provenance = record.parameters["source_provenance"]["registered_source_record"]
    if provenance["corpus_page"] != p["source_record"] or provenance["database_asset"] != p["database_asset"]:
      raise ValueError("registration_source_provenance_or_rights_changed")
