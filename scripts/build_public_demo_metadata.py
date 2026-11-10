#!/usr/bin/env python3
"""Build the compact catalogue record used by the public manuscript demo."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "data/metadata/training_corpus_expansion_batch_01_manifest.yaml",
    ROOT / "data/metadata/training_corpus_validation_manifest.yaml",
)
OUTPUT = ROOT / "data/metadata/public_demo_manuscript_metadata_v1.json"
DEMO_MANUSCRIPTS = {
    "bc-b-0103",
    "csg-0073",
    "csg-0916",
    "ubb-A-II-0013",
    "ubb-F-I-0021",
    "bbb-AA0091",
    "csg-0300",
    "bcj-A2437",
}


def _plain(value: Any) -> str | None:
    if value is None:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", "", str(value))).strip()
    return text or None


def _values(fields: list[dict[str, Any]], *labels: str) -> list[str]:
    accepted = {label.casefold() for label in labels}
    values: list[str] = []
    for field in fields:
        if str(field.get("label", "")).casefold() not in accepted:
            continue
        value = _plain(field.get("value"))
        if value and value not in values:
            values.append(value)
    return values


def _first(fields: list[dict[str, Any]], *labels: str) -> str | None:
    values = _values(fields, *labels)
    return values[0] if values else None


def build() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    manuscripts: dict[str, tuple[dict[str, Any], Path]] = {}
    for source_path in SOURCES:
        source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        for manuscript in source["manuscripts"]:
            if manuscript["id"] in DEMO_MANUSCRIPTS:
                manuscripts.setdefault(manuscript["id"], (manuscript, source_path))

    missing = DEMO_MANUSCRIPTS - manuscripts.keys()
    if missing:
        raise RuntimeError(f"Missing public-demo catalogue records: {sorted(missing)}")

    for manuscript_id in sorted(DEMO_MANUSCRIPTS):
        manuscript, source_path = manuscripts[manuscript_id]
        fields = manuscript.get("raw_source_metadata", {}).get("normalized_metadata", [])
        languages = _values(fields, "Text Language")
        primary_language = _plain(manuscript.get("language"))
        if primary_language and primary_language not in languages:
            languages.insert(0, primary_language)
        records.append(
            {
                "manuscriptId": manuscript["id"],
                "repository": _plain(manuscript.get("repository")),
                "shelfmark": _plain(manuscript.get("shelfmark")),
                "title": _plain(manuscript.get("title")),
                "dateDisplay": _plain(manuscript.get("date", {}).get("display")),
                "dateNotBefore": manuscript.get("date", {}).get("not_before"),
                "dateNotAfter": manuscript.get("date", {}).get("not_after"),
                "dateMethod": _plain(manuscript.get("date", {}).get("method")),
                "century": _first(fields, "Century"),
                "languages": languages,
                "scriptOrHand": _plain(manuscript.get("script")) or _first(fields, "Script", "Hand"),
                "typefaceOrFont": _first(fields, "Typeface", "Font"),
                "material": _plain(manuscript.get("material")) or _first(fields, "Material"),
                "documentType": _first(fields, "Document Type"),
                "doi": _first(fields, "DOI"),
                "dimensions": _first(fields, "Dimensions", "Physical Dimensions"),
                "pageCount": _first(fields, "Number of Pages"),
                "placeOfOrigin": _first(
                    fields,
                    "Place of Origin",
                    "Place of Origin (English)",
                    "Origin",
                ),
                "onlineSince": _first(fields, "Online Since"),
                "digitizedBy": _first(fields, "Digitized by"),
                "persons": _first(fields, "Persons"),
                "summary": _first(fields, "Summary", "Summary (English)"),
                "manifestUrl": manuscript.get("manifest_url"),
                "metadataSource": source_path.name,
            }
        )
    return {
        "version": "public_demo_manuscript_metadata_v1",
        "sources": [str(source.relative_to(ROOT)) for source in SOURCES],
        "recordCount": len(records),
        "records": records,
    }


def main() -> None:
    payload = build()
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {payload['recordCount']} catalogue records to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
