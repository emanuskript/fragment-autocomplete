from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / "data/metadata/public_demo_manuscript_metadata_v1.json"


def test_public_demo_catalogue_has_required_identity_fields() -> None:
    payload = json.loads(METADATA.read_text(encoding="utf-8"))
    records = {record["manuscriptId"]: record for record in payload["records"]}
    demo_ids = {
        "bc-b-0103",
        "csg-0073",
        "csg-0916",
        "ubb-A-II-0013",
        "ubb-F-I-0021",
        "bbb-AA0091",
        "csg-0300",
        "bcj-A2437",
    }

    assert payload["recordCount"] == len(payload["records"]) == 8
    assert demo_ids == records.keys()
    for manuscript_id in demo_ids:
        record = records[manuscript_id]
        assert record["repository"]
        assert record["shelfmark"]
        assert record["title"]
        assert record["dateDisplay"]
        assert record["century"]
        assert record["languages"]
        assert record["material"]
        assert record["documentType"]
        assert record["metadataSource"].endswith("_manifest.yaml")


def test_missing_script_and_font_are_not_filled_from_layout_labels() -> None:
    payload = json.loads(METADATA.read_text(encoding="utf-8"))
    for record in payload["records"]:
        if record["scriptOrHand"] is None:
            assert record["typefaceOrFont"] is None
