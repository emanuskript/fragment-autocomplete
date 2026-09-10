"""Restore only byte-identical registered assets through the existing acquisition helper."""
from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import shutil
import tempfile

from PIL import Image

from .artificial_fragment_registration import resolve_local_path, sha256_file
from .corpus_audit import digest
from src.ingestion.training_corpus import download_resumable

STATUSES = ("available", "restored_checksum_verified", "unavailable_local", "restoration_failed", "requires_manual_action")
# Darwin's SF_DATALESS. Do not open a placeholder and accidentally block on hydration.
DATALESS = 0x40000000


def local_state(path):
  if not path.is_file():
    return {"exists": False, "dataless": False}
  return {"exists": True, "dataless": bool(getattr(path.stat(), "st_flags", 0) & DATALESS)}


def verify_source(path, page):
  state = local_state(path)
  if not state["exists"] or state["dataless"]:
    raise ValueError("source_unavailable_local")
  if sha256_file(path) != page["source_sha256"]:
    raise ValueError("registered_checksum_mismatch")
  if path.stat().st_size != page["source_size_bytes"]:
    raise ValueError("registered_size_mismatch")
  with Image.open(path) as im:
    if list(im.size) != page["dimensions_px"]:
      raise ValueError("registered_dimensions_mismatch")
    im.verify()


def availability(root, pages, *, restore=False, previous=None, downloader=download_resumable):
  """Read-only by default. Staging prevents the acquisition helper replacing unverified bytes.

  Successful restoration events persist on reruns; current availability is separately checked.
  Existing readable but mismatched assets require manual action and are never overwritten.
  """
  prior = {p["page_id"]: p for p in (previous or {}).get("pages", [])}
  unavailable = []
  for page in pages:
    state = local_state(root / page["source_path"])
    if not state["exists"] or state["dataless"]:
      unavailable.append(page)
  sizes = {p["source_size_bytes"] for p in unavailable}
  candidates = {}
  # Search the project's data tree, including processed/local copies; never follow unavailable files.
  for path in sorted((root / "data").rglob("*")):
    state = local_state(path)
    if not state["exists"] or state["dataless"]:
      continue
    size = path.stat().st_size
    if size in sizes:
      candidates.setdefault(size, []).append(path)
  rows = []
  for p in sorted(pages, key=lambda p: p["page_id"]):
    path = resolve_local_path(root, p["source_path"])
    state = local_state(path)
    binding = {"page_id": p["page_id"], "asset_id": p["db_ids"]["image_asset_id"],
      "manuscript_id": p["manuscript_id"], "page": p["canvas_label"], "split": p["split"],
      "path": p["source_path"], "expected_sha256": p["source_sha256"],
      "download_url": p["source_record"]["image"].get("download_url")}
    old = prior.get(p["page_id"], {})
    if old and any(old.get(k) != v for k, v in binding.items()):
      raise ValueError("availability_provenance_changed")
    row = {**binding, "initial_state": old.get("initial_state", state), "current_state": state,
      "identical_local_copies": old.get("identical_local_copies", []), "checksum_verified": False}
    if state["exists"] and not state["dataless"]:
      try:
        verify_source(path, p)
        row.update(status="restored_checksum_verified" if old.get("status") == "restored_checksum_verified" else "available", checksum_verified=True)
        if "restoration" in old:
          row["restoration"] = old["restoration"]
      except (ValueError, OSError):
        row.update(status="requires_manual_action", reason="readable_asset_failed_registered_checksum_size_or_image_validation")
    else:
      matches = [c for c in candidates.get(p["source_size_bytes"], []) if c.resolve() != path and sha256_file(c) == p["source_sha256"]]
      row["identical_local_copies"] = [c.relative_to(root).as_posix() for c in matches]
      row["status"] = "unavailable_local"
      if restore:
        if not matches and not binding["download_url"]:
          row.update(status="requires_manual_action", reason="no_registered_acquisition_url_or_exact_local_copy")
        else:
          original_stat = path.stat() if path.exists() else None
          staging = root / "outputs/artificial_fragments/v0_3/restoration"
          staging.mkdir(parents=True, exist_ok=True)
          try:
            with tempfile.TemporaryDirectory(dir=staging) as temp:
              staged = Path(temp) / path.name
              if matches:
                shutil.copyfile(matches[0], staged)
              else:
                downloader(binding["download_url"], staged, expected_sha256=p["source_sha256"], timeout_seconds=45)
              verify_source(staged, p)
              path.parent.mkdir(parents=True, exist_ok=True)
              os.replace(staged, path)
              if original_stat:
                os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            row.update(status="restored_checksum_verified", checksum_verified=True, current_state=local_state(path),
              restoration={"mechanism": "checksum_identical_local_copy" if matches else "training_corpus.download_resumable",
                           "expected_checksum_verified_before_atomic_replacement": True})
          except Exception as exc:
            # Stable, non-secret diagnostics; no transient paths or timestamps in scientific metadata.
            response = getattr(exc, "response", None)
            row.update(status="restoration_failed", reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                       http_status=getattr(response, "status_code", None))
      elif old.get("status") in ("restoration_failed", "requires_manual_action"):
        for key in ("status", "reason", "http_status"):
          if key in old:
            row[key] = old[key]
    rows.append(row)
    if row["status"] != "available":
      print(f"Source {p['page_id']}: {row['status']}", flush=True)
  counts = Counter(r["status"] for r in rows)
  return {"report_version": "source_availability_v0_3", "statuses": list(STATUSES),
    "counts": {s: counts[s] for s in STATUSES}, "registered_page_count": len(rows),
    "available_now": sum(r["checksum_verified"] for r in rows), "pages": rows,
    "provenance_policy": "Only exact registered bytes may replace unavailable sources; rights, splits and database records are never edited.",
    "input_binding_sha256": digest([{k: p[k] for k in ("page_id", "source_sha256", "source_path", "split")} for p in sorted(pages, key=lambda p: p["page_id"])])}
