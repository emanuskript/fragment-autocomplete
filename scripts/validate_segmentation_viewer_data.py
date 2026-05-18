#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "fp_01_clean_simple": {"regions_min": 100},
    "fr_02_text_block": {"regions_min": 95},
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
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              sr.id::text AS segmentation_run_id,
              sr.parameters->>'sample_id' AS sample_id,
              ia.local_path,
              COALESCE(sr.raw_output->>'overlay_path', sr.parameters->>'overlay_path') AS overlay_path,
              COUNT(lr.id)::int AS region_count,
              ARRAY_REMOVE(ARRAY_AGG(DISTINCT lr.label ORDER BY lr.label), NULL) AS labels
            FROM segmentation_run sr
            LEFT JOIN image_asset ia ON ia.id = sr.image_asset_id
            LEFT JOIN layout_region lr ON lr.segmentation_run_id = sr.id
            WHERE sr.parameters->>'smoke_test_id' = 'segmentation_smoke_test_v0_1'
            GROUP BY sr.id, ia.local_path
            ORDER BY sr.parameters->>'sample_id'
            """
        )
        rows = cur.fetchall()

    if len(rows) != 2:
        print(f"FAIL: expected 2 smoke-test segmentation runs, found {len(rows)}")
        return 1

    seen = set()
    for run_id, sample_id, local_path, overlay_path, region_count, labels in rows:
        seen.add(sample_id)
        if sample_id not in EXPECTED:
            print(f"FAIL: unexpected sample_id in stored viewer data: {sample_id}")
            return 1
        image_path = resolve_path(local_path)
        overlay = resolve_path(overlay_path)
        if not image_path or not image_path.exists():
            print(f"FAIL: original image missing for {sample_id}: {local_path}")
            return 1
        if not overlay or not overlay.exists():
            print(f"FAIL: overlay image missing for {sample_id}: {overlay_path}")
            return 1
        if region_count < EXPECTED[sample_id]["regions_min"]:
            print(f"FAIL: too few layout_region rows for {sample_id}: {region_count}")
            return 1
        if not labels:
            print(f"FAIL: no labels stored for {sample_id}")
            return 1
        print(
            f"OK: {sample_id} run={run_id} image={image_path.name} "
            f"overlay={overlay.name} regions={region_count} labels={', '.join(labels)}"
        )

    missing = set(EXPECTED) - seen
    if missing:
        print(f"FAIL: missing expected smoke-test samples: {sorted(missing)}")
        return 1

    print("PASS: viewer data is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
