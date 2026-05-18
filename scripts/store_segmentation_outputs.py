#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.db import connect


DEFAULT_RESULTS = ROOT / "data/metadata/segmentation_smoke_test_results.yaml"
DEFAULT_INPUTS = ROOT / "data/metadata/segmentation_test_inputs.yaml"
DEFAULT_STORAGE_RESULTS = ROOT / "data/metadata/segmentation_storage_results.yaml"
DEFAULT_REPORT = ROOT / "docs/09_segmentation_storage_report.md"
DEFAULT_SMOKE_TEST_REPORT = ROOT / "docs/08_segmentation_smoke_test_report.md"


@dataclass
class SampleContext:
    sample_id: str
    sample_kind: str
    local_path: str
    source_url: str | None
    db_image_asset_id: str | None
    db_canvas_id: str | None
    db_fragment_id: str | None
    category: str | None
    source: str | None
    rights_review_status: str | None
    access_level: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store segmentation smoke-test outputs in PostgreSQL/PostGIS.")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--inputs", default=str(DEFAULT_INPUTS))
    parser.add_argument("--output", default=str(DEFAULT_STORAGE_RESULTS))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_polygon_wkt(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        "POLYGON(("
        f"{x1:.6f} {y1:.6f}, "
        f"{x2:.6f} {y1:.6f}, "
        f"{x2:.6f} {y2:.6f}, "
        f"{x1:.6f} {y2:.6f}, "
        f"{x1:.6f} {y1:.6f}"
        "))"
    )


def normalize_inputs(inputs_yaml: dict[str, Any]) -> dict[str, SampleContext]:
    selected_inputs = inputs_yaml.get("selected_inputs", [])
    contexts: dict[str, SampleContext] = {}
    for item in selected_inputs:
        sample_id = item["sample_id"]
        contexts[sample_id] = SampleContext(
            sample_id=sample_id,
            sample_kind=item["sample_kind"],
            local_path=item["local_path"],
            source_url=item.get("source_url"),
            db_image_asset_id=item.get("db_image_asset_id"),
            db_canvas_id=item.get("db_canvas_id"),
            db_fragment_id=item.get("db_fragment_id"),
            category=item.get("category"),
            source=item.get("source"),
            rights_review_status=item.get("rights_review_status"),
            access_level=item.get("access_level"),
        )
    return contexts


