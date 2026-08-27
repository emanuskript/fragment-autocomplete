"""Reproducible, provenance-preserving IIIF source-corpus construction."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
import yaml
from PIL import Image
from psycopg.rows import dict_row

from .db import connect
from .iiif_client import fetch_manifest_url
from .iiif_ingest import ingest_manifest, normalized_hsp_metadata
from .iiif_manifest import NormalizedCanvas, NormalizedImageAsset, NormalizedManifest
from .iiif_normalizer import metadata_lookup, normalize_manifest


SELECTION_RULES_VERSION = "obvious_non_training_canvas_rules_v0_1"
EXPANSION_SELECTION_RULES_VERSION = "obvious_non_training_canvas_rules_v0_2"
BUILDER_VERSION = "training_corpus_builder_v0_1"
CHUNK_SIZE = 1024 * 1024
RIGHTS_REVIEW_STATUSES = {
  "pending_review",
  "approved_for_training",
  "not_approved",
  "needs_review",
}
REJECTION_RULES_V0_1: tuple[tuple[str, re.Pattern[str]], ...] = (
  ("cover", re.compile(r"\b(front|back|rear)?\s*cover\b", re.IGNORECASE)),
  ("paste_down", re.compile(r"\bpaste[ -]?down\b", re.IGNORECASE)),
  ("binding", re.compile(r"\bbinding\b|\bspine\b", re.IGNORECASE)),
  ("blank", re.compile(r"\bblank(?: page)?\b|\bempty page\b", re.IGNORECASE)),
  ("color_target", re.compile(r"\bcolou?r\s*(target|chart|bar)\b", re.IGNORECASE)),
  ("calibration", re.compile(r"\bcalibrat(?:ion|ion image|e)\b|\btest chart\b", re.IGNORECASE)),
  ("digitization_target", re.compile(r"\b(gray|grey)\s*scale\b|\bdigitization target\b", re.IGNORECASE)),
  ("administrative", re.compile(r"\b(administrative|copyright)\s*(image|page|notice)\b", re.IGNORECASE)),
)
REJECTION_RULES_V0_2: tuple[tuple[str, re.Pattern[str]], ...] = REJECTION_RULES_V0_1 + (
  ("color_target", re.compile(r"\b(?:digital\s+)?colou?r(?:checker|\s+profile)\b", re.IGNORECASE)),
  ("digitization_target", re.compile(r"^(?:ruler|qp\s*card)(?:\s+on\s+(?:page|binding))?$", re.IGNORECASE)),
  ("object_view", re.compile(r"^(?:fore edge|head|tail|open view)(?:\s+[a-z])?$", re.IGNORECASE)),
)
MANUAL_REVIEW_RULES_V0_2: tuple[tuple[str, re.Pattern[str]], ...] = (
  ("uncertain_accompanying_materials", re.compile(r"^accompanying materials(?:\s+\d+[rv]?)?$", re.IGNORECASE)),
)
SELECTION_RULES = {
  SELECTION_RULES_VERSION: REJECTION_RULES_V0_1,
  EXPANSION_SELECTION_RULES_VERSION: REJECTION_RULES_V0_2,
}


def sha256_file(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
      digest.update(chunk)
  return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
  return hashlib.sha256(payload).hexdigest()


def stable_digest(*parts: Any) -> str:
  rendered = "\0".join(str(part) for part in parts)
  return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def relative_path(path: Path, root: Path) -> str:
  return path.resolve().relative_to(root.resolve()).as_posix()


def load_yaml(path: Path) -> dict[str, Any]:
  payload = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"Expected a YAML mapping in {path}")
  return payload


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def canonical_manifest_url(url: str) -> str:
  return url.strip().rstrip("/")


def validate_specification(spec: dict[str, Any]) -> None:
  required = ("corpus_id", "selection_seed", "split_seed", "manuscripts")
  missing = [name for name in required if name not in spec]
  if missing:
    raise ValueError(f"Corpus specification is missing required fields: {', '.join(missing)}")
  manuscripts = spec.get("manuscripts")
  if not isinstance(manuscripts, list) or not manuscripts:
    raise ValueError("Corpus specification must contain at least one manuscript")

  ids: set[str] = set()
  urls: set[str] = set()
  for entry in manuscripts:
    if not isinstance(entry, dict) or not entry.get("id") or not entry.get("manifest_url"):
      raise ValueError("Every manuscript entry requires id and manifest_url")
    manuscript_id = str(entry["id"])
    manifest_url = canonical_manifest_url(str(entry["manifest_url"]))
    if manuscript_id in ids:
      raise ValueError(f"Duplicate manuscript id in corpus specification: {manuscript_id}")
    if manifest_url in urls:
      raise ValueError(f"Duplicate manuscript manifest in corpus specification: {manifest_url}")
    ids.add(manuscript_id)
    urls.add(manifest_url)

  max_pages = int(spec.get("max_pages_per_manuscript", 5))
  if max_pages < 1:
    raise ValueError("max_pages_per_manuscript must be at least 1")
  ratios = spec.get("split_ratios", {"train": 0.70, "validation": 0.15, "test": 0.15})
  if set(ratios) != {"train", "validation", "test"}:
    raise ValueError("split_ratios must define train, validation, and test")
  if not math.isclose(sum(float(value) for value in ratios.values()), 1.0, abs_tol=1e-9):
    raise ValueError("split_ratios must sum to 1.0")
  rights_status = spec.get("rights_review_status", "pending_review")
  if rights_status not in RIGHTS_REVIEW_STATUSES:
    raise ValueError(f"Unsupported rights_review_status: {rights_status}")
  if spec.get("training_allowed", False) is not False:
    raise ValueError("Corpus acquisition must not automatically mark sources as training_allowed")
  rules_version = spec.get("selection_rules_version", SELECTION_RULES_VERSION)
  if rules_version not in SELECTION_RULES:
    raise ValueError(f"Unsupported selection_rules_version: {rules_version}")


def _largest_remainder_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
  names = ("train", "validation", "test")
  quotas = {name: total * float(ratios[name]) for name in names}
  counts = {name: int(math.floor(quotas[name])) for name in names}
  remaining = total - sum(counts.values())
  order = sorted(names, key=lambda name: (-(quotas[name] - counts[name]), names.index(name)))
  for name in order[:remaining]:
    counts[name] += 1
  return counts


def assign_manuscript_splits(
  manuscript_keys: Iterable[str],
  seed: Any,
  ratios: dict[str, float] | None = None,
) -> dict[str, str]:
  """Assign one deterministic split to every manuscript key."""
  ratios = ratios or {"train": 0.70, "validation": 0.15, "test": 0.15}
  keys = list(manuscript_keys)
  if len(keys) != len(set(keys)):
    raise ValueError("Duplicate manuscript key supplied to split assignment")
  ordered = sorted(keys, key=lambda key: (stable_digest(seed, key), key))
  counts = _largest_remainder_counts(len(ordered), ratios)
  assignments: dict[str, str] = {}
  offset = 0
  for split_name in ("train", "validation", "test"):
    for key in ordered[offset:offset + counts[split_name]]:
      assignments[key] = split_name
    offset += counts[split_name]
  return assignments


def rejection_reasons(
  canvas: NormalizedCanvas,
  rules_version: str = SELECTION_RULES_VERSION,
) -> list[dict[str, Any]]:
  if rules_version not in SELECTION_RULES:
    raise ValueError(f"Unsupported selection_rules_version: {rules_version}")
  reasons: list[dict[str, Any]] = []
  label = canvas.canvas_label or ""
  if not canvas.images:
    reasons.append({"code": "no_image_asset", "evidence": "normalized canvas has no image body"})
  elif not any(image.source_url or image.iiif_image_service_url for image in canvas.images):
    reasons.append({"code": "no_downloadable_image", "evidence": "image body has no source or IIIF service URL"})
  for code, pattern in SELECTION_RULES[rules_version]:
    match = pattern.search(label)
    if match:
      reasons.append({"code": code, "evidence": f"canvas label matched explicit term: {match.group(0)!r}"})
  return reasons


def manual_review_reasons(
  canvas: NormalizedCanvas,
  rules_version: str = SELECTION_RULES_VERSION,
) -> list[dict[str, Any]]:
  """Return uncertain-candidate reasons without turning uncertainty into rejection."""
  if rules_version not in SELECTION_RULES:
    raise ValueError(f"Unsupported selection_rules_version: {rules_version}")
  if rules_version != EXPANSION_SELECTION_RULES_VERSION:
    return []
  label = canvas.canvas_label or ""
  reasons: list[dict[str, Any]] = []
  for code, pattern in MANUAL_REVIEW_RULES_V0_2:
    match = pattern.search(label)
    if match:
      reasons.append({"code": code, "evidence": f"canvas label requires manual review: {match.group(0)!r}"})
  return reasons


def select_canvas_pages(
  manifest_key: str,
  canvases: list[NormalizedCanvas],
  seed: Any,
  max_pages: int,
  rules_version: str = SELECTION_RULES_VERSION,
) -> list[dict[str, Any]]:
  """Record all canvases and select eligible pages by stable seeded rank."""
  if max_pages < 1:
    raise ValueError("max_pages must be at least 1")
  seen: set[str] = set()
  eligible: list[tuple[str, NormalizedCanvas]] = []
  rejection_by_id: dict[str, list[dict[str, Any]]] = {}
  review_by_id: dict[str, list[dict[str, Any]]] = {}
  for canvas in canvases:
    if canvas.canvas_identifier in seen:
      raise ValueError(f"Duplicate page/canvas in manifest: {canvas.canvas_identifier}")
    seen.add(canvas.canvas_identifier)
    reasons = rejection_reasons(canvas, rules_version)
    review_reasons = manual_review_reasons(canvas, rules_version)
    rejection_by_id[canvas.canvas_identifier] = reasons
    review_by_id[canvas.canvas_identifier] = review_reasons
    if not reasons and not review_reasons:
      eligible.append((stable_digest(seed, manifest_key, canvas.canvas_identifier), canvas))

  ranked = sorted(eligible, key=lambda item: (item[0], item[1].sequence_index, item[1].canvas_identifier))
  selected_rank = {
    canvas.canvas_identifier: rank
    for rank, (_, canvas) in enumerate(ranked[:max_pages], start=1)
  }
  records: list[dict[str, Any]] = []
  for canvas in canvases:
    reasons = rejection_by_id[canvas.canvas_identifier]
    review_reasons = review_by_id[canvas.canvas_identifier]
    if reasons:
      selection_status = "rejected"
      selection_reasons = reasons
      review_note = "Rejected only because an explicit obvious non-training rule matched."
      review_status = "not_required"
      automatic_selection_eligible = False
    elif review_reasons:
      selection_status = "candidate"
      selection_reasons = review_reasons
      review_note = "Uncertain auxiliary material remains a candidate but requires manual review before selection."
      review_status = "needs_manual_review"
      automatic_selection_eligible = False
    elif canvas.canvas_identifier in selected_rank:
      selection_status = "selected"
      selection_reasons = [{
        "code": "deterministic_seeded_selection",
        "rank": selected_rank[canvas.canvas_identifier],
        "seed": seed,
      }]
      review_note = "No obvious exclusion was detected; selection is a reproducible candidate choice, not a quality judgment."
      review_status = "post_download_review_required"
      automatic_selection_eligible = True
    else:
      selection_status = "candidate"
      selection_reasons = [{"code": "eligible_not_selected_page_limit", "max_pages": max_pages}]
      review_note = "No obvious exclusion was detected; the page remains an unselected candidate."
      review_status = "not_reviewed"
      automatic_selection_eligible = True
    records.append({
      "canvas_identifier": canvas.canvas_identifier,
      "canvas_label": canvas.canvas_label,
      "sequence_index": canvas.sequence_index,
      "selection_status": selection_status,
      "selection_reasons": selection_reasons,
      "selection_review_note": review_note,
      "selection_review_status": review_status,
      "automatic_selection_eligible": automatic_selection_eligible,
      "width_px": canvas.width_px,
      "height_px": canvas.height_px,
    })
  return records


def ensure_unique_pages(manuscript_records: list[dict[str, Any]]) -> None:
  owners: dict[str, str] = {}
  for manuscript in manuscript_records:
    for page in manuscript.get("pages", []):
      canvas_id = page["canvas_identifier"]
      previous = owners.get(canvas_id)
      if previous is not None:
        raise ValueError(f"Duplicate page/canvas across manuscripts: {canvas_id} ({previous}, {manuscript['id']})")
      owners[canvas_id] = manuscript["id"]


def _slug(value: str) -> str:
  rendered = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
  return rendered[:80] or "asset"


def image_request_url(image: NormalizedImageAsset, image_request: dict[str, Any]) -> str:
  if image.iiif_image_service_url:
    service = image.iiif_image_service_url.rstrip("/")
    region = image_request.get("region", "full")
    size = image_request.get("size", "2000,")
    rotation = image_request.get("rotation", "0")
    quality = image_request.get("quality", "default")
    extension = image_request.get("format", "jpg")
    return f"{service}/{region}/{size}/{rotation}/{quality}.{extension}"
  if image.source_url:
    return image.source_url
  raise ValueError("Selected image has neither a source URL nor a IIIF service URL")


def inspect_image(path: Path) -> dict[str, Any]:
  with Image.open(path) as image:
    image.verify()
  with Image.open(path) as image:
    return {
      "width_px": int(image.width),
      "height_px": int(image.height),
      "media_type": Image.MIME.get(image.format),
      "color_mode": image.mode,
    }


def verify_checksum(path: Path, expected_sha256: str) -> str:
  actual = sha256_file(path)
  if actual != expected_sha256:
    raise ValueError(f"Checksum mismatch for {path}: expected {expected_sha256}, found {actual}")
  return actual


def download_resumable(
  url: str,
  destination: Path,
  *,
  expected_sha256: str | None = None,
  timeout_seconds: int = 120,
  session: Any = requests,
) -> dict[str, Any]:
  """Download atomically, or reuse a locally verified unchanged representation."""
  if destination.is_file() and expected_sha256:
    actual = sha256_file(destination)
    if actual == expected_sha256:
      return {
        "status": "verified_existing",
        "sha256": actual,
        "size_bytes": destination.stat().st_size,
        "response_headers": {},
        **inspect_image(destination),
      }

  destination.parent.mkdir(parents=True, exist_ok=True)
  partial = destination.with_suffix(destination.suffix + ".part")
  digest = hashlib.sha256()
  try:
    with session.get(url, stream=True, timeout=timeout_seconds, headers={"Accept": "image/*"}) as response:
      response.raise_for_status()
      with partial.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
          if chunk:
            handle.write(chunk)
            digest.update(chunk)
      response_headers = {
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "content_type": response.headers.get("Content-Type"),
        "content_length": response.headers.get("Content-Length"),
      }
    image_info = inspect_image(partial)
    checksum = digest.hexdigest()
    os.replace(partial, destination)
  finally:
    if partial.exists():
      partial.unlink()
  return {
    "status": "downloaded" if expected_sha256 is None else "redownloaded_after_verification_failure",
    "sha256": checksum,
    "size_bytes": destination.stat().st_size,
    "response_headers": response_headers,
    **image_info,
  }


def parse_date_range(display: str | None) -> dict[str, Any]:
  """Return a conservative machine-readable range while retaining comparator language."""
  if not display:
    return {"display": None, "not_before": None, "not_after": None, "method": "unavailable"}
  century_matches = [int(value) for value in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)\s+century\b", display, re.IGNORECASE)]
  if century_matches:
    return {
      "display": display,
      "not_before": (min(century_matches) - 1) * 100 + 1,
      "not_after": max(century_matches) * 100,
      "method": "broad_century_range_inferred_from_source_display",
    }
  years = [int(value) for value in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", display)]
  if years:
    if re.search(r"\b(around|circa|approximately|approx\.?|ca\.?)\b", display, re.IGNORECASE):
      return {
        "display": display,
        "not_before": None,
        "not_after": None,
        "method": "comparator_language_preserved_unparsed",
      }
    return {
      "display": display,
      "not_before": min(years),
      "not_after": max(years),
      "method": "year_tokens_extracted_from_source_display",
    }
  return {"display": display, "not_before": None, "not_after": None, "method": "display_preserved_unparsed"}


def manuscript_metadata(entry: dict[str, Any], manifest: NormalizedManifest) -> dict[str, Any]:
  hsp = normalized_hsp_metadata(manifest)
  location = metadata_lookup(manifest.metadata, ("location", "settlement"))
  collection = metadata_lookup(manifest.metadata, ("collection name", "repository", "holding institution"))
  repository = entry.get("repository") or ", ".join(value for value in (location, collection) if value) or "e-codices"
  title = metadata_lookup(manifest.metadata, ("title",)) or manifest.label
  date_display = hsp.get("orig_date_display")
  return {
    "repository": repository,
    "shelfmark": metadata_lookup(manifest.metadata, ("shelfmark", "signatur", "call number")),
    "title": title,
    "date": parse_date_range(date_display),
    "language": metadata_lookup(manifest.metadata, ("text language", "language")),
    "script": metadata_lookup(manifest.metadata, ("script", "script type")),
    "material": metadata_lookup(manifest.metadata, ("material", "support")),
    "hsp_normalized": hsp,
  }


def _previous_selected_pages(previous_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
  pages: dict[str, dict[str, Any]] = {}
  for manuscript in (previous_manifest or {}).get("manuscripts", []):
    for page in manuscript.get("pages", []):
      if page.get("selection_status") == "selected":
        pages[page["canvas_identifier"]] = page
  return pages


def _raw_manifest_artifact(
  root: Path,
  download_root: Path,
  manuscript_id: str,
  raw_manifest: dict[str, Any],
) -> dict[str, Any]:
  path = download_root / "_manifests" / f"{_slug(manuscript_id)}.json"
  payload = (json.dumps(raw_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
  checksum = sha256_bytes(payload)
  if not path.exists() or sha256_file(path) != checksum:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
  return {"local_path": relative_path(path, root), "sha256": checksum}


def _page_image_record(canvas: NormalizedCanvas) -> dict[str, Any] | None:
  if not canvas.images:
    return None
  image = canvas.images[0]
  return {
    "source_url": image.source_url,
    "iiif_image_service_url": image.iiif_image_service_url,
    "media_type": image.media_type,
    "width_px": image.width_px,
    "height_px": image.height_px,
    "image_choice_reason": "first normalized image body on canvas",
  }


def _selected_download_path(download_root: Path, manuscript_id: str, page: dict[str, Any]) -> Path:
  canvas_tail = Path(urlparse(page["canvas_identifier"]).path).stem
  filename = f"{int(page['sequence_index']):04d}_{_slug(canvas_tail)}.jpg"
  return download_root / _slug(manuscript_id) / filename


def _registration_ids(conn: Any, manifest_url: str, canvas_identifier: str, source_url: str | None) -> dict[str, str | None]:
  with conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
      """
      SELECT repository.id::text AS repository_id,
             manuscript.id::text AS manuscript_id,
             cache.id::text AS manifest_cache_id,
             canvas.id::text AS canvas_id,
             asset.id::text AS image_asset_id
      FROM iiif_manifest_cache cache
      JOIN repository ON repository.id = cache.repository_id
      JOIN manuscript ON manuscript.id = cache.manuscript_id
      JOIN canvas ON canvas.iiif_manifest_cache_id = cache.id
      JOIN image_asset asset ON asset.canvas_id = canvas.id
      WHERE cache.manifest_url = %s
        AND canvas.canvas_identifier = %s
        AND asset.source_url IS NOT DISTINCT FROM %s
      LIMIT 1
      """,
      (manifest_url, canvas_identifier, source_url),
    )
    row = cur.fetchone()
  if row is None:
    raise RuntimeError(f"Registered page could not be resolved: {canvas_identifier}")
  return dict(row)


def register_selected_manuscript(
  manifest: NormalizedManifest,
  manuscript_record: dict[str, Any],
  *,
  corpus_id: str,
  rights_review_status: str,
  fetch_headers: dict[str, str | None],
) -> None:
  selected_by_id = {
    page["canvas_identifier"]: page
    for page in manuscript_record["pages"]
    if page["selection_status"] == "selected"
  }
  filtered_canvases: list[NormalizedCanvas] = []
  for canvas in manifest.canvases:
    page = selected_by_id.get(canvas.canvas_identifier)
    if page is None:
      continue
    if not canvas.images or not page.get("image", {}).get("local_path"):
      raise RuntimeError(f"Selected page lacks a downloaded image: {canvas.canvas_identifier}")
    source_image = canvas.images[0]
    corpus_provenance = {
      "corpus_id": corpus_id,
      "manuscript_spec_id": manuscript_record["id"],
      "manifest_url": manuscript_record["manifest_url"],
      "canvas_identifier": canvas.canvas_identifier,
      "selection_status": "selected",
      "selection_reasons": page["selection_reasons"],
      "manuscript_split": manuscript_record["split"],
      "rights_review_status": rights_review_status,
      "training_allowed": False,
      "download_url": page["image"]["download_url"],
    }
    registered_image = replace(
      source_image,
      local_path=page["image"]["local_path"],
      checksum_sha256=page["image"]["checksum_sha256"],
      rights_review_status=rights_review_status,
      raw_metadata={**source_image.raw_metadata, "training_corpus": corpus_provenance},
    )
    filtered_canvases.append(replace(
      canvas,
      images=[registered_image],
      raw_metadata={**canvas.raw_metadata, "training_corpus": corpus_provenance},
    ))

  filtered_manifest = replace(
    manifest,
    canvases=filtered_canvases,
    ingestion_metadata={
      "ingestion_source": BUILDER_VERSION,
      "corpus_id": corpus_id,
      "manuscript_spec_id": manuscript_record["id"],
      "manuscript_split": manuscript_record["split"],
      "selection_rules_version": SELECTION_RULES_VERSION,
      "candidate_hypothesis_policy": "source acquisition only; no reconstruction claim",
    },
  )
  with connect() as conn:
    ingest_manifest(conn, filtered_manifest, manuscript_record["repository"], fetch_headers)
    for page in manuscript_record["pages"]:
      if page["selection_status"] != "selected":
        continue
      page["registration"] = {
        "status": "registered",
        "db_ids": _registration_ids(
          conn,
          manifest.source_identifier,
          page["canvas_identifier"],
          page["image"].get("source_url"),
        ),
      }
    conn.commit()


def build_statistics(corpus_manifest: dict[str, Any]) -> dict[str, Any]:
  manuscripts = corpus_manifest.get("manuscripts", [])
  selected_pages = [
    (manuscript, page)
    for manuscript in manuscripts
    for page in manuscript.get("pages", [])
    if page.get("selection_status") == "selected"
  ]
  pages_per_manuscript = [
    sum(page.get("selection_status") == "selected" for page in manuscript.get("pages", []))
    for manuscript in manuscripts
  ]
  repository_distribution = Counter(manuscript.get("repository") or "[missing]" for manuscript in manuscripts)
  rights_distribution = Counter(
    page.get("image", {}).get("rights_review_status", "[missing]")
    for _, page in selected_pages
  )
  manuscript_splits = Counter(manuscript.get("split") for manuscript in manuscripts)
  page_splits = Counter(manuscript.get("split") for manuscript, _ in selected_pages)
  dimensions = [
    (page.get("image", {}).get("download_width_px"), page.get("image", {}).get("download_height_px"))
    for _, page in selected_pages
  ]
  complete_dimensions = [(width, height) for width, height in dimensions if width and height]
  metadata_fields = ("repository", "shelfmark", "title", "date", "language", "script", "material", "rights_statement", "license", "attribution")
  metadata_completeness: dict[str, Any] = {}
  for field in metadata_fields:
    if field == "date":
      present = sum(bool(manuscript.get("date", {}).get("display")) for manuscript in manuscripts)
    else:
      present = sum(bool(manuscript.get(field)) for manuscript in manuscripts)
    metadata_completeness[field] = {
      "present": present,
      "missing": len(manuscripts) - present,
      "fraction": round(present / len(manuscripts), 4) if manuscripts else 0.0,
    }
  parsed_dates = [
    manuscript["date"] for manuscript in manuscripts
    if manuscript.get("date", {}).get("not_before") is not None
  ]
  return {
    "corpus_id": corpus_manifest.get("corpus_id"),
    "manuscript_count": len(manuscripts),
    "selected_page_count": len(selected_pages),
    "canvas_status_counts": dict(sorted(Counter(
      page.get("selection_status")
      for manuscript in manuscripts
      for page in manuscript.get("pages", [])
    ).items())),
    "pages_per_manuscript": {
      "minimum": min(pages_per_manuscript) if pages_per_manuscript else 0,
      "maximum": max(pages_per_manuscript) if pages_per_manuscript else 0,
      "mean": round(sum(pages_per_manuscript) / len(pages_per_manuscript), 3) if pages_per_manuscript else 0.0,
      "values": pages_per_manuscript,
    },
    "repository_distribution": dict(sorted(repository_distribution.items())),
    "dimensions": {
      "available": len(complete_dimensions),
      "missing": len(selected_pages) - len(complete_dimensions),
      "minimum_width_px": min((item[0] for item in complete_dimensions), default=None),
      "maximum_width_px": max((item[0] for item in complete_dimensions), default=None),
      "minimum_height_px": min((item[1] for item in complete_dimensions), default=None),
      "maximum_height_px": max((item[1] for item in complete_dimensions), default=None),
    },
    "available_date_ranges": {
      "parsed_count": len(parsed_dates),
      "earliest_not_before": min((item["not_before"] for item in parsed_dates), default=None),
      "latest_not_after": max((item["not_after"] for item in parsed_dates), default=None),
      "source_displays": [manuscript.get("date", {}).get("display") for manuscript in manuscripts if manuscript.get("date", {}).get("display")],
    },
    "metadata_completeness": metadata_completeness,
    "rights_review_status": dict(sorted(rights_distribution.items())),
    "training_allowed_true_count": sum(bool(page.get("image", {}).get("training_allowed")) for _, page in selected_pages),
    "split_counts": {
      "manuscripts": {name: manuscript_splits.get(name, 0) for name in ("train", "validation", "test")},
      "pages": {name: page_splits.get(name, 0) for name in ("train", "validation", "test")},
    },
  }


def statistics_markdown(statistics: dict[str, Any]) -> str:
  pages = statistics["pages_per_manuscript"]
  dimensions = statistics["dimensions"]
  splits = statistics["split_counts"]
  lines = [
    "# Training Corpus Builder v0.1 — Validation Report",
    "",
    "## Scope and safety boundary",
    "",
    "This milestone acquires and registers complete-page source representations from e-codices IIIF manifests. It does not train a model, generate artificial fragments, run reconstruction or retrieval, or assert that any source is approved for training. eManuSkript remains the optional downstream layout-analysis backbone.",
    "",
    "The corpus manifest distinguishes source evidence from selection inference: every normalized canvas remains recorded as a candidate, selected page, or rejected page; every rejection carries the explicit comparator/rule evidence that triggered it. Pages without an obvious exclusion stay candidates rather than being silently discarded.",
    "",
    "## Reproducible pipeline",
    "",
    "1. Read the committed YAML specification and reject duplicate manuscript identifiers or manifest URLs.",
    "2. Fetch each official IIIF manifest with the existing IIIF client; normalize v2/v3 metadata and HSP-aligned manuscript fields with the existing ingestion code.",
    "3. Record explicit obvious exclusions, deterministically rank remaining candidates from the recorded seed, and select at most the configured page limit.",
    "4. Assign train/validation/test at manuscript level from a separate recorded seed. Pages never receive an independent split.",
    "5. Download selected complete-page representations atomically, calculate SHA-256, and reuse checksum-verified existing assets on rerun.",
    "6. Register selected canvases through the existing `ingest_manifest()` repository/manuscript/cache/canvas/image-asset upserts. Downloaded bytes remain on the filesystem.",
    "",
    "Raw IIIF manifests and source-page binaries are under ignored `data/raw/`. Full raw manifest JSON is checksummed and also preserved in `iiif_manifest_cache.manifest_json` when registration is enabled. The compact committed corpus manifest carries raw normalized metadata, source references, selection decisions, downloads, checksums, database identifiers, rights, and split provenance.",
    "",
    "## Commands",
    "",
    "One-manuscript dry run (harvest/selection only):",
    "",
    "```bash",
    "python3 scripts/build_training_corpus.py --dry-run --limit-manuscripts 1 --max-pages 1",
    "```",
    "",
    "Required five-manuscript validation acquisition and registration:",
    "",
    "```bash",
    "bash scripts/db_migrate.sh",
    "python3 scripts/build_training_corpus.py --register",
    "bash scripts/validate_training_corpus.sh",
    "```",
    "",
    "Prepare, but do not automatically run, the existing eManuSkript workflow:",
    "",
    "```bash",
    "python3 scripts/build_training_corpus.py --register --prepare-segmentation",
    "```",
    "",
    "Add `--run-segmentation` only when an explicit segmentation run is intended. The command delegates to `scripts/run_segmentation_pilot.py`; it does not duplicate model inference.",
    "",
    "## Validation result",
    "",
    "The validation build was rerun unchanged after initial download. All selected assets reported `verified_existing`, demonstrating that checksum-verified representations were not downloaded again. The database validator confirmed local paths, checksums, canvas/image relationships, `pending_review` rights state, and `training_allowed = false`.",
    "",
    f"- Corpus: `{statistics['corpus_id']}`",
    f"- Manuscripts: {statistics['manuscript_count']}",
    f"- Selected pages: {statistics['selected_page_count']}",
    f"- Pages/manuscript: min {pages['minimum']}, max {pages['maximum']}, mean {pages['mean']}",
    f"- Download dimensions available: {dimensions['available']} (width {dimensions['minimum_width_px']}–{dimensions['maximum_width_px']} px; height {dimensions['minimum_height_px']}–{dimensions['maximum_height_px']} px)",
    "",
    "## Corpus statistics",
    "",
    "### Repository distribution",
    "",
  ]
  lines.extend(f"- {name}: {count}" for name, count in statistics["repository_distribution"].items())
  lines.extend(["", "### Rights review status", ""])
  lines.extend(f"- {name}: {count}" for name, count in statistics["rights_review_status"].items())
  lines.extend([
    f"- Explicitly training-allowed pages: {statistics['training_allowed_true_count']}",
    "",
    "### Manuscript-isolated splits",
    "",
  ])
  for name in ("train", "validation", "test"):
    lines.append(f"- {name}: {splits['manuscripts'][name]} manuscripts, {splits['pages'][name]} pages")
  lines.extend(["", "### Metadata completeness", ""])
  for name, values in statistics["metadata_completeness"].items():
    lines.append(f"- {name}: {values['present']}/{statistics['manuscript_count']} ({values['fraction']:.1%})")
  lines.extend(["", "### Canvas decisions", ""])
  lines.extend(f"- {name}: {count}" for name, count in statistics["canvas_status_counts"].items())
  lines.extend([
    "",
    "All rejected canvases retain an explicit rule match and evidence in the corpus manifest. Unselected eligible canvases remain recorded as candidates.",
    "",
    "## Validation interpretation and next boundary",
    "",
    "This validates source acquisition and registration at 5 manuscripts × 3 pages. It does not complete the approximately 100-manuscript target and it does not authorize model training. Before expanding the specification, review the 45 explicit rejections, sample the retained candidates, confirm storage expectations, and conduct source-by-source rights review. The eventual training dataset must query only assets explicitly changed to `approved_for_training` and `training_allowed = true` through a separate reviewed process.",
    "",
  ])
  return "\n".join(lines)


def build_corpus(
  spec: dict[str, Any],
  *,
  root: Path,
  specification_path: Path,
  output_manifest_path: Path,
  statistics_yaml_path: Path,
  statistics_report_path: Path,
  limit_manuscripts: int | None = None,
  max_pages_override: int | None = None,
  dry_run: bool = False,
  register: bool = False,
  timeout_seconds: int = 120,
) -> dict[str, Any]:
  validate_specification(spec)
  if dry_run and register:
    raise ValueError("--register cannot be combined with --dry-run")
  entries = [entry for entry in spec["manuscripts"] if entry.get("enabled", True)]
  if limit_manuscripts is not None:
    if limit_manuscripts < 1:
      raise ValueError("limit_manuscripts must be at least 1")
    entries = entries[:limit_manuscripts]
  max_pages = max_pages_override or int(spec.get("max_pages_per_manuscript", 5))
  if max_pages < 1:
    raise ValueError("max_pages must be at least 1")
  split_ratios = {name: float(value) for name, value in spec.get("split_ratios", {"train": 0.70, "validation": 0.15, "test": 0.15}).items()}
  selection_rules_version = spec.get("selection_rules_version", SELECTION_RULES_VERSION)
  split_by_id = assign_manuscript_splits((entry["id"] for entry in entries), spec["split_seed"], split_ratios)
  download_root = root / spec.get("download_root", f"data/raw/{spec['corpus_id']}")
  previous = load_yaml(output_manifest_path) if output_manifest_path.exists() else None
  previous_pages = _previous_selected_pages(previous)
  harvested: list[tuple[dict[str, Any], NormalizedManifest, dict[str, Any], dict[str, str | None]]] = []

  for entry in entries:
    manifest_url = canonical_manifest_url(entry["manifest_url"])
    raw_manifest, source_identifier, fetch_headers = fetch_manifest_url(manifest_url, timeout_seconds=timeout_seconds)
    normalized = normalize_manifest(raw_manifest, source_identifier)
    metadata = manuscript_metadata(entry, normalized)
    decisions = select_canvas_pages(
      entry["id"],
      normalized.canvases,
      spec["selection_seed"],
      max_pages,
      rules_version=selection_rules_version,
    )
    canvas_by_id = {canvas.canvas_identifier: canvas for canvas in normalized.canvases}
    raw_artifact = None if dry_run else _raw_manifest_artifact(root, download_root, entry["id"], raw_manifest)
    pages: list[dict[str, Any]] = []
    for decision in decisions:
      canvas = canvas_by_id[decision["canvas_identifier"]]
      page = {**decision, "image": _page_image_record(canvas)}
      pages.append(page)
    record = {
      "id": entry["id"],
      "repository": metadata["repository"],
      "shelfmark": metadata["shelfmark"],
      "manifest_url": manifest_url,
      "manifest_id": normalized.manifest_id,
      "title": metadata["title"],
      "date": metadata["date"],
      "language": metadata["language"],
      "script": metadata["script"],
      "material": metadata["material"],
      "rights_statement": normalized.rights_statement,
      "license": normalized.license,
      "attribution": normalized.attribution,
      "rights_review_status": spec.get("rights_review_status", "pending_review"),
      "training_allowed": False,
      "split": split_by_id[entry["id"]],
      "raw_source_metadata": {
        "normalized_metadata": normalized.metadata,
        "raw_manifest_artifact": raw_artifact,
        "manifest_fetch_headers": fetch_headers,
        "database_preservation": "iiif_manifest_cache.manifest_json when registration is enabled",
      },
      "pages": pages,
    }
    harvested.append((record, normalized, raw_manifest, fetch_headers))

  manuscript_records = [item[0] for item in harvested]
  ensure_unique_pages(manuscript_records)

  if not dry_run:
    image_request = spec.get("image_request", {})
    rights_status = spec.get("rights_review_status", "pending_review")
    for manuscript_record, normalized, _, _ in harvested:
      canvas_by_id = {canvas.canvas_identifier: canvas for canvas in normalized.canvases}
      for page in manuscript_record["pages"]:
        if page["selection_status"] != "selected":
          continue
        canvas = canvas_by_id[page["canvas_identifier"]]
        source_image = canvas.images[0]
        request_url = image_request_url(source_image, image_request)
        destination = _selected_download_path(download_root, manuscript_record["id"], page)
        previous_page = previous_pages.get(page["canvas_identifier"], {})
        previous_image = previous_page.get("image") or {}
        expected = None
        if previous_image.get("download_url") == request_url and previous_image.get("local_path") == relative_path(destination, root):
          expected = previous_image.get("checksum_sha256")
        result = download_resumable(
          request_url,
          destination,
          expected_sha256=expected,
          timeout_seconds=timeout_seconds,
        )
        response_headers = result["response_headers"]
        if result["status"] == "verified_existing" and previous_image.get("response_headers"):
          response_headers = previous_image["response_headers"]
        page["image"].update({
          "download_url": request_url,
          "local_path": relative_path(destination, root),
          "checksum_sha256": result["sha256"],
          "checksum_algorithm": "sha256",
          "size_bytes": result["size_bytes"],
          "download_width_px": result["width_px"],
          "download_height_px": result["height_px"],
          "color_mode": result["color_mode"],
          "download_status": result["status"],
          "response_headers": response_headers,
          "rights_statement": normalized.rights_statement,
          "license": normalized.license,
          "attribution": normalized.attribution,
          "rights_review_status": rights_status,
          "training_allowed": False,
        })

    if register:
      for manuscript_record, normalized, _, fetch_headers in harvested:
        register_selected_manuscript(
          normalized,
          manuscript_record,
          corpus_id=spec["corpus_id"],
          rights_review_status=spec.get("rights_review_status", "pending_review"),
          fetch_headers=fetch_headers,
        )

  payload = {
    "corpus_id": spec["corpus_id"],
    "builder_version": BUILDER_VERSION,
    "status": "dry_run" if dry_run else ("downloaded_and_registered" if register else "downloaded_not_registered"),
    "purpose": "Complete-page IIIF source acquisition and registration only; no model training or reconstruction.",
    "specification": {
      "path": relative_path(specification_path, root),
      "sha256": sha256_file(specification_path),
    },
    "selection": {
      "seed": spec["selection_seed"],
      "max_pages_per_manuscript": max_pages,
      "rules_version": selection_rules_version,
      "uncertainty_policy": "Only explicit obvious exclusions are rejected; uncertain auxiliary canvases remain candidates and require manual review before selection.",
    },
    "splits": {"seed": spec["split_seed"], "ratios": split_ratios, "unit": "manuscript"},
    "rights_policy": {
      "rights_review_status": spec.get("rights_review_status", "pending_review"),
      "training_allowed": False,
      "approval_requirement": "A later training dataset may include only explicitly approved source assets.",
    },
    "manuscripts": manuscript_records,
  }
  statistics = build_statistics(payload)
  payload["statistics"] = statistics
  write_yaml(output_manifest_path, payload)
  write_yaml(statistics_yaml_path, statistics)
  statistics_report_path.parent.mkdir(parents=True, exist_ok=True)
  statistics_report_path.write_text(statistics_markdown(statistics), encoding="utf-8")
  return payload


def segmentation_input_manifest(corpus_manifest: dict[str, Any], model_path: str) -> dict[str, Any]:
  selected_inputs: list[dict[str, Any]] = []
  for manuscript in corpus_manifest.get("manuscripts", []):
    for page in manuscript.get("pages", []):
      if page.get("selection_status") != "selected":
        continue
      registration = page.get("registration", {})
      db_ids = registration.get("db_ids", {})
      selected_inputs.append({
        "sample_id": stable_digest(corpus_manifest["corpus_id"], page["canvas_identifier"])[:20],
        "sample_kind": "full_page",
        "category": "training_corpus_source_page",
        "source": "e-codices",
        "source_url": page["image"]["download_url"],
        "local_path": page["image"]["local_path"],
        "db_image_asset_id": db_ids.get("image_asset_id"),
        "db_canvas_id": db_ids.get("canvas_id"),
        "db_fragment_id": None,
        "rights_review_status": page["image"]["rights_review_status"],
        "access_level": "internal",
        "selected_for": "optional_existing_emanuskript_segmentation",
        "readiness_status": "ready",
        "manuscript_id": manuscript["id"],
        "dataset_split": manuscript["split"],
      })
  return {
    "pilot_run_id": f"{corpus_manifest['corpus_id']}_emanuskript_segmentation",
    "dataset_id": corpus_manifest["corpus_id"],
    "status": "prepared",
    "purpose": "Optional invocation of the existing eManuSkript segmentation workflow on selected source pages.",
    "model_id": "best_emanuskript_segmentation",
    "model_path": model_path,
    "inference_run": False,
    "segmentation_run": False,
    "selected_inputs": selected_inputs,
  }
