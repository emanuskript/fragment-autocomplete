"""Validate the canonical Mergen source and external checkpoint registry."""

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "models/model_registry.yaml"
MERGEN_REPOSITORY_URL = "https://github.com/emanuskript/Mergen"
MERGEN_WEIGHTS_URL = (
  "https://owncloud.gwdg.de/index.php/apps/files/"
  "?dir=/Mergen%20Weights&fileid=4279218283"
)
EXPECTED_FILENAMES = {
  "best_catmus.pt",
  "best_emanuskript_segmentation.pt",
  "best_zone_detection.pt",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def test_mergen_upstream_locations_are_canonical() -> None:
  registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
  upstream = registry["upstream"]

  assert registry["registry_version"] == "mergen_model_registry_v1"
  assert upstream["component"] == "Mergen"
  assert upstream["repository_url"] == MERGEN_REPOSITORY_URL
  assert upstream["weights_directory_url"] == MERGEN_WEIGHTS_URL
  assert upstream["weights_distribution"] == "external_not_committed"
  assert set(upstream["expected_filenames"]) == EXPECTED_FILENAMES


def test_registered_mergen_files_have_checksums_and_ignored_local_paths() -> None:
  registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
  models = registry["models"]

  assert len({model["id"] for model in models}) == len(models)
  assert {model["distribution_filename"] for model in models} == EXPECTED_FILENAMES
  for model in models:
    assert model["local_path"] == f"model weights/{model['distribution_filename']}"
    assert SHA256_PATTERN.fullmatch(model["checksum"])
    assert model["status"] == "compatibility_inspected"
