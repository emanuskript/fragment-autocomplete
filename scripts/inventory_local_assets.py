#!/usr/bin/env python3
"""Inventory local dataset/model folders and emit lightweight metadata manifests."""

from __future__ import annotations

import hashlib
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = "Fragment Autocomplete"
ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOTS = [Path("autocomplete-test-dataset"), Path("model weights")]
MANIFEST_PATH = Path("data/metadata/local_assets_manifest.yaml")
REPORT_PATH = Path("docs/05_local_assets_inventory.md")
MODEL_REGISTRY_PATH = Path("models/model_registry.yaml")
CHECKSUM_SKIP_BYTES = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".jp2", ".webp", ".bmp"}
TEXT_EXTENSIONS = {".json", ".yaml", ".yml", ".csv", ".md", ".txt", ".xml", ".tsv"}
MODEL_EXTENSIONS = {".pt", ".pth", ".ckpt", ".onnx", ".safetensors", ".bin", ".mlmodel", ".h5", ".pb"}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}


def rel(path: Path) -> str:
  return path.relative_to(ROOT).as_posix()


def yaml_scalar(value: Any) -> str:
  if value is None:
    return "null"
  if isinstance(value, bool):
    return "true" if value else "false"
  if isinstance(value, (int, float)):
    return str(value)
  text = str(value)
  escaped = text.replace("\\", "\\\\").replace('"', '\\"')
  return f'"{escaped}"'


def yaml_lines(value: Any, indent: int = 0) -> list[str]:
  pad = " " * indent
  if isinstance(value, dict):
    lines: list[str] = []
    for key, item in value.items():
      if isinstance(item, (dict, list)):
        lines.append(f"{pad}{key}:")
        lines.extend(yaml_lines(item, indent + 2))
      else:
        lines.append(f"{pad}{key}: {yaml_scalar(item)}")
    return lines
  if isinstance(value, list):
    if not value:
      return [f"{pad}[]"]
    lines = []
    for item in value:
      if isinstance(item, dict):
        lines.append(f"{pad}-")
        lines.extend(yaml_lines(item, indent + 2))
      elif isinstance(item, list):
        lines.append(f"{pad}-")
        lines.extend(yaml_lines(item, indent + 2))
      else:
        lines.append(f"{pad}- {yaml_scalar(item)}")
    return lines
  return [f"{pad}{yaml_scalar(value)}"]


