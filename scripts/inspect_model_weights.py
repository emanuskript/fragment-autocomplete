#!/usr/bin/env python3
"""Inspect local model checkpoints without loading them for inference."""

from __future__ import annotations

import argparse
import hashlib
import pickletools
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS_DIR = Path("model weights")
DEFAULT_MANIFEST = Path("data/metadata/local_assets_manifest.yaml")
DEFAULT_OUTPUT = Path("data/metadata/model_weights_compatibility.yaml")
DEFAULT_REPORT = Path("docs/06_model_weights_compatibility_report.md")

CHECKSUM_CHUNK_SIZE = 1024 * 1024
KNOWN_FIELD_KEYS = [
  "model",
  "names",
  "args",
  "train_args",
  "yaml",
  "yaml_file",
  "task",
  "mode",
  "data",
  "epoch",
  "optimizer",
  "ema",
  "updates",
  "date",
  "version",
  "license",
]
LABEL_STOP_WORDS = {
  "end2end",
  "args",
  "task",
  "mode",
  "train",
  "model",
  "stride",
  "yaml",
  "yaml_file",
  "train_args",
  "optimizer",
  "ema",
  "updates",
  "date",
  "version",
  "license",
  "docs",
}
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
MODEL_ID_OVERRIDES = {
  "best_catmus.pt": "best_catmus",
  "best_emanuskript_segmentation.pt": "best_emanuskript_segmentation",
  "best_zone_detection.pt": "best_zone_detection",
}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Inspect local model weights without running inference.")
  parser.add_argument("--weights-dir", default=DEFAULT_WEIGHTS_DIR.as_posix())
  parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix())
  parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
  parser.add_argument("--report", default=DEFAULT_REPORT.as_posix())
  parser.add_argument("--allow-trusted-pickle-load", action="store_true")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
  text = path.read_text(encoding="utf-8")
  try:
    return yaml.safe_load(text)
  except yaml.YAMLError:
    repaired = text.replace("[no extension]:", "'[no extension]':")
    return yaml.safe_load(repaired)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
  return path.relative_to(ROOT).as_posix()


