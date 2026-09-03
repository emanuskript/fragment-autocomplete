#!/usr/bin/env python3
"""Snapshot and validate Batch 01 acquisition/registration reruns.

This module is deliberately validation-only.  It reads artifacts emitted by the
existing Training Corpus Builder, reads the existing PostgreSQL schema, and
records enough state to prove that a later registered rerun reused rather than
rewrote source assets or duplicated database records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))


DEFAULT_SPEC = ROOT / "data/metadata/training_corpus_expansion_batch_01_spec.yaml"
DEFAULT_MANIFEST = ROOT / "data/metadata/training_corpus_expansion_batch_01_manifest.yaml"
DEFAULT_STATISTICS = ROOT / "data/metadata/training_corpus_expansion_batch_01_statistics.yaml"
DEFAULT_BASELINE = ROOT / "data/metadata/training_corpus_validation_manifest.yaml"
DEFAULT_REVIEW = ROOT / "data/metadata/training_corpus_expansion_readiness_review.yaml"
DEFAULT_OUTPUT = ROOT / "data/metadata/training_corpus_expansion_batch_01_acquisition_validation.yaml"
DEFAULT_STATE = Path("/tmp/training_corpus_expansion_batch_01_acquisition_state.json")

STATE_VERSION = "training_corpus_expansion_batch_01_acquisition_state_v0_1"
VALIDATION_VERSION = "training_corpus_expansion_batch_01_acquisition_validation_v0_1"
DECISIONS = {"keep", "reject"}
SPLITS = ("train", "validation", "test")
DOWNLOADED_STATUSES = {"downloaded", "redownloaded_after_verification_failure"}
REUSED_STATUSES = {"verified_existing"}
EXPECTED_REPLACEMENT_CANVASES = {
  "https://www.e-codices.unifr.ch/metadata/iiif/bc-b-0103/canvas/bc-b-0103_040r.json",
  "https://www.e-codices.unifr.ch/metadata/iiif/bcul-Ms0403/canvas/bcul-Ms0403_086r.json",
  "https://www.e-codices.unifr.ch/metadata/iiif/bcj-A2437/canvas/bcj-A2437_0102.json",
}
REQUIRED_DECISION_FIELDS = (
  "manuscript_id",
  "canvas_identifier",
  "sequence_index",
  "split",
  "decision",
  "decision_scope",
  "reason_code",
  "decision_reason",
  "reviewer",
  "decision_version",
  "recorded_at",
  "decision_provenance",
  "selection_application",
)


class ValidationError(ValueError):
  """Raised when a Batch acquisition invariant is not satisfied."""


def load_yaml(path: Path) -> dict[str, Any]:
  payload = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValidationError(f"Expected YAML mapping: {path}")
  return payload


def sha256_file(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
  rendered = json.dumps(json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
  return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def json_safe(value: Any) -> Any:
  if isinstance(value, dict):
    return {str(key): json_safe(item) for key, item in value.items()}
  if isinstance(value, (list, tuple)):
    return [json_safe(item) for item in value]
  if isinstance(value, (date, datetime)):
    return value.isoformat()
  if isinstance(value, Path):
    return value.as_posix()
  return value


def resolve_path(root: Path, value: str | Path) -> Path:
  path = Path(value)
  return path if path.is_absolute() else root / path


def relative_path(root: Path, path: Path) -> str:
  try:
    return path.resolve().relative_to(root.resolve()).as_posix()
  except ValueError as exc:
    raise ValidationError(f"Artifact lies outside the project root: {path}") from exc


def page_index(manifest: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
  result: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
  for manuscript in manifest.get("manuscripts", []):
    for page in manuscript.get("pages", []):
      canvas_id = page.get("canvas_identifier")
      if not canvas_id:
        raise ValidationError(f"Page without canvas identifier in manuscript {manuscript.get('id')}")
      if canvas_id in result:
        raise ValidationError(f"Duplicate canvas in manifest: {canvas_id}")
      result[canvas_id] = (manuscript, page)
  return result


def selected_pages(manifest: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
  return [
    (manuscript, page)
    for manuscript in manifest.get("manuscripts", [])
    for page in manuscript.get("pages", [])
    if page.get("selection_status") == "selected"
  ]


def extract_review_decisions(review: dict[str, Any]) -> list[dict[str, Any]]:
  """Return all readiness-review exceptions after validating decision metadata."""
  decisions: list[dict[str, Any]] = []
  seen: set[tuple[str, str]] = set()
  for corpus in review.get("corpora", []):
    corpus_id = corpus.get("corpus_id")
    if not corpus_id:
      raise ValidationError("Review corpus record lacks corpus_id")
    for exception in corpus.get("exceptions", []):
      missing = [
        field
        for field in REQUIRED_DECISION_FIELDS
        if field not in exception
        or exception[field] is None
        or (isinstance(exception[field], str) and not exception[field].strip())
      ]
      if missing:
        canvas = exception.get("canvas_identifier", "[missing canvas]")
        raise ValidationError(f"Manual decision {canvas} lacks fields: {', '.join(missing)}")
      decision = str(exception["decision"]).lower()
      if decision not in DECISIONS:
        raise ValidationError(f"Unsupported manual decision {decision!r}: {exception['canvas_identifier']}")
      recorded_at = exception["recorded_at"]
      if isinstance(recorded_at, str):
        try:
          datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        except ValueError as exc:
          raise ValidationError(f"Invalid recorded_at for {exception['canvas_identifier']}: {recorded_at}") from exc
      elif not isinstance(recorded_at, (date, datetime)):
        raise ValidationError(f"Invalid recorded_at type for {exception['canvas_identifier']}")
      key = (str(corpus_id), str(exception["canvas_identifier"]))
      if key in seen:
        raise ValidationError(f"Duplicate manual decision: {key[1]}")
      seen.add(key)
      decisions.append({"corpus_id": corpus_id, **json_safe(exception), "decision": decision})
  if not decisions:
    raise ValidationError("Readiness review contains no page decisions")
  gate = review.get("acquisition_gate", {})
  unresolved = gate.get("unresolved_exception_count")
  if unresolved not in (None, 0):
    raise ValidationError(f"Acquisition gate still reports {unresolved} unresolved decisions")
  gate_status = str(gate.get("status", ""))
  if gate_status != "ready_for_batch_01_acquisition":
    raise ValidationError(f"Acquisition gate is not explicitly ready: {gate_status}")
  return decisions


def reason_codes(page: dict[str, Any]) -> set[str]:
  return {
    str(reason.get("code"))
    for reason in page.get("selection_reasons", [])
    if isinstance(reason, dict) and reason.get("code")
  }


def _manual_decision_matches(page: dict[str, Any], decision: dict[str, Any]) -> bool:
  recorded = page.get("manual_decision")
  if not isinstance(recorded, dict):
    return False
  fields = (
    "decision",
    "decision_scope",
    "reason_code",
    "decision_reason",
    "reviewer",
    "decision_version",
    "recorded_at",
    "decision_provenance",
    "selection_application",
  )
  return all(json_safe(recorded.get(field)) == json_safe(decision.get(field)) for field in fields)


def _replacement_references(reason: dict[str, Any]) -> set[str]:
  for field in (
    "rejected_canvas_identifiers",
    "manual_rejected_canvas_identifiers",
    "rejected_canvas_ids",
    "replaces",
  ):
    value = reason.get(field)
    if isinstance(value, str):
      return {value}
    if isinstance(value, list):
      return {str(item) for item in value}
  return set()


def _has_insufficient_state(manuscript: dict[str, Any]) -> bool:
  def walk(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
      for key, item in value.items():
        if key in {"code", "status", "selection_status", "selection_completion_status"} and isinstance(item, str):
          yield item.lower()
        yield from walk(item)
    elif isinstance(value, list):
      for item in value:
        yield from walk(item)

  markers = ("insufficient", "unsuitable", "no_replacement", "page_quota_unmet")
  return any(any(marker in item for marker in markers) for item in walk(manuscript))


def validate_decisions(
  batch: dict[str, Any],
  baseline: dict[str, Any],
  review: dict[str, Any],
) -> dict[str, Any]:
  decisions = extract_review_decisions(review)
  batch_id = batch.get("corpus_id")
  baseline_id = baseline.get("corpus_id")
  batch_pages = page_index(batch)
  baseline_pages = page_index(baseline)
  batch_rejected: dict[str, dict[str, Any]] = {}
  counts: Counter[str] = Counter()

  for decision in decisions:
    corpus_id = decision["corpus_id"]
    canvas_id = decision["canvas_identifier"]
    if corpus_id == batch_id:
      owner_page = batch_pages.get(canvas_id)
      if owner_page is None:
        raise ValidationError(f"Batch decision canvas is absent from final manifest: {canvas_id}")
      manuscript, page = owner_page
      if manuscript.get("id") != decision.get("manuscript_id"):
        raise ValidationError(f"Batch decision manuscript differs for {canvas_id}")
      if not _manual_decision_matches(page, decision):
        raise ValidationError(f"Final Batch page lacks matching manual_decision: {canvas_id}")
      codes = reason_codes(page)
      if decision["reason_code"] not in codes and not any("manual" in code for code in codes):
        raise ValidationError(f"Final Batch page lacks structured manual-decision reason: {canvas_id}")
      if decision["decision"] == "keep":
        if page.get("selection_status") != "selected":
          raise ValidationError(f"Kept Batch page is not selected: {canvas_id}")
      else:
        if page.get("selection_status") != "rejected":
          raise ValidationError(f"Rejected Batch page remains selected/candidate: {canvas_id}")
        if page.get("automatic_selection_eligible") is not False:
          raise ValidationError(f"Rejected Batch page remains automatically eligible: {canvas_id}")
        batch_rejected[canvas_id] = decision
      counts[f"batch_{decision['decision']}"] += 1
    elif corpus_id == baseline_id:
      owner_page = baseline_pages.get(canvas_id)
      if owner_page is None:
        raise ValidationError(f"Historical decision canvas is absent from frozen baseline: {canvas_id}")
      manuscript, page = owner_page
      if manuscript.get("id") != decision.get("manuscript_id"):
        raise ValidationError(f"Historical decision manuscript differs for {canvas_id}")
      if decision["decision"] == "keep" and page.get("selection_status") != "selected":
        raise ValidationError(f"Kept historical page is not selected: {canvas_id}")
      if decision["decision"] == "reject" and page.get("selection_status") == "selected":
        application = str(decision.get("selection_application", "")).lower()
        if not any(marker in application for marker in ("historical", "audit", "frozen")):
          raise ValidationError(f"Historical reject leaves selected page without frozen/audit scope: {canvas_id}")
      counts[f"historical_{decision['decision']}"] += 1
    else:
      raise ValidationError(f"Decision references unknown corpus {corpus_id}: {canvas_id}")

  replacement_reasons: list[tuple[str, str, dict[str, Any]]] = []
  for manuscript in batch.get("manuscripts", []):
    for page in manuscript.get("pages", []):
      if page.get("selection_status") != "selected":
        continue
      for reason in page.get("selection_reasons", []):
        if isinstance(reason, dict) and reason.get("code") in {
          "deterministic_replacement_after_manual_rejection",
          "deterministic_same_manuscript_replacement",
        }:
          rank = reason.get("promoted_original_seeded_rank", reason.get("seeded_rank_before_manual_decisions"))
          if not isinstance(rank, int) or rank < 1:
            raise ValidationError(f"Replacement lacks promoted original seeded rank: {page['canvas_identifier']}")
          references = _replacement_references(reason)
          if not references:
            raise ValidationError(f"Replacement lacks rejected canvas provenance: {page['canvas_identifier']}")
          replacement_reasons.append((manuscript["id"], page["canvas_identifier"], reason))

  untraced_rejections: list[str] = []
  for canvas_id, decision in batch_rejected.items():
    owner = decision["manuscript_id"]
    traced = any(owner == manuscript_id and canvas_id in _replacement_references(reason) for manuscript_id, _, reason in replacement_reasons)
    manuscript = next(item for item in batch["manuscripts"] if item["id"] == owner)
    if not traced and not _has_insufficient_state(manuscript):
      untraced_rejections.append(canvas_id)
  if untraced_rejections:
    raise ValidationError(f"Rejected decisions lack explicit replacement/insufficient-page provenance: {untraced_rejections}")

  if counts != Counter({"batch_reject": 7, "historical_reject": 1}):
    raise ValidationError(f"Unexpected resolved decision distribution: {dict(counts)}")

  batch_review_records = [
    item for item in review.get("corpora", []) if item.get("corpus_id") == batch_id
  ]
  if len(batch_review_records) != 1:
    raise ValidationError("Expected one Batch review record")
  replacement_reviews = batch_review_records[0].get("replacement_reviews", [])
  if len(replacement_reviews) != 8:
    raise ValidationError("Expected eight annotation-only replacement reviews")
  reviewed_replacements: set[str] = set()
  for item in replacement_reviews:
    missing = [
      field
      for field in REQUIRED_DECISION_FIELDS
      if field not in item
      or item[field] is None
      or (isinstance(item[field], str) and not item[field].strip())
    ]
    if missing:
      raise ValidationError(f"Replacement review lacks fields {missing}: {item.get('canvas_identifier')}")
    if item.get("decision_scope") != "replacement_suitability_review" or item.get("selection_application") != "review_evidence_only":
      raise ValidationError(f"Replacement review is not annotation-only: {item['canvas_identifier']}")
    owner_page = batch_pages.get(item["canvas_identifier"])
    if owner_page is None or owner_page[0].get("id") != item.get("manuscript_id"):
      raise ValidationError(f"Replacement review canvas/manuscript is absent: {item['canvas_identifier']}")
    recorded = owner_page[1].get("replacement_review") or {}
    if any(json_safe(recorded.get(field)) != json_safe(item.get(field)) for field in REQUIRED_DECISION_FIELDS):
      raise ValidationError(f"Final manifest lacks matching replacement review: {item['canvas_identifier']}")
    reviewed_replacements.add(str(item["canvas_identifier"]))
  if len(reviewed_replacements) != 8:
    raise ValidationError("Replacement reviews contain duplicate canvases")

  max_pages = int(batch.get("selection", {}).get("max_pages_per_manuscript") or 0)
  insufficient_manuscripts: list[str] = []
  for manuscript in batch.get("manuscripts", []):
    selected_count = sum(page.get("selection_status") == "selected" for page in manuscript.get("pages", []))
    if max_pages and selected_count > max_pages:
      raise ValidationError(f"Manuscript exceeds final page quota: {manuscript['id']}")
    if max_pages and selected_count < max_pages:
      if not _has_insufficient_state(manuscript):
        raise ValidationError(f"Manuscript has an unexplained selection shortfall: {manuscript['id']}")
      insufficient_manuscripts.append(manuscript["id"])

  if len(replacement_reasons) != 3:
    raise ValidationError(f"Expected three deterministic replacements, found {len(replacement_reasons)}")
  if {canvas_id for _, canvas_id, _ in replacement_reasons} != EXPECTED_REPLACEMENT_CANVASES:
    raise ValidationError("Deterministic replacement identities differ from the reviewed replacements")
  if insufficient_manuscripts != ["cea-FaZellweger-90A-01-2"]:
    raise ValidationError(f"Unexpected unsuitable/shortfall manuscripts: {insufficient_manuscripts}")
  unsuitable = next(item for item in batch["manuscripts"] if item["id"] == insufficient_manuscripts[0])
  suitability = unsuitable.get("manuscript_suitability_decision") or {}
  evidence = suitability.get("evidence") or {}
  if (
    suitability.get("decision") != "unsuitable_for_training_corpus"
    or suitability.get("decision_scope") != "manuscript_training_corpus_suitability"
    or suitability.get("selection_application") != "batch_selection"
    or evidence.get("reviewed_seeded_candidate_count") != 9
    or evidence.get("suitable_seeded_candidate_count") != 2
    or evidence.get("unsuitable_seeded_candidate_count") != 7
    or unsuitable.get("page_selection", {}).get("selected_page_count") != 0
    or unsuitable.get("page_selection", {}).get("shortfall_count") != 5
  ):
    raise ValidationError("The exact manuscript-unsuitable decision/evidence is not preserved")

  return {
    "decision_count": len(decisions),
    "decision_counts": dict(sorted(counts.items())),
    "unresolved_decision_count": 0,
    "batch_manual_rejected_count": len(batch_rejected),
    "replacement_page_count": len(replacement_reasons),
    "replacement_records": [
      {
        "manuscript_id": manuscript_id,
        "canvas_identifier": canvas_id,
        "promoted_original_seeded_rank": reason.get(
          "promoted_original_seeded_rank",
          reason.get("seeded_rank_before_manual_decisions"),
        ),
        "rejected_canvas_identifiers": sorted(_replacement_references(reason)),
      }
      for manuscript_id, canvas_id, reason in replacement_reasons
    ],
    "insufficient_or_unsuitable_manuscript_count": len(insufficient_manuscripts),
    "insufficient_or_unsuitable_manuscripts": insufficient_manuscripts,
  }


def validate_structure(
  batch: dict[str, Any],
  baseline: dict[str, Any],
  review: dict[str, Any],
  spec: dict[str, Any] | None = None,
  statistics: dict[str, Any] | None = None,
) -> dict[str, Any]:
  manuscripts = batch.get("manuscripts", [])
  if not manuscripts:
    raise ValidationError("Batch manifest contains no manuscripts")
  ids = [str(item.get("id")) for item in manuscripts]
  urls = [str(item.get("manifest_url")) for item in manuscripts]
  if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
    raise ValidationError("Batch manuscript IDs or manifest URLs are duplicated")
  if len(manuscripts) != 15:
    raise ValidationError(f"Expected 15 assigned Batch manuscripts, found {len(manuscripts)}")
  if spec is not None:
    expected_membership = {
      (str(item.get("id")), str(item.get("manifest_url")))
      for item in spec.get("manuscripts", [])
      if item.get("enabled", True)
    }
    actual_membership = set(zip(ids, urls))
    if len(expected_membership) != 15 or actual_membership != expected_membership:
      raise ValidationError("Batch manuscript membership differs from the specification")

  pages = page_index(batch)
  baseline_pages = page_index(baseline)
  baseline_ids = {str(item.get("id")) for item in baseline.get("manuscripts", [])}
  baseline_urls = {str(item.get("manifest_url")) for item in baseline.get("manuscripts", [])}
  if set(ids) & baseline_ids or set(urls) & baseline_urls or set(pages) & set(baseline_pages):
    raise ValidationError("Batch overlaps the frozen validation corpus")

  manuscript_splits: Counter[str] = Counter()
  page_splits: Counter[str] = Counter()
  repositories: Counter[str] = Counter()
  status_counts: Counter[str] = Counter()
  selected_count = 0
  for manuscript in manuscripts:
    split = manuscript.get("split")
    if split not in SPLITS:
      raise ValidationError(f"Unsupported manuscript split {split!r}: {manuscript.get('id')}")
    manuscript_splits[str(split)] += 1
    repositories[str(manuscript.get("repository") or "[missing]")] += 1
    for page in manuscript.get("pages", []):
      status = str(page.get("selection_status"))
      status_counts[status] += 1
      if status == "selected":
        selected_count += 1
        page_splits[str(split)] += 1
      if not page.get("selection_reasons"):
        raise ValidationError(f"Page decision lacks reasons: {page.get('canvas_identifier')}")
      if status == "rejected" and page.get("automatic_selection_eligible") is not False:
        raise ValidationError(f"Rejected page is automatically eligible: {page.get('canvas_identifier')}")

  decision_summary = validate_decisions(batch, baseline, review)
  summary = {
    "manuscript_count": len(manuscripts),
    "selected_page_count": selected_count,
    "rejected_page_count": status_counts.get("rejected", 0),
    "canvas_status_counts": dict(sorted(status_counts.items())),
    "repository_distribution": dict(sorted(repositories.items())),
    "split_counts": {
      "manuscripts": {name: manuscript_splits.get(name, 0) for name in SPLITS},
      "pages": {name: page_splits.get(name, 0) for name in SPLITS},
    },
    "cross_batch_overlap": {"manuscripts": 0, "manifest_urls": 0, "canvases": 0},
    "decisions": decision_summary,
  }
  if summary["selected_page_count"] != 70:
    raise ValidationError(f"Expected 70 selected pages, found {summary['selected_page_count']}")
  if summary["split_counts"]["manuscripts"] != {"train": 11, "validation": 2, "test": 2}:
    raise ValidationError(f"Unexpected manuscript splits: {summary['split_counts']['manuscripts']}")
  if summary["split_counts"]["pages"] != {"train": 50, "validation": 10, "test": 10}:
    raise ValidationError(f"Unexpected selected-page splits: {summary['split_counts']['pages']}")
  if statistics is not None:
    comparisons = {
      "manuscript_count": summary["manuscript_count"],
      "selected_page_count": summary["selected_page_count"],
      "canvas_status_counts": summary["canvas_status_counts"],
      "repository_distribution": summary["repository_distribution"],
      "split_counts": summary["split_counts"],
    }
    for field, expected in comparisons.items():
      if statistics.get(field) != expected:
        raise ValidationError(f"Statistics {field} differs from the final manifest")
  return summary


def inspect_image(path: Path) -> tuple[int, int, str | None]:
  with Image.open(path) as image:
    image.verify()
  with Image.open(path) as image:
    return int(image.width), int(image.height), Image.MIME.get(image.format)


def snapshot_file(path: Path, root: Path, *, image: bool = False) -> dict[str, Any]:
  if not path.is_file():
    raise ValidationError(f"Required local artifact is missing: {path}")
  stat = path.stat()
  result: dict[str, Any] = {
    "local_path": relative_path(root, path),
    "sha256": sha256_file(path),
    "size_bytes": stat.st_size,
    "mtime_ns": stat.st_mtime_ns,
  }
  if image:
    width, height, media_type = inspect_image(path)
    result.update({"width_px": width, "height_px": height, "media_type": media_type})
  return result


def selected_asset_snapshot(batch: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
  records: list[dict[str, Any]] = []
  local_paths: set[str] = set()
  status_counts: Counter[str] = Counter()
  rights_counts: Counter[str] = Counter()
  failures = 0
  total_bytes = 0
  training_allowed_count = 0
  for manuscript, page in selected_pages(batch):
    image = page.get("image") or {}
    canvas_id = page["canvas_identifier"]
    required = ("local_path", "checksum_sha256", "download_width_px", "download_height_px", "size_bytes", "download_status")
    missing = [field for field in required if image.get(field) is None]
    if missing:
      raise ValidationError(f"Selected page lacks acquisition fields {missing}: {canvas_id}")
    path = resolve_path(root, image["local_path"])
    local_path = relative_path(root, path)
    if local_path in local_paths:
      raise ValidationError(f"Duplicate local source asset path: {local_path}")
    local_paths.add(local_path)
    file_record = snapshot_file(path, root, image=True)
    if file_record["sha256"] != image["checksum_sha256"]:
      raise ValidationError(f"Checksum differs from manifest: {local_path}")
    if file_record["size_bytes"] != int(image["size_bytes"]):
      raise ValidationError(f"Size differs from manifest: {local_path}")
    if (file_record["width_px"], file_record["height_px"]) != (
      int(image["download_width_px"]),
      int(image["download_height_px"]),
    ):
      raise ValidationError(f"Downloaded dimensions differ from manifest: {local_path}")
    status = str(image["download_status"])
    status_counts[status] += 1
    if status not in DOWNLOADED_STATUSES | REUSED_STATUSES:
      failures += 1
    rights_status = str(image.get("rights_review_status") or "[missing]")
    rights_counts[rights_status] += 1
    if image.get("training_allowed") is not False:
      training_allowed_count += 1
    total_bytes += file_record["size_bytes"]
    records.append({
      "manuscript_id": manuscript["id"],
      "manifest_url": manuscript["manifest_url"],
      "canvas_identifier": canvas_id,
      "source_url": image.get("source_url"),
      "iiif_image_service_url": image.get("iiif_image_service_url"),
      "split": manuscript["split"],
      "rights_review_status": rights_status,
      "training_allowed": image.get("training_allowed"),
      **file_record,
    })
  records.sort(key=lambda item: (item["manuscript_id"], item["canvas_identifier"]))
  return records, {
    "selected_pages": len(records),
    "downloaded_pages": sum(status_counts.get(name, 0) for name in DOWNLOADED_STATUSES),
    "reused_pages": sum(status_counts.get(name, 0) for name in REUSED_STATUSES),
    "failures": failures,
    "download_status_counts": dict(sorted(status_counts.items())),
    "total_bytes": total_bytes,
    "rights_status_counts": dict(sorted(rights_counts.items())),
    "training_allowed_count": training_allowed_count,
  }


def source_tree_snapshot(spec: dict[str, Any], batch: dict[str, Any], root: Path) -> list[dict[str, Any]]:
  download_root = resolve_path(root, spec.get("download_root") or f"data/raw/{batch['corpus_id']}")
  if not download_root.is_dir():
    raise ValidationError(f"Batch download root is missing: {download_root}")
  partials = sorted(path for path in download_root.rglob("*.part") if path.is_file())
  if partials:
    raise ValidationError(f"Incomplete partial downloads remain: {[relative_path(root, path) for path in partials]}")
  records: list[dict[str, Any]] = []
  for path in sorted(item for item in download_root.rglob("*") if item.is_file()):
    is_image = path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".jp2"}
    records.append(snapshot_file(path, root, image=is_image))
  if not records:
    raise ValidationError("Batch download root contains no files")
  raw_artifacts = []
  for manuscript in batch.get("manuscripts", []):
    artifact = manuscript.get("raw_source_metadata", {}).get("raw_manifest_artifact") or {}
    if not artifact.get("local_path") or not artifact.get("sha256"):
      raise ValidationError(f"Manuscript lacks raw manifest artifact: {manuscript.get('id')}")
    path = resolve_path(root, artifact["local_path"])
    record = snapshot_file(path, root)
    if record["sha256"] != artifact["sha256"]:
      raise ValidationError(f"Raw manifest checksum differs: {artifact['local_path']}")
    raw_artifacts.append(record["local_path"])
  if len(set(raw_artifacts)) != len(batch.get("manuscripts", [])):
    raise ValidationError("Raw manifest artifact paths are duplicated or incomplete")
  expected_paths = set(raw_artifacts)
  expected_paths.update(
    str(page.get("image", {}).get("local_path"))
    for _, page in selected_pages(batch)
  )
  actual_paths = {item["local_path"] for item in records}
  if actual_paths != expected_paths:
    extra = sorted(actual_paths - expected_paths)
    missing = sorted(expected_paths - actual_paths)
    raise ValidationError(f"Batch source tree contains missing/orphan artifacts; missing={missing}, extra={extra}")
  return records


def compare_file_snapshots(
  earlier: list[dict[str, Any]],
  later: list[dict[str, Any]],
  label: str,
) -> None:
  earlier_by_path = {item["local_path"]: item for item in earlier}
  later_by_path = {item["local_path"]: item for item in later}
  if set(earlier_by_path) != set(later_by_path):
    raise ValidationError(f"{label} changed the source-file path set")
  stable_fields = ("sha256", "size_bytes", "mtime_ns", "width_px", "height_px", "media_type")
  for path in sorted(earlier_by_path):
    for field in stable_fields:
      if earlier_by_path[path].get(field) != later_by_path[path].get(field):
        raise ValidationError(f"{label} changed {field} for {path}")


def git_safety(spec: dict[str, Any], batch: dict[str, Any], source_files: list[dict[str, Any]], root: Path) -> dict[str, Any]:
  download_root = resolve_path(root, spec.get("download_root") or f"data/raw/{batch['corpus_id']}")
  download_rel = relative_path(root, download_root)
  tracked_result = subprocess.run(
    ["git", "ls-files", "--", download_rel],
    cwd=root,
    check=True,
    capture_output=True,
    text=True,
  )
  tracked = [line for line in tracked_result.stdout.splitlines() if line.strip()]
  if tracked:
    raise ValidationError(f"Batch source artifacts are tracked by Git: {tracked}")
  paths = [item["local_path"] for item in source_files]
  ignored_result = subprocess.run(
    ["git", "check-ignore", "--stdin"],
    cwd=root,
    input="\n".join(paths) + "\n",
    capture_output=True,
    text=True,
  )
  if ignored_result.returncode not in (0, 1):
    raise ValidationError(f"git check-ignore failed: {ignored_result.stderr.strip()}")
  ignored = {line.strip() for line in ignored_result.stdout.splitlines() if line.strip()}
  unignored = sorted(set(paths) - ignored)
  if unignored:
    raise ValidationError(f"Batch source artifacts are not Git-ignored: {unignored}")
  return {
    "download_root": download_rel,
    "tracked_batch_artifact_count": 0,
    "ignored_batch_artifact_count": len(ignored),
    "binary_commit_safety": "passed",
  }


def _database_rows(manifest_urls: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
  from psycopg.rows import dict_row

  from src.ingestion.db import connect

  with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
    cur.execute("SET TRANSACTION READ ONLY")
    cur.execute(
      """
      SELECT cache.manifest_url,
             repository.id::text AS repository_id,
             repository.name AS repository_name,
             manuscript.id::text AS manuscript_db_id,
             cache.id::text AS manifest_cache_id,
             manuscript.shelfmark,
             manuscript.title,
             manuscript.language,
             manuscript.script,
             manuscript.material,
             manuscript.orig_date_display,
             manuscript.raw_metadata->'ingestion'->>'corpus_id' AS manuscript_corpus_id,
             manuscript.raw_metadata->'ingestion'->>'manuscript_spec_id' AS manuscript_spec_id,
             manuscript.raw_metadata->'ingestion'->>'manuscript_split' AS manuscript_split,
             manuscript.raw_metadata->'ingestion'->>'selection_rules_version' AS selection_rules_version,
             cache.fetch_status,
             jsonb_typeof(cache.manifest_json) AS manifest_json_type
      FROM iiif_manifest_cache cache
      JOIN repository ON repository.id = cache.repository_id
      JOIN manuscript ON manuscript.id = cache.manuscript_id
      WHERE cache.manifest_url = ANY(%s)
      ORDER BY cache.manifest_url
      """,
      (manifest_urls,),
    )
    registrations = [dict(item) for item in cur.fetchall()]
    cur.execute(
      """
      SELECT cache.manifest_url,
             repository.id::text AS repository_id,
             repository.name AS repository_name,
             manuscript.id::text AS manuscript_db_id,
             cache.id::text AS manifest_cache_id,
             canvas.id::text AS canvas_db_id,
             canvas.canvas_identifier,
             canvas.canvas_label,
             canvas.sequence_index,
             canvas.width_px AS canvas_width_px,
             canvas.height_px AS canvas_height_px,
             canvas.manuscript_id::text AS canvas_manuscript_id,
             asset.id::text AS image_asset_id,
             asset.source_url,
             asset.iiif_image_service_url,
             asset.local_path,
             asset.checksum_sha256,
             asset.width_px,
             asset.height_px,
             asset.rights_statement,
             asset.license,
             asset.attribution,
             asset.rights_review_status,
             asset.training_allowed,
             asset.raw_metadata->'ingestion'->>'corpus_id' AS asset_corpus_id,
             asset.raw_metadata->'ingestion'->>'manuscript_split' AS asset_split,
             asset.raw_metadata->'ingestion'->>'selection_rules_version' AS asset_selection_rules_version,
             asset.raw_metadata->'ingestion'->>'download_url' AS asset_download_url,
             canvas.raw_metadata->'ingestion'->>'corpus_id' AS canvas_corpus_id,
             canvas.raw_metadata->'ingestion'->>'manuscript_split' AS canvas_split,
             canvas.raw_metadata->'ingestion'->>'selection_rules_version' AS canvas_selection_rules_version,
             asset.raw_metadata->'rights_review' AS rights_review_provenance
      FROM iiif_manifest_cache cache
      JOIN repository ON repository.id = cache.repository_id
      JOIN manuscript ON manuscript.id = cache.manuscript_id
      JOIN canvas ON canvas.iiif_manifest_cache_id = cache.id
      JOIN image_asset asset ON asset.canvas_id = canvas.id
      WHERE cache.manifest_url = ANY(%s)
      ORDER BY cache.manifest_url, canvas.canvas_identifier, asset.source_url, asset.iiif_image_service_url
      """,
      (manifest_urls,),
    )
    rows = [dict(item) for item in cur.fetchall()]
    cur.execute(
      """
      SELECT count(*) FROM (
        SELECT canvas.iiif_manifest_cache_id, canvas.canvas_identifier
        FROM canvas
        JOIN iiif_manifest_cache cache ON cache.id = canvas.iiif_manifest_cache_id
        WHERE cache.manifest_url = ANY(%s)
        GROUP BY canvas.iiif_manifest_cache_id, canvas.canvas_identifier
        HAVING count(*) > 1
      ) duplicate_canvases
      """,
      (manifest_urls,),
    )
    duplicate_canvas_groups = int(cur.fetchone()["count"])
    cur.execute(
      """
      SELECT count(*) FROM (
        SELECT asset.canvas_id, asset.source_url, asset.iiif_image_service_url
        FROM image_asset asset
        JOIN canvas ON canvas.id = asset.canvas_id
        JOIN iiif_manifest_cache cache ON cache.id = canvas.iiif_manifest_cache_id
        WHERE cache.manifest_url = ANY(%s)
        GROUP BY asset.canvas_id, asset.source_url, asset.iiif_image_service_url
        HAVING count(*) > 1
      ) duplicate_assets
      """,
      (manifest_urls,),
    )
    duplicate_asset_groups = int(cur.fetchone()["count"])
  return rows, registrations, duplicate_canvas_groups, duplicate_asset_groups


def validate_database_rows(
  batch: dict[str, Any],
  rows: list[dict[str, Any]],
  registrations: list[dict[str, Any]],
  duplicate_canvas_groups: int = 0,
  duplicate_asset_groups: int = 0,
) -> dict[str, Any]:
  if duplicate_canvas_groups or duplicate_asset_groups:
    raise ValidationError(
      f"Database contains duplicate Batch identities: canvases={duplicate_canvas_groups}, assets={duplicate_asset_groups}"
    )
  expected_manuscripts_by_url = {
    str(manuscript["manifest_url"]): manuscript
    for manuscript in batch.get("manuscripts", [])
  }
  registrations_by_url: dict[str, dict[str, Any]] = {}
  for row in registrations:
    manifest_url = str(row.get("manifest_url"))
    if manifest_url in registrations_by_url:
      raise ValidationError(f"Database contains duplicate manifest-cache registrations: {manifest_url}")
    registrations_by_url[manifest_url] = row
  if set(registrations_by_url) != set(expected_manuscripts_by_url):
    raise ValidationError("Database does not contain exactly the 15 assigned Batch manifest registrations")
  for manifest_url, manuscript in expected_manuscripts_by_url.items():
    row = registrations_by_url[manifest_url]
    expected_metadata = {
      "repository_name": manuscript.get("repository"),
      "shelfmark": manuscript.get("shelfmark"),
      "title": manuscript.get("title"),
      "language": manuscript.get("language"),
      "script": manuscript.get("script"),
      "material": manuscript.get("material"),
      "orig_date_display": manuscript.get("date", {}).get("display"),
      "manuscript_corpus_id": batch.get("corpus_id"),
      "manuscript_spec_id": manuscript.get("id"),
      "manuscript_split": manuscript.get("split"),
      "selection_rules_version": batch.get("selection", {}).get("rules_version"),
      "fetch_status": "completed",
      "manifest_json_type": "object",
    }
    for field, expected_value in expected_metadata.items():
      if row.get(field) != expected_value:
        raise ValidationError(f"Database manuscript/cache {field} differs: {manuscript['id']}")
  expected: dict[tuple[Any, ...], tuple[dict[str, Any], dict[str, Any]]] = {}
  for manuscript, page in selected_pages(batch):
    image = page["image"]
    key = (
      manuscript["manifest_url"],
      page["canvas_identifier"],
      image.get("source_url"),
      image.get("iiif_image_service_url"),
    )
    if key in expected:
      raise ValidationError(f"Duplicate expected database identity: {key}")
    expected[key] = (manuscript, page)
  actual: dict[tuple[Any, ...], dict[str, Any]] = {}
  for row in rows:
    key = (
      row.get("manifest_url"),
      row.get("canvas_identifier"),
      row.get("source_url"),
      row.get("iiif_image_service_url"),
    )
    if key in actual:
      raise ValidationError(f"Database returned duplicate image identity: {key}")
    actual[key] = row
  if set(expected) != set(actual):
    missing = sorted(str(key) for key in set(expected) - set(actual))
    extra = sorted(str(key) for key in set(actual) - set(expected))
    raise ValidationError(f"Database selected-page identities differ; missing={missing}, extra={extra}")

  identities: list[dict[str, Any]] = []
  rights_counts: Counter[str] = Counter()
  manuscript_ids: set[str] = set()
  cache_ids: set[str] = set()
  training_allowed_count = 0
  for key in sorted(expected, key=str):
    manuscript, page = expected[key]
    image = page["image"]
    row = actual[key]
    registration_ids = page.get("registration", {}).get("db_ids", {})
    id_pairs = {
      "repository_id": "repository_id",
      "manuscript_id": "manuscript_db_id",
      "manifest_cache_id": "manifest_cache_id",
      "canvas_id": "canvas_db_id",
      "image_asset_id": "image_asset_id",
    }
    for manifest_field, row_field in id_pairs.items():
      if registration_ids.get(manifest_field) != row.get(row_field):
        raise ValidationError(f"Registration ID differs for {page['canvas_identifier']}: {manifest_field}")
    stable_pairs = {
      "local_path": image.get("local_path"),
      "checksum_sha256": image.get("checksum_sha256"),
      "rights_statement": manuscript.get("rights_statement"),
      "license": manuscript.get("license"),
      "attribution": manuscript.get("attribution"),
      "rights_review_status": image.get("rights_review_status"),
    }
    for row_field, expected_value in stable_pairs.items():
      if row.get(row_field) != expected_value:
        raise ValidationError(f"Database {row_field} differs for {page['canvas_identifier']}")
    if row.get("width_px") != image.get("width_px") or row.get("height_px") != image.get("height_px"):
      raise ValidationError(f"Database source dimensions differ for {page['canvas_identifier']}")
    canvas_pairs = {
      "canvas_label": page.get("canvas_label"),
      "sequence_index": page.get("sequence_index"),
      "canvas_width_px": page.get("width_px"),
      "canvas_height_px": page.get("height_px"),
      "asset_download_url": image.get("download_url"),
      "asset_selection_rules_version": batch.get("selection", {}).get("rules_version"),
      "canvas_selection_rules_version": batch.get("selection", {}).get("rules_version"),
    }
    for row_field, expected_value in canvas_pairs.items():
      if row.get(row_field) != expected_value:
        raise ValidationError(f"Database {row_field} differs for {page['canvas_identifier']}")
    if row.get("repository_name") != manuscript.get("repository"):
      raise ValidationError(f"Database repository differs for {page['canvas_identifier']}")
    if row.get("canvas_manuscript_id") != row.get("manuscript_db_id"):
      raise ValidationError(f"Canvas/manuscript relationship differs for {page['canvas_identifier']}")
    if row.get("asset_corpus_id") != batch.get("corpus_id") or row.get("canvas_corpus_id") != batch.get("corpus_id"):
      raise ValidationError(f"Database corpus provenance differs for {page['canvas_identifier']}")
    if row.get("asset_split") != manuscript.get("split") or row.get("canvas_split") != manuscript.get("split"):
      raise ValidationError(f"Database split provenance differs for {page['canvas_identifier']}")
    if row.get("training_allowed") is not False:
      training_allowed_count += 1
    rights_counts[str(row.get("rights_review_status") or "[missing]")] += 1
    manuscript_ids.add(str(row["manuscript_db_id"]))
    cache_ids.add(str(row["manifest_cache_id"]))
    identities.append({
      "manifest_url": row["manifest_url"],
      "canvas_identifier": row["canvas_identifier"],
      "repository_id": row["repository_id"],
      "manuscript_id": row["manuscript_db_id"],
      "manifest_cache_id": row["manifest_cache_id"],
      "canvas_id": row["canvas_db_id"],
      "image_asset_id": row["image_asset_id"],
      "local_path": row["local_path"],
      "checksum_sha256": row["checksum_sha256"],
      "rights_review_status": row["rights_review_status"],
      "training_allowed": row["training_allowed"],
      "rights_review_provenance": row.get("rights_review_provenance"),
    })
  if training_allowed_count:
    raise ValidationError(f"Database automatically enabled training for {training_allowed_count} Batch assets")
  expected_active_manuscripts = sum(
    any(page.get("selection_status") == "selected" for page in manuscript.get("pages", []))
    for manuscript in batch.get("manuscripts", [])
  )
  if len(manuscript_ids) != expected_active_manuscripts or len(cache_ids) != expected_active_manuscripts:
    raise ValidationError("Database selected-page-bearing manuscript/cache cardinality differs")
  return {
    "assigned_manuscript_count": len(registrations_by_url),
    "assigned_manifest_cache_count": len(registrations_by_url),
    "selected_page_bearing_manuscript_count": len(manuscript_ids),
    "selected_page_bearing_manifest_cache_count": len(cache_ids),
    "canvas_count": len(identities),
    "image_asset_count": len(identities),
    "duplicate_canvas_identity_groups": 0,
    "duplicate_image_identity_groups": 0,
    "training_allowed_count": 0,
    "rights_status_counts": dict(sorted(rights_counts.items())),
    "identities": identities,
  }


def database_snapshot(batch: dict[str, Any]) -> dict[str, Any]:
  manifest_urls = [str(item["manifest_url"]) for item in batch.get("manuscripts", [])]
  rows, registrations, duplicate_canvases, duplicate_assets = _database_rows(manifest_urls)
  return validate_database_rows(batch, rows, registrations, duplicate_canvases, duplicate_assets)


def rights_state_snapshot(manifest_urls: list[str]) -> list[dict[str, Any]]:
  """Capture reviewed authorization fields before/after ordinary acquisition."""
  from psycopg.rows import dict_row

  from src.ingestion.db import connect
  from src.ingestion.iiif_ingest import validate_training_rights_state

  with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
    cur.execute("SET TRANSACTION READ ONLY")
    cur.execute(
      """
      SELECT asset.id::text AS image_asset_id,
             asset.rights_review_status,
             asset.training_allowed,
             asset.raw_metadata->'rights_review' AS rights_review_provenance
      FROM image_asset asset
      JOIN canvas ON canvas.id = asset.canvas_id
      JOIN iiif_manifest_cache cache ON cache.id = canvas.iiif_manifest_cache_id
      WHERE cache.manifest_url = ANY(%s)
      ORDER BY asset.id
      """,
      (manifest_urls,),
    )
    rows = [dict(item) for item in cur.fetchall()]
  for row in rows:
    metadata = {}
    if row.get("rights_review_provenance") is not None:
      metadata["rights_review"] = row["rights_review_provenance"]
    validate_training_rights_state(
      row["rights_review_status"],
      row["training_allowed"],
      metadata,
    )
  return rows


def require_preexisting_rights_preserved(
  before: list[dict[str, Any]],
  after: list[dict[str, Any]],
) -> None:
  after_by_id = {item["image_asset_id"]: item for item in after}
  for earlier in before:
    asset_id = earlier["image_asset_id"]
    later = after_by_id.get(asset_id)
    if later is None:
      raise ValidationError(f"Acquisition removed a preexisting Batch image asset: {asset_id}")
    if canonical_sha256(earlier) != canonical_sha256(later):
      raise ValidationError(f"Acquisition changed preexisting human rights-review state: {asset_id}")


def compare_database_snapshots(earlier: dict[str, Any], later: dict[str, Any]) -> None:
  if canonical_sha256(earlier) != canonical_sha256(later):
    raise ValidationError("Registered rerun changed Batch database identities or preserved fields")


def phase_snapshot(
  *,
  root: Path,
  spec_path: Path,
  manifest_path: Path,
  statistics_path: Path,
  baseline_path: Path,
  review_path: Path,
  include_database: bool,
) -> dict[str, Any]:
  spec = load_yaml(spec_path)
  batch = load_yaml(manifest_path)
  statistics = load_yaml(statistics_path)
  baseline = load_yaml(baseline_path)
  review = load_yaml(review_path)
  if batch.get("corpus_id") != spec.get("corpus_id"):
    raise ValidationError("Batch manifest corpus differs from specification")
  structure = validate_structure(batch, baseline, review, spec, statistics)
  assets, metrics = selected_asset_snapshot(batch, root)
  if metrics["selected_pages"] != structure["selected_page_count"]:
    raise ValidationError("Selected asset count differs from structural selected-page count")
  if metrics["failures"]:
    raise ValidationError(f"Batch acquisition contains {metrics['failures']} failed/incomplete selected assets")
  if metrics["training_allowed_count"]:
    raise ValidationError("Batch acquisition automatically enabled training")
  expected_acquisition_statistics = {
    "selected_pages": metrics["selected_pages"],
    "acquired_pages": metrics["selected_pages"],
    "downloaded_pages": metrics["downloaded_pages"],
    "reused_pages": metrics["reused_pages"],
    "failures": metrics["failures"],
    "download_status_counts": metrics["download_status_counts"],
    "total_bytes": metrics["total_bytes"],
  }
  if statistics.get("acquisition") != expected_acquisition_statistics:
    raise ValidationError("Batch acquisition statistics differ from checksum-verified local assets")
  if statistics.get("rights_review_status") != metrics["rights_status_counts"]:
    raise ValidationError("Batch rights-status statistics differ from selected assets")
  if statistics.get("training_allowed_true_count") != metrics["training_allowed_count"]:
    raise ValidationError("Batch training-allowed statistics differ from selected assets")
  source_files = source_tree_snapshot(spec, batch, root)
  snapshot = {
    "manifest_status": batch.get("status"),
    "manifest_sha256": sha256_file(manifest_path),
    "statistics_sha256": sha256_file(statistics_path),
    "statistics_canonical_sha256": canonical_sha256(statistics),
    "structure": structure,
    "metrics": metrics,
    "selected_assets": assets,
    "source_files": source_files,
    "source_tree_sha256": canonical_sha256(source_files),
    "git_safety": git_safety(spec, batch, source_files, root),
  }
  if include_database:
    snapshot["database"] = database_snapshot(batch)
  return snapshot


def write_json(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_state(path: Path) -> dict[str, Any]:
  if not path.is_file():
    raise ValidationError(f"Acquisition state is missing: {path}")
  payload = json.loads(path.read_text(encoding="utf-8"))
  if payload.get("state_version") != STATE_VERSION:
    raise ValidationError(f"Unsupported acquisition state version: {payload.get('state_version')}")
  return payload


def require_reused(snapshot: dict[str, Any], label: str) -> None:
  metrics = snapshot["metrics"]
  if metrics["reused_pages"] != metrics["selected_pages"] or metrics["downloaded_pages"] != 0:
    raise ValidationError(
      f"{label} did not reuse every selected asset: "
      f"downloaded={metrics['downloaded_pages']}, reused={metrics['reused_pages']}, selected={metrics['selected_pages']}"
    )


def run_phase(args: argparse.Namespace) -> dict[str, Any] | None:
  root = Path(args.root).resolve()
  spec_path = resolve_path(root, args.spec)
  manifest_path = resolve_path(root, args.manifest)
  statistics_path = resolve_path(root, args.statistics)
  baseline_path = resolve_path(root, args.baseline)
  review_path = resolve_path(root, args.review)
  state_path = Path(args.state)

  if args.phase == "capture-preflight":
    spec = load_yaml(spec_path)
    batch = load_yaml(manifest_path)
    statistics = load_yaml(statistics_path)
    baseline = load_yaml(baseline_path)
    review = load_yaml(review_path)
    if batch.get("status") != "dry_run" or batch.get("selection", {}).get("status") != "ready":
      raise ValidationError("Acquisition preflight requires the passed decision-aware dry-run manifest")
    structure = validate_structure(batch, baseline, review, spec, statistics)
    manifest_urls = [str(item["manifest_url"]) for item in batch["manuscripts"]]
    state = {
      "state_version": STATE_VERSION,
      "preflight": {
        "structure": structure,
        "manifest_sha256": sha256_file(manifest_path),
        "statistics_sha256": sha256_file(statistics_path),
        "preexisting_rights_state": rights_state_snapshot(manifest_urls),
      },
    }
    write_json(state_path, state)
    return None

  if args.phase == "capture-initial":
    state = load_state(state_path)
    snapshot = phase_snapshot(
      root=root,
      spec_path=spec_path,
      manifest_path=manifest_path,
      statistics_path=statistics_path,
      baseline_path=baseline_path,
      review_path=review_path,
      include_database=False,
    )
    if snapshot["manifest_status"] != "downloaded_not_registered":
      raise ValidationError(f"Initial acquisition status is {snapshot['manifest_status']!r}, expected downloaded_not_registered")
    if state.get("preflight", {}).get("structure") != snapshot["structure"]:
      raise ValidationError("Selection/split/decision structure changed between preflight and acquisition")
    state["initial_acquisition"] = snapshot
    write_json(state_path, state)
    return None

  state = load_state(state_path)
  snapshot = phase_snapshot(
    root=root,
    spec_path=spec_path,
    manifest_path=manifest_path,
    statistics_path=statistics_path,
    baseline_path=baseline_path,
    review_path=review_path,
    include_database=True,
  )
  if snapshot["manifest_status"] != "downloaded_and_registered":
    raise ValidationError(f"Registered acquisition status is {snapshot['manifest_status']!r}")
  current_rights_state = rights_state_snapshot(
    [str(item["manifest_url"]) for item in load_yaml(manifest_path)["manuscripts"]]
  )
  require_preexisting_rights_preserved(
    state.get("preflight", {}).get("preexisting_rights_state", []),
    current_rights_state,
  )
  compare_file_snapshots(state["initial_acquisition"]["source_files"], snapshot["source_files"], args.phase)
  require_reused(snapshot, args.phase)

  if args.phase == "capture-registration":
    state["registration_run"] = snapshot
    write_json(state_path, state)
    return None

  if "registration_run" not in state:
    raise ValidationError("Registration snapshot is missing from acquisition state")
  previous = state["registration_run"]
  compare_file_snapshots(previous["source_files"], snapshot["source_files"], "unchanged registered rerun")
  compare_database_snapshots(previous["database"], snapshot["database"])
  if previous["manifest_sha256"] != snapshot["manifest_sha256"]:
    raise ValidationError("Unchanged registered rerun did not reproduce a byte-identical manifest")
  if previous["statistics_sha256"] != snapshot["statistics_sha256"]:
    raise ValidationError("Unchanged registered rerun did not reproduce byte-identical statistics")
  if previous["structure"] != snapshot["structure"]:
    raise ValidationError("Unchanged registered rerun changed selection/split/decision structure")

  output = {
    "validation_version": VALIDATION_VERSION,
    "status": "passed_acquired_registered_and_idempotent",
    "batch_corpus_id": snapshot["structure"] and load_yaml(manifest_path)["corpus_id"],
    "manifest_path": relative_path(root, manifest_path),
    "manifest_sha256": snapshot["manifest_sha256"],
    "statistics_path": relative_path(root, statistics_path),
    "statistics_sha256": snapshot["statistics_sha256"],
    "selection_and_provenance": snapshot["structure"],
    "acquisition_runs": {
      "initial_acquisition": state["initial_acquisition"]["metrics"],
      "registration_run": previous["metrics"],
      "unchanged_registered_rerun": snapshot["metrics"],
    },
    "file_integrity": {
      "source_file_count": len(snapshot["source_files"]),
      "selected_asset_count": len(snapshot["selected_assets"]),
      "source_tree_sha256": snapshot["source_tree_sha256"],
      "checksums_dimensions_sizes_match": True,
      "paths_hashes_sizes_dimensions_and_mtimes_unchanged_on_rerun": True,
    },
    "database_integrity": {
      key: value for key, value in snapshot["database"].items() if key != "identities"
    },
    "database_identity_sha256": canonical_sha256(snapshot["database"]["identities"]),
    "rights": {
      "manifest_rights_status_counts": snapshot["metrics"]["rights_status_counts"],
      "database_rights_status_counts": snapshot["database"]["rights_status_counts"],
      "training_allowed_count": 0,
      "automatic_rights_approval_introduced": False,
      "preexisting_reviewed_rights_records_preserved": True,
      "preexisting_batch_image_asset_count": len(state.get("preflight", {}).get("preexisting_rights_state", [])),
    },
    "git_safety": snapshot["git_safety"],
    "next_milestone": (
      "Run the existing eManuSkript segmentation pipeline over the acquired Batch 01 pages and "
      "validate source-sized masks and provenance at expanded scale."
    ),
  }
  output["validation_sha256"] = canonical_sha256(output)
  output_path = resolve_path(root, args.output)
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
  return output


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Capture and validate Batch 01 acquisition/registration reruns.")
  parser.add_argument(
    "--phase",
    required=True,
    choices=("capture-preflight", "capture-initial", "capture-registration", "validate-rerun"),
  )
  parser.add_argument("--root", default=str(ROOT))
  parser.add_argument("--spec", default=str(DEFAULT_SPEC))
  parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
  parser.add_argument("--statistics", default=str(DEFAULT_STATISTICS))
  parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
  parser.add_argument("--review", default=str(DEFAULT_REVIEW))
  parser.add_argument("--state", default=str(DEFAULT_STATE))
  parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    output = run_phase(args)
  except (OSError, ValidationError, KeyError, TypeError) as exc:
    print(f"FAIL: {exc}", file=sys.stderr)
    return 1
  if args.phase == "capture-preflight":
    print(f"PASS: deterministic gate and pre-acquisition rights state captured in {args.state}")
  elif args.phase == "capture-initial":
    print(f"PASS: captured initial Batch acquisition snapshot in {args.state}")
  elif args.phase == "capture-registration":
    print(f"PASS: captured registered Batch snapshot in {args.state}")
  else:
    print(
      f"PASS: {output['selection_and_provenance']['selected_page_count']} Batch pages are "
      "registered, checksum-valid, rights-gated, and idempotent"
    )
    print(f"Validation: {args.output}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
