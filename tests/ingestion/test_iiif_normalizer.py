import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.ingestion.iiif_normalizer import normalize_manifest


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
  return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_v2_fixture_parses():
  manifest = normalize_manifest(load_fixture("iiif_v2_minimal_manifest.json"), "fixture:v2")

  assert manifest.manifest_id == "https://fixtures.example.org/iiif/v2/manifest"
  assert manifest.label == "Fixture V2 Manuscript"
  assert manifest.license == "https://creativecommons.org/publicdomain/mark/1.0/"
  assert manifest.attribution == "Fixture Repository"
  assert len(manifest.canvases) == 1
  assert len(manifest.canvases[0].images) == 1
  assert manifest.canvases[0].images[0].source_url == "https://fixtures.example.org/images/v2/p1/full/full/0/default.jpg"
  assert manifest.canvases[0].images[0].iiif_image_service_url == "https://fixtures.example.org/iiif/image/v2/p1"


def test_v3_fixture_parses():
  manifest = normalize_manifest(load_fixture("iiif_v3_minimal_manifest.json"), "fixture:v3")

  assert manifest.manifest_id == "https://fixtures.example.org/iiif/v3/manifest"
  assert manifest.label == "Fixture V3 Manuscript"
  assert manifest.license == "https://creativecommons.org/licenses/by/4.0/"
  assert manifest.attribution == "Fixture Repository"
  assert len(manifest.canvases) == 1
  assert len(manifest.canvases[0].images) == 1
  assert manifest.canvases[0].images[0].source_url == "https://fixtures.example.org/images/v3/p1/full/max/0/default.jpg"
  assert manifest.canvases[0].images[0].iiif_image_service_url == "https://fixtures.example.org/iiif/image/v3/p1"


def test_normalized_output_has_stable_keys():
  manifest = normalize_manifest(load_fixture("iiif_v3_minimal_manifest.json"), "fixture:v3")
  canvas = manifest.canvases[0]
  image = canvas.images[0]

  assert set(manifest.__dataclass_fields__) == {
    "source_identifier",
    "manifest_id",
    "label",
    "metadata",
    "rights_statement",
    "license",
    "attribution",
    "raw_metadata",
    "canvases",
  }
  assert set(canvas.__dataclass_fields__) == {
    "canvas_identifier",
    "canvas_label",
    "width_px",
    "height_px",
    "sequence_index",
    "raw_metadata",
    "images",
  }
  assert set(image.__dataclass_fields__) == {
    "source_url",
    "iiif_image_service_url",
    "media_type",
    "width_px",
    "height_px",
    "raw_metadata",
  }