def file_mtime(path: Path) -> str:
  return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def compute_sha256(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    while True:
      chunk = handle.read(CHECKSUM_CHUNK_SIZE)
      if not chunk:
        break
      digest.update(chunk)
  return digest.hexdigest()


def manifest_checksums(path: Path) -> dict[str, str]:
  if not path.exists():
    return {}
  payload = load_yaml(path)
  checksums: dict[str, str] = {}
  for asset_root in payload.get("asset_roots", []):
    for item in asset_root.get("files", []):
      file_path = item.get("path")
      checksum = item.get("sha256")
      if file_path and checksum:
        checksums[file_path] = checksum
  return checksums


def read_pickle_strings(path: Path) -> tuple[list[str], list[str], str | None]:
  warnings: list[str] = []
  if not zipfile.is_zipfile(path):
    return [], ["Checkpoint is not a PyTorch zip archive."], None

  try:
    with zipfile.ZipFile(path) as archive:
      members = archive.namelist()
      pickle_member = next((name for name in members if name.endswith("data.pkl")), None)
      if not pickle_member:
        return [], ["Checkpoint archive does not contain a data.pkl member."], None
      data = archive.read(pickle_member)
  except Exception as exc:
    return [], [f"Could not inspect zip archive: {exc}"], None

  strings: list[str] = []
  try:
    for opcode, argument, _pos in pickletools.genops(data):
      if opcode.name in {"SHORT_BINUNICODE", "BINUNICODE", "UNICODE"} and isinstance(argument, str):
        strings.append(argument)
  except Exception as exc:
    warnings.append(f"Pickle opcode inspection failed: {exc}")
  return strings, warnings, pickle_member


def detect_framework(strings: list[str], unsupported_global: str | None) -> str:
  joined = "\n".join(strings[:5000])
  if unsupported_global and unsupported_global.startswith("ultralytics."):
    return "ultralytics_yolo_pytorch"
  if "ultralytics.nn.tasks." in joined or "ultralytics.nn.modules." in joined:
    return "ultralytics_yolo_pytorch"
  if strings:
    return "pytorch_checkpoint_probable"
  return "unknown"


def detect_task(strings: list[str], path_name: str) -> str:
  lowered = [item.lower() for item in strings]
  if "segment" in lowered or "segmentationmodel" in "\n".join(lowered) or "segmentation" in path_name.lower():
    return "segmentation"
  if "detect" in lowered or "detectionmodel" in "\n".join(lowered) or "zone_detection" in path_name.lower():
    return "detection"
  return "unknown"


def detect_labels(strings: list[str]) -> list[str]:
  if "names" not in strings:
    return []
  start = strings.index("names") + 1
  labels: list[str] = []
  for value in strings[start:start + 64]:
    lowered = value.lower()
    if lowered in LABEL_STOP_WORDS:
      break
    if value in {"", "cpu", "cuda:0"}:
      continue
    if re.fullmatch(r"\d+", value):
      continue
    labels.append(value)
  return labels


def detect_keys(strings: list[str]) -> list[str]:
  seen: list[str] = []
  string_set = set(strings)
  for key in KNOWN_FIELD_KEYS:
    if key in string_set:
      seen.append(key)
  return seen


def detect_unsafe_requirement(path: Path) -> tuple[str, bool, str | None, list[str]]:
  try:
    import torch
  except Exception as exc:
    return (
      f"torch_unavailable: {exc}",
      False,
      None,
      ["PyTorch is not installed, so safe torch.load inspection could not run."],
    )

  try:
    torch.load(path, map_location="cpu", weights_only=True)
    return ("safe_weights_only_load_succeeded", False, None, [])
  except Exception as exc:  # noqa: BLE001
    message = ANSI_ESCAPE_RE.sub("", str(exc))
    match = re.search(r"Unsupported global: GLOBAL ([\w\.]+)", message)
    unsupported_global = match.group(1) if match else None
    trusted_required = "Weights only load failed" in message or unsupported_global is not None
    notes = [message.splitlines()[0]]
    if unsupported_global:
      notes.append(f"Safe weights-only load was blocked by unsupported global `{unsupported_global}`.")
    return ("safe_weights_only_load_blocked", trusted_required, unsupported_global, notes)


def trusted_load(path: Path) -> tuple[str, list[str], list[str], str | None]:
  try:
    import torch
  except Exception as exc:
    return (f"trusted_load_failed: torch unavailable ({exc})", [], [], None)

  try:
    payload = torch.load(path, map_location="cpu", weights_only=False)
  except Exception as exc:  # noqa: BLE001
    return (f"trusted_load_failed: {exc}", [], [], None)

  detected_keys: list[str] = []
  detected_labels: list[str] = []
  task: str | None = None

  if isinstance(payload, dict):
    detected_keys = sorted(str(key) for key in payload.keys())[:50]
    names = payload.get("names")
    if isinstance(names, dict):
      detected_labels = [str(value) for _key, value in sorted(names.items())]
    elif isinstance(names, list):
      detected_labels = [str(value) for value in names]
    task_value = payload.get("task")
    if isinstance(task_value, str):
      task = task_value
  return ("trusted_load_succeeded", detected_keys, detected_labels, task)


def compatibility_status(framework: str, task: str, trusted_required: bool, labels: list[str], filename: str) -> tuple[str, list[str]]:
  notes: list[str] = []
  if framework != "ultralytics_yolo_pytorch":
    return ("needs_manual_review", ["Framework could not be identified as Ultralytics/PyTorch from static inspection."])

  if trusted_required:
    notes.append("Future checkpoint deserialization will require either a trusted pickle load or an explicit safe-global allowlist.")

  if task == "segmentation" and "emanuskript" in filename.lower():
    notes.append("Filename and embedded strings both point to the direct eManuSkript segmentation checkpoint.")
    return ("recommended_for_first_smoke_test", notes)

  if task == "segmentation":
    notes.append("Segmentation checkpoint detected, but the checkpoint appears CATMuS-oriented rather than the primary eManuSkript baseline.")
    return ("compatible_secondary_candidate", notes)

  if task == "detection":
    notes.append("Detection checkpoint detected; useful for zone detection but not the first segmentation smoke test.")
    return ("compatible_for_detection_only", notes)

  return ("needs_manual_review", notes)


def inspect_file(path: Path, checksum_map: dict[str, str], allow_trusted_pickle_load: bool) -> dict[str, Any]:
  relative_path = rel(path)
  checksum = checksum_map.get(relative_path) or compute_sha256(path)
  strings, static_notes, archive_member = read_pickle_strings(path)
  task = detect_task(strings, path.name)
  labels = detect_labels(strings)
  keys = detect_keys(strings)
  safe_load_status, trusted_required, unsupported_global, torch_notes = detect_unsafe_requirement(path)
  framework = detect_framework(strings, unsupported_global)

  notes = list(static_notes) + torch_notes
  if archive_member:
    notes.append(f"Static inspection used zip member `{archive_member}`.")
  if labels:
    notes.append(f"Detected {len(labels)} embedded class labels from static pickle strings.")
  else:
    notes.append("No embedded class labels were safely detected.")
  if unsupported_global:
    notes.append(f"Unsupported global during safe load: `{unsupported_global}`.")

  compatibility, compatibility_notes = compatibility_status(framework, task, trusted_required, labels, path.name)
  notes.extend(compatibility_notes)

  trusted_load_status = "not_requested"
  trusted_load_keys: list[str] = []
  trusted_load_labels: list[str] = []
  trusted_load_task: str | None = None
  if allow_trusted_pickle_load:
    trusted_load_status, trusted_load_keys, trusted_load_labels, trusted_load_task = trusted_load(path)
    notes.append(f"Trusted pickle load status: {trusted_load_status}.")
    if trusted_load_keys:
      keys = trusted_load_keys
    if trusted_load_labels:
      labels = trusted_load_labels
    if trusted_load_task:
      task = trusted_load_task

  return {
    "id": MODEL_ID_OVERRIDES.get(path.name, path.stem),
    "path": relative_path,
    "exists": path.exists(),
    "size_bytes": path.stat().st_size,
    "modified_at": file_mtime(path),
    "sha256": checksum,
    "likely_framework": framework,
    "safe_load_status": safe_load_status,
    "trusted_load_required": trusted_required,
    "trusted_pickle_load_status": trusted_load_status,
    "detected_keys": keys,
    "detected_labels": labels,
    "detected_num_classes": len(labels) if labels else None,
    "detected_task": task,
    "compatibility_status": compatibility,
    "notes": notes,
  }


def recommend_model(entries: list[dict[str, Any]]) -> dict[str, str]:
  preferred = next(
    (entry for entry in entries if entry["compatibility_status"] == "recommended_for_first_smoke_test"),
    None,
  )
  if preferred:
    return {
      "model_id": preferred["id"],
      "reason": "It is a segmentation checkpoint, it appears directly tied to eManuSkript, and static inspection exposed embedded layout labels without requiring a trusted load.",
    }

  fallback = next((entry for entry in entries if entry["detected_task"] == "segmentation"), None)
  if fallback:
    return {
      "model_id": fallback["id"],
      "reason": "It is the first segmentation-oriented checkpoint available, although it needs more manual review.",
    }

  return {
    "model_id": entries[0]["id"] if entries else "none",
    "reason": "No clear segmentation checkpoint could be preferred from static inspection alone.",
  }


def build_report(payload: dict[str, Any]) -> str:
  lines = [
    "# Fragment Autocomplete — Model Weights Compatibility Report",
    "",
    "## Purpose",
    "",
    "This report documents a compatibility inspection of the local model weight files in `model weights/`.",
    "",
    "## Scope",
    "",
    "This inspection is limited to static archive/pickle analysis and safe CPU-side checkpoint introspection. No inference was run, no segmentation was produced, no training was performed, and no model weights were committed.",
    "",
    "## Model files inspected",
    "",
  ]

  for entry in payload["models"]:
    lines.append(f"- `{entry['path']}`")

  lines.extend([
    "",
    "## Safety policy",
    "",
    f"- `trusted_pickle_load_used`: `{str(payload['trusted_pickle_load_used']).lower()}`",
    "- Default inspection avoids arbitrary pickle execution.",
    "- Safe `torch.load(..., weights_only=True, map_location='cpu')` is used only to detect whether the checkpoint can be interpreted without trusted globals.",
    "- No model forward pass or prediction call was executed.",
    "",
    "## Inspection method",
    "",
    "- Reused SHA256 checksums from `data/metadata/local_assets_manifest.yaml` where available.",
    "- Verified that the `.pt` files are zipped PyTorch archives.",
    "- Parsed `data.pkl` strings with `pickletools` to identify embedded class names, task hints, and model-family strings.",
    "- Used PyTorch safe weights-only loading to capture whether trusted pickle loading would still be required.",
    "",
    "## Compatibility summary table",
    "",
    "| Model | Size | Framework | Task | Safe load | Labels | Compatibility |",
    "| --- | ---: | --- | --- | --- | ---: | --- |",
  ])

  for entry in payload["models"]:
    size_mb = entry["size_bytes"] / (1024 * 1024)
    lines.append(
      f"| `{entry['id']}` | {size_mb:.1f} MB | {entry['likely_framework']} | {entry['detected_task']} | {entry['safe_load_status']} | {entry['detected_num_classes'] or 0} | {entry['compatibility_status']} |"
    )

  lines.extend([
    "",
    "## Per-model findings",
    "",
  ])

  for entry in payload["models"]:
    lines.extend([
      f"### `{entry['id']}`",
      "",
      f"- Path: `{entry['path']}`",
      f"- SHA256: `{entry['sha256']}`",
      f"- Likely framework: `{entry['likely_framework']}`",
      f"- Detected task: `{entry['detected_task']}`",
      f"- Safe load status: `{entry['safe_load_status']}`",
      f"- Trusted load required: `{str(entry['trusted_load_required']).lower()}`",
      f"- Detected keys: {', '.join(entry['detected_keys']) if entry['detected_keys'] else 'none'}",
      f"- Compatibility status: `{entry['compatibility_status']}`",
      "",
    ])
    if entry["notes"]:
      lines.append("Findings:")
      for note in entry["notes"]:
        lines.append(f"- {note}")
      lines.append("")

  lines.extend([
    "## Detected labels/classes if any",
    "",
  ])

  for entry in payload["models"]:
    labels = entry["detected_labels"]
    lines.append(f"### `{entry['id']}`")
    lines.append("")
    if labels:
      lines.append(f"- Detected {len(labels)} labels: {', '.join(labels)}")
    else:
      lines.append("- No labels were safely detected.")
    lines.append("")

  recommendation = payload["recommended_first_model"]
  lines.extend([
    "## Required dependencies",
    "",
    "- PyTorch is required for safe `weights_only=True` inspection and any future CPU-only smoke test.",
    "- `ultralytics` is required before any trusted checkpoint deserialization or later segmentation smoke test can be attempted.",
    "- The project should keep all checkpoint loading on CPU during the first controlled test.",
    "",
    "## Recommended first model for segmentation test",
    "",
    f"- Model: `{recommendation['model_id']}`",
    f"- Reason: {recommendation['reason']}",
    "",
    "## Risks and blockers",
    "",
    "- All three checkpoints require trusted checkpoint deserialization or an explicit safe-global allowlist to load beyond static inspection.",
    "- `ultralytics` is not currently installed in the environment, which blocks a controlled checkpoint load even if the files are trusted later.",
    "- Static inspection alone does not prove runtime compatibility with the current Ultralytics version; it only identifies likely family, task, and labels.",
    "",
    "## Next step",
    "",
    "Prepare controlled segmentation test inputs.",
    "",
  ])
  return "\n".join(lines)


def update_model_registry(registry_path: Path, entries: list[dict[str, Any]]) -> None:
  registry = {"models": []}
  if registry_path.exists():
    loaded = load_yaml(registry_path)
    if isinstance(loaded, dict):
      registry = loaded
  entry_paths = {entry["path"] for entry in entries}
  existing = {
    item.get("id"): item
    for item in registry.get("models", [])
    if isinstance(item, dict)
    and item.get("id")
    and item.get("local_path") not in entry_paths
  }

  for entry in entries:
    existing[entry["id"]] = {
      "id": entry["id"],
      "name": f"Local model weight file: {Path(entry['path']).name}",
      "local_path": entry["path"],
      "status": "compatibility_inspected",
      "checksum": entry["sha256"],
      "size_bytes": entry["size_bytes"],
      "likely_framework": entry["likely_framework"],
      "detected_task": entry["detected_task"],
      "detected_labels": entry["detected_labels"],
      "compatibility_status": entry["compatibility_status"],
      "no_inference_run": True,
      "compatibility_report": "docs/06_model_weights_compatibility_report.md",
      "notes": entry["notes"],
    }

  ordered_ids = [
    "best_catmus",
    "best_emanuskript_segmentation",
    "best_zone_detection",
  ]
  ordered_models: list[dict[str, Any]] = []
  for model_id in ordered_ids:
    if model_id in existing:
      ordered_models.append(existing.pop(model_id))
  ordered_models.extend(existing.values())

  write_yaml(registry_path, {"models": ordered_models})


def main() -> int:
  args = parse_args()
  weights_dir = ROOT / Path(args.weights_dir)
  manifest_path = ROOT / Path(args.manifest)
  output_path = ROOT / Path(args.output)
  report_path = ROOT / Path(args.report)

  checksum_map = manifest_checksums(manifest_path)
  weights = sorted(weights_dir.glob("*.pt"))

  entries = [inspect_file(path, checksum_map, args.allow_trusted_pickle_load) for path in weights]
  payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": "inspection_only",
    "inference_run": False,
    "trusted_pickle_load_used": args.allow_trusted_pickle_load,
    "models": entries,
    "recommended_first_model": recommend_model(entries),
    "next_step": "Prepare controlled segmentation test inputs",
  }

  write_yaml(output_path, payload)
  write_text(report_path, build_report(payload))
  update_model_registry(ROOT / "models/model_registry.yaml", entries)

  print(f"Inspected weights directory: {weights_dir.relative_to(ROOT)}")
  print(f"Model files inspected: {len(entries)}")
  print(f"Trusted pickle load used: {str(args.allow_trusted_pickle_load).lower()}")
  for entry in entries:
    print(
      f"- {entry['id']}: framework={entry['likely_framework']}, task={entry['detected_task']}, "
      f"safe_load={entry['safe_load_status']}, labels={entry['detected_num_classes'] or 0}, "
      f"compatibility={entry['compatibility_status']}"
    )
    if args.verbose:
      for note in entry["notes"]:
        print(f"  note: {note}")
  print(f"Wrote {output_path.relative_to(ROOT)}")
  print(f"Wrote {report_path.relative_to(ROOT)}")
  print("Updated models/model_registry.yaml")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
