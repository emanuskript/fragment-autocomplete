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


DEFAULT_RESULTS = ROOT / "data/metadata/segmentation_pilot_results.yaml"
DEFAULT_INPUTS = ROOT / "data/metadata/segmentation_pilot_inputs.yaml"
DEFAULT_STORAGE_RESULTS = ROOT / "data/metadata/segmentation_pilot_storage_results.yaml"
DEFAULT_REPORT = ROOT / "docs/11_full_pilot_segmentation_report.md"


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
    parser = argparse.ArgumentParser(description="Store full pilot segmentation outputs in PostgreSQL/PostGIS.")
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
    contexts: dict[str, SampleContext] = {}
    for item in inputs_yaml.get("selected_inputs", []):
        contexts[item["sample_id"]] = SampleContext(
            sample_id=item["sample_id"],
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


def find_existing_run(cur: Any, context: SampleContext, pilot_run_id: str, model_name: str) -> str | None:
    cur.execute(
        """
        SELECT id
        FROM segmentation_run
        WHERE image_asset_id = %s
          AND COALESCE(fragment_id::text, '') = COALESCE(%s, '')
          AND model_name = %s
          AND parameters->>'pilot_run_id' = %s
          AND parameters->>'sample_id' = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (
            context.db_image_asset_id,
            context.db_fragment_id,
            model_name,
            pilot_run_id,
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
    pilot_run_id: str,
    pilot_results: dict[str, Any],
    sample_result: dict[str, Any],
    raw_prediction: dict[str, Any],
    generated_at: str,
) -> str:
    sample_status = sample_result.get("status", "success")
    # A failed sample should stay visible as failed in the database; otherwise the viewer suggests
    # the run completed normally even when no layout regions were produced.
    db_status = {
        "success": "completed",
        "warning": "completed",
        "error": "failed",
    }.get(sample_status, "completed")
    parameters = {
        "pilot_run_id": pilot_run_id,
        "sample_id": context.sample_id,
        "sample_kind": context.sample_kind,
        "source_url": context.source_url,
        "local_path": context.local_path,
        "overlay_path": sample_result.get("overlay_path"),
        "raw_output_path": sample_result.get("raw_output_path"),
        "results_yaml_path": str(Path(pilot_results["_results_path"]).relative_to(ROOT)),
        "device": pilot_results.get("device"),
        "confidence_threshold": pilot_results.get("confidence_threshold"),
        "imgsz": pilot_results.get("imgsz"),
        "db_canvas_id": context.db_canvas_id,
        "db_fragment_id": context.db_fragment_id,
        "db_image_asset_id": context.db_image_asset_id,
        "category": context.category,
        "source": context.source,
        "rights_review_status": context.rights_review_status,
        "access_level": context.access_level,
        "dataset_id": pilot_results.get("dataset_id"),
    }
    raw_output = {
        "sample_id": context.sample_id,
        "sample_kind": context.sample_kind,
        "source_url": context.source_url,
        "local_path": context.local_path,
        "raw_output_path": sample_result.get("raw_output_path"),
        "overlay_path": sample_result.get("overlay_path"),
        "raw_prediction": raw_prediction,
        "pilot_result": sample_result,
    }
    values = (
        context.db_image_asset_id,
        context.db_fragment_id,
        pilot_results.get("model_id"),
        pilot_results.get("environment", {}).get("ultralytics_version"),
        pilot_results.get("model_path"),
        json.dumps(parameters),
        db_status,
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


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(to_plain_data(payload), handle, sort_keys=False, allow_unicode=True)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Fragment Autocomplete — Full Pilot Segmentation Report",
        "",
        "## Purpose",
        "Document the full 10-item pilot segmentation run and the subsequent PostgreSQL/PostGIS storage step.",
        "",
        "## Scope",
        "Segmentation was run on the 10-item pilot dataset only. No training was performed, and no artificial fragment generation, reconstruction, retrieval, MSI workflow, or CoMMA workflow was implemented here.",
        "",
        "## Input Dataset",
        f"- Pilot run ID: `{payload['pilot_run_id']}`",
        f"- Pilot inputs: `{payload['pilot_inputs_path']}`",
        f"- Pilot results: `{payload['pilot_results_path']}`",
        "",
        "## Model Used",
        f"- Model ID: `{payload['model_id']}`",
        f"- Model path: `{payload['model_path']}`",
        "",
        "## Inference Settings",
        f"- Device: `{payload['device']}`",
        f"- Confidence threshold: `{payload['confidence_threshold']}`",
        f"- Image size: `{payload['imgsz']}`",
        "",
        "## Per-sample Results Table",
        "",
        "| Sample | Kind | Regions | Labels | Status | Warnings |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    all_labels: set[str] = set()
    for sample in payload["samples"]:
        labels = ", ".join(sample["detected_labels"]) if sample["detected_labels"] else "none"
        all_labels.update(sample["detected_labels"])
        warnings_text = "; ".join(sample.get("warnings", [])) if sample.get("warnings") else ""
        lines.append(
            f"| `{sample['sample_id']}` | `{sample['sample_kind']}` | {sample['layout_region_count']} | {labels} | `{sample['status']}` | {warnings_text} |"
        )
    lines.extend(
        [
            "",
            "## Detected Labels Summary",
            f"- Unique labels across the pilot run: {', '.join(sorted(all_labels)) if all_labels else 'none'}",
            "",
            "## Output Paths",
        ]
    )
    for sample in payload["samples"]:
        lines.append(f"- `{sample['sample_id']}` raw: `{sample['raw_output_path']}`")
        lines.append(f"- `{sample['sample_id']}` overlay: `{sample['overlay_path']}`")
    lines.extend(
        [
            "",
            "## Database Storage Summary",
            f"- Stored sample count: `{len(payload['samples'])}`",
            "- Tables written: `segmentation_run`, `layout_region`",
            "- Geometry strategy: SRID 0 polygons derived from bbox coordinates where persisted mask polygons were unavailable.",
            "",
            "## Viewer Update",
            "The local Streamlit viewer now lists both smoke-test and full-pilot segmentation runs, supports filtering by run type, and allows selecting multiple runs for the same sample.",
            "",
            "## Known Issues",
            "- The pilot run preserves outputs locally and in PostgreSQL/PostGIS only; it does not provide a production UI.",
            "- The viewer is for local development/demo use and remains read-only.",
        ]
    )
    for sample in payload["samples"]:
        if sample.get("warnings"):
            lines.append(f"- `{sample['sample_id']}`: {'; '.join(sample['warnings'])}")
    lines.extend(
        [
            "",
            "## What Has Not Been Implemented",
            "- No artificial fragment generation was implemented.",
            "- No reconstruction was implemented.",
            "- No retrieval was implemented.",
            "- No MSI or CoMMA workflow was implemented.",
            "",
            "## Next Step",
            "Build the artificial fragment generator for complete-page samples.",
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
    pilot_results = load_yaml(results_path)
    pilot_results["_results_path"] = str(results_path)
    inputs_yaml = load_yaml(inputs_path)
    contexts = normalize_inputs(inputs_yaml)
    pilot_run_id = pilot_results["pilot_run_id"]
    generated_at = pilot_results.get("generated_at") or iso_now()
    samples_out: list[dict[str, Any]] = []

    if args.dry_run:
        for sample_result in pilot_results.get("results", []):
            context = contexts[sample_result["sample_id"]]
            raw_prediction = load_json((ROOT / sample_result["raw_output_path"]).resolve())
            detections = raw_prediction.get("detections", [])
            samples_out.append(
                {
                    "sample_id": context.sample_id,
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
                    "warnings": sample_result.get("warnings", []),
                }
            )
            if args.verbose:
                print(f"[dry-run] {context.sample_id}: would store 1 segmentation_run and {len(detections)} layout_region rows")
        payload = {
            "generated_at": iso_now(),
            "storage_status": "dry_run",
            "pilot_run_id": pilot_run_id,
            "inference_rerun": False,
            "database_write": False,
            "pilot_results_path": str(results_path.relative_to(ROOT)),
            "pilot_inputs_path": str(inputs_path.relative_to(ROOT)),
            "samples": samples_out,
        }
        write_yaml(output_path, payload)
        print("Dry run completed. No database writes were performed.")
        return 0

    with connect() as conn:
        with conn.cursor() as cur:
            for sample_result in pilot_results.get("results", []):
                context = contexts[sample_result["sample_id"]]
                raw_prediction = load_json((ROOT / sample_result["raw_output_path"]).resolve())
                detections = raw_prediction.get("detections", [])
                existing_run_id = find_existing_run(cur, context, pilot_run_id, pilot_results.get("model_id"))
                run_id = upsert_segmentation_run(
                    cur,
                    existing_run_id=existing_run_id,
                    context=context,
                    pilot_run_id=pilot_run_id,
                    pilot_results=pilot_results,
                    sample_result=sample_result,
                    raw_prediction=raw_prediction,
                    generated_at=generated_at,
                )
                layout_count = replace_layout_regions(cur, run_id, detections)
                samples_out.append(
                    {
                        "sample_id": context.sample_id,
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
                        "warnings": sample_result.get("warnings", []),
                    }
                )
                if args.verbose:
                    action = "updated" if existing_run_id else "created"
                    print(f"{context.sample_id}: {action} segmentation_run {run_id} with {layout_count} layout_region rows")
            conn.commit()

    payload = {
        "generated_at": iso_now(),
        "storage_status": "stored",
        "pilot_run_id": pilot_run_id,
        "dataset_id": pilot_results.get("dataset_id"),
        "model_id": pilot_results.get("model_id"),
        "model_path": pilot_results.get("model_path"),
        "device": pilot_results.get("device"),
        "confidence_threshold": pilot_results.get("confidence_threshold"),
        "imgsz": pilot_results.get("imgsz"),
        "inference_rerun": False,
        "database_write": True,
        "pilot_results_path": str(results_path.relative_to(ROOT)),
        "pilot_inputs_path": str(inputs_path.relative_to(ROOT)),
        "samples": samples_out,
    }
    write_yaml(output_path, payload)
    write_report(report_path, payload)
    print(f"Stored pilot segmentation outputs for {len(samples_out)} samples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
