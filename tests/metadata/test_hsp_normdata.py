"""Validation tests for extracted HSP normdata and field-mapping metadata."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
TERMS_PATH = ROOT / "data/metadata/hsp_normdata_terms.yaml"
MAPPING_PATH = ROOT / "data/metadata/hsp_metadata_field_mapping.yaml"


EXPECTED_COUNTS = {
  "SCRP": 116,
  "FORM": 92,
  "CODC": 73,
  "BNDG": 240,
  "HSP_SIMPLIFIED": 18,
}


def load_yaml(path: Path):
  return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_normdata_term_counts_match_workbook():
  payload = load_yaml(TERMS_PATH)
  actual = {item["code"]: item["actual_term_count"] for item in payload["vocabularies"]}
  assert actual == EXPECTED_COUNTS


def test_normdata_notations_are_unique_per_vocabulary():
  payload = load_yaml(TERMS_PATH)
  for vocabulary in payload["vocabularies"]:
    notations = [term["notation"] for term in vocabulary["terms"]]
    assert len(notations) == len(set(notations)), vocabulary["code"]


def test_known_terms_are_present():
  payload = load_yaml(TERMS_PATH)
  terms = {
    vocabulary["code"]: {term["notation"] for term in vocabulary["terms"]}
    for vocabulary in payload["vocabularies"]
  }
  assert any(notation.startswith("SCRP-") for notation in terms["SCRP"])
  assert "CODC-A366" in terms["CODC"]
  assert "form" in terms["HSP_SIMPLIFIED"]
  assert "status" in terms["HSP_SIMPLIFIED"]


def test_field_mapping_contains_core_tables():
  payload = load_yaml(MAPPING_PATH)
  table_names = {table["table"] for table in payload["tables"]}
  assert "repository" in table_names
  assert "manuscript" in table_names
  assert "canvas" in table_names
  assert "image_asset" in table_names
  assert "fragment_extensions" in table_names
  assert payload["field_count"] > 100
