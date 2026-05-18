#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import yaml


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_SMOKE = {
    "fp_01_clean_simple": {"regions_min": 100},
    "fr_02_text_block": {"regions_min": 95},
}
EXPECTED_PILOT = {
    "fp_01_clean_simple": {"regions_min": 1},
    "fp_02_clean_simple": {"regions_min": 1},
    "fp_03_complex_layout": {"regions_min": 1},
    "fp_04_complex_layout": {"regions_min": 1},
    "fp_05_iiif_rights": {"regions_min": 1},
    "fr_01_binding_strip": {"regions_min": 1},
    "fr_02_text_block": {"regions_min": 1},
    "fr_03_marginal_gloss": {"regions_min": 1},
    "fr_04_decoration_initial": {"regions_min": 1},
    "fr_05_damaged_irregular": {"regions_min": 1},
}


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("FRAGMENT_DB_HOST", "localhost"),
        port=os.environ.get("FRAGMENT_DB_PORT", "55432"),
        dbname=os.environ.get("FRAGMENT_DB_NAME", "fragment"),
        user=os.environ.get("FRAGMENT_DB_USER", "fragment"),
        password=os.environ.get("FRAGMENT_DB_PASSWORD", "fragment_dev_password"),
    )


def resolve_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def main() -> int:
    pilot_storage = yaml.safe_load((ROOT / "data/metadata/segmentation_pilot_storage_results.yaml").read_text(encoding="utf-8"))
    pilot_warnings = {item["sample_id"]: item.get("warnings", []) for item in pilot_storage.get("samples", [])}
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              CASE
                WHEN sr.parameters->>'pilot_run_id' = 'segmentation_pilot_v0_1' THEN 'full_pilot'
                WHEN sr.parameters->>'smoke_test_id' = 'segmentation_smoke_test_v0_1' THEN 'smoke_test'
                ELSE 'other'
              END AS run_type,
              sr.id::text AS segmentation_run_id,
              sr.parameters->>'sample_id' AS sample_id,
              ia.local_path,
              COALESCE(sr.raw_output->>'overlay_path', sr.parameters->>'overlay_path') AS overlay_path,
              COUNT(lr.id)::int AS region_count,
              ARRAY_REMOVE(ARRAY_AGG(DISTINCT lr.label ORDER BY lr.label), NULL) AS labels
            FROM segmentation_run sr
            LEFT JOIN image_asset ia ON ia.id = sr.image_asset_id
            LEFT JOIN layout_region lr ON lr.segmentation_run_id = sr.id
            WHERE (sr.parameters->>'smoke_test_id' = 'segmentation_smoke_test_v0_1'
               OR sr.parameters->>'pilot_run_id' = 'segmentation_pilot_v0_1')
            GROUP BY sr.id, ia.local_path
            ORDER BY run_type, sr.parameters->>'sample_id'
            """
        )
        rows = cur.fetchall()

    if len(rows) < 12:
        print(f"FAIL: expected at least 12 stored runs across smoke test and pilot, found {len(rows)}")
        return 1

    seen_smoke = set()
    seen_pilot = set()
    for run_type, run_id, sample_id, local_path, overlay_path, region_count, labels in rows:
        warning_list: list[str] = []
        if run_type == "smoke_test":
            if sample_id not in EXPECTED_SMOKE:
                print(f"FAIL: unexpected smoke-test sample_id in viewer data: {sample_id}")
                return 1
            seen_smoke.add(sample_id)
            expected_min = EXPECTED_SMOKE[sample_id]["regions_min"]
        elif run_type == "full_pilot":
            if sample_id not in EXPECTED_PILOT:
                print(f"FAIL: unexpected pilot sample_id in viewer data: {sample_id}")
                return 1
            seen_pilot.add(sample_id)
            expected_min = EXPECTED_PILOT[sample_id]["regions_min"]
            warning_list = pilot_warnings.get(sample_id, [])
        else:
            print(f"FAIL: unexpected run type in viewer data: {run_type}")
            return 1
        image_path = resolve_path(local_path)
        overlay = resolve_path(overlay_path)
        if not image_path or not image_path.exists():
            print(f"FAIL: original image missing for {run_type}/{sample_id}: {local_path}")
            return 1
        if not overlay or not overlay.exists():
            print(f"FAIL: overlay image missing for {run_type}/{sample_id}: {overlay_path}")
            return 1
        if run_type == "full_pilot" and warning_list:
            print(
                f"OK: {run_type}/{sample_id} run={run_id} image={image_path.name} "
                f"overlay={overlay.name} regions={region_count} warnings={'; '.join(warning_list)}"
            )
            continue
        if region_count < expected_min:
            print(f"FAIL: too few layout_region rows for {run_type}/{sample_id}: {region_count}")
            return 1
        if not labels:
            print(f"FAIL: no labels stored for {run_type}/{sample_id}")
            return 1
        print(
            f"OK: {run_type}/{sample_id} run={run_id} image={image_path.name} "
            f"overlay={overlay.name} regions={region_count} labels={', '.join(labels)}"
        )

    missing_smoke = set(EXPECTED_SMOKE) - seen_smoke
    if missing_smoke:
        print(f"FAIL: missing expected smoke-test samples: {sorted(missing_smoke)}")
        return 1

    missing_pilot = set(EXPECTED_PILOT) - seen_pilot
    if missing_pilot:
        print(f"FAIL: missing expected pilot samples: {sorted(missing_pilot)}")
        return 1

    print("PASS: viewer data is ready for smoke-test and full-pilot runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
