from pathlib import Path

import yaml


CONFIG = Path("data/metadata/initial_sample_dataset.yaml")


EXPECTED_FULL_PAGE_CATEGORIES = {
  "clean_simple",
  "complex_layout",
  "iiif_rights_metadata",
}

EXPECTED_FRAGMENT_CATEGORIES = {
  "binding_strip",
  "text_block",
  "marginal_gloss",
  "decoration_initial",
  "damaged_irregular",
}


def load_config():
  return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_sample_dataset_yaml_loads():
  config = load_config()
  assert config["dataset_id"] == "initial_sample_dataset_v0_1"
  assert config["created_from"] == "autocomplete-test-dataset"


def test_sample_counts_and_unique_ids():
  config = load_config()
  full_pages = config["full_pages"]
  fragments = config["fragments"]
  ids = [item["id"] for item in full_pages + fragments]

  assert len(full_pages) == 5
  assert len(fragments) == 5
  assert len(ids) == len(set(ids))


def test_required_fields_and_conservative_rights():
  config = load_config()
  required = {
    "id",
    "category",
    "source",
    "url",
    "local_path",
    "local_file_mapping_status",
    "purpose",
    "rights_review_status",
    "training_allowed",
    "publication_allowed",
    "demo_allowed",
    "access_level",
  }

  for item in config["full_pages"] + config["fragments"]:
    assert required.issubset(item)
    assert item["url"]
    assert item["rights_review_status"] == "pending_review"
    assert item["training_allowed"] is False
    assert item["publication_allowed"] is False
    assert item["demo_allowed"] is False
    assert item["access_level"] == "internal"


def test_categories_match_expected_values():
  config = load_config()
  assert {item["category"] for item in config["full_pages"]} == EXPECTED_FULL_PAGE_CATEGORIES
  assert {item["category"] for item in config["fragments"]} == EXPECTED_FRAGMENT_CATEGORIES