def find_existing_run(cur: Any, context: SampleContext, smoke_test_id: str, model_name: str) -> str | None:
    cur.execute(
        """
        SELECT id
        FROM segmentation_run
        WHERE image_asset_id = %s
          AND COALESCE(fragment_id::text, '') = COALESCE(%s, '')
          AND model_name = %s
          AND parameters->>'smoke_test_id' = %s
          AND parameters->>'sample_id' = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (
            context.db_image_asset_id,
            context.db_fragment_id,
            model_name,
            smoke_test_id,
            context.sample_id,
        ),
    )
    row = cur.fetchone()
    return row[0] if row else None


def upsert_segmentation_run(
    cur: Any,
    *,
    existing_run_id: str | None,
    context: SampleContext,
    smoke_test_id: str,
    smoke_test_results: dict[str, Any],
    sample_result: dict[str, Any],
    raw_prediction: dict[str, Any],
    generated_at: str,
) -> str:
    parameters = {
        "smoke_test_id": smoke_test_id,
        "sample_id": context.sample_id,
        "sample_kind": context.sample_kind,
        "source_url": context.source_url,
        "local_path": context.local_path,
        "overlay_path": sample_result.get("overlay_path"),
        "raw_output_path": sample_result.get("raw_output_path"),
        "results_yaml_path": str(Path(smoke_test_results["_results_path"]).relative_to(ROOT)),
        "smoke_test_report_path": str(DEFAULT_SMOKE_TEST_REPORT.relative_to(ROOT)),
        "device": smoke_test_results.get("device"),
        "confidence_threshold": smoke_test_results.get("confidence_threshold"),
        "imgsz": smoke_test_results.get("imgsz"),
        "db_canvas_id": context.db_canvas_id,
        "db_fragment_id": context.db_fragment_id,
        "db_image_asset_id": context.db_image_asset_id,
        "category": context.category,
        "source": context.source,
        "rights_review_status": context.rights_review_status,
        "access_level": context.access_level,
    }
    raw_output = {
        "sample_id": context.sample_id,
        "sample_kind": context.sample_kind,
        "source_url": context.source_url,
        "local_path": context.local_path,
        "raw_output_path": sample_result.get("raw_output_path"),
        "overlay_path": sample_result.get("overlay_path"),
        "raw_prediction": raw_prediction,
        "smoke_test_result": sample_result,
    }
    values = (
        context.db_image_asset_id,
        context.db_fragment_id,
        smoke_test_results.get("model_id"),
        smoke_test_results.get("environment", {}).get("ultralytics_version"),
        smoke_test_results.get("model_path"),
        json.dumps(parameters),
        "completed",
        generated_at,
        generated_at,
        sample_result.get("raw_output_path"),
        "ultralytics_segmentation_json",
        json.dumps(sample_result.get("confidence_summary", {})),
        json.dumps(raw_output),
    )
    if existing_run_id:
        cur.execute(
            """
            UPDATE segmentation_run
            SET image_asset_id = %s,
                fragment_id = %s,
                model_name = %s,
                model_version = %s,
                model_source = %s,
                parameters = %s::jsonb,
                status = %s,
                started_at = %s,
                completed_at = %s,
                output_path = %s,
                output_format = %s,
                confidence_summary = %s::jsonb,
                raw_output = %s::jsonb,
                updated_at = now()
            WHERE id = %s
            """,
            values + (existing_run_id,),
        )
        return existing_run_id

    cur.execute(
        """
        INSERT INTO segmentation_run (
            image_asset_id,
            fragment_id,
            model_name,
            model_version,
            model_source,
            parameters,
            status,
            started_at,
            completed_at,
            output_path,
            output_format,
            confidence_summary,
            raw_output
        ) VALUES (
            %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
        )
        RETURNING id
        """,
        values,
    )
    return cur.fetchone()[0]


def replace_layout_regions(cur: Any, segmentation_run_id: str, detections: list[dict[str, Any]]) -> int:
    cur.execute("DELETE FROM layout_region WHERE segmentation_run_id = %s", (segmentation_run_id,))
    inserted = 0
    for detection in detections:
        bbox = detection.get("bbox_xyxy")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = [float(value) for value in bbox]
        if x2 <= x1 or y2 <= y1:
            continue
        wkt = make_polygon_wkt(x1, y1, x2, y2)
        area = max(0.0, (x2 - x1) * (y2 - y1))
        cur.execute(
            """
            INSERT INTO layout_region (
                segmentation_run_id,
                label,
                label_id,
                confidence,
                region_geom,
                bbox_geom,
                reading_order_index,
                region_area_px,
                mask_path,
                raw_region
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                ST_GeomFromText(%s, 0),
                ST_GeomFromText(%s, 0),
                %s,
                %s,
                %s,
                %s::jsonb
            )
            """,
            (
                segmentation_run_id,
                detection.get("label", "unknown"),
                detection.get("class_id"),
                detection.get("confidence"),
                wkt,
                wkt,
                detection.get("index"),
                area,
                detection.get("mask_path"),
                json.dumps(detection),
            ),
        )
        inserted += 1
    return inserted


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(to_plain_data(payload), handle, sort_keys=False, allow_unicode=True)


def to_plain_data(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Fragment Autocomplete — Segmentation Storage Report",
        "",
        "## Purpose",
        "Store the existing two-sample segmentation smoke-test outputs in PostgreSQL/PostGIS as structured `segmentation_run` and `layout_region` records.",
        "",
        "## Scope",
        "This step stores only the already-generated smoke-test outputs for one full page and one fragment. No inference was rerun, no training was performed, and no UI was built.",
        "",
        "## Inputs Used",
        f"- Smoke-test results: `{payload['smoke_test_results_path']}`",
        f"- Prepared inputs: `{payload['segmentation_test_inputs_path']}`",
        f"- Smoke-test ID: `{payload['smoke_test_id']}`",
        "",
        "## Database Tables Written",
        "- `segmentation_run`",
        "- `layout_region`",
        "",
        "## Segmentation Runs Created or Matched",
    ]
    for sample in payload["samples"]:
        lines.extend(
            [
                f"- `{sample['sample_id']}`: run `{sample['db_segmentation_run_id']}` ({sample['status']})",
            ]
        )
    lines.extend(
        [
            "",
            "## Layout Regions Created or Matched",
        ]
    )
    for sample in payload["samples"]:
        lines.append(f"- `{sample['sample_id']}`: `{sample['layout_region_count']}` layout regions stored")
    lines.extend(
        [
            "",
            "## Geometry Strategy",
            "The raw smoke-test JSON did not include persisted mask polygons. Each region was therefore stored as a page-local SRID 0 polygon derived from the detected bounding box, and the same polygon was written to both `region_geom` and `bbox_geom`.",
            "",
            "## Labels and Confidence Summary",
        ]
    )
    for sample in payload["samples"]:
        labels = ", ".join(sample["detected_labels"]) if sample["detected_labels"] else "none"
        lines.append(f"- `{sample['sample_id']}`: labels `{labels}`")
    lines.extend(
        [
            "",
            "## Output Paths Preserved",
        ]
    )
    for sample in payload["samples"]:
        lines.extend(
            [
                f"- `{sample['sample_id']}` raw output: `{sample['raw_output_path']}`",
                f"- `{sample['sample_id']}` overlay: `{sample['overlay_path']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Validation Result",
            f"- Storage status: `{payload['storage_status']}`",
            f"- Database write: `{str(payload['database_write']).lower()}`",
            "",
            "## What Has Not Been Implemented",
            "- No inference was rerun.",
            "- No training was performed.",
            "- No database-backed UI viewer exists yet.",
            "- Artificial fragments and reconstruction are not implemented here.",
            "",
            "## Next Step",
            "Build a minimal local UI viewer for the stored segmentation outputs.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    results_path = Path(args.results).resolve()
    inputs_path = Path(args.inputs).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()

    smoke_test_results = load_yaml(results_path)
    smoke_test_results["_results_path"] = str(results_path)
    inputs_yaml = load_yaml(inputs_path)
    contexts = normalize_inputs(inputs_yaml)
    smoke_test_id = smoke_test_results["test_set_id"]
    generated_at = smoke_test_results.get("generated_at") or iso_now()

    samples_out: list[dict[str, Any]] = []

    if args.dry_run:
        for sample_result in smoke_test_results.get("results", []):
            sample_id = sample_result["sample_id"]
            context = contexts[sample_id]
            raw_prediction = load_json((ROOT / sample_result["raw_output_path"]).resolve())
            detections = raw_prediction.get("detections", [])
            samples_out.append(
                {
                    "sample_id": sample_id,
                    "sample_kind": context.sample_kind,
                    "db_image_asset_id": context.db_image_asset_id,
                    "db_canvas_id": context.db_canvas_id,
                    "db_fragment_id": context.db_fragment_id,
                    "db_segmentation_run_id": None,
                    "layout_region_count": len(detections),
                    "detected_labels": sample_result.get("detected_labels", []),
                    "raw_output_path": sample_result.get("raw_output_path"),
                    "overlay_path": sample_result.get("overlay_path"),
                    "status": "dry_run_ready",
                    "warnings": [],
                }
            )
            if args.verbose:
                print(f"[dry-run] {sample_id}: would store 1 segmentation_run and {len(detections)} layout_region rows")
        payload = {
            "generated_at": iso_now(),
            "storage_status": "dry_run",
            "smoke_test_id": smoke_test_id,
            "inference_rerun": False,
            "database_write": False,
            "smoke_test_results_path": str(results_path.relative_to(ROOT)),
            "segmentation_test_inputs_path": str(inputs_path.relative_to(ROOT)),
            "samples": samples_out,
        }
        write_yaml(output_path, payload)
        print("Dry run completed. No database writes were performed.")
        return 0

    with connect() as conn:
        with conn.cursor() as cur:
            for sample_result in smoke_test_results.get("results", []):
                sample_id = sample_result["sample_id"]
                context = contexts[sample_id]
                raw_prediction = load_json((ROOT / sample_result["raw_output_path"]).resolve())
                detections = raw_prediction.get("detections", [])
                existing_run_id = find_existing_run(cur, context, smoke_test_id, smoke_test_results.get("model_id"))
                run_id = upsert_segmentation_run(
                    cur,
                    existing_run_id=existing_run_id,
                    context=context,
                    smoke_test_id=smoke_test_id,
                    smoke_test_results=smoke_test_results,
                    sample_result=sample_result,
                    raw_prediction=raw_prediction,
                    generated_at=generated_at,
                )
                layout_count = replace_layout_regions(cur, run_id, detections)
                samples_out.append(
                    {
                        "sample_id": sample_id,
                        "sample_kind": context.sample_kind,
                        "db_image_asset_id": context.db_image_asset_id,
                        "db_canvas_id": context.db_canvas_id,
                        "db_fragment_id": context.db_fragment_id,
                        "db_segmentation_run_id": run_id,
                        "layout_region_count": layout_count,
                        "detected_labels": sample_result.get("detected_labels", []),
                        "raw_output_path": sample_result.get("raw_output_path"),
                        "overlay_path": sample_result.get("overlay_path"),
                        "status": "matched_and_refreshed" if existing_run_id else "created",
                        "warnings": [],
                    }
                )
                if args.verbose:
                    action = "updated" if existing_run_id else "created"
                    print(f"{sample_id}: {action} segmentation_run {run_id} with {layout_count} layout_region rows")
            conn.commit()

    payload = {
        "generated_at": iso_now(),
        "storage_status": "stored",
        "smoke_test_id": smoke_test_id,
        "inference_rerun": False,
        "database_write": True,
        "smoke_test_results_path": str(results_path.relative_to(ROOT)),
        "segmentation_test_inputs_path": str(inputs_path.relative_to(ROOT)),
        "samples": samples_out,
    }
    write_yaml(output_path, payload)
    write_report(report_path, payload)
    print(f"Stored smoke-test outputs for {len(samples_out)} samples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
