#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/store_segmentation_outputs.py --verbose >/dev/null

python3 - <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import yaml

ROOT = Path.cwd()
results_path = ROOT / "data/metadata/segmentation_storage_results.yaml"
report_path = ROOT / "docs/09_segmentation_storage_report.md"

if not results_path.exists():
    print("FAIL: segmentation_storage_results.yaml is missing")
    sys.exit(1)
if not report_path.exists():
    print("FAIL: docs/09_segmentation_storage_report.md is missing")
    sys.exit(1)

payload = yaml.safe_load(results_path.read_text(encoding="utf-8"))
samples = payload.get("samples", [])
if payload.get("database_write") is not True:
    print("FAIL: database_write is not true")
    sys.exit(1)
if len(samples) != 2:
    print(f"FAIL: expected 2 stored samples, found {len(samples)}")
    sys.exit(1)

conn = psycopg.connect(
    host=os.environ.get("FRAGMENT_DB_HOST", "localhost"),
    port=os.environ.get("FRAGMENT_DB_PORT", "55432"),
    dbname=os.environ.get("FRAGMENT_DB_NAME", "fragment"),
    user=os.environ.get("FRAGMENT_DB_USER", "fragment"),
    password=os.environ.get("FRAGMENT_DB_PASSWORD", "fragment_dev_password"),
)
expected_min_counts = {
    "fp_01_clean_simple": 1,
    "fr_02_text_block": 1,
}
expected_labels = {
    "fp_01_clean_simple": "Main script black",
    "fr_02_text_block": "Main script black",
}
with conn, conn.cursor() as cur:
    smoke_test_id = payload["smoke_test_id"]
    cur.execute(
        """
        SELECT COUNT(*)
        FROM segmentation_run
        WHERE parameters->>'smoke_test_id' = %s
        """,
        (smoke_test_id,),
    )
    run_count = cur.fetchone()[0]
    if run_count != 2:
        print(f"FAIL: expected 2 segmentation_run rows for smoke test, found {run_count}")
        sys.exit(1)

    for sample in samples:
        sample_id = sample["sample_id"]
        run_id = sample.get("db_segmentation_run_id")
        if not run_id:
            print(f"FAIL: missing db_segmentation_run_id for {sample_id}")
            sys.exit(1)
        cur.execute(
            """
            SELECT model_name, model_source, output_path
            FROM segmentation_run
            WHERE id = %s
            """,
            (run_id,),
        )
        run_row = cur.fetchone()
        if not run_row:
            print(f"FAIL: segmentation_run {run_id} missing for {sample_id}")
            sys.exit(1)
        model_name, model_source, output_path = run_row
        if not model_name or not model_source or not output_path:
            print(f"FAIL: missing model/output metadata for {sample_id}")
            sys.exit(1)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM layout_region
            WHERE segmentation_run_id = %s
            """,
            (run_id,),
        )
        region_count = cur.fetchone()[0]
        if region_count < expected_min_counts[sample_id]:
            print(f"FAIL: no layout regions stored for {sample_id}")
            sys.exit(1)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM layout_region
            WHERE segmentation_run_id = %s AND label = %s
            """,
            (run_id, expected_labels[sample_id]),
        )
        label_count = cur.fetchone()[0]
        if label_count < 1:
            print(f"FAIL: expected label '{expected_labels[sample_id]}' missing for {sample_id}")
            sys.exit(1)
        if sample_id == "fp_01_clean_simple" and region_count < 100:
            print(f"FAIL: expected roughly 102 regions for {sample_id}, found {region_count}")
            sys.exit(1)
        if sample_id == "fr_02_text_block" and region_count < 95:
            print(f"FAIL: expected roughly 98 regions for {sample_id}, found {region_count}")
            sys.exit(1)

print("PASS: segmentation smoke-test outputs are stored in PostgreSQL/PostGIS")
PY
