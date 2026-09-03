#!/usr/bin/env python3
"""Run the existing eManuSkript segmentation batch and emit reproducible metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import yaml
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.segmentation_masks import (  # noqa: E402
    mask_pixel_area,
    restore_mask_to_source,
    save_binary_mask,
)

DEFAULT_INPUTS = ROOT / "data/metadata/segmentation_pilot_inputs.yaml"
DEFAULT_RESULTS = ROOT / "data/metadata/segmentation_pilot_results.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "outputs/segmentation_pilot"


FAILURE_STATUSES = {"error", "failure"}


class PageSegmentationError(RuntimeError):
    """Carry the original page failure type and preprocessing state across handlers."""

    def __init__(self, error: Exception, preprocessing: dict[str, Any]):
        super().__init__(str(error))
        self.error_type = type(error).__name__
        self.preprocessing = dict(preprocessing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the existing eManuSkript segmentation workflow on prepared inputs.")
    parser.add_argument("--inputs", default=DEFAULT_INPUTS.as_posix())
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR.as_posix())
    parser.add_argument("--results", default=DEFAULT_RESULTS.as_posix(), help="YAML result manifest path.")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--sample-kind", choices=("all", "full_page", "fragment"), default="all")
    parser.add_argument("--force", action="store_true", help="Ignore cached raw/overlay outputs and rerun inference.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--single-sample-json", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--run-identity-json", default=None, help=argparse.SUPPRESS)
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
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_identity(
    payload: dict[str, Any],
    selected_inputs: list[dict[str, Any]],
    model_path: Path,
    *,
    device: str,
    conf: float,
    imgsz: int,
    software_versions: dict[str, str],
) -> dict[str, Any]:
    source_assets: list[dict[str, Any]] = []
    for sample in sorted(selected_inputs, key=lambda item: item["sample_id"]):
        local_path = ROOT / sample["local_path"]
        if not local_path.is_file():
            raise FileNotFoundError(f"Input image does not exist: {sample['local_path']}")
        source_assets.append(
            {
                "sample_id": sample["sample_id"],
                "db_image_asset_id": sample.get("db_image_asset_id"),
                "db_canvas_id": sample.get("db_canvas_id"),
                "db_manuscript_id": sample.get("db_manuscript_id"),
                "db_repository_id": sample.get("db_repository_id"),
                "manuscript_id": sample.get("manuscript_id"),
                "repository": sample.get("repository"),
                "canvas_identifier": sample.get("canvas_identifier"),
                "canvas_label": sample.get("canvas_label"),
                "sequence_index": sample.get("sequence_index"),
                "dataset_split": sample.get("dataset_split"),
                "source_url": sample.get("source_url"),
                "local_path": sample["local_path"],
                "source_sha256": file_sha256(local_path),
                "source_dimensions_px": sample.get("source_dimensions_px"),
            }
        )
    descriptor = {
        "identity_version": "emanuskript_corpus_run_identity_v0_1",
        "dataset_id": payload.get("dataset_id"),
        "prepared_run_id": payload.get("pilot_run_id"),
        "model_id": payload.get("model_id"),
        "model_path": rel(model_path),
        "model_sha256": file_sha256(model_path),
        "configuration": {
            "device": device,
            "confidence_threshold": conf,
            "imgsz": imgsz,
            "retina_masks": True,
            "preprocessing_max_side": 2048,
            "mask_restoration": "nearest_neighbor_binary_to_original_source_dimensions",
        },
        "software_versions": software_versions,
        "source_assets": source_assets,
    }
    canonical = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "run_identity_sha256": hashlib.sha256(canonical).hexdigest(),
        "descriptor": descriptor,
    }


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
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(confidences),
        "min": round(min(confidences), 6),
        "max": round(max(confidences), 6),
        "mean": round(mean(confidences), 6),
        "median": round(median(confidences), 6),
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


def attach_instance_masks(
    result: Any,
    detections: list[dict[str, Any]],
    *,
    sample_id: str,
    mask_dir: Path,
    preprocessing: dict[str, Any],
    run_provenance: dict[str, Any],
) -> list[dict[str, Any]]:
    """Restore and save one authoritative binary mask for every detection."""
    if not detections:
        return detections
    if result.masks is None or result.masks.data is None:
        raise RuntimeError(f"Segmentation checkpoint returned boxes without masks for {sample_id}")
    mask_tensors = result.masks.data
    if len(mask_tensors) != len(detections):
        raise RuntimeError(
            f"Mask/detection count mismatch for {sample_id}: masks={len(mask_tensors)}, detections={len(detections)}"
        )

    inference_size = tuple(int(value) for value in preprocessing["inference_size"])
    source_size = tuple(int(value) for value in preprocessing["original_size"])
    result_size = (int(result.orig_shape[1]), int(result.orig_shape[0]))
    if result_size != inference_size:
        raise RuntimeError(
            f"Inference result dimensions do not match preprocessing metadata for {sample_id}: "
            f"result={result_size}, preprocessing={inference_size}"
        )

    region_run_provenance = {
        key: value
        for key, value in run_provenance.items()
        if key != "run_identity_descriptor"
    }
    region_run_provenance["run_identity_descriptor_location"] = "results_manifest.run_identity_descriptor"
    enriched: list[dict[str, Any]] = []
    for detection, tensor in zip(detections, mask_tensors):
        array = tensor.detach().cpu().ge(0.5).to(dtype=tensor.dtype).mul(255).byte().numpy()
        model_mask = Image.fromarray(array)
        source_mask = restore_mask_to_source(
            model_mask,
            inference_size=inference_size,
            source_size=source_size,
        )
        index = int(detection["index"])
        mask_path = mask_dir / sample_id / f"region_{index:04d}.png"
        mask_sha256 = save_binary_mask(source_mask, mask_path)
        item = dict(detection)
        item.update(
            {
                "mask_path": rel(mask_path),
                "mask_sha256": mask_sha256,
                "mask_pixel_area": mask_pixel_area(source_mask),
                "mask_dimensions_px": [source_mask.width, source_mask.height],
                "mask_coordinate_space": "original_source_image",
                "mask_value_semantics": "255=region pixel; 0=outside region",
                "mask_threshold": 0.5,
                "segmentation_provenance": {
                    **region_run_provenance,
                    "preprocessing": preprocessing,
                    "model_mask_dimensions_px": [model_mask.width, model_mask.height],
                    "inference_image_dimensions_px": list(inference_size),
                    "restored_source_dimensions_px": list(source_size),
                    "coordinate_restoration": "nearest_neighbor_binary_resize",
                },
            }
        )
        enriched.append(item)
    return enriched


def cached_mask_artifacts_complete(raw_payload: dict[str, Any], expected_run_identity: str) -> bool:
    """Return true only when every cached detection has a valid referenced mask."""
    provenance = raw_payload.get("segmentation_provenance") or {}
    if provenance.get("run_identity_sha256") != expected_run_identity:
        return False
    detections = raw_payload.get("detections", [])
    source_shape = raw_payload.get("orig_shape") or []
    expected_dimensions = [source_shape[1], source_shape[0]] if len(source_shape) == 2 else None
    for detection in detections:
        mask_path = detection.get("mask_path")
        if not mask_path or detection.get("mask_dimensions_px") != expected_dimensions:
            return False
        resolved_mask = ROOT / mask_path
        if not resolved_mask.exists():
            return False
        if not detection.get("mask_sha256") or file_sha256(resolved_mask) != detection["mask_sha256"]:
            return False
        with Image.open(resolved_mask) as mask:
            if mask.mode != "L" or [mask.width, mask.height] != expected_dimensions:
                return False
    return raw_payload.get("status") not in FAILURE_STATUSES


def scale_detections(
    detections: list[dict[str, Any]],
    *,
    scale_x: float,
    scale_y: float,
    source_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    """Convert YOLO boxes to source coordinates and clip them to the source raster."""
    scaled: list[dict[str, Any]] = []
    for detection in detections:
        item = dict(detection)
        bbox_xyxy = detection.get("bbox_xyxy") or []
        bbox_xywh = detection.get("bbox_xywh") or []
        if len(bbox_xyxy) == 4:
            x1 = float(bbox_xyxy[0]) * scale_x
            y1 = float(bbox_xyxy[1]) * scale_y
            x2 = float(bbox_xyxy[2]) * scale_x
            y2 = float(bbox_xyxy[3]) * scale_y
            if source_size is not None:
                width, height = source_size
                x1 = max(0.0, min(float(width), x1))
                y1 = max(0.0, min(float(height), y1))
                x2 = max(0.0, min(float(width), x2))
                y2 = max(0.0, min(float(height), y2))
            if x2 <= x1 or y2 <= y1:
                raise ValueError(
                    f"Detection {detection.get('index')} has an empty bbox after source-coordinate clipping"
                )
            item["bbox_xyxy"] = [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)]
            item["bbox_xywh"] = [
                round((x1 + x2) / 2.0, 3),
                round((y1 + y2) / 2.0, 3),
                round(x2 - x1, 3),
                round(y2 - y1, 3),
            ]
        elif len(bbox_xywh) == 4:
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


def result_from_raw(
    sample: dict[str, Any],
    raw_payload: dict[str, Any],
    raw_path: Path,
    overlay_path: Path,
    *,
    artifact_disposition: str | None = None,
    execution_duration_seconds: float | None = None,
) -> dict[str, Any]:
    detections = raw_payload.get("detections", [])
    detected_labels = sorted({item.get("label", "unknown") for item in detections})
    confidences = [float(item.get("confidence")) for item in detections if item.get("confidence") is not None]
    status = raw_payload.get("status", "success")
    errors = raw_payload.get("errors", [])
    warnings = raw_payload.get("warnings", [])
    provenance = raw_payload.get("segmentation_provenance") or {}
    return {
        "sample_id": sample["sample_id"],
        "sample_kind": sample["sample_kind"],
        "category": sample.get("category"),
        "source": sample.get("source"),
        "repository": sample.get("repository"),
        "source_url": sample.get("source_url"),
        "local_path": sample["local_path"],
        "source_sha256": sample.get("source_sha256"),
        "source_dimensions_px": sample.get("source_dimensions_px"),
        "db_image_asset_id": sample.get("db_image_asset_id"),
        "db_fragment_id": sample.get("db_fragment_id"),
        "db_canvas_id": sample.get("db_canvas_id"),
        "db_manuscript_id": sample.get("db_manuscript_id"),
        "db_repository_id": sample.get("db_repository_id"),
        "manuscript_id": sample.get("manuscript_id"),
        "canvas_identifier": sample.get("canvas_identifier"),
        "canvas_label": sample.get("canvas_label"),
        "sequence_index": sample.get("sequence_index"),
        "dataset_split": sample.get("dataset_split"),
        "run_identity_sha256": provenance.get("run_identity_sha256"),
        "status": status,
        "artifact_disposition": artifact_disposition,
        "execution_duration_seconds": (
            round(execution_duration_seconds, 6) if execution_duration_seconds is not None else None
        ),
        "raw_output_path": rel(raw_path),
        "overlay_path": rel(overlay_path),
        "detected_region_count": len(detections),
        "mask_region_count": sum(bool(item.get("mask_path")) for item in detections),
        "mask_geometry_available": bool(detections) and all(bool(item.get("mask_path")) for item in detections),
        "detected_labels": detected_labels,
        "confidence_summary": confidence_summary(confidences),
        "preprocessing": raw_payload.get("preprocessing"),
        "timing": raw_payload.get("timing"),
        "failure": raw_payload.get("failure"),
        "errors": errors,
        "warnings": warnings,
    }


def run_single_prediction(
    model: Any,
    sample: dict[str, Any],
    output_dir: Path,
    device: str,
    conf: float,
    imgsz: int,
    *,
    force: bool,
    run_provenance: dict[str, Any],
) -> dict[str, Any]:
    image_path = ROOT / sample["local_path"]
    if not image_path.exists():
        raise FileNotFoundError(f"Input image does not exist: {sample['local_path']}")
    raw_dir = output_dir / "raw"
    overlay_dir = output_dir / "overlays"
    mask_dir = output_dir / "masks"
    raw_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{sample['sample_id']}.json"
    overlay_path = overlay_dir / f"{sample['sample_id']}_overlay.jpg"

    if not force and raw_path.exists() and overlay_path.exists():
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        if cached_mask_artifacts_complete(raw_payload, run_provenance["run_identity_sha256"]):
            return result_from_raw(
                sample,
                raw_payload,
                raw_path,
                overlay_path,
                artifact_disposition="reused_checksum_verified",
                execution_duration_seconds=0.0,
            )

    preprocessing: dict[str, Any] = {"status": "not_started"}
    temp_path: Path | None = None
    page_started_at = datetime.now(timezone.utc).isoformat()
    page_wall_started = time.perf_counter()
    try:
        inference_source, preprocessing, temp_path = prepare_inference_source(image_path)
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
        detections = attach_instance_masks(
            result,
            detections,
            sample_id=sample["sample_id"],
            mask_dir=mask_dir,
            preprocessing=preprocessing,
            run_provenance=run_provenance,
        )
        detections = scale_detections(
            detections,
            scale_x=preprocessing["scale_x"],
            scale_y=preprocessing["scale_y"],
            source_size=tuple(preprocessing["original_size"]),
        )
        wall_duration = time.perf_counter() - page_wall_started
        raw_payload = {
            "sample_id": sample["sample_id"],
            "sample_kind": sample["sample_kind"],
            "image_path": sample["local_path"],
            "source_url": sample.get("source_url"),
            "source_sha256": sample.get("source_sha256") or file_sha256(image_path),
            "repository": sample.get("repository"),
            "manuscript_id": sample.get("manuscript_id"),
            "canvas_identifier": sample.get("canvas_identifier"),
            "db_image_asset_id": sample.get("db_image_asset_id"),
            "db_canvas_id": sample.get("db_canvas_id"),
            "dataset_split": sample.get("dataset_split"),
            "orig_shape": [
                int(preprocessing["original_size"][1]),
                int(preprocessing["original_size"][0]),
            ],
            "inference_shape": list(result.orig_shape),
            "speed_ms": result.speed,
            "names": result.names,
            "preprocessing": preprocessing,
            "mask_artifact_directory": rel(mask_dir / sample["sample_id"]),
            "mask_coordinate_space": "original_source_image",
            "segmentation_provenance": run_provenance,
            "timing": {
                "started_at": page_started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "wall_duration_seconds": round(wall_duration, 6),
                "model_speed_ms": result.speed,
            },
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

        return result_from_raw(
            sample,
            raw_payload,
            raw_path,
            overlay_path,
            artifact_disposition="generated",
            execution_duration_seconds=wall_duration,
        )
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, PageSegmentationError):
            raise
        raise PageSegmentationError(exc, preprocessing) from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def build_error_result(
    sample: dict[str, Any],
    output_dir: Path,
    error: Exception,
    run_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    image_path = ROOT / sample["local_path"]
    raw_path = output_dir / "raw" / f"{sample['sample_id']}.json"
    overlay_path = output_dir / "overlays" / f"{sample['sample_id']}_overlay.jpg"
    error_type = getattr(error, "error_type", type(error).__name__)
    error_message_text = str(error)
    error_message = f"{error_type}: {error_message_text}"
    preprocessing = getattr(error, "preprocessing", {"status": "not_available"})
    retry_appropriate = error_type not in {"FileNotFoundError", "UnidentifiedImageError"}
    raw_payload = {
        "sample_id": sample["sample_id"],
        "sample_kind": sample["sample_kind"],
        "image_path": sample["local_path"],
        "source_url": sample.get("source_url"),
        "source_sha256": sample.get("source_sha256"),
        "repository": sample.get("repository"),
        "manuscript_id": sample.get("manuscript_id"),
        "canvas_identifier": sample.get("canvas_identifier"),
        "db_image_asset_id": sample.get("db_image_asset_id"),
        "db_canvas_id": sample.get("db_canvas_id"),
        "dataset_split": sample.get("dataset_split"),
        "preprocessing": preprocessing,
        "status": "failure",
        "failure": {
            "sample_id": sample["sample_id"],
            "manuscript_id": sample.get("manuscript_id"),
            "source_asset_id": sample.get("db_image_asset_id"),
            "error_type": error_type,
            "error_message": error_message_text,
            "preprocessing_state": preprocessing,
            "retry_appropriate": retry_appropriate,
        },
        "errors": [error_message],
        "warnings": ["Segmentation inference failed for this sample."],
        "segmentation_provenance": {
            "run_identity_sha256": (run_identity or {}).get("run_identity_sha256"),
            "run_identity_descriptor": (run_identity or {}).get("descriptor"),
        },
        "detections": [],
    }
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
    if image_path.is_file():
        try:
            render_failure_overlay(image_path, overlay_path, "Segmentation failed")
        except Exception as overlay_error:  # noqa: BLE001
            raw_payload["warnings"].append(
                f"Failure overlay could not be rendered: {type(overlay_error).__name__}: {overlay_error}"
            )
            raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
    return result_from_raw(
        sample,
        raw_payload,
        raw_path,
        overlay_path,
        artifact_disposition="failed",
    )


def run_sample_subprocess(
    sample: dict[str, Any],
    inputs_path: Path,
    output_dir: Path,
    device: str,
    conf: float,
    imgsz: int,
    *,
    force: bool,
    run_identity: dict[str, Any],
) -> dict[str, Any]:
    execution_started = time.perf_counter()
    raw_path = output_dir / "raw" / f"{sample['sample_id']}.json"
    overlay_path = output_dir / "overlays" / f"{sample['sample_id']}_overlay.jpg"
    if not force and raw_path.exists() and overlay_path.exists():
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        if cached_mask_artifacts_complete(raw_payload, run_identity["run_identity_sha256"]):
            return result_from_raw(
                sample,
                raw_payload,
                raw_path,
                overlay_path,
                artifact_disposition="reused_checksum_verified",
                execution_duration_seconds=time.perf_counter() - execution_started,
            )

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
        "--run-identity-json",
        json.dumps(run_identity),
    ]
    if force:
        command.append("--force")
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        message = stderr or stdout or f"subprocess exited with code {completed.returncode}"
        raise RuntimeError(message)
    if not raw_path.exists() or not overlay_path.exists():
        raise RuntimeError(f"subprocess completed but outputs are missing for {sample['sample_id']}")
    raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    disposition = "failed" if raw_payload.get("status") in FAILURE_STATUSES else "generated"
    return result_from_raw(
        sample,
        raw_payload,
        raw_path,
        overlay_path,
        artifact_disposition=disposition,
        execution_duration_seconds=time.perf_counter() - execution_started,
    )


def main() -> int:
    args = parse_args()
    inputs_path = Path(args.inputs)
    output_dir = Path(args.output_dir)
    results_path = Path(args.results)
    if not inputs_path.is_absolute():
        inputs_path = ROOT / inputs_path
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    if not results_path.is_absolute():
        results_path = ROOT / results_path

    if args.single_sample_json:
        YOLO, ultralytics, torch = require_ultralytics()
        payload = load_yaml(inputs_path)
        model_path = ROOT / payload["model_path"]
        model = YOLO(str(model_path))
        sample = json.loads(args.single_sample_json)
        identity = (
            json.loads(args.run_identity_json)
            if args.run_identity_json
            else build_run_identity(
                payload,
                payload.get("selected_inputs", []),
                model_path,
                device=args.device,
                conf=args.conf,
                imgsz=args.imgsz,
                software_versions={
                    "ultralytics": str(ultralytics.__version__),
                    "torch": str(torch.__version__),
                },
            )
        )
        run_provenance = {
            "pilot_run_id": payload["pilot_run_id"],
            "model_id": payload["model_id"],
            "model_path": payload["model_path"],
            "device": args.device,
            "confidence_threshold": args.conf,
            "imgsz": args.imgsz,
            "retina_masks": True,
            "ultralytics_version": str(ultralytics.__version__),
            "torch_version": str(torch.__version__),
            "run_identity_sha256": identity["run_identity_sha256"],
            "run_identity_descriptor": identity["descriptor"],
        }
        try:
            run_single_prediction(
                model,
                sample,
                output_dir,
                args.device,
                args.conf,
                args.imgsz,
                force=args.force,
                run_provenance=run_provenance,
            )
        except Exception as exc:  # noqa: BLE001
            build_error_result(sample, output_dir, exc, identity)
        return 0

    YOLO, ultralytics, torch = require_ultralytics()
    payload = load_yaml(inputs_path)
    all_inputs = payload.get("selected_inputs", [])
    if not all_inputs:
        raise RuntimeError("Segmentation input manifest contains no selected inputs")
    selected_inputs = [
        sample for sample in all_inputs if args.sample_kind == "all" or sample.get("sample_kind") == args.sample_kind
    ]
    model_path = ROOT / payload["model_path"]
    if not model_path.exists():
        raise FileNotFoundError(f"Model path does not exist: {payload['model_path']}")
    run_identity = build_run_identity(
        payload,
        all_inputs,
        model_path,
        device=args.device,
        conf=args.conf,
        imgsz=args.imgsz,
        software_versions={
            "ultralytics": str(ultralytics.__version__),
            "torch": str(torch.__version__),
        },
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw").mkdir(parents=True, exist_ok=True)
    (output_dir / "overlays").mkdir(parents=True, exist_ok=True)
    (output_dir / "masks").mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)

    execution_started_at = datetime.now(timezone.utc).isoformat()
    execution_wall_started = time.perf_counter()
    refreshed_results: dict[str, dict[str, Any]] = {}
    for sample in selected_inputs:
        try:
            result_payload = run_sample_subprocess(
                sample,
                inputs_path,
                output_dir,
                args.device,
                args.conf,
                args.imgsz,
                force=args.force,
                run_identity=run_identity,
            )
        except Exception as exc:  # noqa: BLE001
            result_payload = build_error_result(sample, output_dir, exc, run_identity)
        refreshed_results[sample["sample_id"]] = result_payload
        if args.verbose:
            labels = ", ".join(result_payload["detected_labels"]) if result_payload["detected_labels"] else "none"
            print(
                f"{sample['sample_id']}: status={result_payload['status']} "
                f"detections={result_payload['detected_region_count']} labels={labels}"
            )
            if result_payload["errors"]:
                print(f"  errors={'; '.join(result_payload['errors'])}")

    existing_results: dict[str, dict[str, Any]] = {}
    if results_path.exists() and args.sample_kind != "all":
        previous_payload = load_yaml(results_path)
        existing_results = {item["sample_id"]: item for item in previous_payload.get("results", [])}
    results: list[dict[str, Any]] = []
    for sample in all_inputs:
        sample_id = sample["sample_id"]
        if sample_id in refreshed_results:
            results.append(refreshed_results[sample_id])
        elif sample_id in existing_results:
            results.append(existing_results[sample_id])
        else:
            raise RuntimeError(f"No refreshed or existing pilot result available for {sample_id}")

    execution_wall_duration = time.perf_counter() - execution_wall_started
    preprocessing_counts = Counter(
        str((result.get("preprocessing") or {}).get("strategy", "unavailable"))
        for result in results
    )
    disposition_counts = Counter(str(result.get("artifact_disposition") or "unknown") for result in results)
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_multiplier = 1 if sys.platform == "darwin" else 1024
    run_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pilot_run_id": payload["pilot_run_id"],
        "dataset_id": payload.get("dataset_id", "initial_sample_dataset_v0_1"),
        "model_id": payload["model_id"],
        "model_path": payload["model_path"],
        "model_sha256": run_identity["descriptor"]["model_sha256"],
        "run_identity_sha256": run_identity["run_identity_sha256"],
        "run_identity_descriptor": run_identity["descriptor"],
        "inference_run": True,
        "segmentation_run": True,
        "rerun_scope": args.sample_kind,
        "selected_run_count": len(selected_inputs),
        "mask_artifact_count": sum(int(result.get("mask_region_count", 0)) for result in results),
        "device": args.device,
        "confidence_threshold": args.conf,
        "imgsz": args.imgsz,
        "output_dir": rel(output_dir),
        "environment": {
            "python_version": platform.python_version(),
            "torch_version": str(torch.__version__),
            "ultralytics_version": str(ultralytics.__version__),
        },
        "performance": {
            "execution_started_at": execution_started_at,
            "execution_completed_at": datetime.now(timezone.utc).isoformat(),
            "total_wall_duration_seconds": round(execution_wall_duration, 6),
            "mean_wall_time_per_selected_page_seconds": round(
                execution_wall_duration / len(selected_inputs), 6
            ),
            "requested_device": args.device,
            "host_machine": platform.machine(),
            "processor": platform.processor() or None,
            "torch_cuda_available": bool(torch.cuda.is_available()),
            "torch_mps_available": bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            ),
            "artifact_disposition_counts": dict(sorted(disposition_counts.items())),
            "inference_executed_page_count": disposition_counts.get("generated", 0),
            "artifact_reused_page_count": disposition_counts.get("reused_checksum_verified", 0),
            "failed_page_count": disposition_counts.get("failed", 0),
            "preprocessing_strategy_counts": dict(sorted(preprocessing_counts.items())),
            "downscaled_page_count": preprocessing_counts.get("downscaled_temp_copy", 0),
            "observed_child_process_max_rss_bytes": int(child_usage.ru_maxrss * rss_multiplier),
            "memory_observation_method": "getrusage_RUSAGE_CHILDREN_ru_maxrss",
        },
        "results": results,
    }
    preserve_existing_manifest = False
    if results_path.is_file() and not args.force and disposition_counts == {"reused_checksum_verified": len(results)}:
        existing_payload = load_yaml(results_path)
        existing_ids = [item.get("sample_id") for item in existing_payload.get("results", [])]
        current_ids = [item.get("sample_id") for item in results]
        preserve_existing_manifest = (
            existing_payload.get("run_identity_sha256") == run_identity["run_identity_sha256"]
            and existing_ids == current_ids
        )
    if not preserve_existing_manifest:
        write_yaml(results_path, run_payload)
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
                    f"total_wall_duration_seconds={run_payload['performance']['total_wall_duration_seconds']}",
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
    print(f"Wrote {rel(results_path)}")
    if preserve_existing_manifest:
        print("Unchanged checksum-verified rerun reused every page and preserved the results manifest bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
