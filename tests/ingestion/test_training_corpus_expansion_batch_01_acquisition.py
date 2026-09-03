"""Tests for the Batch 01 acquisition/registration validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_training_corpus_expansion_batch_01_acquisition.py"
SPEC = importlib.util.spec_from_file_location("batch_01_acquisition_validator", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def load(name: str) -> dict:
  return yaml.safe_load((ROOT / "data/metadata" / name).read_text(encoding="utf-8"))


def test_final_batch_artifacts_pass_batch_aware_structure_validation() -> None:
  summary = validator.validate_structure(
    load("training_corpus_expansion_batch_01_manifest.yaml"),
    load("training_corpus_validation_manifest.yaml"),
    load("training_corpus_expansion_readiness_review.yaml"),
    load("training_corpus_expansion_batch_01_spec.yaml"),
    load("training_corpus_expansion_batch_01_statistics.yaml"),
  )

  assert summary["manuscript_count"] == 15
  assert summary["selected_page_count"] == 70
  assert summary["split_counts"] == {
    "manuscripts": {"train": 11, "validation": 2, "test": 2},
    "pages": {"train": 50, "validation": 10, "test": 10},
  }
  assert summary["decisions"]["decision_count"] == 8
  assert summary["decisions"]["replacement_page_count"] == 3
  assert summary["decisions"]["insufficient_or_unsuitable_manuscripts"] == [
    "cea-FaZellweger-90A-01-2"
  ]


def test_source_tree_rejects_orphan_or_rejected_page_downloads(tmp_path: Path) -> None:
  download_root = tmp_path / "data/raw/batch"
  image_path = download_root / "ms" / "0001_page.jpg"
  image_path.parent.mkdir(parents=True)
  Image.new("RGB", (12, 18), "white").save(image_path)
  manifest_path = download_root / "_manifests/ms.json"
  manifest_path.parent.mkdir(parents=True)
  manifest_path.write_text("{}\n", encoding="utf-8")
  batch = {
    "corpus_id": "batch",
    "manuscripts": [{
      "id": "ms",
      "raw_source_metadata": {"raw_manifest_artifact": {
        "local_path": "data/raw/batch/_manifests/ms.json",
        "sha256": validator.sha256_file(manifest_path),
      }},
      "pages": [{
        "canvas_identifier": "canvas-1",
        "selection_status": "selected",
        "image": {"local_path": "data/raw/batch/ms/0001_page.jpg"},
      }],
    }],
  }
  spec = {"download_root": "data/raw/batch"}

  assert len(validator.source_tree_snapshot(spec, batch, tmp_path)) == 2
  (download_root / "ms" / "rejected-page.jpg").write_bytes(image_path.read_bytes())
  with pytest.raises(validator.ValidationError, match="missing/orphan"):
    validator.source_tree_snapshot(spec, batch, tmp_path)


def test_preexisting_reviewed_rights_state_must_survive() -> None:
  before = [{
    "image_asset_id": "asset-1",
    "rights_review_status": "approved_for_training",
    "training_allowed": True,
    "rights_review_provenance": {"review_version": "v1"},
  }]
  validator.require_preexisting_rights_preserved(before, list(before))

  changed = [{**before[0], "training_allowed": False}]
  with pytest.raises(validator.ValidationError, match="changed preexisting human rights-review state"):
    validator.require_preexisting_rights_preserved(before, changed)


def test_database_validator_counts_assigned_and_page_bearing_manuscripts_separately() -> None:
  corpus_id = "fixture-batch"
  rules = "obvious_non_training_canvas_rules_v0_2"
  manuscript_one = {
    "id": "ms-one",
    "manifest_url": "https://example.test/ms-one/manifest",
    "repository": "Repository",
    "shelfmark": "MS 1",
    "title": "Manuscript one",
    "language": "Latin",
    "script": "Caroline minuscule",
    "material": "Parchment",
    "date": {"display": "12th century"},
    "split": "train",
    "pages": [{
      "canvas_identifier": "canvas-one",
      "canvas_label": "1r",
      "sequence_index": 0,
      "width_px": 1200,
      "height_px": 1800,
      "selection_status": "selected",
      "image": {
        "source_url": "https://example.test/full.jpg",
        "iiif_image_service_url": "https://example.test/iiif",
        "local_path": "data/raw/fixture/ms-one/0000_one.jpg",
        "checksum_sha256": "a" * 64,
        "width_px": 1200,
        "height_px": 1800,
        "download_url": "https://example.test/iiif/full/2000,/0/default.jpg",
        "rights_review_status": "pending_review",
      },
      "registration": {"db_ids": {
        "repository_id": "repo-id",
        "manuscript_id": "manuscript-one-id",
        "manifest_cache_id": "cache-one-id",
        "canvas_id": "canvas-id",
        "image_asset_id": "asset-id",
      }},
    }],
  }
  manuscript_two = {
    "id": "ms-two",
    "manifest_url": "https://example.test/ms-two/manifest",
    "repository": "Repository",
    "shelfmark": "MS 2",
    "title": "Manuscript two",
    "language": None,
    "script": None,
    "material": None,
    "date": {"display": None},
    "split": "train",
    "pages": [],
  }
  batch = {
    "corpus_id": corpus_id,
    "selection": {"rules_version": rules},
    "manuscripts": [manuscript_one, manuscript_two],
  }
  registrations = []
  for manuscript, manuscript_db_id, cache_id in (
    (manuscript_one, "manuscript-one-id", "cache-one-id"),
    (manuscript_two, "manuscript-two-id", "cache-two-id"),
  ):
    registrations.append({
      "manifest_url": manuscript["manifest_url"],
      "repository_id": "repo-id",
      "repository_name": manuscript["repository"],
      "manuscript_db_id": manuscript_db_id,
      "manifest_cache_id": cache_id,
      "shelfmark": manuscript["shelfmark"],
      "title": manuscript["title"],
      "language": manuscript["language"],
      "script": manuscript["script"],
      "material": manuscript["material"],
      "orig_date_display": manuscript["date"]["display"],
      "manuscript_corpus_id": corpus_id,
      "manuscript_spec_id": manuscript["id"],
      "manuscript_split": manuscript["split"],
      "selection_rules_version": rules,
      "fetch_status": "completed",
      "manifest_json_type": "object",
    })
  page = manuscript_one["pages"][0]
  image = page["image"]
  rows = [{
    **registrations[0],
    "canvas_db_id": "canvas-id",
    "canvas_identifier": page["canvas_identifier"],
    "canvas_label": page["canvas_label"],
    "sequence_index": page["sequence_index"],
    "canvas_width_px": page["width_px"],
    "canvas_height_px": page["height_px"],
    "canvas_manuscript_id": "manuscript-one-id",
    "image_asset_id": "asset-id",
    "source_url": image["source_url"],
    "iiif_image_service_url": image["iiif_image_service_url"],
    "local_path": image["local_path"],
    "checksum_sha256": image["checksum_sha256"],
    "width_px": image["width_px"],
    "height_px": image["height_px"],
    "rights_statement": None,
    "license": None,
    "attribution": None,
    "rights_review_status": "pending_review",
    "training_allowed": False,
    "asset_corpus_id": corpus_id,
    "asset_split": "train",
    "asset_selection_rules_version": rules,
    "asset_download_url": image["download_url"],
    "canvas_corpus_id": corpus_id,
    "canvas_split": "train",
    "canvas_selection_rules_version": rules,
    "rights_review_provenance": None,
  }]

  result = validator.validate_database_rows(batch, rows, registrations)

  assert result["assigned_manuscript_count"] == 2
  assert result["selected_page_bearing_manuscript_count"] == 1
  assert result["canvas_count"] == 1
  assert result["image_asset_count"] == 1
