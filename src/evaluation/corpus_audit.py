"""Read-only complete-page corpus audit; source evidence and review remain separate."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import sys
from statistics import mean, median, pstdev
from urllib.parse import urlparse

from PIL import Image, ImageChops
import yaml

from .artificial_fragments import canonical_json, sha256_file
from .artificial_fragment_registration import resolve_local_path
from .segmentation_masks import validate_binary_mask

BATCHES = (
  ("training_corpus_validation", "training_corpus_segmentation"),
  ("training_corpus_expansion_batch_01", "training_corpus_expansion_batch_01_segmentation"),
)
SPLITS = ("train", "validation", "test")
LOW_CONFIDENCE_MEAN = 0.40
REVIEW_CLASSES = (
  "valid_zero_content_or_nonstandard_page", "probable_segmentation_failure",
  "low_confidence_but_usable", "requires_human_review",
)


def digest(value):
  return sha256(canonical_json(value).encode()).hexdigest()


def write_stable(path, payload):
  """No timestamps; preserve mtime when serialized content is unchanged."""
  content = payload if isinstance(payload, str) else json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
  path.parent.mkdir(parents=True, exist_ok=True)
  if not path.exists() or path.read_text() != content:
    path.write_text(content)


def distribution(values):
  values = sorted(v for v in values if v is not None)
  return {"count": len(values), "mean": round(mean(values), 10) if values else None,
          "median": median(values) if values else None, "minimum": min(values) if values else None,
          "maximum": max(values) if values else None,
          "population_standard_deviation": round(pstdev(values), 10) if len(values) > 1 else None}


def artifact(root, path):
  file = resolve_local_path(root, path)
  if not file.is_file():
    raise ValueError(f"missing_artifact:{path}")
  # Darwin sys/stat.h SF_DATALESS: avoid unbounded iCloud recall timeouts.
  if sys.platform == "darwin" and getattr(file.stat(), "st_flags", 0) & 0x40000000:
    raise ValueError(f"unavailable_local_artifact_icloud_dataless:{path}")
  return {"path": path, "sha256": sha256_file(file), "size_bytes": file.stat().st_size}


def read_region_mask(root, detection, size):
  """Validate the whole source-sized mask, including pixels outside its bbox."""
  path = detection.get("mask_path")
  if not path:
    raise ValueError("missing_segmentation_mask")
  ref = artifact(root, path)
  if ref["sha256"] != detection.get("mask_sha256"):
    raise ValueError(f"segmentation_mask_checksum_mismatch:{path}")
  with Image.open(resolve_local_path(root, path)) as image:
    validate_binary_mask(image, tuple(size))
    mask = image.copy()
  area = mask.histogram()[255]
  if area <= 0 or area != detection.get("mask_pixel_area"):
    raise ValueError(f"invalid_segmentation_mask_area:{path}")
  if list(size) != detection.get("mask_dimensions_px"):
    raise ValueError(f"segmentation_mask_dimensions_mismatch:{path}")
  return mask


def load_corpus(root, batches=BATCHES):
  """Join immutable manifests and their declared segmentation runs by asset ID."""
  pages, manuscripts, inputs = [], {}, []
  for corpus_prefix, segmentation_prefix in batches:
    docs = {}
    for key, name in (("corpus", corpus_prefix + "_manifest"),
                      ("results", segmentation_prefix + "_results"),
                      ("storage", segmentation_prefix + "_storage_results")):
      path = f"data/metadata/{name}.yaml"
      inputs.append(artifact(root, path))
      docs[key] = yaml.safe_load((root / path).read_text())
    corpus, results, storage = (docs[k] for k in ("corpus", "results", "storage"))
    if corpus["status"] != "downloaded_and_registered":
      raise ValueError("corpus_not_registered")
    by_asset = {r["db_image_asset_id"]: r for r in results["results"]}
    stored = {r["db_image_asset_id"]: r for r in storage["samples"]}
    if len(by_asset) != len(results["results"]) or len(stored) != len(storage["samples"]):
      raise ValueError("duplicate_segmentation_asset")
    for manuscript in corpus["manuscripts"]:
      mid = manuscript["id"]
      info = {k: deepcopy(manuscript.get(k)) for k in ("id", "repository", "split", "manifest_url", "script", "language", "date", "material")}
      if mid in manuscripts and manuscripts[mid] != info:
        raise ValueError(f"conflicting_manuscript_assignment:{mid}")
      manuscripts[mid] = info
      for page in manuscript["pages"]:
        if page["selection_status"] != "selected":
          continue
        if page.get("registration", {}).get("status") != "registered":
          raise ValueError("selected_page_not_registered")
        ids, image = page["registration"]["db_ids"], page["image"]
        result, stored_run = by_asset.get(ids["image_asset_id"], {}), stored.get(ids["image_asset_id"], {})
        pages.append({
          "page_id": result.get("sample_id", ids["image_asset_id"]), "manuscript_id": mid,
          "corpus_id": corpus["corpus_id"], "split": manuscript["split"],
          "canvas_identifier": page["canvas_identifier"], "canvas_label": page.get("canvas_label"),
          "repository": manuscript.get("repository"), "provider": urlparse(manuscript["manifest_url"]).netloc,
          "source_path": image["local_path"], "source_sha256": image.get("checksum_sha256"),
          "dimensions_px": [image.get("download_width_px"), image.get("download_height_px")],
          "source_size_bytes": image.get("size_bytes"), "db_ids": ids,
          "source_record": deepcopy(page), "result": result, "stored_run": stored_run,
          "model": {k: results.get(k) for k in ("model_id", "model_sha256", "run_identity_sha256", "confidence_threshold", "imgsz")},
        })
  for key in ("page_id", "source_path", "canvas_identifier"):
    if len({p[key] for p in pages}) != len(pages):
      raise ValueError(f"duplicate_corpus_{key}")
  if len({p["db_ids"]["image_asset_id"] for p in pages}) != len(pages):
    raise ValueError("duplicate_corpus_asset")
  return sorted(pages, key=lambda p: p["page_id"]), dict(sorted(manuscripts.items())), sorted(inputs, key=lambda p: p["path"])


def inspect_page(root, page):
  """Artifact failures are explicit; an empty successful detection set is valid evidence."""
  p = deepcopy(page)
  p.update(errors=[], artifacts=[], detections=[], confidence=distribution([]), mask_areas=[],
           union_mask_area_px=None, class_counts={}, valid_mask_count=0)
  try:
    source = artifact(root, p["source_path"])
    p["artifacts"].append(source)
    if source["sha256"] != p["source_sha256"]:
      raise ValueError("source_checksum_mismatch")
    with Image.open(resolve_local_path(root, p["source_path"])) as image:
      image.verify()
      if list(image.size) != p["dimensions_px"]:
        raise ValueError("source_dimensions_mismatch")
    if source["size_bytes"] != p["source_size_bytes"]:
      raise ValueError("source_size_mismatch")
  except (ValueError, OSError, KeyError) as exc:
    p["errors"].append(str(exc))
  try:
    r, s = p["result"], p["stored_run"]
    if r.get("status") != "success" or not s.get("db_segmentation_run_id"):
      raise ValueError("missing_successful_stored_segmentation")
    for record in (r, s):
      if record.get("dataset_split") != p["split"] or record.get("db_image_asset_id") != p["db_ids"]["image_asset_id"]:
        raise ValueError("segmentation_source_or_split_mismatch")
    for key in ("raw_output_path", "overlay_path"):
      p["artifacts"].append(artifact(root, r[key]))
    raw = json.loads((root / r["raw_output_path"]).read_text())
    if raw.get("sample_id") != p["page_id"] or raw.get("status") != "success":
      raise ValueError("raw_segmentation_identity_or_status_mismatch")
    if raw.get("orig_shape") != list(reversed(p["dimensions_px"])):
      raise ValueError("segmentation_source_dimensions_mismatch")
    p["raw"] = raw
    p["detections"] = raw["detections"]
    if len(raw["detections"]) != r["detected_region_count"] or len(raw["detections"]) != s["layout_region_count"]:
      raise ValueError("segmentation_detection_count_mismatch")
    indices = [d["index"] for d in raw["detections"]]
    if len(set(indices)) != len(indices):
      raise ValueError("duplicate_region_index")
    p["confidence"] = distribution([d.get("confidence") for d in raw["detections"]])
    p["class_counts"] = dict(sorted(Counter(d["label"] for d in raw["detections"]).items()))
    union = Image.new("L", tuple(p["dimensions_px"]), 0)
    for detection in sorted(raw["detections"], key=lambda d: d["index"]):
      try:
        mask = read_region_mask(root, detection, p["dimensions_px"])
        union = ImageChops.lighter(union, mask)
        p["mask_areas"].append(mask.histogram()[255])
        p["valid_mask_count"] += 1
        p["artifacts"].append(artifact(root, detection["mask_path"]))
      except (ValueError, OSError) as exc:
        p["errors"].append(str(exc))
    if p["valid_mask_count"] == len(raw["detections"]):
      p["union_mask_area_px"] = union.histogram()[255]
  except (ValueError, OSError, KeyError) as exc:
    p["errors"].append(str(exc))
  p["errors"] = sorted(set(p["errors"]))
  return p


def audit_corpus(pages, manuscripts, inputs):
  pages = sorted(pages, key=lambda p: p["page_id"])
  by_split = {s: [p for p in pages if p["split"] == s] for s in SPLITS}
  counts = Counter(p["manuscript_id"] for p in pages)
  classes = sorted({c for p in pages for c in p["class_counts"]})
  class_split = {c: {s: sum(p["class_counts"].get(c, 0) for p in by_split[s]) for s in SPLITS} for c in classes}
  zero = [p["page_id"] for p in pages if not p["errors"] and not p["detections"]]
  low = [p["page_id"] for p in pages if p["confidence"]["mean"] is not None and p["confidence"]["mean"] < LOW_CONFIDENCE_MEAN]
  return {
    "audit_version": "complete_page_corpus_audit_v0_2", "inputs": inputs,
    "scientific_note": "Segmentation is model-derived evidence. Counts and coverage do not measure manuscript content completeness or recovery.",
    "structure": {"total_pages": len(pages), "page_bearing_manuscripts": len(counts), "assigned_manuscripts": len(manuscripts),
      "pages_per_manuscript": {m: counts[m] for m in sorted(manuscripts)},
      "pages_per_split": {s: len(by_split[s]) for s in SPLITS},
      "page_bearing_manuscripts_per_split": {s: len({p["manuscript_id"] for p in by_split[s]}) for s in SPLITS},
      "assigned_manuscripts_per_split": {s: sum(m["split"] == s for m in manuscripts.values()) for s in SPLITS},
      "pages_by_repository": dict(sorted(Counter(p["repository"] for p in pages).items())),
      "pages_by_provider": dict(sorted(Counter(p["provider"] for p in pages).items()))},
    "images": {"width_px": distribution(p["dimensions_px"][0] for p in pages),
      "height_px": distribution(p["dimensions_px"][1] for p in pages),
      "aspect_ratio": distribution(p["dimensions_px"][0] / p["dimensions_px"][1] for p in pages),
      "file_size_bytes": distribution(p["source_size_bytes"] for p in pages),
      "database_vs_acquired_dimensions_differ_count": sum(p.get("database_dimensions_px", p["dimensions_px"]) != p["dimensions_px"] for p in pages),
      "dimension_note": "Image statistics use acquired rasters. Existing DB dimensions preserve advertised IIIF dimensions and are not rewritten.",
      "source_checksum_recorded_count": sum(bool(p["source_sha256"]) for p in pages),
      "source_checksum_verified_count": sum(any(a["path"] == p["source_path"] and a["sha256"] == p["source_sha256"] for a in p["artifacts"]) for p in pages)},
    "segmentation": {"declared_run_count": len({p["stored_run"].get("db_segmentation_run_id") for p in pages} - {None}),
      "total_layout_regions": sum(len(p["detections"]) for p in pages),
      "regions_per_page": distribution(len(p["detections"]) for p in pages if "raw" in p),
      "zero_region_pages": zero, "low_confidence_mean_threshold": LOW_CONFIDENCE_MEAN, "low_confidence_pages": low,
      "region_counts_by_class_and_split": class_split,
      "valid_mask_count": sum(p["valid_mask_count"] for p in pages),
      "mask_area_px": distribution(a for p in pages for a in p["mask_areas"]),
      "union_mask_fraction_of_source_raster": distribution(p["union_mask_area_px"] / (p["dimensions_px"][0] * p["dimensions_px"][1]) for p in pages if p["union_mask_area_px"] is not None),
      "pages_missing_or_invalid_artifacts": [{"page_id": p["page_id"], "reasons": p["errors"]} for p in pages if p["errors"]]},
    "diversity": {"largest_manuscript_page_fraction": max(counts.values(), default=0) / len(pages) if pages else None,
      "classes_missing_from_validation": [c for c in classes if class_split[c]["validation"] == 0],
      "classes_missing_from_test": [c for c in classes if class_split[c]["test"] == 0],
      "script_metadata_missing_manuscripts": sum(not m.get("script") for m in manuscripts.values()),
      "outliers_by_manuscript": dict(sorted(Counter(p["manuscript_id"] for p in pages if p["page_id"] in set(zero + low)).items()))},
    "pages": [{k: p[k] for k in ("page_id", "manuscript_id", "split", "canvas_label", "source_path", "source_sha256", "dimensions_px", "source_size_bytes", "confidence", "class_counts", "valid_mask_count", "union_mask_area_px", "errors")} for p in pages],
  }


def review_outliers(pages, flags, decisions):
  """Replay explicitly recorded visual observations only against their exact evidence."""
  by_id = {p["page_id"]: p for p in pages}
  reviews = []
  for reason, ids in sorted(flags.items()):
    for page_id in sorted(ids):
      p = by_id[page_id]
      decision = deepcopy(decisions.get(page_id, {}))
      evidence = sorted(p["artifacts"], key=lambda a: a["path"])
      valid_review = decision.get("evidence_sha256") == digest(evidence)
      classification = decision.get("classification") if valid_review else "requires_human_review"
      if classification not in REVIEW_CLASSES:
        raise ValueError("invalid_review_classification")
      reviews.append({"page_id": page_id, "manuscript_id": p["manuscript_id"], "canvas_label": p["canvas_label"],
        "canvas_identifier": p["canvas_identifier"], "split": p["split"], "source_asset": p["db_ids"],
        "source_path": p["source_path"], "source_sha256": p["source_sha256"], "dimensions_px": p["dimensions_px"],
        "segmentation_run_id": p["stored_run"].get("db_segmentation_run_id"), "model": p["model"],
        "detected_regions": len(p["detections"]), "confidence": p["confidence"], "flag_reason": reason,
        "classification": classification, "evidence": evidence, "evidence_sha256": digest(evidence),
        "review": decision if valid_review else {"note": "No review matches current artifacts; human review required."},
        "artifact_errors": p["errors"], "corpus_decision": "retained_without_reclassification_or_split_change"})
  return {"review_version": "segmentation_outlier_review_v0_2", "classification_vocabulary": list(REVIEW_CLASSES),
          "review_is_scholarly_approval": False, "outliers": sorted(reviews, key=lambda p: p["page_id"])}


def audit_markdown(audit):
  s, seg, div = audit["structure"], audit["segmentation"], audit["diversity"]
  lines = ["# Complete-page corpus diversity audit v0.2", "",
    "Read-only measurements of the registered corpus. eManuSkript masks are model-derived layout evidence, not manual annotations.", "",
    f"{s['total_pages']} pages; {s['page_bearing_manuscripts']} page-bearing manuscripts; {s['assigned_manuscripts']} assigned manuscripts (including zero-page assignments).", "",
    "| Split | Pages | Page-bearing manuscripts | Assigned manuscripts |", "| --- | ---: | ---: | ---: |"]
  for split in SPLITS:
    lines.append(f"| {split} | {s['pages_per_split'][split]} | {s['page_bearing_manuscripts_per_split'][split]} | {s['assigned_manuscripts_per_split'][split]} |")
  lines += ["", "## Image characteristics", "", "```json", json.dumps(audit["images"], indent=2), "```", "",
    "## Layout evidence", "", f"{seg['declared_run_count']} declared runs; {seg['total_layout_regions']} regions; {seg['valid_mask_count']} verified source-sized masks.", "",
    f"Regions per page: {seg['regions_per_page']}", "", f"Union mask coverage (overlapping instances counted once): {seg['union_mask_fraction_of_source_raster']}", "",
    f"Zero-region pages: {', '.join(seg['zero_region_pages']) or 'none'}. Low-confidence pages (mean < {LOW_CONFIDENCE_MEAN}): {', '.join(seg['low_confidence_pages']) or 'none'}.", "",
    "| Model class | Train regions | Validation regions | Test regions |", "| --- | ---: | ---: | ---: |"]
  for cls, counts in seg["region_counts_by_class_and_split"].items():
    lines.append(f"| {cls} | {counts['train']} | {counts['validation']} | {counts['test']} |")
  lines += ["", "## Quantitative gaps", "",
    f"Largest manuscript contributes {div['largest_manuscript_page_fraction']:.2%} of pages. Pages per manuscript: `{s['pages_per_manuscript']}`.", "",
    f"Provider concentration: `{s['pages_by_provider']}`. Repository distribution: `{s['pages_by_repository']}`.", "",
    f"Classes absent in validation: {', '.join(div['classes_missing_from_validation'])}. Classes absent in test: {', '.join(div['classes_missing_from_test'])}.", "",
    f"Script metadata is missing for {div['script_metadata_missing_manuscripts']} assigned manuscripts; no script-diversity claim is supported. Outlier concentration: `{div['outliers_by_manuscript']}`.", "",
    f"Missing/invalid artifact pages: `{seg['pages_missing_or_invalid_artifacts']}`.", "",
    "Inspect the machine-readable audit for per-page dimensions, density, confidence and checksums. Image ratios describe acquired rasters, not physical codex dimensions. Zero detections do not establish zero manuscript content. Test inspection here is a read-only structural audit; test pages remain excluded from v0.2 experiments.", ""]
  return "\n".join(lines)
