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
