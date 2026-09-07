#!/usr/bin/env python3
"""Audit, generate, register, measure and verify Artificial Fragment Experiment v0.2."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psycopg.rows import dict_row
import yaml
from src.ingestion.db import connect
from src.evaluation.corpus_audit import (
  artifact, audit_corpus, audit_markdown, digest, inspect_page, load_corpus, review_outliers, write_stable,
)
from src.evaluation.artificial_fragment_experiment import (
  OUTPUT, aggregate, build_specification, generate_task, load_task, measurements_markdown,
  registration_records, task_paths,
)
from src.evaluation.artificial_fragment_registration import register_records, task_identity
from src.evaluation.experiment_database import assert_registration_sources, database_snapshot, verify_database
from scripts.register_artificial_fragment_tasks import PostgresArtificialFragmentTaskStore

PREFIX = "data/metadata/artificial_fragment_v02"


class CorpusTaskStore(PostgresArtificialFragmentTaskStore):
  """Use verified acquired dimensions, preserving the DB's advertised IIIF dimensions."""
  def __init__(self, cursor, pages):
    super().__init__(cursor)
    self.pages = {p["db_ids"]["image_asset_id"]: p for p in pages}

  def source_context(self, image_asset_id):
    context = super().source_context(image_asset_id)
    if context is None:
      return None
    page = self.pages[image_asset_id]
    advertised = page["database_dimensions_px"]
    if [context.width_px, context.height_px] != advertised:
      raise ValueError("database_advertised_dimensions_changed")
    return replace(context, width_px=page["dimensions_px"][0], height_px=page["dimensions_px"][1])


def read(name):
  return json.loads((ROOT / f"{PREFIX}_{name}.json").read_text())


def save(name, value):
  write_stable(ROOT / f"{PREFIX}_{name}.json", value)


def inspect(cursor):
  pages, manuscripts, inputs = load_corpus(ROOT)
  inspected = []
  for index, p in enumerate(pages, 1):
    inspected.append(inspect_page(ROOT, p))
    if index % 10 == 0 or index == len(pages):
      print(f"Audited {index}/{len(pages)} pages", flush=True)
  pages = inspected
  db = verify_database(cursor, pages)
  return pages, manuscripts, inputs, db


def file_snapshot(pages, inputs):
  refs = {r["path"]: r for p in pages for r in p["artifacts"]}
  refs.update({r["path"]: r for r in inputs})
  # Preserve every v0.1 task artifact and both committed pilot manifests too.
  for filename in ("artificial_fragment_generation_results", "artificial_fragment_task_registration_results"):
    path = f"data/metadata/{filename}.yaml"
    refs[path] = artifact(ROOT, path)
  pilot = yaml.safe_load((ROOT / "data/metadata/artificial_fragment_generation_results.yaml").read_text())
  for task in pilot["core_pilot_tasks"] + pilot["transformation_sanity_tasks"]:
    for ref in task["artifacts"].values():
      refs[ref["path"]] = artifact(ROOT, ref["path"])
  snapshots = [{**r, "mtime_ns": (ROOT / path).stat().st_mtime_ns} for path, r in sorted(refs.items())]
  for p in pages:
    if p["source_path"] not in refs:
      file = ROOT / p["source_path"]
      snapshots.append({"path": p["source_path"], "expected_sha256": p["source_sha256"],
        "checksum_verified": False, "availability": "unavailable",
        "size_bytes": file.stat().st_size if file.exists() else None,
        "mtime_ns": file.stat().st_mtime_ns if file.exists() else None})
  return sorted(snapshots, key=lambda r: r["path"])


def current_outlier_review(pages):
  flags = yaml.safe_load((ROOT / "data/metadata/training_corpus_expansion_batch_01_segmentation_statistics.yaml").read_text())["outliers_for_review"]
  flags = {k: [item["sample_id"] for item in v] for k, v in flags.items() if isinstance(v, list)}
  return review_outliers(pages, flags, read("review_decisions"))


def audit():
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    pages, manuscripts, inputs, db = inspect(cursor)
    snapshot = {"database": database_snapshot(cursor), "files": file_snapshot(pages, inputs)}
  snapshot_path = ROOT / OUTPUT / "invariants_before.json"
  if snapshot_path.exists() and json.loads(snapshot_path.read_text()) != snapshot:
    raise ValueError("frozen_pre_experiment_state_changed; do not overwrite baseline")
  write_stable(snapshot_path, snapshot)
  report = audit_corpus(pages, manuscripts, inputs)
  report["database"] = db
  save("corpus_audit", report)
  write_stable(ROOT / "docs/19a_corpus_diversity_audit.md", audit_markdown(report))
  review = current_outlier_review(pages)
  save("outlier_review", review)
  save("specification", build_specification(pages))
  print(json.dumps({"audit": report["structure"], "database": db, "outlier_count": len(review["outliers"])}))


