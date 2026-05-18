#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = ROOT / "data/metadata/segmentation_test_inputs.yaml"
DEFAULT_RESULTS = ROOT / "data/metadata/segmentation_smoke_test_results.yaml"
DEFAULT_REPORT = ROOT / "docs/08_segmentation_smoke_test_report.md"
DEFAULT_OUTPUT_DIR = ROOT / "outputs/segmentation_smoke_test"


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run a controlled segmentation smoke test on prepared inputs.")
  parser.add_argument("--inputs", default=DEFAULT_INPUTS.as_posix())
  parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR.as_posix())
  parser.add_argument("--device", default="cpu")
  parser.add_argument("--conf", type=float, default=0.25)
  parser.add_argument("--imgsz", type=int, default=320)
  parser.add_argument("--verbose", action="store_true")
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
  try:
    import torch
    from ultralytics import YOLO
    import ultralytics
  except Exception as exc:  # noqa: BLE001
    raise RuntimeError(
      "ultralytics is required for the smoke test. Install it with `python3 -m pip install -r requirements.txt`."
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


def run_single_prediction(model, sample: dict[str, Any], output_dir: Path, device: str, conf: float, imgsz: int) -> dict[str, Any]:
  image_path = ROOT / sample["local_path"]
  if not image_path.exists():
    raise FileNotFoundError(f"Input image does not exist: {sample['local_path']}")

  results = model.predict(
    source=str(image_path),
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
  raw_dir = output_dir / "raw"
  overlay_dir = output_dir / "overlays"
  raw_dir.mkdir(parents=True, exist_ok=True)
  overlay_dir.mkdir(parents=True, exist_ok=True)

  raw_path = raw_dir / f"{sample['sample_id']}.json"
  overlay_path = overlay_dir / f"{sample['sample_id']}_overlay.jpg"

  detections, labels, confidences = raw_detection_payload(result)
  raw_payload = {
    "sample_id": sample["sample_id"],
    "sample_kind": sample["sample_kind"],
    "image_path": sample["local_path"],
    "orig_shape": list(result.orig_shape),
    "speed_ms": result.speed,
    "names": result.names,
    "detections": detections,
  }
  raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")

  render_overlay(image_path, detections, overlay_path)

  warnings: list[str] = []
  if not detections:
    warnings.append("No regions detected above the configured confidence threshold.")

  return {
    "sample_id": sample["sample_id"],
    "sample_kind": sample["sample_kind"],
    "local_path": sample["local_path"],
    "db_image_asset_id": sample.get("db_image_asset_id"),
    "db_fragment_id": sample.get("db_fragment_id"),
    "db_canvas_id": sample.get("db_canvas_id"),
    "status": "success",
    "raw_output_path": rel(raw_path),
    "overlay_path": rel(overlay_path),
    "detected_region_count": len(detections),
    "detected_labels": labels,
    "confidence_summary": confidence_summary(confidences),
    "errors": [],
    "warnings": warnings,
  }


def build_report(payload: dict[str, Any]) -> str:
  lines = [
    "# Fragment Autocomplete — Segmentation Smoke Test Report",
    "",
    "## Purpose",
    "",
    "This report documents the first controlled segmentation smoke test on the two prepared pilot inputs.",
    "",
    "## Scope",
    "",
    "Inference was run only on the two prepared inputs. No training was done, no segmentation output was stored in the database, and no UI was built.",
    "",
    "## Model used",
    "",
    f"- Model ID: `{payload['model_id']}`",
    f"- Model path: `{payload['model_path']}`",
    "",
    "## Inputs used",
    "",
  ]
  for result in payload["results"]:
    lines.append(f"- `{result['sample_id']}` ({result['sample_kind']}) -> `{result['local_path']}`")

  lines.extend([
    "",
    "## Environment and dependencies",
    "",
    f"- Python: `{payload['environment']['python_version']}`",
    f"- PyTorch: `{payload['environment']['torch_version']}`",
    f"- Ultralytics: `{payload['environment']['ultralytics_version']}`",
      f"- Device: `{payload['device']}`",
      f"- Inference image size: `{payload['imgsz']}`",
    "",
    "## Inference settings",
    "",
    f"- Confidence threshold: `{payload['confidence_threshold']}`",
    f"- Inference image size: `{payload['imgsz']}`",
    f"- Output directory: `{payload['output_dir']}`",
    "",
    "## Output files",
    "",
    f"- Raw outputs: `{payload['output_dir']}/raw/`",
    f"- Overlays: `{payload['output_dir']}/overlays/`",
    f"- Logs: `{payload['output_dir']}/logs/`",
    "",
    "## Per-sample results",
    "",
  ])

  all_labels: list[str] = []
  for result in payload["results"]:
    all_labels.extend(result["detected_labels"])
    lines.extend([
      f"### `{result['sample_id']}`",
      "",
      f"- Status: `{result['status']}`",
      f"- Detected regions: {result['detected_region_count']}",
      f"- Detected labels: {', '.join(result['detected_labels']) if result['detected_labels'] else 'none'}",
      f"- Raw output: `{result['raw_output_path']}`",
      f"- Overlay: `{result['overlay_path']}`",
      "",
    ])

  lines.extend([
    "## Detected labels summary",
    "",
    f"- Unique labels across both samples: {', '.join(sorted(set(all_labels))) if all_labels else 'none'}",
    "",
    "## Visual overlay paths",
    "",
  ])
  for result in payload["results"]:
    lines.append(f"- `{result['sample_id']}`: `{result['overlay_path']}`")

  lines.extend([
    "",
    "## Known issues",
    "",
    "- This was a smoke test only; it confirms model execution and basic output format, not evaluation quality.",
    "- Outputs remain on the local filesystem and have not yet been stored in the database.",
    "",
    "## Next step",
    "",
    "Store segmentation smoke-test outputs in the database.",
    "",
  ])
  return "\n".join(lines)


def main() -> int:
  args = parse_args()
  inputs_path = ROOT / Path(args.inputs)
  output_dir = ROOT / Path(args.output_dir)

  YOLO, ultralytics, torch = require_ultralytics()
  payload = load_yaml(inputs_path)

  selected_inputs = payload.get("selected_inputs", [])
  if len(selected_inputs) != 2:
    raise RuntimeError(f"Expected exactly 2 selected inputs, found {len(selected_inputs)}")

  model_path = ROOT / payload["model_path"]
  if not model_path.exists():
    raise FileNotFoundError(f"Model path does not exist: {payload['model_path']}")

  output_dir.mkdir(parents=True, exist_ok=True)
  (output_dir / "raw").mkdir(parents=True, exist_ok=True)
  (output_dir / "overlays").mkdir(parents=True, exist_ok=True)
  (output_dir / "logs").mkdir(parents=True, exist_ok=True)

  model = YOLO(str(model_path))

  results: list[dict[str, Any]] = []
  for sample in selected_inputs:
    result_payload = run_single_prediction(model, sample, output_dir, args.device, args.conf, args.imgsz)
    results.append(result_payload)
    if args.verbose:
      print(
        f"{sample['sample_id']}: {result_payload['detected_region_count']} detections, "
        f"labels={', '.join(result_payload['detected_labels']) if result_payload['detected_labels'] else 'none'}"
      )

  run_payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "test_set_id": payload["test_set_id"],
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
  write_text(DEFAULT_REPORT, build_report(run_payload))
  write_text(
    output_dir / "logs" / "smoke_test.log",
    "\n".join(
      [
        f"generated_at={run_payload['generated_at']}",
        f"model_id={run_payload['model_id']}",
        f"device={run_payload['device']}",
        f"confidence_threshold={run_payload['confidence_threshold']}",
        f"imgsz={run_payload['imgsz']}",
        f"ultralytics_version={run_payload['environment']['ultralytics_version']}",
        f"torch_version={run_payload['environment']['torch_version']}",
      ]
    ),
  )

  print(f"Smoke test completed for {len(results)} inputs.")
  print(f"Model: {run_payload['model_id']} ({run_payload['model_path']})")
  print(f"Device: {run_payload['device']}")
  for result in results:
    print(
      f"- {result['sample_id']}: {result['detected_region_count']} detections | "
      f"labels={', '.join(result['detected_labels']) if result['detected_labels'] else 'none'}"
    )
    print(f"  raw={result['raw_output_path']}")
    print(f"  overlay={result['overlay_path']}")
  print(f"Wrote {rel(DEFAULT_RESULTS)}")
  print(f"Wrote {rel(DEFAULT_REPORT)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
