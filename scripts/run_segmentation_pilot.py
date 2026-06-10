#!/usr/bin/env python3
"""Run the full pilot segmentation batch and emit reproducible result metadata."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = ROOT / "data/metadata/segmentation_pilot_inputs.yaml"
DEFAULT_RESULTS = ROOT / "data/metadata/segmentation_pilot_results.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "outputs/segmentation_pilot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full 10-item pilot segmentation inference.")
    parser.add_argument("--inputs", default=DEFAULT_INPUTS.as_posix())
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR.as_posix())
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--single-sample-json", default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def require_ultralytics():
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    try:
        import torch
        import ultralytics
        from ultralytics import YOLO
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "ultralytics is required for the pilot run. Install it with `python3 -m pip install -r requirements.txt`."
        ) from exc
    return YOLO, ultralytics, torch


def confidence_summary(confidences: list[float]) -> dict[str, Any]:
    if not confidences:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(confidences),
        "min": round(min(confidences), 6),
        "max": round(max(confidences), 6),
        "mean": round(mean(confidences), 6),
    }


def raw_detection_payload(result) -> tuple[list[dict[str, Any]], list[str], list[float]]:
    detections: list[dict[str, Any]] = []
    labels: list[str] = []
    confidences: list[float] = []

    if result.boxes is None or len(result.boxes) == 0:
        return detections, labels, confidences

    xyxy = result.boxes.xyxy.cpu().tolist()
    xywh = result.boxes.xywh.cpu().tolist()
    cls_ids = [int(value) for value in result.boxes.cls.cpu().tolist()]
    confs = [float(value) for value in result.boxes.conf.cpu().tolist()]
    for index, class_id in enumerate(cls_ids):
        label = result.names.get(class_id, str(class_id))
        labels.append(label)
        confidences.append(confs[index])
        detections.append(
            {
                "index": index,
                "class_id": class_id,
                "label": label,
                "confidence": round(confs[index], 6),
                "bbox_xyxy": [round(float(value), 3) for value in xyxy[index]],
                "bbox_xywh": [round(float(value), 3) for value in xywh[index]],
            }
        )

    return detections, sorted(set(labels)), confidences


def scale_detections(detections: list[dict[str, Any]], *, scale_x: float, scale_y: float) -> list[dict[str, Any]]:
    """Convert YOLO boxes from inference-image coordinates back to original-image coordinates."""
    scaled: list[dict[str, Any]] = []
    for detection in detections:
        item = dict(detection)
        bbox_xyxy = detection.get("bbox_xyxy") or []
        bbox_xywh = detection.get("bbox_xywh") or []
        if len(bbox_xyxy) == 4:
            item["bbox_xyxy"] = [
                round(float(bbox_xyxy[0]) * scale_x, 3),
                round(float(bbox_xyxy[1]) * scale_y, 3),
                round(float(bbox_xyxy[2]) * scale_x, 3),
                round(float(bbox_xyxy[3]) * scale_y, 3),
            ]
        if len(bbox_xywh) == 4:
            item["bbox_xywh"] = [
                round(float(bbox_xywh[0]) * scale_x, 3),
                round(float(bbox_xywh[1]) * scale_y, 3),
                round(float(bbox_xywh[2]) * scale_x, 3),
                round(float(bbox_xywh[3]) * scale_y, 3),
            ]
        scaled.append(item)
    return scaled


def overlay_color(class_id: int) -> tuple[int, int, int]:
    palette = [
        (220, 20, 60),
        (0, 128, 255),
        (34, 139, 34),
        (255, 140, 0),
        (138, 43, 226),
        (0, 180, 180),
        (205, 92, 92),
        (70, 130, 180),
    ]
    return palette[class_id % len(palette)]


def render_overlay(image_path: Path, detections: list[dict[str, Any]], overlay_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for detection in detections:
        class_id = int(detection["class_id"])
        color = overlay_color(class_id)
        fill = (*color, 40)
        outline = (*color, 255)
        bbox = detection["bbox_xyxy"]
        draw.rectangle(bbox, outline=outline, width=3, fill=fill)
        label = f"{detection['label']} {detection['confidence']:.2f}"
        text_x = bbox[0]
        text_y = max(0, bbox[1] - 18)
        draw.rectangle([text_x, text_y, text_x + (8 * len(label)) + 8, text_y + 16], fill=(*color, 180))
        draw.text((text_x + 4, text_y + 2), label, fill=(255, 255, 255, 255))
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(overlay_path, format="JPEG", quality=85)


def render_failure_overlay(image_path: Path, overlay_path: Path, message: str) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    banner_height = 44
    draw.rectangle([0, 0, image.width, banner_height], fill=(160, 0, 0, 220))
    draw.text((12, 12), message[:120], fill=(255, 255, 255, 255))
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(overlay_path, format="JPEG", quality=85)


def prepare_inference_source(image_path: Path, max_side: int = 2048) -> tuple[Path, dict[str, Any], Path | None]:
    """Use a bounded temporary image for very large inputs while preserving original output coordinates."""
    image = Image.open(image_path).convert("RGB")
    original_width, original_height = image.size
    largest_side = max(original_width, original_height)
    if largest_side <= max_side:
        return image_path, {
            "strategy": "original",
            "original_size": [original_width, original_height],
            "inference_size": [original_width, original_height],
            "scale_x": 1.0,
            "scale_y": 1.0,
        }, None

    scale = max_side / float(largest_side)
    resized_width = max(1, int(round(original_width * scale)))
    resized_height = max(1, int(round(original_height * scale)))
    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    fd, temp_name = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    temp_path = Path(temp_name)
    resized.save(temp_path, format="JPEG", quality=90)
    return temp_path, {
        "strategy": "downscaled_temp_copy",
        "original_size": [original_width, original_height],
        "inference_size": [resized_width, resized_height],
        "scale_x": original_width / float(resized_width),
        "scale_y": original_height / float(resized_height),
    }, temp_path


def result_from_raw(sample: dict[str, Any], raw_payload: dict[str, Any], raw_path: Path, overlay_path: Path) -> dict[str, Any]:
    detections = raw_payload.get("detections", [])
    detected_labels = sorted({item.get("label", "unknown") for item in detections})
    confidences = [float(item.get("confidence")) for item in detections if item.get("confidence") is not None]
    status = raw_payload.get("status", "success")
    errors = raw_payload.get("errors", [])
    warnings = raw_payload.get("warnings", [])
    return {
        "sample_id": sample["sample_id"],
        "sample_kind": sample["sample_kind"],
        "category": sample.get("category"),
        "source": sample.get("source"),
        "source_url": sample.get("source_url"),
        "local_path": sample["local_path"],
        "db_image_asset_id": sample.get("db_image_asset_id"),
        "db_fragment_id": sample.get("db_fragment_id"),
        "db_canvas_id": sample.get("db_canvas_id"),
        "status": status,
        "raw_output_path": rel(raw_path),
        "overlay_path": rel(overlay_path),
        "detected_region_count": len(detections),
        "detected_labels": detected_labels,
        "confidence_summary": confidence_summary(confidences),
        "errors": errors,
        "warnings": warnings,
    }


def run_single_prediction(model, sample: dict[str, Any], output_dir: Path, device: str, conf: float, imgsz: int) -> dict[str, Any]:
    image_path = ROOT / sample["local_path"]
    if not image_path.exists():
        raise FileNotFoundError(f"Input image does not exist: {sample['local_path']}")
    raw_dir = output_dir / "raw"
    overlay_dir = output_dir / "overlays"
    raw_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{sample['sample_id']}.json"
    overlay_path = overlay_dir / f"{sample['sample_id']}_overlay.jpg"

    if raw_path.exists() and overlay_path.exists():
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        # Cached failures should not block a later retry after the large-image guard changes.
        if raw_payload.get("status") != "error":
            return result_from_raw(sample, raw_payload, raw_path, overlay_path)

    inference_source, preprocessing, temp_path = prepare_inference_source(image_path)
    try:
        results = model.predict(
            source=str(inference_source),
            device=device,
            conf=conf,
            imgsz=imgsz,
            verbose=False,
            retina_masks=True,
            save=False,
        )
        if len(results) != 1:
            raise RuntimeError(f"Expected exactly one result for {sample['sample_id']}, got {len(results)}")
        result = results[0]

        detections, _, _ = raw_detection_payload(result)
        detections = scale_detections(
            detections,
            scale_x=preprocessing["scale_x"],
            scale_y=preprocessing["scale_y"],
        )
        raw_payload = {
            "sample_id": sample["sample_id"],
            "sample_kind": sample["sample_kind"],
            "image_path": sample["local_path"],
            "orig_shape": [
                int(preprocessing["original_size"][1]),
                int(preprocessing["original_size"][0]),
            ],
            "inference_shape": list(result.orig_shape),
            "speed_ms": result.speed,
            "names": result.names,
            "preprocessing": preprocessing,
            "status": "success",
            "errors": [],
            "warnings": [],
            "detections": detections,
        }
        raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
        render_overlay(image_path, detections, overlay_path)

        warnings: list[str] = []
        if not detections:
            warnings.append("No regions detected above the configured confidence threshold.")
            raw_payload["warnings"] = warnings
            raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")

        return result_from_raw(sample, raw_payload, raw_path, overlay_path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def build_error_result(sample: dict[str, Any], output_dir: Path, error: Exception) -> dict[str, Any]:
    image_path = ROOT / sample["local_path"]
    raw_path = output_dir / "raw" / f"{sample['sample_id']}.json"
    overlay_path = output_dir / "overlays" / f"{sample['sample_id']}_overlay.jpg"
    error_message = f"{type(error).__name__}: {error}"
    raw_payload = {
        "sample_id": sample["sample_id"],
        "sample_kind": sample["sample_kind"],
        "image_path": sample["local_path"],
        "status": "error",
        "errors": [error_message],
        "warnings": ["Segmentation inference failed for this sample."],
        "detections": [],
    }
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
    render_failure_overlay(image_path, overlay_path, "Segmentation failed")
    return result_from_raw(sample, raw_payload, raw_path, overlay_path)


def run_sample_subprocess(sample: dict[str, Any], inputs_path: Path, output_dir: Path, device: str, conf: float, imgsz: int) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--inputs",
        str(inputs_path.relative_to(ROOT)),
        "--output-dir",
        str(output_dir.relative_to(ROOT)),
        "--device",
        device,
        "--conf",
        str(conf),
        "--imgsz",
        str(imgsz),
        "--single-sample-json",
        json.dumps(sample),
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    raw_path = output_dir / "raw" / f"{sample['sample_id']}.json"
    overlay_path = output_dir / "overlays" / f"{sample['sample_id']}_overlay.jpg"
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        message = stderr or stdout or f"subprocess exited with code {completed.returncode}"
        raise RuntimeError(message)
    if not raw_path.exists() or not overlay_path.exists():
        raise RuntimeError(f"subprocess completed but outputs are missing for {sample['sample_id']}")
    raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    return result_from_raw(sample, raw_payload, raw_path, overlay_path)


def main() -> int:
    args = parse_args()
    inputs_path = ROOT / Path(args.inputs)
    output_dir = ROOT / Path(args.output_dir)

    if args.single_sample_json:
        YOLO, _, _ = require_ultralytics()
        payload = load_yaml(inputs_path)
        model_path = ROOT / payload["model_path"]
        model = YOLO(str(model_path))
        sample = json.loads(args.single_sample_json)
        run_single_prediction(model, sample, output_dir, args.device, args.conf, args.imgsz)
        return 0

    YOLO, ultralytics, torch = require_ultralytics()
    payload = load_yaml(inputs_path)
    selected_inputs = payload.get("selected_inputs", [])
    if len(selected_inputs) != 10:
        raise RuntimeError(f"Expected exactly 10 pilot inputs, found {len(selected_inputs)}")
    model_path = ROOT / payload["model_path"]
    if not model_path.exists():
        raise FileNotFoundError(f"Model path does not exist: {payload['model_path']}")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw").mkdir(parents=True, exist_ok=True)
    (output_dir / "overlays").mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for sample in selected_inputs:
        try:
            result_payload = run_sample_subprocess(sample, inputs_path, output_dir, args.device, args.conf, args.imgsz)
        except Exception as exc:  # noqa: BLE001
            result_payload = build_error_result(sample, output_dir, exc)
        results.append(result_payload)
        if args.verbose:
            labels = ", ".join(result_payload["detected_labels"]) if result_payload["detected_labels"] else "none"
            print(
                f"{sample['sample_id']}: status={result_payload['status']} "
                f"detections={result_payload['detected_region_count']} labels={labels}"
            )
            if result_payload["errors"]:
                print(f"  errors={'; '.join(result_payload['errors'])}")

    run_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pilot_run_id": payload["pilot_run_id"],
        "dataset_id": "initial_sample_dataset_v0_1",
        "model_id": payload["model_id"],
        "model_path": payload["model_path"],
        "inference_run": True,
        "segmentation_run": True,
        "device": args.device,
        "confidence_threshold": args.conf,
        "imgsz": args.imgsz,
        "output_dir": rel(output_dir),
        "environment": {
            "python_version": platform.python_version(),
            "torch_version": str(torch.__version__),
            "ultralytics_version": str(ultralytics.__version__),
        },
        "results": results,
    }
    write_yaml(DEFAULT_RESULTS, run_payload)
    write_text(
        output_dir / "logs" / "segmentation_pilot.log",
        "\n".join(
            [
                f"generated_at={run_payload['generated_at']}",
                f"pilot_run_id={run_payload['pilot_run_id']}",
                f"model_id={run_payload['model_id']}",
                f"device={run_payload['device']}",
                f"confidence_threshold={run_payload['confidence_threshold']}",
                f"imgsz={run_payload['imgsz']}",
                f"ultralytics_version={run_payload['environment']['ultralytics_version']}",
                f"torch_version={run_payload['environment']['torch_version']}",
            ]
        ),
    )
    print(f"Pilot segmentation completed for {len(results)} inputs.")
    print(f"Model: {run_payload['model_id']} ({run_payload['model_path']})")
    print(f"Device: {run_payload['device']} | conf={args.conf} | imgsz={args.imgsz}")
    for result in results:
        labels = ", ".join(result["detected_labels"]) if result["detected_labels"] else "none"
        print(f"- {result['sample_id']}: {result['detected_region_count']} detections | labels={labels}")
        print(f"  raw={result['raw_output_path']}")
        print(f"  overlay={result['overlay_path']}")
    print(f"Wrote {rel(DEFAULT_RESULTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
