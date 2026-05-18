#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
import os
from pathlib import Path

import psycopg
import yaml

ROOT = Path.cwd()
results_path = ROOT / "data/metadata/segmentation_pilot_storage_results.yaml"
if not results_path.exists():
    raise SystemExit("FAIL: segmentation_pilot_storage_results.yaml is missing")
payload = yaml.safe_load(results_path.read_text(encoding="utf-8"))
samples = payload.get("samples", [])
if len(samples) != 10:
    raise SystemExit(f"FAIL: expected 10 stored pilot samples, found {len(samples)}")

conn = psycopg.connect(
    host=os.environ.get("FRAGMENT_DB_HOST", "localhost"),
    port=os.environ.get("FRAGMENT_DB_PORT", "55432"),
    dbname=os.environ.get("FRAGMENT_DB_NAME", "fragment"),
    user=os.environ.get("FRAGMENT_DB_USER", "fragment"),
    password=os.environ.get("FRAGMENT_DB_PASSWORD", "fragment_dev_password"),
)
with conn, conn.cursor() as cur:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM segmentation_run
        WHERE parameters->>'pilot_run_id' = 'segmentation_pilot_v0_1'
        """
    )
    run_count = cur.fetchone()[0]
    if run_count != 10:
        raise SystemExit(f"FAIL: expected 10 pilot segmentation_run rows, found {run_count}")

    for sample in samples:
        run_id = sample.get("db_segmentation_run_id")
        if not run_id:
            raise SystemExit(f"FAIL: missing db_segmentation_run_id for {sample['sample_id']}")
        cur.execute(
            """
            SELECT model_name, model_source, output_path
            FROM segmentation_run
            WHERE id = %s
            """,
            (run_id,),
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"FAIL: segmentation_run missing for {sample['sample_id']}: {run_id}")
        model_name, model_source, output_path = row
        if not model_name or not model_source or not output_path:
            raise SystemExit(f"FAIL: incomplete model/output metadata for {sample['sample_id']}")
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT label) FROM layout_region WHERE segmentation_run_id = %s", (run_id,))
        region_count, label_count = cur.fetchone()
        if region_count < 1 and not sample.get("warnings"):
            raise SystemExit(f"FAIL: no layout_region rows for {sample['sample_id']}")
        if region_count >= 1 and label_count < 1:
            raise SystemExit(f"FAIL: labels missing for {sample['sample_id']}")
print("PASS: pilot segmentation outputs are stored in PostgreSQL/PostGIS")
PY
