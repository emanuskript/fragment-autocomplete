#!/usr/bin/env python3
"""Validate the frozen baseline audit and first corpus-expansion dry run."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.ingestion.iiif_manifest import NormalizedCanvas, NormalizedImageAsset  # noqa: E402
from src.ingestion.training_corpus import (  # noqa: E402
  EXPANSION_SELECTION_RULES_VERSION,
  select_canvas_pages,
  sha256_file,
)


BASELINE_MANIFEST = ROOT / "data/metadata/training_corpus_validation_manifest.yaml"
BATCH_SPEC = ROOT / "data/metadata/training_corpus_expansion_batch_01_spec.yaml"
BATCH_MANIFEST = ROOT / "data/metadata/training_corpus_expansion_batch_01_manifest.yaml"
BATCH_STATISTICS = ROOT / "data/metadata/training_corpus_expansion_batch_01_statistics.yaml"
REVIEW = ROOT / "data/metadata/training_corpus_expansion_readiness_review.yaml"
AUDIT_OUTPUT = ROOT / "data/metadata/training_corpus_validation_decision_audit.yaml"
VALIDATION_OUTPUT = ROOT / "data/metadata/training_corpus_expansion_batch_01_validation.yaml"
AUDIT_REPORT = ROOT / "docs/16_training_corpus_validation_decision_audit.md"
BATCH_REPORT = ROOT / "docs/17_training_corpus_expansion_batch_01.md"


def load_yaml(path: Path) -> dict[str, Any]:
  payload = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"Expected YAML mapping: {path.relative_to(ROOT)}")
  return payload


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def canonical_sha256(payload: Any) -> str:
  value = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
  return hashlib.sha256(value).hexdigest()


def reconstructed_canvas(page: dict[str, Any]) -> NormalizedCanvas:
  image = page.get("image") or {}
  images = []
  if image:
    images.append(NormalizedImageAsset(
      source_url=image.get("source_url"),
      iiif_image_service_url=image.get("iiif_image_service_url"),
      media_type=image.get("media_type"),
      width_px=image.get("width_px"),
      height_px=image.get("height_px"),
      raw_metadata={"reconstructed_for_decision_audit": True},
    ))
  return NormalizedCanvas(
    canvas_identifier=page["canvas_identifier"],
    canvas_label=page.get("canvas_label"),
    width_px=page.get("width_px"),
    height_px=page.get("height_px"),
    sequence_index=page["sequence_index"],
    raw_metadata={"reconstructed_for_decision_audit": True},
    images=images,
  )


def corpus_review(review: dict[str, Any], corpus_id: str) -> dict[str, Any]:
  matches = [item for item in review.get("corpora", []) if item.get("corpus_id") == corpus_id]
  if len(matches) != 1:
    raise ValueError(f"Expected one visual review record for {corpus_id}")
  return matches[0]


def selected_pages(manifest: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
  result: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
  for manuscript in manifest.get("manuscripts", []):
    for page in manuscript.get("pages", []):
      if page.get("selection_status") != "selected":
        continue
      canvas_id = page["canvas_identifier"]
      if canvas_id in result:
        raise ValueError(f"Duplicate selected canvas: {canvas_id}")
      result[canvas_id] = (manuscript, page)
  return result


def audit_baseline(baseline: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
  original_reasons: Counter[str] = Counter()
  transitions: Counter[str] = Counter()
  newly_rejected: list[dict[str, Any]] = []
  manual_review_candidates: list[dict[str, Any]] = []
  original_selected: set[str] = set()
  projected_selected: set[str] = set()
  for manuscript in baseline["manuscripts"]:
    pages = manuscript["pages"]
    for page in pages:
      if page["selection_status"] == "rejected":
        original_reasons.update(reason["code"] for reason in page["selection_reasons"])
      elif page["selection_status"] == "selected":
        original_selected.add(page["canvas_identifier"])
    projected = select_canvas_pages(
      manuscript["id"],
      [reconstructed_canvas(page) for page in pages],
      baseline["selection"]["seed"],
      baseline["selection"]["max_pages_per_manuscript"],
      rules_version=EXPANSION_SELECTION_RULES_VERSION,
    )
    projected_by_id = {page["canvas_identifier"]: page for page in projected}
    for old in pages:
      new = projected_by_id[old["canvas_identifier"]]
      transitions[f"{old['selection_status']}_to_{new['selection_status']}"] += 1
      if new["selection_status"] == "selected":
        projected_selected.add(new["canvas_identifier"])
      if old["selection_status"] == "candidate" and new["selection_status"] == "rejected":
        newly_rejected.append({
          "manuscript_id": manuscript["id"],
          "canvas_identifier": old["canvas_identifier"],
          "canvas_label": old.get("canvas_label"),
          "reasons": new["selection_reasons"],
        })
      if new.get("selection_review_status") == "needs_manual_review":
        manual_review_candidates.append({
          "manuscript_id": manuscript["id"],
          "canvas_identifier": old["canvas_identifier"],
          "canvas_label": old.get("canvas_label"),
          "reasons": new["selection_reasons"],
        })
  if sum(original_reasons.values()) != 45 or original_reasons != Counter({"cover": 20, "binding": 15, "paste_down": 10}):
    raise ValueError(f"Historical rejection set changed unexpectedly: {dict(original_reasons)}")
  if len(newly_rejected) != 35:
    raise ValueError(f"Expected 35 newly recognized obvious exclusions, found {len(newly_rejected)}")
  if len(manual_review_candidates) != 12:
    raise ValueError(f"Expected 12 uncertain accompanying-material candidates, found {len(manual_review_candidates)}")
  if original_selected != projected_selected:
    raise ValueError("Versioned rule audit changed the historical 15 selected page identities")
  review_record = corpus_review(review, baseline["corpus_id"])
  if review_record["reviewed_selected_page_count"] != 15 or len(review_record["exceptions"]) != 1:
    raise ValueError("Baseline visual review must cover 15 selections and record its one exception")
  payload = {
    "audit_version": "training_corpus_validation_decision_audit_v0_1",
    "status": "passed_with_expansion_rule_corrections",
    "historical_corpus_id": baseline["corpus_id"],
    "historical_manifest_sha256": sha256_file(BASELINE_MANIFEST),
    "historical_rules_version": baseline["selection"]["rules_version"],
    "expansion_rules_version": EXPANSION_SELECTION_RULES_VERSION,
    "historical_rejection_count": 45,
    "historical_rejection_reasons": dict(sorted(original_reasons.items())),
    "state_transitions_under_expansion_rules": dict(sorted(transitions.items())),
    "new_obvious_exclusion_count": len(newly_rejected),
    "new_obvious_exclusions": newly_rejected,
    "uncertain_manual_review_candidate_count": len(manual_review_candidates),
    "uncertain_manual_review_candidates": manual_review_candidates,
    "historical_selected_pages_unchanged_under_new_label_rules": True,
    "selected_page_visual_triage": review_record,
    "interpretation": "The frozen validation evidence remains unchanged; corrected rules apply only to new expansion batches.",
  }
  payload["audit_sha256"] = canonical_sha256(payload)
  return payload


def validate_visual_review(
  review_record: dict[str, Any],
  selected: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> None:
  exceptions = review_record.get("exceptions", [])
  if review_record.get("reviewed_selected_page_count") != len(selected):
    raise ValueError("Visual review count differs from selected page count")
  if review_record.get("default_outcome_count") + len(exceptions) != len(selected):
    raise ValueError("Visual review default/exception counts do not cover every selected page")
  exception_ids = [item["canvas_identifier"] for item in exceptions]
  if len(exception_ids) != len(set(exception_ids)):
    raise ValueError("Visual review contains duplicate exceptions")
  for item in exceptions:
    if item["canvas_identifier"] not in selected:
      raise ValueError(f"Visual review exception is not selected: {item['canvas_identifier']}")
    manuscript, page = selected[item["canvas_identifier"]]
    if manuscript["id"] != item["manuscript_id"] or page.get("canvas_label") != item.get("canvas_label"):
      raise ValueError(f"Visual review provenance differs from manifest: {item['canvas_identifier']}")


def validate_batch(
  baseline: dict[str, Any],
  spec: dict[str, Any],
  batch: dict[str, Any],
  statistics: dict[str, Any],
  review: dict[str, Any],
) -> dict[str, Any]:
  if batch.get("status") != "dry_run":
    raise ValueError("Batch 01 must remain a dry run until manual exceptions are resolved")
  if batch.get("selection", {}).get("rules_version") != EXPANSION_SELECTION_RULES_VERSION:
    raise ValueError("Batch 01 does not use the corrected expansion rule set")
  if batch.get("specification", {}).get("sha256") != sha256_file(BATCH_SPEC):
    raise ValueError("Batch manifest specification checksum differs")
  manuscripts = batch.get("manuscripts", [])
  if len(manuscripts) != 15 or len(spec.get("manuscripts", [])) != 15:
    raise ValueError("Batch 01 must contain exactly 15 new manuscripts")
  spec_entries = {item["id"]: item for item in spec["manuscripts"]}
  if len(spec_entries) != 15 or set(spec_entries) != {item["id"] for item in manuscripts}:
    raise ValueError("Batch manifest membership differs from the frozen specification")
  discovery_seed = spec.get("discovery", {}).get("selection_seed")
  prefix_counts: Counter[str] = Counter()
  for manuscript_id, entry in spec_entries.items():
    expected_rank = hashlib.sha256(f"{discovery_seed}|{manuscript_id}".encode("utf-8")).hexdigest()
    if entry.get("discovery_rank_sha256") != expected_rank:
      raise ValueError(f"Discovery rank provenance differs: {manuscript_id}")
    if entry.get("manifest_url") != f"https://www.e-codices.unifr.ch/metadata/iiif/{manuscript_id}/manifest.json":
      raise ValueError(f"Manifest URL does not match its official e-codices identifier: {manuscript_id}")
    prefix_counts[manuscript_id.split("-", 1)[0]] += 1
  if max(prefix_counts.values(), default=0) > 2:
    raise ValueError("Discovery diversity cap exceeds two manuscripts per e-codices prefix")
  baseline_ids = {item["id"] for item in baseline["manuscripts"]}
  baseline_urls = {item["manifest_url"] for item in baseline["manuscripts"]}
  batch_ids = {item["id"] for item in manuscripts}
  batch_urls = {item["manifest_url"] for item in manuscripts}
  if baseline_ids & batch_ids or baseline_urls & batch_urls:
    raise ValueError("Expansion batch overlaps the frozen baseline manuscript set")
  baseline_canvases = {
    page["canvas_identifier"]
    for manuscript in baseline["manuscripts"]
    for page in manuscript["pages"]
  }
  batch_canvases = {
    page["canvas_identifier"]
    for manuscript in manuscripts
    for page in manuscript["pages"]
  }
  if baseline_canvases & batch_canvases:
    raise ValueError("Expansion batch contains a canvas already recorded in the baseline")
  split_counts = Counter(item["split"] for item in manuscripts)
  if split_counts != Counter({"train": 11, "validation": 2, "test": 2}):
    raise ValueError(f"Unexpected batch manuscript splits: {dict(split_counts)}")
  selected = selected_pages(batch)
  if len(selected) != 75:
    raise ValueError(f"Expected 75 selected dry-run pages, found {len(selected)}")
  if any(sum(page["selection_status"] == "selected" for page in item["pages"]) != 5 for item in manuscripts):
    raise ValueError("Every batch manuscript must have exactly five dry-run selections")
  for manuscript in manuscripts:
    if manuscript.get("rights_review_status") != "pending_review" or manuscript.get("training_allowed") is not False:
      raise ValueError(f"Conservative manuscript rights changed: {manuscript['id']}")
    if not manuscript.get("license") or not manuscript.get("rights_statement") or not manuscript.get("attribution"):
      raise ValueError(f"Source rights provenance is incomplete: {manuscript['id']}")
    document_types = [
      item.get("value")
      for item in manuscript.get("raw_source_metadata", {}).get("normalized_metadata", [])
      if str(item.get("label", "")).lower() == "document type"
    ]
    if document_types != ["Manuscript"]:
      raise ValueError(f"Official source does not identify the record as a manuscript: {manuscript['id']}")
    for page in manuscript["pages"]:
      if not page.get("selection_reasons"):
        raise ValueError(f"Canvas decision lacks reasons: {page['canvas_identifier']}")
      if page.get("selection_status") == "rejected" and page.get("automatic_selection_eligible") is not False:
        raise ValueError(f"Rejected page remains automatically eligible: {page['canvas_identifier']}")
      if page.get("selection_review_status") == "needs_manual_review":
        if page.get("selection_status") != "candidate" or page.get("automatic_selection_eligible") is not False:
          raise ValueError(f"Uncertain candidate handling differs: {page['canvas_identifier']}")
      image = page.get("image") or {}
      if page.get("selection_status") == "selected" and any(
        key in image for key in ("local_path", "checksum_sha256", "download_status", "registration")
      ):
        raise ValueError(f"Dry run unexpectedly downloaded or registered a page: {page['canvas_identifier']}")
  if statistics.get("manuscript_count") != 15 or statistics.get("selected_page_count") != 75:
    raise ValueError("Committed statistics do not describe the batch manifest")
  if statistics.get("split_counts", {}).get("manuscripts") != {"train": 11, "validation": 2, "test": 2}:
    raise ValueError("Committed statistics contain unexpected manuscript splits")
  review_record = corpus_review(review, batch["corpus_id"])
  validate_visual_review(review_record, selected)
  gate = review.get("acquisition_gate", {})
  unresolved = len(corpus_review(review, baseline["corpus_id"])["exceptions"]) + len(review_record["exceptions"])
  if gate.get("unresolved_exception_count") != unresolved or gate.get("status") != "blocked_pending_manual_page_decisions":
    raise ValueError("Acquisition gate does not match unresolved visual-review exceptions")
  baseline_split_counts = Counter(item["split"] for item in baseline["manuscripts"])
  aggregate_splits = {
    name: baseline_split_counts.get(name, 0) + split_counts.get(name, 0)
    for name in ("train", "validation", "test")
  }
  if aggregate_splits != {"train": 14, "validation": 3, "test": 3}:
    raise ValueError(f"Unexpected aggregate 20-manuscript split: {aggregate_splits}")
  baseline_source_bytes = sum(
    int(page.get("image", {}).get("size_bytes") or 0)
    for manuscript in baseline["manuscripts"]
    for page in manuscript["pages"]
    if page.get("selection_status") == "selected"
  )
  mean_source_bytes = baseline_source_bytes / 15
  payload = {
    "validation_version": "training_corpus_expansion_batch_01_validation_v0_1",
    "status": "passed_dry_run_blocked_pending_manual_page_decisions",
    "batch_corpus_id": batch["corpus_id"],
    "batch_manifest_sha256": sha256_file(BATCH_MANIFEST),
    "batch_statistics_sha256": sha256_file(BATCH_STATISTICS),
    "new_manuscript_count": 15,
    "dry_run_selected_page_count": 75,
    "repository_count": len({item["repository"] for item in manuscripts}),
    "batch_split_counts": {name: split_counts[name] for name in ("train", "validation", "test")},
    "aggregate_manuscript_count": 20,
    "aggregate_split_counts": aggregate_splits,
    "cross_batch_manuscript_overlap_count": 0,
    "cross_batch_manifest_overlap_count": 0,
    "cross_batch_canvas_overlap_count": 0,
    "rights_review_status": "pending_review",
    "training_allowed": False,
    "downloaded_page_count": 0,
    "registered_page_count": 0,
    "visual_reviewed_page_count": 75,
    "batch_visual_exception_count": len(review_record["exceptions"]),
    "total_unresolved_visual_exception_count": unresolved,
    "acquisition_gate": gate["status"],
    "storage_projection": {
      "basis": "mean bytes across the 15 checksum-verified validation JPEGs",
      "baseline_source_bytes": baseline_source_bytes,
      "mean_source_bytes_per_page": round(mean_source_bytes),
      "batch_75_page_source_bytes": round(mean_source_bytes * 75),
      "full_500_page_source_bytes": round(mean_source_bytes * 500),
      "excludes": "raw manifests, safety margin, optional segmentation, and database overhead",
    },
    "next_gate": "Resolve all eight recorded page exceptions, then rerun the unchanged dry-run validator before acquisition.",
  }
  payload["validation_sha256"] = canonical_sha256(payload)
  return payload


def write_audit_report(audit: dict[str, Any]) -> None:
  reasons = audit["historical_rejection_reasons"]
  review = audit["selected_page_visual_triage"]
  lines = [
    "# Training Corpus Validation Decision Audit",
    "",
    "## Outcome",
    "",
    "The frozen five-manuscript validation manifest remains unchanged. Its 45 recorded rejections are all explicit label-based exclusions: "
    f"{reasons['cover']} covers, {reasons['paste_down']} paste-downs, and {reasons['binding']} binding/calibration views.",
    "",
    f"Applying the versioned expansion rules in audit mode identifies {audit['new_obvious_exclusion_count']} additional obvious auxiliary views that the historical rules retained as candidates. It also identifies {audit['uncertain_manual_review_candidate_count']} accompanying-material canvases; these remain candidates with a manual-review requirement and are not silently rejected.",
    "",
    "## Visual engineering triage",
    "",
    f"All {review['reviewed_selected_page_count']} downloaded validation selections were inspected at review scale. Fourteen are page-like manuscript content. One (`ubb-F-IX-0068`, `V2v`) is a blank-like damaged flyleaf and is explicitly flagged for manual review. This is engineering triage, not scholarly or rights approval.",
    "",
    "## Rule correction",
    "",
    "Expansion rule version `obvious_non_training_canvas_rules_v0_2` adds explicit matches for digital color checkers/color profiles, rulers/QP cards, fore-edge/head/tail views, and open views. `Accompanying materials` stays a candidate but is excluded from automatic seeded selection pending review.",
    "",
    "The historical validation artifacts keep rule version v0.1 and are not regenerated. The corrected rules apply only to new batch specifications.",
    "",
  ]
  AUDIT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_batch_report(validation: dict[str, Any], statistics: dict[str, Any], review: dict[str, Any]) -> None:
  projection = validation["storage_projection"]
  batch_review = corpus_review(review, validation["batch_corpus_id"])
  lines = [
    "# Training Corpus Expansion — Batch 01 Dry-Run Readiness",
    "",
    "## Outcome",
    "",
    "A separate immutable dry-run batch now contains 15 newly verified official e-codices manuscript manifests. It does not overlap or rewrite the frozen five-manuscript validation corpus. Together they represent 20 manuscripts with aggregate 14/3/3 train/validation/test manuscript splits.",
    "",
    f"The dry run selected {validation['dry_run_selected_page_count']} pages (five per new manuscript) across {validation['repository_count']} repositories. No page was downloaded, registered, segmented, or marked training-allowed.",
    "",
    "## Review gate",
    "",
    f"All {batch_review['reviewed_selected_page_count']} selected IIIF thumbnails were visually triaged. {batch_review['default_outcome_count']} appear page-like at review scale; {len(batch_review['exceptions'])} are explicitly flagged as blank-like, photographic/non-text, or low-contrast and need a manual keep/reject decision.",
    "",
    "Acquisition is intentionally blocked. No uncertain page has been silently discarded or replaced. Any rejection must preserve its evidence and a replacement must come from the unchanged seeded order.",
    "",
    "## Dry-run statistics",
    "",
    f"- New manuscripts: {validation['new_manuscript_count']}",
    f"- Selected pages: {validation['dry_run_selected_page_count']}",
    f"- Candidate canvases: {statistics['canvas_status_counts'].get('candidate', 0)}",
    f"- Explicitly rejected canvases: {statistics['canvas_status_counts'].get('rejected', 0)}",
    f"- Batch splits: {validation['batch_split_counts']['train']} train / {validation['batch_split_counts']['validation']} validation / {validation['batch_split_counts']['test']} test manuscripts",
    f"- Cross-batch overlaps: {validation['cross_batch_manuscript_overlap_count']} manuscripts, {validation['cross_batch_manifest_overlap_count']} manifests, {validation['cross_batch_canvas_overlap_count']} canvases",
    "- Rights: `pending_review`; `training_allowed: false`",
    "",
    "## Storage planning estimate",
    "",
    f"The 15-page validation set contains {projection['baseline_source_bytes']} source-image bytes, or approximately {projection['mean_source_bytes_per_page']} bytes/page. At that observed mean, this 75-page batch would use about {projection['batch_75_page_source_bytes']} bytes and 500 pages about {projection['full_500_page_source_bytes']} bytes before raw manifests, safety margin, optional segmentation, and database overhead.",
    "",
    "## Reproduce",
    "",
    "```bash",
    "PYTHON_BIN=/usr/bin/python3 bash scripts/validate_training_corpus_expansion_batch.sh",
    "```",
    "",
    "This command runs the dry build twice and requires byte-identical manifests/statistics before executing the structural, provenance, split, rights, overlap, and review-gate validator.",
    "",
    "## Next gate",
    "",
    validation["next_gate"],
    "",
  ]
  BATCH_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
  baseline = load_yaml(BASELINE_MANIFEST)
  spec = load_yaml(BATCH_SPEC)
  batch = load_yaml(BATCH_MANIFEST)
  statistics = load_yaml(BATCH_STATISTICS)
  review = load_yaml(REVIEW)
  audit = audit_baseline(baseline, review)
  validation = validate_batch(baseline, spec, batch, statistics, review)
  write_yaml(AUDIT_OUTPUT, audit)
  write_yaml(VALIDATION_OUTPUT, validation)
  write_audit_report(audit)
  write_batch_report(validation, statistics, review)
  print(
    "PASS: batch 01 dry run has 15 new manuscripts/75 selections and no baseline overlap; "
    "acquisition remains blocked on 8 explicit visual-review decisions"
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
