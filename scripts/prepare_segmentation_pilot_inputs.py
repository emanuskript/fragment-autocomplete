#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import psycopg
import yaml


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESOLVED = ROOT / "data/metadata/initial_sample_dataset_resolved.yaml"
DEFAULT_OUTPUT = ROOT / "data/metadata/segmentation_pilot_inputs.yaml"
MODEL_PATH = ROOT / "model weights/best_emanuskript_segmentation.pt"
PILOT_RUN_ID = "segmentation_pilot_v0_1"
EXPECTED_FULL_PAGES = [
    "fp_01_clean_simple",
    "fp_02_clean_simple",
    "fp_03_complex_layout",
    "fp_04_complex_layout",
    "fp_05_iiif_rights",
]
EXPECTED_FRAGMENTS = [
    "fr_01_binding_strip",
    "fr_02_text_block",
    "fr_03_marginal_gloss",
    "fr_04_decoration_initial",
    "fr_05_damaged_irregular",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the 10-item pilot segmentation input manifest.")
    parser.add_argument("--resolved", default=str(DEFAULT_RESOLVED))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("FRAGMENT_DB_HOST", "localhost"),
        port=os.environ.get("FRAGMENT_DB_PORT", "55432"),
        dbname=os.environ.get("FRAGMENT_DB_NAME", "fragment"),
        user=os.environ.get("FRAGMENT_DB_USER", "fragment"),
        password=os.environ.get("FRAGMENT_DB_PASSWORD", "fragment_dev_password"),
    )


def db_exists(cur: Any, table: str, record_id: str | None) -> bool:
    if not record_id:
        return False
    cur.execute(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE id = %s)", (record_id,))
    return bool(cur.fetchone()[0])


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    db_ids = item.get("db_ids", {})
    return {
        "sample_id": item["id"],
        "sample_kind": item["sample_kind"],
        "category": item["category"],
        "source": item["source"],
        "source_url": item["url"],
        "local_path": item["local_path"],
        "db_image_asset_id": db_ids.get("image_asset_id"),
        "db_canvas_id": db_ids.get("canvas_id"),
        "db_fragment_id": db_ids.get("fragment_id"),
        "rights_review_status": item.get("rights_review_status"),
        "access_level": item.get("access_level"),
        "selected_for": "full_pilot_segmentation",
        "readiness_status": "ready",
    }


def main() -> int:
    args = parse_args()
    resolved = load_yaml(Path(args.resolved))
    full_pages = {item["id"]: item for item in resolved.get("full_pages", [])}
    fragments = {item["id"]: item for item in resolved.get("fragments", [])}

    missing_full = [sample_id for sample_id in EXPECTED_FULL_PAGES if sample_id not in full_pages]
    missing_fragments = [sample_id for sample_id in EXPECTED_FRAGMENTS if sample_id not in fragments]
    if missing_full or missing_fragments:
        raise RuntimeError(f"Missing expected sample IDs: full_pages={missing_full}, fragments={missing_fragments}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model path does not exist: {MODEL_PATH}")

    selected_inputs = [normalize_item(full_pages[sample_id]) for sample_id in EXPECTED_FULL_PAGES]
    selected_inputs.extend(normalize_item(fragments[sample_id]) for sample_id in EXPECTED_FRAGMENTS)

    with connect() as conn, conn.cursor() as cur:
        for item in selected_inputs:
            local_path = ROOT / item["local_path"]
            if not local_path.exists():
                raise FileNotFoundError(f"Local input image missing: {item['local_path']}")
            if not db_exists(cur, "image_asset", item["db_image_asset_id"]):
                raise RuntimeError(f"Missing image_asset record for {item['sample_id']}: {item['db_image_asset_id']}")
            if item["sample_kind"] == "full_page" and not db_exists(cur, "canvas", item["db_canvas_id"]):
                raise RuntimeError(f"Missing canvas record for {item['sample_id']}: {item['db_canvas_id']}")
            if item["sample_kind"] == "fragment" and not db_exists(cur, "fragment", item["db_fragment_id"]):
                raise RuntimeError(f"Missing fragment record for {item['sample_id']}: {item['db_fragment_id']}")

    payload = {
        "pilot_run_id": PILOT_RUN_ID,
        "status": "prepared",
        "purpose": "Full pilot segmentation run over the 10 registered pilot samples.",
        "model_id": "best_emanuskript_segmentation",
        "model_path": str(MODEL_PATH.relative_to(ROOT)),
        "inference_run": False,
        "segmentation_run": False,
        "selected_inputs": selected_inputs,
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    write_yaml(output, payload)

    print(f"Prepared pilot segmentation inputs: {len(selected_inputs)} samples")
    print(f"- full pages: {len(EXPECTED_FULL_PAGES)}")
    print(f"- fragments: {len(EXPECTED_FRAGMENTS)}")
    print(f"- model: {payload['model_path']}")
    if args.verbose:
        for item in selected_inputs:
            target = item["db_canvas_id"] if item["sample_kind"] == "full_page" else item["db_fragment_id"]
            print(f"  {item['sample_id']}: {item['sample_kind']} | image_asset={item['db_image_asset_id']} | target={target}")
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