def current_validation(cursor):
  pages, _, _ = load_corpus(ROOT)
  # DB verification covers every source; only validation masks are read for generation/storage.
  # Other splits receive DB relationship/count checks, without opening their masks here.
  inspected = [inspect_page(ROOT, p) for p in pages if p["split"] == "validation"]
  validation_ids = {p["page_id"] for p in inspected}
  others = [dict(p, errors=[]) for p in pages if p["page_id"] not in validation_ids]
  all_pages = inspected + others
  verify_database(cursor, all_pages)
  return inspected


def checked_spec(pages):
  specification = build_specification(pages)
  if specification != read("specification"):
    raise ValueError("validation_specification_changed; run audit and review explicit rejections")
  return specification


def generate(regenerate=False):
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    pages = current_validation(cursor)
  spec = checked_spec(pages)
  by_page = {p["page_id"]: p for p in pages}
  tasks = []
  for index, entry in enumerate(spec["tasks"], 1):
    path = task_paths(ROOT, entry["task_id"]).metadata
    if path.exists() and not regenerate:
      ref = artifact(ROOT, path.relative_to(ROOT).as_posix())
      task = load_task(ROOT, {k: ref[k] for k in ("path", "sha256")})
      registration_records(ROOT, {"tasks": [entry], "selected_pages": spec["selected_pages"]}, [task])
    else:
      task = generate_task(ROOT, by_page[entry["page_id"]], entry)
    tasks.append(task)
    print(f"{index}/{len(spec['tasks'])}: {entry['task_id']}", flush=True)
  records = registration_records(ROOT, spec, tasks)
  assert_registration_sources(records, pages)
  save("generation", {"specification_sha256": digest(spec), "task_count": len(tasks),
    "tasks": [{"task_id": t["task_id"], "page_id": t["source_sample_id"], "manuscript_id": t["manuscript_id"],
      "database_id": task_identity(t)[0], "identity_sha256": task_identity(t)[1],
      "mask_family": t["mask_family"], "severity": t["requested_severity"], "artifacts": t["artifacts"],
      "region_measurement_count": len(t["layout_survival_estimate"]["regions"])} for t in tasks]})
  report(tasks)


def read_tasks():
  generation, spec = read("generation"), read("specification")
  if generation["specification_sha256"] != digest(spec):
    raise ValueError("generation_specification_checksum_mismatch")
  tasks = [load_task(ROOT, t["artifacts"]["metadata"]) for t in generation["tasks"]]
  registration_records(ROOT, spec, tasks)
  return tasks


def register():
  tasks = read_tasks()
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    pages = current_validation(cursor)
    spec = checked_spec(pages)
    records = registration_records(ROOT, spec, tasks)
    assert_registration_sources(records, pages)
    before = database_snapshot(cursor)
    store = CorpusTaskStore(cursor, pages)
    stats = register_records(store, records)
    if stats["updated"]:
      raise ValueError("v02_registration_would_change_existing_measurements; transaction rolled back")
    once = database_snapshot(cursor, experiment=True)
    rerun = register_records(store, records)
    if rerun != {"inserted": 0, "updated": 0, "matched": len(records), "validated": len(records)}:
      raise ValueError("registration_not_idempotent")
    if database_snapshot(cursor, experiment=True) != once or database_snapshot(cursor) != before:
      raise ValueError("registration_changed_frozen_rows_or_timestamps")
  save("registration", {"registered_task_count": len(records), "split": "validation",
    "binary_data_stored_in_postgresql": False, "rerun": rerun, "experiment_database": once,
    "frozen_database_unchanged": True})
  print(json.dumps({"first_pass": stats, "second_pass": rerun}))


def report(tasks=None):
  summary = aggregate(tasks if tasks is not None else read_tasks())
  save("measurements", summary)
  write_stable(ROOT / "docs/19b_artificial_fragment_v02_measurements.md", measurements_markdown(summary))
  print(f"Measured {summary['task_count']} tasks / {summary['region_measurement_count']} region overlaps.")


