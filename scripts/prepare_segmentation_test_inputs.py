#!/usr/bin/env python3
"""Prepare the two-sample smoke-test manifest for future segmentation runs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import yaml
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/metadata/segmentation_test_inputs.yaml"
DEFAULT_RESOLVED = ROOT / "data/metadata/initial_sample_dataset_resolved.yaml"
DEFAULT_MODEL_COMPAT = ROOT / "data/metadata/model_weights_compatibility.yaml"
DEFAULT_REPORT = ROOT / "docs/07_segmentation_test_inputs.md"
TARGET_MODEL_ID = "best_emanuskript_segmentation"
TARGET_MODEL_PATH = "model weights/best_emanuskript_segmentation.pt"

sys.path.insert(0, str(ROOT))
from src.ingestion.db import connect  # noqa: E402


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Prepare controlled segmentation smoke-test inputs.")
  parser.add_argument("--full-page-sample", default="fp_01_clean_simple")
  parser.add_argument("--fragment-sample", default="fr_02_text_block")
  parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
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


def find_item(items: list[dict[str, Any]], sample_id: str) -> dict[str, Any] | None:
  return next((item for item in items if item.get("id") == sample_id), None)


def db_record_exists(conn, table: str, record_id: str | None) -> bool:
  if not record_id:
    return False
  with conn.cursor(row_factory=dict_row) as cursor:
    cursor.execute(f"SELECT id FROM {table} WHERE id = %s", (record_id,))
    return cursor.fetchone() is not None


def item_ready(conn, item: dict[str, Any], sample_kind: str) -> tuple[bool, list[str]]:
  notes: list[str] = []
  local_path = item.get("local_path")
  local_exists = bool(local_path and (ROOT / local_path).exists())
  if not local_exists:
    notes.append("Local image path is missing or does not exist.")

  db_ids = item.get("db_ids", {})
  image_asset_id = db_ids.get("image_asset_id")
  image_exists = db_record_exists(conn, "image_asset", image_asset_id)
  if not image_exists:
    notes.append("Linked image_asset record is missing in the database.")

  if sample_kind == "full_page":
    canvas_id = db_ids.get("canvas_id")
    if not db_record_exists(conn, "canvas", canvas_id):
      notes.append("Linked canvas record is missing in the database.")
  else:
    fragment_id = db_ids.get("fragment_id")
    if not db_record_exists(conn, "fragment", fragment_id):
      notes.append("Linked fragment record is missing in the database.")

  return (local_exists and image_exists and not notes, notes)


def choose_item(conn, items: list[dict[str, Any]], preferred_id: str, sample_kind: str) -> tuple[dict[str, Any], str]:
  preferred = find_item(items, preferred_id)
  if preferred:
    ready, notes = item_ready(conn, preferred, sample_kind)
    if ready:
      return preferred, "Preferred registered sample with local image path and verified DB records."
    preferred["_selection_notes"] = notes

  for candidate in items:
    ready, notes = item_ready(conn, candidate, sample_kind)
    if ready:
      reason = "Fallback selected because the preferred sample was missing or failed readiness checks."
      if preferred and preferred.get("_selection_notes"):
        reason += f" Preferred sample issue: {' '.join(preferred['_selection_notes'])}"
      return candidate, reason

  raise RuntimeError(f"No ready {sample_kind} sample was found in the registered dataset.")


def build_selected_input(item: dict[str, Any], sample_kind: str, reason_selected: str) -> dict[str, Any]:
  db_ids = item.get("db_ids", {})
  local_path = item.get("local_path")
  notes = [
    "Prepared for a future smoke test only.",
    "No model checkpoint was loaded during preparation.",
    "No inference or segmentation output exists yet.",
  ]
  return {
    "sample_id": item["id"],
    "sample_kind": sample_kind,
    "category": item["category"],
    "source": item["source"],
    "source_url": item["url"],
    "local_path": local_path,
    "db_image_asset_id": db_ids.get("image_asset_id"),
    "db_fragment_id": db_ids.get("fragment_id") if sample_kind == "fragment" else None,
    "db_canvas_id": db_ids.get("canvas_id") if sample_kind == "full_page" else None,
    "rights_review_status": item.get("rights_review_status"),
    "training_allowed": item.get("training_allowed", False),
    "publication_allowed": item.get("publication_allowed", False),
    "demo_allowed": item.get("demo_allowed", False),
    "access_level": item.get("access_level", "internal"),
    "reason_selected": reason_selected,
    "readiness_status": "ready",
    "notes": notes,
  }


def build_report(payload: dict[str, Any]) -> str:
  full_page = next(item for item in payload["selected_inputs"] if item["sample_kind"] == "full_page")
  fragment = next(item for item in payload["selected_inputs"] if item["sample_kind"] == "fragment")
  lines = [
    "# Fragment Autocomplete — Segmentation Test Inputs",
    "",
    "## Purpose",
    "",
    "This document records the two controlled inputs selected for the first future eManuSkript/Ultralytics segmentation smoke test.",
    "",
    "## Selected samples",
    "",
    f"- Full page: `{full_page['sample_id']}`",
    f"- Fragment: `{fragment['sample_id']}`",
    "",
    "## Why these samples were selected",
    "",
    f"- `{full_page['sample_id']}`: {full_page['reason_selected']}",
    f"- `{fragment['sample_id']}`: {fragment['reason_selected']}",
    "",
    "## Model chosen for future smoke test",
    "",
    f"- Model ID: `{payload['model_id']}`",
    f"- Model path: `{payload['model_path']}`",
    "",
    "## Local file readiness",
    "",
    f"- `{full_page['sample_id']}` local path: `{full_page['local_path']}`",
    f"- `{fragment['sample_id']}` local path: `{fragment['local_path']}`",
    "",
    "## Database record readiness",
    "",
    f"- `{full_page['sample_id']}` image asset: `{full_page['db_image_asset_id']}`, canvas: `{full_page['db_canvas_id']}`",
    f"- `{fragment['sample_id']}` image asset: `{fragment['db_image_asset_id']}`, fragment: `{fragment['db_fragment_id']}`",
    "",
    "## Rights/access status",
    "",
    "- Rights review status remains `pending_review` for both inputs.",
    "- Training, publication, and demo flags remain false.",
    "- Access level remains `internal`.",
    "",
    "## What has not been run",
    "",
    "- No inference was run.",
    "- No segmentation was produced.",
    "- Model weights were not loaded.",
        "- This preparation step only selected controlled inputs for the first smoke test.",
    "",
    "## Next step",
    "",
    "Run the first controlled eManuSkript segmentation smoke test.",
    "",
  ]
  return "\n".join(lines)


def main() -> int:
  args = parse_args()
  resolved = load_yaml(DEFAULT_RESOLVED)
  model_compat = load_yaml(DEFAULT_MODEL_COMPAT)

  recommended = model_compat.get("recommended_first_model", {})
  if recommended.get("model_id") != TARGET_MODEL_ID:
    raise RuntimeError(
      f"Expected recommended model `{TARGET_MODEL_ID}`, found `{recommended.get('model_id')}`."
    )

  model_path = ROOT / TARGET_MODEL_PATH
  if not model_path.exists():
    raise RuntimeError(f"Recommended model path does not exist: {TARGET_MODEL_PATH}")

  with connect() as conn:
    full_page_item, full_reason = choose_item(conn, resolved.get("full_pages", []), args.full_page_sample, "full_page")
    fragment_item, fragment_reason = choose_item(conn, resolved.get("fragments", []), args.fragment_sample, "fragment")

  payload = {
    "test_set_id": "segmentation_smoke_test_v0_1",
    "status": "prepared",
    "purpose": "First controlled segmentation smoke test inputs for the future eManuSkript/Ultralytics smoke test.",
    "model_id": TARGET_MODEL_ID,
    "model_path": TARGET_MODEL_PATH,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "inference_run": False,
    "segmentation_run": False,
    "selected_inputs": [
      build_selected_input(full_page_item, "full_page", full_reason),
      build_selected_input(fragment_item, "fragment", fragment_reason),
    ],
  }

  output_path = ROOT / Path(args.output)
  write_yaml(output_path, payload)
  write_text(DEFAULT_REPORT, build_report(payload))

  print(f"Prepared test set: {payload['test_set_id']}")
  print(f"Model: {payload['model_id']} ({payload['model_path']})")
  for item in payload["selected_inputs"]:
    print(
      f"- {item['sample_kind']}: {item['sample_id']} | local_exists={bool(item['local_path'] and (ROOT / item['local_path']).exists())} "
      f"| image_asset={item['db_image_asset_id']} | canvas={item['db_canvas_id']} | fragment={item['db_fragment_id']}"
    )
    if args.verbose:
      print(f"  reason: {item['reason_selected']}")
  print(f"Wrote {rel(output_path)}")
  print(f"Wrote {rel(DEFAULT_REPORT)}")
  print("Inference run: false")
  print("Segmentation run: false")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
