"""v0.3 operations behind the existing artificial_fragment_experiment CLI."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from psycopg.rows import dict_row

from src.ingestion.db import connect
from src.evaluation.corpus_audit import artifact, digest, load_corpus, write_stable
from src.evaluation.experiment_database import database_snapshot
from src.evaluation.source_availability import availability, local_state
from src.evaluation.structured_fragment_experiment import VERSION, OUTPUT

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "data/metadata/artificial_fragment_v03"


def read(name):
  return json.loads((ROOT / f"{PREFIX}_{name}.json").read_text())


def save(name, value):
  write_stable(ROOT / f"{PREFIX}_{name}.json", value)


def frozen_files():
  # Include all corpus source/mask/raw evidence listed by the historical audit,
  # all historical task outputs, and the historical reports and immutable input manifests.
  audit = json.loads((ROOT / "data/metadata/artificial_fragment_v02_corpus_audit.json").read_text())
  paths = {p["source_path"] for p in audit["pages"]}
  old_baseline = json.loads((ROOT / "outputs/artificial_fragments/v0_2/invariants_before.json").read_text())
  paths.update(r["path"] for r in old_baseline["files"])
  generation = json.loads((ROOT / "data/metadata/artificial_fragment_v02_generation.json").read_text())
  paths.update(r["path"] for t in generation["tasks"] for r in t["artifacts"].values())
  paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "data/metadata").glob("*") if p.suffix in (".json", ".yaml") and not p.name.startswith("artificial_fragment_v03"))
  paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs").glob("19*.md"))
  paths.add("outputs/artificial_fragments/v0_2/invariants_before.json")
  result = []
  for path in sorted(paths):
    file = ROOT / path
    state = local_state(file)
    ref = artifact(ROOT, path) if state["exists"] and not state["dataless"] else {"path": path, "availability": state}
    result.append({**ref, "mtime_ns": file.stat().st_mtime_ns if file.exists() else None})
  return result


def snapshot():
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    db = database_snapshot(cursor, experiment_version=VERSION)
  return {"database": db, "files": frozen_files()}


def freeze(name):
  state = snapshot()
  path = ROOT / OUTPUT / name
  if path.exists() and json.loads(path.read_text()) != state:
    raise ValueError(f"frozen_state_changed:{name}")
  write_stable(path, state)
  return state


def source_availability(args):
  pages, _, _ = load_corpus(ROOT)
  from src.evaluation.experiment_database import verify_database
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    verify_database(cursor, [dict(p, errors=[]) for p in pages])
  previous = read("availability") if (ROOT / f"{PREFIX}_availability.json").exists() else None
  if not args.dry_run:
    initial_path = ROOT / OUTPUT / "before_restoration.json"
    if not initial_path.exists():
      freeze("before_restoration.json")
  report = availability(ROOT, pages, restore=args.restore and not args.dry_run, previous=previous)
  if not args.dry_run:
    initial = json.loads((ROOT / OUTPUT / "before_restoration.json").read_text())
    current = snapshot()
    restored = {r["path"] for r in report["pages"] if r["status"] == "restored_checksum_verified"}
    unchanged = lambda rows: [r for r in rows if r["path"] not in restored]
    if initial["database"] != current["database"] or unchanged(initial["files"]) != unchanged(current["files"]):
      raise ValueError("restoration_changed_unrelated_frozen_data")
    save("availability", report)
    # The experiment baseline is established by spec, after availability decisions.
    # An existing experiment baseline remains immutable on later source checks.
    baseline = ROOT / OUTPUT / "invariants_before.json"
    if baseline.exists() and json.loads(baseline.read_text()) != current:
      raise ValueError("source_availability_changed_frozen_experiment_inputs")
  print(json.dumps({k: report[k] for k in ("counts", "available_now")}))


def dispatch(args):
  if args.action == "availability":
    return source_availability(args)
  return globals()[args.action.replace("-", "_")](**({"dry_run": args.dry_run} if args.action == "register" else {}))


def pairing_audit(cursor, pages):
  """Inspect explicit relationship fields, never parse r/v labels into putative leaves."""
  cursor.execute("""SELECT c.id::text, c.folio_number, c.page_number, c.raw_metadata AS canvas_metadata,
    m.raw_metadata AS manuscript_metadata FROM canvas c JOIN manuscript m ON m.id=c.manuscript_id
    WHERE c.id = ANY(%s::uuid[]) ORDER BY c.id""", ([p["db_ids"]["canvas_id"] for p in pages],))
  rows = cursor.fetchall()
  terms = {"leaf_id", "physical_leaf_id", "paired_canvas_id", "opposite_side", "recto_canvas_id", "verso_canvas_id", "leaf_relationship", "recto_verso_pair"}
  found = []
  def walk(value, path):
    if isinstance(value, dict):
      for key, child in sorted(value.items()):
        if key.lower().replace("-", "_") in terms and child:
          found.append({"path": path + [key], "value": child})
        walk(child, path + [key])
    elif isinstance(value, list):
      for index, child in enumerate(value):
        walk(child, path + [str(index)])
  for row in rows:
    walk(row, [row["id"]])
  for p in pages:
    walk(p["source_record"], [p["page_id"], "source_record"])
  cached_manifests, manifest_keys, metadata_labels = [], set(), set()
  def catalog(value):
    if isinstance(value, dict):
      manifest_keys.update(value)
      for item in value.get("metadata", []):
        if isinstance(item, dict):
          metadata_labels.add(str(item.get("label")))
      for child in value.values():
        catalog(child)
    elif isinstance(value, list):
      for child in value:
        catalog(child)
  for file in sorted((ROOT / "data/raw").glob("ecodices_training_source*/_manifests/*.json")):
    value = json.loads(file.read_text())
    walk(value, [file.relative_to(ROOT).as_posix()])
    catalog(value)
    cached_manifests.append(artifact(ROOT, file.relative_to(ROOT).as_posix()))
  if found:
    raise ValueError("explicit_pairing_candidates_require_relationship_and_coordinate_review")
  return {"status": "blocked_by_absent_explicit_physical_leaf_relationships", "canvases_inspected": len(rows),
    "nonnull_folio_number_count": sum(r["folio_number"] is not None for r in rows),
    "explicit_relationship_candidates": found, "reliable_pairs": 0,
    "cached_manifest_count": len(cached_manifests), "cached_manifests": cached_manifests,
    "cached_manifest_object_keys": sorted(manifest_keys), "cached_manifest_metadata_labels": sorted(metadata_labels), "paired_leaf_support_implemented": False,
    "inspected_sources": ["registered source records", "canvas raw_metadata and folio/page fields", "manuscript raw_metadata", "current schema", "20 cached source IIIF manifests (all object keys and metadata labels)"],
    "metadata_snapshot_sha256": digest(rows), "recognized_relationship_fields": sorted(terms),
    "coordinate_requirement": "Future explicit pairs require physical leaf identity, sides and documented mirror convention; separate source checksums/masks remain mandatory.",
    "restriction": "No pairing from filenames, page labels or adjacency; no bifolium inference."}


def prepare_review(pages):
  from html import escape
  from PIL import Image, ImageChops
  from src.evaluation.corpus_audit import read_region_mask
  from src.evaluation.structured_fragment_experiment import save_image
  historical = json.loads((ROOT / "data/metadata/artificial_fragment_v02_outlier_review.json").read_text())
  by_page = {p["page_id"]: p for p in pages}
  rows = []
  html = ['<!doctype html><meta charset="utf-8"><title>Human segmentation review — v0.3</title>',
    '<style>body{font:16px system-ui;max-width:1250px;margin:32px auto}img{max-width:100%}article{margin:40px 0}pre{white-space:pre-wrap}</style>',
    '<h1>Human segmentation review</h1><p>Technical evidence only. Existing v0.2 classifications are unchanged; no scholarly approval is recorded.</p>']
  for old in sorted(historical["outliers"], key=lambda p: p["page_id"]):
    p = by_page[old["page_id"]]
    if p["errors"] or sorted(p["artifacts"], key=lambda a: a["path"]) != old["evidence"]:
      raise ValueError("outlier_review_evidence_changed")
    union = Image.new("L", tuple(p["dimensions_px"]), 0)
    for d in p["detections"]:
      union = ImageChops.lighter(union, read_region_mask(ROOT, d, union.size))
    panel = Image.new("RGB", (1200, 560), "#f3f3f3")
    images = [Image.open(ROOT / p["source_path"]), Image.open(ROOT / p["result"]["overlay_path"]), union]
    for index, image in enumerate(images):
      thumb = image.convert("RGB")
      thumb.thumbnail((390, 550))
      panel.paste(thumb, (index*400, 0))
      image.close()
    path = ROOT / OUTPUT / "review" / f"{p['page_id']}.png"
    save_image(path, panel)
    row = {"page_id": p["page_id"], "manuscript_id": p["manuscript_id"], "page": p["canvas_label"],
      "split": p["split"], "classification": old["classification"], "historical_review": old["review"],
      "source": artifact(ROOT, p["source_path"]), "overlay": artifact(ROOT, p["result"]["overlay_path"]),
      "region_count": len(p["detections"]), "confidence": p["confidence"], "class_counts": p["class_counts"],
      "union_mask_area_px": p["union_mask_area_px"], "union_mask_page_fraction": p["union_mask_area_px"] / (p["dimensions_px"][0]*p["dimensions_px"][1]),
      "dimensions_px": p["dimensions_px"], "review_image": artifact(ROOT, path.relative_to(ROOT).as_posix()),
      "scholarly_review_required": True, "classification_overridden": False}
    rows.append(row)
    html += [f'<article><h2>{escape(p["manuscript_id"])} — {escape(p["canvas_label"])}</h2>',
      f'<p>{escape(row["classification"])} · {row["region_count"]} regions · mask coverage {row["union_mask_page_fraction"]:.4%}</p>',
      '<p>Left: source. Middle: existing overlay. Right: union of full-size region masks (displayed at reduced size).</p>',
      f'<img src="{p["page_id"]}.png"><pre>{escape(json.dumps(row, indent=2))}</pre></article>']
  path = ROOT / OUTPUT / "review/index.html"
  write_stable(path, "\n".join(html)+"\n")
  save("outlier_review", {"version": VERSION, "human_review_required": True, "outliers": rows,
                         "review_index": artifact(ROOT, path.relative_to(ROOT).as_posix())})


def review():
  from src.evaluation.corpus_audit import inspect_page
  pages, _, _ = load_corpus(ROOT)
  prepare_review([inspect_page(ROOT, p) for p in pages if p["manuscript_id"] == "fmb-cb-0902"])


def spec():
  from scripts.artificial_fragment_experiment import inspect
  from src.evaluation.corpus_audit import audit_corpus
  from src.evaluation.structured_fragment_experiment import build_specification
  freeze("invariants_before.json")
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    pages, manuscripts, inputs, db = inspect(cursor)
    pairing = pairing_audit(cursor, pages)
  audit = audit_corpus(pages, manuscripts, inputs)
  audit.update(audit_version=VERSION, database=db)
  save("corpus_audit", audit)
  save("pairing", pairing)
  prepare_review(pages)
  specification = build_specification(pages)
  save("specification", specification)
  print(json.dumps({k: specification[k] for k in ("selected_page_count", "matrix_task_count", "rejected_pages", "rejected_tasks")}))


def validation_state():
  from scripts.artificial_fragment_experiment import current_validation
  from src.evaluation.structured_fragment_experiment import build_specification
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    pages = current_validation(cursor)
  specification = build_specification(pages)
  if specification != read("specification"):
    raise ValueError("v03_validation_specification_changed")
  return pages, specification


def generate():
  from src.evaluation.structured_fragment_experiment import generate_task, registration_records
  from src.evaluation.artificial_fragment_registration import task_identity
  from src.evaluation.experiment_database import assert_registration_sources
  pages, specification = validation_state()
  by_page = {p["page_id"]: p for p in pages}
  tasks = []
  for index, entry in enumerate(specification["tasks"], 1):
    task = generate_task(ROOT, by_page[entry["page_id"]], entry)
    tasks.append(task)
    print(f"Generated {index}/{len(specification['tasks'])}: {entry['task_id']}", flush=True)
  records = registration_records(ROOT, specification, tasks)
  assert_registration_sources(records, pages)
  save("generation", {"version": VERSION, "specification_sha256": digest(specification), "task_count": len(tasks),
    "tasks": [{"task_id": t["task_id"], "page_id": t["source_sample_id"], "manuscript_id": t["manuscript_id"],
      "database_id": task_identity(t)[0], "identity_sha256": task_identity(t)[1], "mask_family": t["mask_family"],
      "severity": t["requested_severity"], "artifacts": t["artifacts"],
      "region_measurement_count": len(t["layout_survival_estimate"]["regions"])} for t in tasks]})
  report(tasks)


def read_tasks():
  from src.evaluation.artificial_fragment_experiment import load_task
  from src.evaluation.structured_fragment_experiment import registration_records
  generation, specification = read("generation"), read("specification")
  if generation["specification_sha256"] != digest(specification):
    raise ValueError("generation_specification_checksum_mismatch")
  tasks = [load_task(ROOT, t["artifacts"]["metadata"]) for t in generation["tasks"]]
  registration_records(ROOT, specification, tasks)
  return tasks


def register(dry_run=False):
  from scripts.artificial_fragment_experiment import current_validation, CorpusTaskStore
  from src.evaluation.structured_fragment_experiment import build_specification, registration_records
  from src.evaluation.artificial_fragment_registration import register_records
  from src.evaluation.experiment_database import assert_registration_sources
  tasks = read_tasks()
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" + (" READ ONLY" if dry_run else ""))
    pages = current_validation(cursor)
    specification = build_specification(pages)
    if specification != read("specification"):
      raise ValueError("registration_validation_inputs_changed")
    records = registration_records(ROOT, specification, tasks)
    assert_registration_sources(records, pages)
    before = database_snapshot(cursor, experiment_version=VERSION)
    store = CorpusTaskStore(cursor, pages)
    stats = register_records(store, records, dry_run=dry_run)
    if stats["updated"]:
      raise ValueError("v03_registration_would_modify_existing_task; rolling_back")
    if dry_run:
      print(json.dumps(stats))
      return
    once = database_snapshot(cursor, experiment=True, experiment_version=VERSION)
    rerun = register_records(store, records)
    if rerun != {"inserted": 0, "updated": 0, "matched": len(records), "validated": len(records)}:
      raise ValueError("v03_registration_not_idempotent")
    if database_snapshot(cursor, experiment=True, experiment_version=VERSION) != once or database_snapshot(cursor, experiment_version=VERSION) != before:
      raise ValueError("registration_changed_frozen_data_or_timestamps")
  save("registration", {"registered_task_count": len(records), "split": "validation", "rerun": rerun,
    "binary_data_stored_in_postgresql": False, "experiment_database": once, "frozen_database_unchanged": True})
  print(json.dumps({"first_pass": stats, "second_pass": rerun}))


def coverage(tasks):
  audit, specification = read("corpus_audit"), read("specification")
  selected = {p["page_id"] for p in specification["selected_pages"]}
  groups = {"complete_corpus": audit["pages"], **{s: [p for p in audit["pages"] if p["split"] == s] for s in ("train", "validation", "test")},
            "v03_eligible_pages": [p for p in audit["pages"] if p["page_id"] in selected]}
  counts = {key: dict(sorted(sum((Counter(p["class_counts"]) for p in pages), Counter()).items())) for key, pages in groups.items()}
  counts["v03_generated_tasks"] = dict(sorted(Counter(r["label"] for t in tasks for r in t["layout_survival_estimate"]["regions"]).items()))
  all_classes = set(counts["complete_corpus"])
  return {"counts": counts, "missing_observed_classes": {key: sorted(all_classes-set(value)) for key, value in counts.items()},
    "interpretation": "Model-detected regions, not scholarly class ground truth. Generated-task counts repeat source regions under each synthetic transformation; splits unchanged.",
    "batch_02_selection_criteria": ["New manuscripts with verified Border, Illustrations, Running header or Table examples for future validation coverage.",
      "Layouts with underrepresented classes and lower Main script black dominance; inspect density and segmentation quality with humans.",
      "Additional source providers/repositories and explicit physical leaf relationships with coordinate conventions.",
      "Separate human rights review; availability never implies training authorization; preserve existing test assignments."]}


def report(tasks=None):
  from src.evaluation.artificial_fragment_experiment import load_task
  from src.evaluation.structured_fragment_experiment import compare
  tasks = read_tasks() if tasks is None else tasks
  historical = json.loads((ROOT / "data/metadata/artificial_fragment_v02_generation.json").read_text())
  controls = [load_task(ROOT, t["artifacts"]["metadata"]) for t in historical["tasks"]]
  summary = compare(tasks, controls)
  save("measurements", summary)
  save("coverage", coverage(tasks))
  lines = ["# Structured synthetic damage measurements v0.3", "",
    "Known source pixels are ground truth; eManuSkript regions are model evidence. Survival is pixel retention, not semantic recoverability or historical likelihood.", "",
    summary["all_v03"]["rate_semantics"], "",
    f"All v0.3: {len(tasks)} tasks / {summary['all_v03']['region_measurement_count']} region observations. Matched controls use {len(summary['matched_page_ids'])} common pages.", ""]
  for name, result in [("All v0.3 pages", summary["all_v03"])] + list(summary["matched_comparison"].items()):
    lines += [f"## {name}", "", "| Family:severity | Tasks | Regions | Page loss | Severity error | Mean region survival | Median | Fully removed rate | Mostly removed | Partial | Almost complete / mostly surviving |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for key, value in result["family_severity"].items():
      values = [value["actual_page_loss"]["mean"], value["severity_error"]["mean"], value["region_survival"]["mean"], value["region_survival"]["median"], value["fully_removed_region_rate"], value["mostly_removed_region_rate"], value["partially_surviving_region_rate"], value["almost_complete_survival_rate"]]
      lines.append(f"| {key} | {value['task_count']} | {value['region_measurement_count']} | " + " | ".join("undefined" if v is None else f"{v:.8f}" for v in values) + " |")
    lines.append("")
  lines += [summary["comparison_note"], "", "JSON includes count/mean/median/population SD/min/max by experiment, family, severity, manuscript, page and class, plus each family/severity/class combination.", ""]
  write_stable(ROOT / "docs/20a_artificial_fragment_v03_measurements.md", "\n".join(lines))
  print(f"Measured {len(tasks)} tasks / {summary['all_v03']['region_measurement_count']} region observations.", flush=True)


def verify():
  from src.evaluation.structured_fragment_experiment import compare
  from src.evaluation.artificial_fragment_experiment import load_task
  before = json.loads((ROOT / OUTPUT / "invariants_before.json").read_text())
  if snapshot() != before:
    raise ValueError("frozen_source_segmentation_historical_rights_split_state_changed")
  pages, specification = validation_state()
  for ref in read("pairing")["cached_manifests"]:
    if artifact(ROOT, ref["path"]) != ref:
      raise ValueError("cached_pairing_manifest_changed")
  tasks = read_tasks()
  historical = json.loads((ROOT / "data/metadata/artificial_fragment_v02_generation.json").read_text())
  controls = [load_task(ROOT, t["artifacts"]["metadata"]) for t in historical["tasks"]]
  if compare(tasks, controls) != read("measurements") or coverage(tasks) != read("coverage"):
    raise ValueError("measurements_or_coverage_changed")
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    registered = database_snapshot(cursor, experiment=True, experiment_version=VERSION)
  if registered != read("registration")["experiment_database"]:
    raise ValueError("v03_database_rows_changed")
  save("validation", {"status": "passed", "task_count": len(tasks), "selected_validation_pages": specification["selected_page_count"],
    "rejected_validation_pages": specification["rejected_pages"], "rejected_tasks": specification["rejected_tasks"],
    "region_measurement_count": sum(len(t["layout_survival_estimate"]["regions"]) for t in tasks),
    "topology_passed_count": sum(t["topology_validation"]["passed"] for t in tasks),
    "frozen_database": before["database"], "frozen_file_count": len(before["files"]), "frozen_file_snapshot_sha256": digest(before["files"]),
    "historical_v01_v02_artifacts_and_rows_unchanged": True, "sources_masks_and_mtimes_unchanged_after_authorized_restoration": True,
    "test_pages_used_for_generation_or_registration": 0, "rights_provenance_splits_and_training_allowed_unchanged": True,
    "binary_data_stored_in_postgresql": False, "model_training_or_reconstruction_performed": False})
  print("Verified frozen corpus, all historical artifacts/rows, test exclusion, measurements and v0.3 registration.", flush=True)


def check_determinism():
  tasks = read_tasks()
  paths = {r["path"] for t in tasks for r in t["artifacts"].values()}
  paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "data/metadata").glob("artificial_fragment_v03_*.json") if not p.name.endswith(("determinism.json", "validation.json")))
  paths.update(r["review_image"]["path"] for r in read("outlier_review")["outliers"])
  paths.add(read("outlier_review")["review_index"]["path"])
  paths.add("docs/20a_artificial_fragment_v03_measurements.md")
  def capture():
    return [{**artifact(ROOT, path), "mtime_ns": (ROOT / path).stat().st_mtime_ns} for path in sorted(paths)]
  before = capture()
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    db_before = database_snapshot(cursor, experiment=True, experiment_version=VERSION)
  # A complete second run: source check, full corpus mask audit/specification, review aids,
  # actual binary generation and overlaps, reports, live guarded registration and invariants.
  from argparse import Namespace
  source_availability(Namespace(restore=False, dry_run=False))
  spec()
  generate()
  register()
  verify()
  with connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
    db_after = database_snapshot(cursor, experiment=True, experiment_version=VERSION)
  if before != capture() or db_before != db_after:
    raise ValueError("full_v03_rerun_changed_bytes_mtimes_or_database_rows")
  save("determinism", {"status": "passed", "method": "full_source_check_audit_spec_review_generation_measurement_registration_verification_rerun",
    "task_count": len(tasks), "compared_artifact_count": len(paths), "generated_task_binary_count": 4*len(tasks),
    "review_artifact_count": len(read("outlier_review")["outliers"])+1,
    "byte_identical_artifacts_and_unchanged_file_mtimes": True, "identical_selection_ids_parameters_orientations_checksums_measurements": True,
    "database_rows_and_timestamps_unchanged": True, "scientific_artifact_snapshot_sha256": digest(before)})
  print("Full v0.3 recomputation is byte-identical, with unchanged file mtimes and database rows/timestamps.", flush=True)