def write_yaml(path: Path, data: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("\n".join(yaml_lines(data)) + "\n", encoding="utf-8")


def classify(path: Path) -> str:
  suffixes = [suffix.lower() for suffix in path.suffixes]
  extension = suffixes[-1] if suffixes else ""
  compound = "".join(suffixes[-2:]) if len(suffixes) >= 2 else extension
  if extension in IMAGE_EXTENSIONS:
    return "image"
  if extension in MODEL_EXTENSIONS:
    return "model_weight"
  if compound in {".tar.gz"} or extension in ARCHIVE_EXTENSIONS:
    return "archive"
  if extension in TEXT_EXTENSIONS:
    return "metadata_text"
  if not extension:
    return "unknown"
  return "unknown"


def extension_for(path: Path) -> str:
  suffixes = [suffix.lower() for suffix in path.suffixes]
  if len(suffixes) >= 2 and "".join(suffixes[-2:]) == ".tar.gz":
    return ".tar.gz"
  return suffixes[-1] if suffixes else ""


def sha256_stream(path: Path) -> tuple[str | None, str, str | None]:
  try:
    size = path.stat().st_size
    if size > CHECKSUM_SKIP_BYTES:
      return None, "skipped_due_to_size", f"File exceeds checksum threshold of {CHECKSUM_SKIP_BYTES} bytes."
    digest = hashlib.sha256()
    with path.open("rb") as handle:
      for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
        digest.update(chunk)
    return digest.hexdigest(), "computed", None
  except PermissionError:
    return None, "failed_permission_error", "Permission denied while reading file."
  except OSError as exc:
    return None, "failed_os_error", str(exc)


def likely_framework(path: Path) -> str:
  extension = extension_for(path)
  if extension in {".pt", ".pth"}:
    return "pytorch_probable"
  if extension == ".ckpt":
    return "checkpoint_unknown_framework"
  if extension == ".onnx":
    return "onnx"
  if extension == ".safetensors":
    return "safetensors"
  if extension in {".h5", ".pb"}:
    return "tensorflow_keras_probable"
  if extension == ".mlmodel":
    return "coreml"
  return "unknown"


def scan_root(asset_root: Path) -> dict[str, Any]:
  absolute_root = ROOT / asset_root
  root_data: dict[str, Any] = {
    "path": asset_root.as_posix(),
    "exists": absolute_root.exists(),
    "total_files": 0,
    "total_directories": 0,
    "total_size_bytes": 0,
    "extensions": {},
    "largest_files": [],
    "image_files": [],
    "metadata_text_files": [],
    "model_weight_files": [],
    "archive_files": [],
    "unknown_files": [],
    "files": [],
    "errors": [],
  }
  if not absolute_root.exists():
    return root_data

  extension_counts: Counter[str] = Counter()
  category_paths: dict[str, list[str]] = defaultdict(list)
  all_files: list[dict[str, Any]] = []

  for current_root, dirnames, filenames in os.walk(absolute_root, topdown=True):
    dirnames.sort()
    filenames.sort()
    root_data["total_directories"] += len(dirnames)
    for filename in filenames:
      path = Path(current_root) / filename
      relative = rel(path)
      try:
        size = path.stat().st_size
      except OSError as exc:
        root_data["errors"].append({"path": relative, "error": str(exc)})
        continue

      extension = extension_for(path)
      kind = classify(path)
      sha256, checksum_status, reason = sha256_stream(path)
      file_data = {
        "path": relative,
        "size_bytes": size,
        "extension": extension,
        "kind": kind,
        "sha256": sha256,
        "checksum_status": checksum_status,
      }
      if reason:
        file_data["reason"] = reason

      root_data["total_files"] += 1
      root_data["total_size_bytes"] += size
      extension_counts[extension or "[no extension]"] += 1
      category_paths[f"{kind}_files"].append(relative)
      all_files.append(file_data)

  root_data["extensions"] = dict(sorted(extension_counts.items()))
  root_data["files"] = all_files
  root_data["largest_files"] = [
    {"path": item["path"], "size_bytes": item["size_bytes"], "kind": item["kind"]}
    for item in sorted(all_files, key=lambda item: item["size_bytes"], reverse=True)[:15]
  ]
  for key in ("image_files", "metadata_text_files", "model_weight_files", "archive_files", "unknown_files"):
    root_data[key] = category_paths.get(key, [])
  return root_data


def build_model_registry(asset_roots: list[dict[str, Any]]) -> dict[str, Any]:
  models: list[dict[str, Any]] = []
  counter = 1
  for root_data in asset_roots:
    for file_data in root_data.get("files", []):
      if file_data.get("kind") != "model_weight":
        continue
      models.append({
        "id": f"local_model_weights_{counter:03d}",
        "name": f"Local model weight file: {Path(file_data['path']).name}",
        "status": "inventory_only",
        "local_path": file_data["path"],
        "file_count": 1,
        "total_size_bytes": file_data["size_bytes"],
        "likely_framework": likely_framework(Path(file_data["path"])),
        "detected_extensions": [file_data["extension"]],
        "sha256": file_data.get("sha256"),
        "checksum_status": file_data.get("checksum_status"),
        "checksum_manifest": MANIFEST_PATH.as_posix(),
        "notes": [
          "Model has not been loaded or executed.",
          "Framework and label mapping still need compatibility inspection.",
          "Do not commit local model weights to git.",
        ],
      })
      counter += 1
  return {"models": models}


def format_bytes(size: int) -> str:
  value = float(size)
  for unit in ("B", "KB", "MB", "GB", "TB"):
    if value < 1024 or unit == "TB":
      return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
    value /= 1024
  return f"{size} B"


def markdown_report(manifest: dict[str, Any]) -> str:
  roots = manifest["asset_roots"]
  lines = [
    "# Fragment Autocomplete — Local Assets Inventory",
    "",
    "## 1. Purpose",
    "",
    "This report inventories local dataset and model-weight inputs added to the repository working tree. It documents paths, sizes, file types, checksums, and git-protection status before dataset registration or model execution.",
    "",
    "No eManuSkript run, model inference, dataset registration, IIIF downloading, reconstruction, retrieval, UI work, or ML training was performed.",
    "",
    "## 2. Asset roots inspected",
    "",
  ]
  for root in roots:
    lines.append(f"- `{root['path']}`: {'exists' if root['exists'] else 'missing'}")

  lines.extend([
    "",
    "## 3. Summary table",
    "",
    "| Asset root | Exists | Files | Directories | Total size |",
    "| --- | --- | ---: | ---: | ---: |",
  ])
  for root in roots:
    lines.append(f"| `{root['path']}` | {root['exists']} | {root['total_files']} | {root['total_directories']} | {format_bytes(root['total_size_bytes'])} |")

  for root in roots:
    title = "Dataset folder inventory" if root["path"] == "autocomplete-test-dataset" else "Model weights inventory"
    lines.extend(["", f"## {4 if root['path'] == 'autocomplete-test-dataset' else 5}. {title}", ""])
    lines.append(f"Path: `{root['path']}`")
    lines.append("")
    lines.append(f"- Files: {root['total_files']}")
    lines.append(f"- Directories: {root['total_directories']}")
    lines.append(f"- Total size: {format_bytes(root['total_size_bytes'])}")
    lines.append(f"- Extensions: {', '.join(f'`{key}` ({value})' for key, value in root['extensions'].items()) or 'none'}")

  all_extensions: Counter[str] = Counter()
  all_largest: list[dict[str, Any]] = []
  all_model_weights: list[str] = []
  for root in roots:
    all_extensions.update(root["extensions"])
    all_largest.extend(root["largest_files"])
    all_model_weights.extend(root["model_weight_files"])

  lines.extend([
    "",
    "## 6. File type summary",
    "",
    "| Extension | Count |",
    "| --- | ---: |",
  ])
  for extension, count in sorted(all_extensions.items()):
    lines.append(f"| `{extension}` | {count} |")

  lines.extend(["", "## 7. Largest files", "", "| Path | Size | Kind |", "| --- | ---: | --- |"])
  for item in sorted(all_largest, key=lambda entry: entry["size_bytes"], reverse=True)[:20]:
    lines.append(f"| `{item['path']}` | {format_bytes(item['size_bytes'])} | {item['kind']} |")

  lines.extend([
    "",
    "## 8. Checksums and provenance",
    "",
    f"Structured checksums are recorded in `{MANIFEST_PATH.as_posix()}`. Checksums are computed with streaming SHA256 reads, so binary files are not loaded into memory.",
    "",
    "The inventory records local filesystem evidence only. Repository/source provenance and rights-review status still need to be captured during initial sample dataset registration.",
    "",
    "## 9. Git protection / ignored paths",
    "",
    "The local asset roots and common large model/data extensions are ignored in `.gitignore`. The committed inventory files are metadata only and do not include dataset images or model-weight binaries.",
    "",
    "Ignored local roots:",
    "",
    "- `autocomplete-test-dataset/`",
    "- `model weights/`",
    "",
    "## 10. Risks and notes",
    "",
    "- Local files may not yet have authoritative source provenance or rights metadata.",
    "- Model-weight files are inventory-only; they have not been loaded, inspected internally, or executed.",
    "- Dataset files should be registered into metadata before any segmentation test.",
    "- Checksums identify local files but do not establish usage rights.",
    "",
    "Detected likely model-weight files:",
    "",
  ])
  if all_model_weights:
    lines.extend([f"- `{path}`" for path in all_model_weights])
  else:
    lines.append("- None detected.")

  lines.extend([
    "",
    "## 11. Recommended next step",
    "",
    "Register the initial sample dataset from `autocomplete-test-dataset/`.",
    "",
  ])
  return "\n".join(lines)


def main() -> int:
  asset_roots = [scan_root(path) for path in ASSET_ROOTS]
  manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "project": PROJECT,
    "checksum_algorithm": "sha256",
    "checksum_skip_threshold_bytes": CHECKSUM_SKIP_BYTES,
    "asset_roots": asset_roots,
  }
  write_yaml(ROOT / MANIFEST_PATH, manifest)
  write_yaml(ROOT / MODEL_REGISTRY_PATH, build_model_registry(asset_roots))
  (ROOT / REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
  (ROOT / REPORT_PATH).write_text(markdown_report(manifest), encoding="utf-8")

  for root in asset_roots:
    print(
      f"{root['path']}: exists={root['exists']} "
      f"files={root['total_files']} dirs={root['total_directories']} "
      f"size={format_bytes(root['total_size_bytes'])}"
    )
  print(f"Wrote {MANIFEST_PATH}")
  print(f"Wrote {REPORT_PATH}")
  print(f"Wrote {MODEL_REGISTRY_PATH}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
