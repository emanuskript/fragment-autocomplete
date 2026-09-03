"""Tests for deterministic provenance-preserving source-corpus construction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from PIL import Image

from src.ingestion.iiif_manifest import NormalizedCanvas, NormalizedImageAsset
from src.ingestion.iiif_normalizer import normalize_manifest
from src.ingestion.training_corpus import (
  EXPANSION_SELECTION_RULES_VERSION,
  assign_manuscript_splits,
  build_corpus,
  download_resumable,
  ensure_unique_pages,
  manual_page_decisions_for_corpus,
  manuscript_suitability_decisions_for_corpus,
  replacement_page_reviews_for_corpus,
  select_canvas_pages,
  validate_specification,
  verify_checksum,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture_payload(name: str = "iiif_v2_minimal_manifest.json") -> dict:
  return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def canvas(index: int, label: str | None = None) -> NormalizedCanvas:
  return NormalizedCanvas(
    canvas_identifier=f"https://fixtures.example.org/canvas/{index}",
    canvas_label=label or f"fol. {index}r",
    width_px=1200,
    height_px=1800,
    sequence_index=index,
    raw_metadata={"fixture_index": index},
    images=[NormalizedImageAsset(
      source_url=f"https://fixtures.example.org/image/{index}.jpg",
      iiif_image_service_url=f"https://fixtures.example.org/iiif/{index}",
      media_type="image/jpeg",
      width_px=1200,
      height_px=1800,
      raw_metadata={"fixture_index": index},
    )],
  )


def basic_spec() -> dict:
  return {
    "corpus_id": "fixture_corpus_v0_1",
    "selection_seed": 1234,
    "split_seed": "split-seed",
    "max_pages_per_manuscript": 1,
    "split_ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
    "rights_review_status": "pending_review",
    "training_allowed": False,
    "download_root": "data/raw/fixture_corpus_v0_1",
    "manuscripts": [{"id": "fixture-ms", "manifest_url": "https://fixtures.example.org/manifest.json"}],
  }


def explicit_page_decision(
  manuscript_id: str,
  canvas_identifier: str,
  decision: str = "reject",
  *,
  corpus_id: str | None = None,
  sequence_index: int = 1,
  split: str = "train",
) -> dict:
  payload = {
    "manuscript_id": manuscript_id,
    "canvas_identifier": canvas_identifier,
    "sequence_index": sequence_index,
    "split": split,
    "decision": decision,
    "decision_reason": f"Fixture {decision} decision",
    "reason_code": f"fixture_{decision}",
    "reviewer": "Fixture reviewer",
    "decision_scope": "training_corpus_selection",
    "selection_application": "batch_selection",
    "decision_version": "fixture_page_decisions_v1",
    "recorded_at": "2026-09-02T00:00:00+00:00",
    "decision_provenance": "Fixture explicit decision",
  }
  if corpus_id is not None:
    payload["corpus_id"] = corpus_id
  return payload


def unsuitable_manuscript_decision(manuscript_id: str, *, corpus_id: str | None = None) -> dict:
  payload = {
    "manuscript_id": manuscript_id,
    "decision": "unsuitable_for_training_corpus",
    "decision_reason": "Fixture manuscript is unsuitable after candidate review",
    "reason_code": "fixture_insufficient_suitable_pages",
    "reviewer": "Fixture reviewer",
    "decision_scope": "manuscript_training_corpus_suitability",
    "selection_application": "batch_selection",
    "decision_version": "fixture_manuscript_decisions_v1",
    "recorded_at": "2026-09-02",
    "decision_provenance": "Fixture manuscript decision",
  }
  if corpus_id is not None:
    payload["corpus_id"] = corpus_id
  return payload


def test_deterministic_page_selection_records_all_states():
  canvases = [canvas(index) for index in range(1, 8)]
  canvases.extend([canvas(8, "Front cover"), canvas(9, "Colour target")])
  first = select_canvas_pages("fixture-ms", canvases, seed=99, max_pages=3)
  second = select_canvas_pages("fixture-ms", canvases, seed=99, max_pages=3)

  assert first == second
  assert sum(item["selection_status"] == "selected" for item in first) == 3
  assert sum(item["selection_status"] == "candidate" for item in first) == 4
  assert sum(item["selection_status"] == "rejected" for item in first) == 2
  assert all(item["selection_reasons"] for item in first)


def test_manual_reject_is_consumed_retained_and_replaced_deterministically():
  canvases = [canvas(index) for index in range(1, 8)]
  initial = select_canvas_pages("fixture-ms", canvases, seed=99, max_pages=3)
  rejected_initial = next(item for item in initial if item["selection_status"] == "selected")
  decision = explicit_page_decision(
    "fixture-ms",
    rejected_initial["canvas_identifier"],
    sequence_index=rejected_initial["sequence_index"],
  )

  first = select_canvas_pages(
    "fixture-ms",
    canvases,
    seed=99,
    max_pages=3,
    manual_page_decisions=[decision],
  )
  second = select_canvas_pages(
    "fixture-ms",
    canvases,
    seed=99,
    max_pages=3,
    manual_page_decisions=[decision],
  )

  assert first == second
  rejected = next(item for item in first if item["canvas_identifier"] == decision["canvas_identifier"])
  assert rejected["selection_status"] == "rejected"
  assert rejected["automatic_selection_eligible"] is False
  assert rejected["manual_decision"]["decision"] == "reject"
  assert "explicit_manual_review_reject" in {reason["code"] for reason in rejected["selection_reasons"]}
  selected = [item for item in first if item["selection_status"] == "selected"]
  assert len(selected) == 3
  replacements = [
    item for item in selected
    if "deterministic_same_manuscript_replacement" in {reason["code"] for reason in item["selection_reasons"]}
  ]
  assert len(replacements) == 1
  replacement_reason = next(
    reason for reason in replacements[0]["selection_reasons"]
    if reason["code"] == "deterministic_same_manuscript_replacement"
  )
  assert decision["canvas_identifier"] in replacement_reason["manual_rejected_canvas_identifiers"]
  assert replacement_reason["seeded_rank_before_manual_decisions"] > 3


def test_manual_reject_sequence_must_match_canvas():
  target = canvas(1)
  decision = explicit_page_decision("fixture-ms", target.canvas_identifier, sequence_index=2)
  with pytest.raises(ValueError, match="sequence differs"):
    select_canvas_pages("fixture-ms", [target], seed=1, max_pages=1, manual_page_decisions=[decision])


def test_manuscript_unsuitable_state_records_all_pages_without_selection():
  canvases = [canvas(index) for index in range(1, 5)]
  result = select_canvas_pages(
    "fixture-ms",
    canvases,
    seed=7,
    max_pages=3,
    manuscript_suitability_decision=unsuitable_manuscript_decision("fixture-ms"),
  )

  assert not any(item["selection_status"] == "selected" for item in result)
  assert all(item["selection_review_status"] == "manuscript_excluded" for item in result)
  assert all(item["automatic_selection_eligible"] is False for item in result)


@pytest.mark.parametrize(
  "label,reason_code",
  [
    ("Digital Colorchecker", "color_target"),
    ("Color profile", "color_target"),
    ("Ruler", "digitization_target"),
    ("Ruler on page", "digitization_target"),
    ("QP card on page", "digitization_target"),
    ("Fore edge", "object_view"),
    ("Head", "object_view"),
    ("Tail", "object_view"),
    ("Open view", "object_view"),
    ("Open view a", "object_view"),
  ],
)
def test_expansion_rules_reject_explicit_auxiliary_views(label: str, reason_code: str):
  result = select_canvas_pages(
    "fixture-ms",
    [canvas(1, label), canvas(2, "fol. 1r")],
    seed=99,
    max_pages=1,
    rules_version=EXPANSION_SELECTION_RULES_VERSION,
  )
  rejected = next(item for item in result if item["canvas_label"] == label)
  assert rejected["selection_status"] == "rejected"
  assert reason_code in {reason["code"] for reason in rejected["selection_reasons"]}
  assert rejected["automatic_selection_eligible"] is False


def test_uncertain_accompanying_material_stays_candidate_but_is_not_auto_selected():
  result = select_canvas_pages(
    "fixture-ms",
    [canvas(1, "Accompanying materials 1"), canvas(2, "fol. 1r")],
    seed=99,
    max_pages=1,
    rules_version=EXPANSION_SELECTION_RULES_VERSION,
  )
  uncertain = next(item for item in result if item["canvas_label"] == "Accompanying materials 1")
  assert uncertain["selection_status"] == "candidate"
  assert uncertain["selection_review_status"] == "needs_manual_review"
  assert uncertain["automatic_selection_eligible"] is False
  assert result[1]["selection_status"] == "selected"


def test_uncertain_accompanying_material_recto_verso_stays_candidate():
  result = select_canvas_pages(
    "fixture-ms",
    [canvas(1, "Accompanying materials 3v"), canvas(2, "fol. 1r")],
    seed=99,
    max_pages=1,
    rules_version=EXPANSION_SELECTION_RULES_VERSION,
  )
  assert result[0]["selection_status"] == "candidate"
  assert result[0]["selection_review_status"] == "needs_manual_review"


def test_validation_rules_version_retains_historical_selection_semantics():
  legacy = select_canvas_pages("fixture-ms", [canvas(1, "Open view")], seed=99, max_pages=1)
  assert legacy[0]["selection_status"] == "selected"


def test_manifest_parsing_preserves_raw_metadata_and_image_provenance():
  raw = fixture_payload("iiif_v3_minimal_manifest.json")
  manifest = normalize_manifest(raw, "fixture:v3")

  assert manifest.raw_metadata == raw
  assert manifest.metadata[0]["raw"] == raw["metadata"][0]
  assert manifest.canvases[0].raw_metadata == raw["items"][0]
  assert manifest.canvases[0].images[0].raw_metadata["id"].endswith("default.jpg")


def test_duplicate_manuscript_prevention():
  spec = basic_spec()
  spec["manuscripts"].append({"id": "second-id", "manifest_url": spec["manuscripts"][0]["manifest_url"]})
  with pytest.raises(ValueError, match="Duplicate manuscript manifest"):
    validate_specification(spec)


def test_duplicate_page_prevention_within_and_across_manuscripts():
  duplicate = canvas(1)
  with pytest.raises(ValueError, match="Duplicate page/canvas in manifest"):
    select_canvas_pages("fixture-ms", [duplicate, duplicate], seed=1, max_pages=1)

  records = [
    {"id": "one", "pages": [{"canvas_identifier": duplicate.canvas_identifier}]},
    {"id": "two", "pages": [{"canvas_identifier": duplicate.canvas_identifier}]},
  ]
  with pytest.raises(ValueError, match="Duplicate page/canvas across manuscripts"):
    ensure_unique_pages(records)


def test_manuscript_level_split_is_deterministic_and_isolated():
  manuscript_ids = [f"ms-{index:03d}" for index in range(100)]
  first = assign_manuscript_splits(manuscript_ids, "fixed-seed")
  second = assign_manuscript_splits(reversed(manuscript_ids), "fixed-seed")

  assert first == second
  assert {name: list(first.values()).count(name) for name in ("train", "validation", "test")} == {
    "train": 70,
    "validation": 15,
    "test": 15,
  }
  page_splits = {(manuscript_id, page): first[manuscript_id] for manuscript_id in manuscript_ids for page in range(5)}
  assert all(len({split for (owner, _), split in page_splits.items() if owner == manuscript_id}) == 1 for manuscript_id in manuscript_ids)


def test_resume_behavior_skips_verified_existing_asset(tmp_path: Path):
  destination = tmp_path / "page.jpg"
  Image.new("RGB", (12, 18), "white").save(destination)
  checksum = __import__("hashlib").sha256(destination.read_bytes()).hexdigest()

  class NoNetwork:
    def get(self, *args, **kwargs):  # pragma: no cover - called only on regression
      raise AssertionError("verified existing asset must not trigger a request")

  result = download_resumable(
    "https://fixtures.example.org/page.jpg",
    destination,
    expected_sha256=checksum,
    session=NoNetwork(),
  )
  assert result["status"] == "verified_existing"
  assert result["sha256"] == checksum


def test_checksum_verification_rejects_mismatch(tmp_path: Path):
  path = tmp_path / "asset.bin"
  path.write_bytes(b"source bytes")
  with pytest.raises(ValueError, match="Checksum mismatch"):
    verify_checksum(path, "0" * 64)


def test_metadata_provenance_and_rights_status_are_preserved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
  raw = fixture_payload()
  raw["metadata"].extend([
    {"label": "Collection Name", "value": "Fixture Collection"},
    {"label": "Location", "value": "Fixture City"},
    {"label": "Title (English)", "value": "Fixture Source Title"},
    {"label": "Date of Origin (English)", "value": "13th century"},
    {"label": "Material", "value": "Parchment"},
  ])

  def fake_fetch(url: str, timeout_seconds: int = 30):
    return raw, url, {"etag": "fixture-etag", "last_modified": "fixture-date"}

  def fake_download(url: str, destination: Path, **kwargs):
    return {
      "status": "downloaded",
      "sha256": "a" * 64,
      "size_bytes": 100,
      "response_headers": {"etag": "fixture-image-etag"},
      "width_px": 1000,
      "height_px": 1500,
      "media_type": "image/jpeg",
      "color_mode": "RGB",
    }

  monkeypatch.setattr("src.ingestion.training_corpus.fetch_manifest_url", fake_fetch)
  monkeypatch.setattr("src.ingestion.training_corpus.download_resumable", fake_download)
  spec = basic_spec()
  spec_path = tmp_path / "spec.yaml"
  spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
  payload = build_corpus(
    spec,
    root=tmp_path,
    specification_path=spec_path,
    output_manifest_path=tmp_path / "manifest.yaml",
    statistics_yaml_path=tmp_path / "statistics.yaml",
    statistics_report_path=tmp_path / "statistics.md",
  )

  manuscript = payload["manuscripts"][0]
  page = next(item for item in manuscript["pages"] if item["selection_status"] == "selected")
  assert manuscript["repository"] == "Fixture City, Fixture Collection"
  assert manuscript["shelfmark"] == "Fixture MS V2"
  assert manuscript["title"] == "Fixture Source Title"
  assert manuscript["date"]["not_before"] == 1201
  assert manuscript["material"] == "Parchment"
  assert manuscript["raw_source_metadata"]["raw_manifest_artifact"]["sha256"]
  assert page["image"]["rights_review_status"] == "pending_review"
  assert page["image"]["training_allowed"] is False
  assert page["image"]["license"] == raw["license"]
  assert payload["statistics"]["training_allowed_true_count"] == 0


def test_build_reports_insufficient_pages_and_preserves_reject_audit(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  raw = fixture_payload()

  def fake_fetch(url: str, timeout_seconds: int = 30):
    return raw, url, {"etag": "fixture-etag", "last_modified": "fixture-date"}

  monkeypatch.setattr("src.ingestion.training_corpus.fetch_manifest_url", fake_fetch)
  spec = basic_spec()
  spec_path = tmp_path / "spec.yaml"
  spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
  decision = explicit_page_decision(
    "fixture-ms",
    "https://fixtures.example.org/iiif/v2/canvas/p1",
    corpus_id=spec["corpus_id"],
    sequence_index=0,
  )
  payload = build_corpus(
    spec,
    root=tmp_path,
    specification_path=spec_path,
    output_manifest_path=tmp_path / "manifest.yaml",
    statistics_yaml_path=tmp_path / "statistics.yaml",
    statistics_report_path=tmp_path / "statistics.md",
    dry_run=True,
    manual_page_decisions=[decision],
  )

  manuscript = payload["manuscripts"][0]
  page = manuscript["pages"][0]
  assert page["selection_status"] == "rejected"
  assert page["manual_decision"]["reason_code"] == "fixture_reject"
  assert manuscript["page_selection"] == {
    "status": "insufficient_acceptable_pages",
    "requested_page_count": 1,
    "selected_page_count": 0,
    "shortfall_count": 1,
  }
  assert payload["selection"]["status"] == "blocked_insufficient_acceptable_pages"
  assert payload["statistics"]["selected_page_count"] == 0
  assert payload["statistics"]["manuscript_selection_shortfalls"][0]["manuscript_id"] == "fixture-ms"


def test_decision_aware_dry_build_is_byte_deterministic(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  raw = fixture_payload()

  def fake_fetch(url: str, timeout_seconds: int = 30):
    return raw, url, {"etag": "fixture-etag", "last_modified": "fixture-date"}

  monkeypatch.setattr("src.ingestion.training_corpus.fetch_manifest_url", fake_fetch)
  spec = basic_spec()
  spec_path = tmp_path / "spec.yaml"
  spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
  paths = {
    "output_manifest_path": tmp_path / "manifest.yaml",
    "statistics_yaml_path": tmp_path / "statistics.yaml",
    "statistics_report_path": tmp_path / "statistics.md",
  }

  keep = explicit_page_decision(
    "fixture-ms",
    "https://fixtures.example.org/iiif/v2/canvas/p1",
    decision="keep",
    corpus_id=spec["corpus_id"],
    sequence_index=0,
  )
  first = build_corpus(
    spec,
    root=tmp_path,
    specification_path=spec_path,
    dry_run=True,
    manual_page_decisions=[keep],
    **paths,
  )
  first_manifest = paths["output_manifest_path"].read_bytes()
  first_statistics = paths["statistics_yaml_path"].read_bytes()
  second = build_corpus(
    spec,
    root=tmp_path,
    specification_path=spec_path,
    dry_run=True,
    manual_page_decisions=[keep],
    **paths,
  )

  assert first == second
  assert paths["output_manifest_path"].read_bytes() == first_manifest
  assert paths["statistics_yaml_path"].read_bytes() == first_statistics


def test_replacement_reviews_are_annotation_only_and_manifest_traceable(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  raw = fixture_payload()

  def fake_fetch(url: str, timeout_seconds: int = 30):
    return raw, url, {"etag": "fixture-etag", "last_modified": "fixture-date"}

  monkeypatch.setattr("src.ingestion.training_corpus.fetch_manifest_url", fake_fetch)
  spec = basic_spec()
  spec_path = tmp_path / "spec.yaml"
  spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
  replacement_review = explicit_page_decision(
    "fixture-ms",
    "https://fixtures.example.org/iiif/v2/canvas/p1",
    decision="keep",
    corpus_id=spec["corpus_id"],
    sequence_index=0,
  )
  replacement_review.update({
    "decision_scope": "replacement_suitability_review",
    "selection_application": "review_evidence_only",
  })
  artifact = {"path": "data/metadata/review.yaml", "sha256": "a" * 64, "review_version": "fixture_review_v1"}
  payload = build_corpus(
    spec,
    root=tmp_path,
    specification_path=spec_path,
    output_manifest_path=tmp_path / "manifest.yaml",
    statistics_yaml_path=tmp_path / "statistics.yaml",
    statistics_report_path=tmp_path / "statistics.md",
    dry_run=True,
    replacement_page_reviews=[replacement_review],
    manual_review_artifact=artifact,
  )

  page = payload["manuscripts"][0]["pages"][0]
  assert page["selection_status"] == "selected"
  assert page["selection_review_status"] == "resolved_keep"
  assert page["replacement_review"] == replacement_review
  assert payload["manual_review_artifact"] == artifact
  assert payload["selection"]["replacement_review_count"] == 1


def test_batch_review_artifact_exposes_all_annotation_only_replacement_reviews() -> None:
  root = Path(__file__).resolve().parents[2]
  review = yaml.safe_load((root / "data/metadata/training_corpus_expansion_readiness_review.yaml").read_text())
  replacements = replacement_page_reviews_for_corpus(
    review,
    "ecodices_training_source_expansion_batch_01_v0_1",
  )

  assert len(replacements) == 8
  assert all(item["selection_application"] == "review_evidence_only" for item in replacements)
  assert all(item["decision_scope"] == "replacement_suitability_review" for item in replacements)


def test_frozen_validation_reject_is_audit_only_and_membership_is_unchanged() -> None:
  root = Path(__file__).resolve().parents[2]
  review = yaml.safe_load((root / "data/metadata/training_corpus_expansion_readiness_review.yaml").read_text())
  baseline = yaml.safe_load((root / "data/metadata/training_corpus_validation_manifest.yaml").read_text())
  decisions = manual_page_decisions_for_corpus(review, baseline["corpus_id"])

  assert len(decisions) == 1
  assert decisions[0]["decision"] == "reject"
  assert decisions[0]["selection_application"] == "audit_only_frozen_corpus"
  historical_page = next(
    page
    for manuscript in baseline["manuscripts"]
    for page in manuscript["pages"]
    if page["canvas_identifier"] == decisions[0]["canvas_identifier"]
  )
  assert historical_page["selection_status"] == "selected"
  with pytest.raises(ValueError, match="Only batch_selection decisions"):
    select_canvas_pages(
      decisions[0]["manuscript_id"],
      [canvas(decisions[0]["sequence_index"])],
      seed=1,
      max_pages=1,
      manual_page_decisions=decisions,
    )


def test_spec_rejects_automatic_training_permission():
  spec = basic_spec()
  spec["training_allowed"] = True
  with pytest.raises(ValueError, match="must not automatically"):
    validate_specification(spec)


def test_spec_rejects_unknown_selection_rules_version():
  spec = basic_spec()
  spec["selection_rules_version"] = "unknown"
  with pytest.raises(ValueError, match="Unsupported selection_rules_version"):
    validate_specification(spec)