def verify():
  before = json.loads((ROOT / OUTPUT / "invariants_before.json").read_text())
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    pages, manuscripts, inputs, db = inspect(cursor)
    after = {"database": database_snapshot(cursor), "files": file_snapshot(pages, inputs)}
    experiment = database_snapshot(cursor, experiment=True)
  if before != after:
    raise ValueError("source_segmentation_rights_splits_or_legacy_pilot_changed")
  spec = checked_spec(pages)
  fresh_audit = audit_corpus(pages, manuscripts, inputs)
  fresh_audit["database"] = db
  if fresh_audit != read("corpus_audit"):
    raise ValueError("corpus_audit_not_stable")
  if current_outlier_review(pages) != read("outlier_review"):
    raise ValueError("outlier_review_not_stable")
  tasks = read_tasks()
  if aggregate(tasks) != read("measurements"):
    raise ValueError("aggregate_measurements_not_stable")
  if experiment != read("registration")["experiment_database"]:
    raise ValueError("registered_experiment_rows_changed")
  save("validation", {"status": "passed", "validation_pages": spec["selected_page_count"],
    "task_count": len(tasks), "region_measurement_count": sum(len(t["layout_survival_estimate"]["regions"]) for t in tasks),
    "available_source_files_checksums_sizes_and_mtimes_unchanged": True,
    "unavailable_source_files": [r["path"] for r in before["files"] if r.get("availability") == "unavailable"],
    "unavailable_source_note": "Only metadata/size/mtime can be verified for unavailable files; no byte-integrity claim is made for them.", "all_frozen_database_rows_and_timestamps_unchanged": True,
    "test_pages_used_for_generation": 0, "rights_and_training_authorization_unchanged": True,
    "legacy_pilot_unchanged": True, "audit_and_measurements_stable": True,
    "frozen_database": before["database"], "frozen_artifact_count": len(before["files"]),
    "frozen_file_snapshot_sha256": digest(before["files"]), "registered_experiment": experiment})
  print("Verified frozen sources, rights, splits, masks, legacy tasks, audit, measurements and database rows.")


def check_determinism():
  """Recompute every binary; compare scientific bytes and registered rows across runs."""
  tasks = read_tasks()
  paths = {ref["path"] for task in tasks for ref in task["artifacts"].values()}
  paths.update(f"{PREFIX}_{name}.json" for name in ("specification", "generation", "measurements", "registration", "corpus_audit", "outlier_review", "review_decisions"))
  paths.update(("docs/19a_corpus_diversity_audit.md", "docs/19b_artificial_fragment_v02_measurements.md"))
  before = [artifact(ROOT, path) for path in sorted(paths)]
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    database_before = database_snapshot(cursor, experiment=True)
  generate(regenerate=True)
  register()
  after = [artifact(ROOT, path) for path in sorted(paths)]
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    database_after = database_snapshot(cursor, experiment=True)
  if before != after or database_before != database_after:
    raise ValueError("full_regeneration_bytes_or_registered_rows_changed")
  save("determinism", {"status": "passed", "method": "full_regeneration_and_registration",
    "task_count": len(tasks), "compared_artifact_count": len(before),
    "generated_binary_count": sum(path.endswith(".png") for path in paths),
    "scientific_artifact_snapshot_sha256": digest(before),
    "byte_identical_artifacts": True, "identical_task_identities_and_checksums": True,
    "database_rows_and_timestamps_unchanged": True,
    "source_of_truth": "Existing metadata/artifact checksums compared before and after actual recomputation; no cache-only determinism claim."})
  print("Full recomputation is byte-identical; registration preserves rows and timestamps.")


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  sub = parser.add_subparsers(dest="command", required=True)
  sub.add_parser("audit", help="Read-only DB and full-mask corpus audit, four-outlier review and validation specification.", description="Audit both registered corpus batches and all available full-sized masks; emit source availability, reviewed outliers and validation-only specification.")
  gen = sub.add_parser("generate", help="Generate every eligible validation task; verify and reuse unchanged tasks.", description="Generate the saved validation-only matrix into ignored outputs/artificial_fragments/v0_2. Reject changed evidence; preserve test pages and v0.1 tasks.")
  gen.add_argument("--regenerate", action="store_true", help="Recompute images and overlaps to check byte determinism; never uses test pages.")
  sub.add_parser("register", help="Validate and idempotently store v0.2 JSON/paths in existing task rows; verify a second registration.", description="Validate artifacts, source rights/provenance and stored validation splits before transactional registration. A second pass must match without row updates.")
  sub.add_parser("report", help="Validate generated task artifacts and emit deterministic aggregates and Markdown.", description="Read checksummed per-task measurements and produce deterministic summaries by family, severity, manuscript, page and region class.")
  sub.add_parser("verify", help="Compare source/legacy DB and file invariants with the initial audit snapshot.", description="Check all frozen DB rows, available source/mask/legacy file checksums and mtimes, stable audit/review/measurement artifacts and registered v0.2 rows.")
  sub.add_parser("check-determinism", help="Fully recompute binaries and compare scientific artifacts, IDs, checksums and registered rows.", description="Requires an already generated and registered experiment. Performs real recomputation and registration, verifies unchanged bytes and row timestamps, and saves determinism.json.")
  args = parser.parse_args()
  if args.command == "generate":
    generate(args.regenerate)
  else:
    {"audit": audit, "register": register, "report": report, "verify": verify, "check-determinism": check_determinism}[args.command]()


if __name__ == "__main__":
  main()
