"""Focused regressions for acquisition-safe image-asset rights handling."""

from __future__ import annotations

from typing import Any

import pytest
from psycopg.types.json import Jsonb

from src.ingestion import iiif_ingest
from src.ingestion.iiif_ingest import (
  IngestStats,
  merge_image_asset_raw_metadata,
  upsert_image_asset,
  validate_training_rights_state,
)
from src.ingestion.iiif_manifest import NormalizedImageAsset, NormalizedManifest


def review_provenance(status: str, training_allowed: bool) -> dict[str, Any]:
  return {
    "review_version": "image_asset_rights_review_v0_1",
    "reviewer": "Fixture Reviewer",
    "reviewed_at": "2026-09-02T10:30:00+00:00",
    "decision_reason": "Fixture decision for regression testing.",
    "rights_review_status": status,
    "training_allowed": training_allowed,
  }


@pytest.mark.parametrize(
  "status,training_allowed,with_provenance",
  [
    ("pending_review", False, False),
    ("needs_review", False, False),
    ("not_approved", False, True),
    ("approved_for_training", True, True),
  ],
)
def test_training_rights_state_accepts_consistent_statuses(
  status: str,
  training_allowed: bool,
  with_provenance: bool,
) -> None:
  metadata = {"rights_review": review_provenance(status, training_allowed)} if with_provenance else {}
  validate_training_rights_state(status, training_allowed, metadata)


@pytest.mark.parametrize(
  "status,training_allowed",
  [
    ("pending_review", True),
    ("needs_review", True),
    ("not_approved", True),
    ("approved_for_training", False),
  ],
)
def test_training_rights_state_rejects_inconsistent_flags(status: str, training_allowed: bool) -> None:
  metadata = {"rights_review": review_provenance(status, training_allowed)}
  with pytest.raises(ValueError, match="training_allowed must be true only"):
    validate_training_rights_state(status, training_allowed, metadata)


def test_training_rights_state_requires_versioned_human_decision_provenance() -> None:
  with pytest.raises(ValueError, match="requires versioned rights_review provenance"):
    validate_training_rights_state("approved_for_training", True, {})

  incomplete = review_provenance("not_approved", False)
  incomplete.pop("review_version")
  with pytest.raises(ValueError, match="review_version"):
    validate_training_rights_state("not_approved", False, {"rights_review": incomplete})


def test_training_rights_state_rejects_provenance_that_differs_from_columns() -> None:
  provenance = review_provenance("approved_for_training", True)
  provenance["rights_review_status"] = "not_approved"
  with pytest.raises(ValueError, match="status differs"):
    validate_training_rights_state("approved_for_training", True, {"rights_review": provenance})


def test_training_rights_state_rejects_non_mapping_raw_metadata() -> None:
  with pytest.raises(ValueError, match="raw_metadata must be a mapping"):
    validate_training_rights_state("pending_review", False, [])  # type: ignore[arg-type]


def test_raw_metadata_merge_refreshes_harvested_values_and_preserves_rights_review() -> None:
  provenance = review_provenance("approved_for_training", True)
  existing = {
    "source": "old_source",
    "unrelated_evidence": {"keep": True},
    "rights_review": provenance,
  }
  harvested = {
    "source": "iiif_ingestion",
    "raw_image": {"id": "https://fixtures.example.org/image.jpg"},
    "ingestion": {"corpus_id": "fixture"},
  }

  merged = merge_image_asset_raw_metadata(existing, harvested)

  assert merged["source"] == "iiif_ingestion"
  assert merged["unrelated_evidence"] == {"keep": True}
  assert merged["rights_review"] == provenance
  assert merged["raw_image"] == harvested["raw_image"]


def test_raw_metadata_merge_rejects_ingestion_rights_review_replacement() -> None:
  with pytest.raises(ValueError, match="must not introduce or replace"):
    merge_image_asset_raw_metadata({}, {"rights_review": review_provenance("not_approved", False)})


def normalized_records(*, requested_status: str = "pending_review") -> tuple[NormalizedImageAsset, NormalizedManifest]:
  image = NormalizedImageAsset(
    source_url="https://fixtures.example.org/image.jpg",
    iiif_image_service_url="https://fixtures.example.org/iiif/image",
    media_type="image/jpeg",
    width_px=1000,
    height_px=1500,
    local_path="data/raw/fixture/page.jpg",
    checksum_sha256="a" * 64,
    rights_review_status=requested_status,
    raw_metadata={"id": "https://fixtures.example.org/image.jpg", "training_corpus": {"corpus_id": "fixture"}},
  )
  manifest = NormalizedManifest(
    source_identifier="fixture:manifest",
    manifest_id="https://fixtures.example.org/manifest.json",
    label="Fixture Manuscript",
    metadata=[],
    rights_statement="https://creativecommons.org/licenses/by/4.0/",
    license="https://creativecommons.org/licenses/by/4.0/",
    attribution="Fixture Repository",
    raw_metadata={},
    canvases=[],
  )
  return image, manifest


def test_existing_human_training_decision_survives_ordinary_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
  provenance = review_provenance("approved_for_training", True)
  existing = {
    "id": "asset-1",
    "rights_review_status": "approved_for_training",
    "training_allowed": True,
    "raw_metadata": {"source": "previous", "rights_review": provenance},
  }
  captured: dict[str, Any] = {}

  monkeypatch.setattr(iiif_ingest, "_fetch_one", lambda *args, **kwargs: existing)

  def fake_execute(conn: object, query: str, params: tuple[Any, ...]) -> dict[str, str]:
    captured.update(query=query, params=params)
    return {"id": "asset-1"}

  monkeypatch.setattr(iiif_ingest, "_execute_returning", fake_execute)
  image, manifest = normalized_records()

  asset_id = upsert_image_asset(object(), "repository-1", "canvas-1", image, manifest, IngestStats())

  assert asset_id == "asset-1"
  assert "training_allowed =" not in captured["query"]
  assert "rights_review_status =" not in captured["query"]
  assert "publication_allowed = %s" in captured["query"]
  assert captured["query"].count("%s") == len(captured["params"])
  stored_json = next(param.obj for param in captured["params"] if isinstance(param, Jsonb))
  assert stored_json["rights_review"] == provenance
  assert stored_json["source"] == "iiif_ingestion"


def test_new_image_asset_is_always_pending_and_training_disallowed(monkeypatch: pytest.MonkeyPatch) -> None:
  captured: dict[str, Any] = {}
  monkeypatch.setattr(iiif_ingest, "_fetch_one", lambda *args, **kwargs: None)

  def fake_execute(conn: object, query: str, params: tuple[Any, ...]) -> dict[str, str]:
    captured.update(query=query, params=params)
    return {"id": "asset-new"}

  monkeypatch.setattr(iiif_ingest, "_execute_returning", fake_execute)
  image, manifest = normalized_records(requested_status="approved_for_training")

  asset_id = upsert_image_asset(object(), "repository-1", "canvas-1", image, manifest, IngestStats())

  assert asset_id == "asset-new"
  assert captured["query"].count("%s") == len(captured["params"])
  assert captured["params"][13] is False
  assert captured["params"][18] == "pending_review"
  stored_json = next(param.obj for param in captured["params"] if isinstance(param, Jsonb))
  assert "rights_review" not in stored_json
