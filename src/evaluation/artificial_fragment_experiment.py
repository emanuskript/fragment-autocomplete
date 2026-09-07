"""Segmentation-aware validation experiment around the unchanged v0.1 generator."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
import json

from PIL import Image, ImageChops

from .artificial_fragments import (
  ArtifactPaths, GENERATION_VERSION, MASK_FAMILIES, GenerationConfig, SourcePage,
  generate_fragment_task, stable_seed, sha256_file,
)
from .artificial_fragment_registration import _validate_full_task, validate_artifact
from .corpus_audit import digest, distribution, read_region_mask, write_stable
from .segmentation_masks import validate_binary_mask

EXPERIMENT_VERSION = "artificial_fragment_experiment_v0_2"
OUTPUT = "outputs/artificial_fragments/v0_2"
SEVERITIES = (0.30, 0.60)
BASE_SEED = 20260907
SURVIVAL_THRESHOLDS = {"almost_complete_min": 0.95, "mostly_destroyed_max": 0.05, "fully_removed": 0.0}


def survival_category(fraction):
  if fraction is None:
    return "undefined"
  if not 0 <= fraction <= 1:
    raise ValueError("survival_fraction_outside_unit_interval")
  if fraction == SURVIVAL_THRESHOLDS["fully_removed"]:
    return "fully_removed"
  if fraction <= SURVIVAL_THRESHOLDS["mostly_destroyed_max"]:
    return "mostly_destroyed"
  if fraction >= SURVIVAL_THRESHOLDS["almost_complete_min"]:
    return "almost_complete"
  return "partial"


def mask_overlap(region, survival):
  """Full-raster pixel counts; no bbox and no inference about missing content."""
  validate_binary_mask(survival)
  validate_binary_mask(region, survival.size)
  area = region.histogram()[255]
  surviving = ImageChops.multiply(region, survival).histogram()[255]
  return {"source_region_area_px": area, "surviving_area_px": surviving,
          "removed_area_px": area - surviving,
          "surviving_fraction": surviving / area if area else None,
          "removed_fraction": (area - surviving) / area if area else None}


def measure_regions(root, detections, survival, run_id):
  regions = []
  for d in sorted(detections, key=lambda d: d["index"]):
    mask = read_region_mask(root, d, survival.size)
    metrics = mask_overlap(mask, survival)
    regions.append({**metrics, "source_region_index": d["index"],
      "source_region_identifier": f"{run_id}:{d['index']}", "db_layout_region_id": d.get("db_layout_region_id"),
      "label": d["label"], "class_id": d["class_id"], "confidence": d.get("confidence"),
      "geometry_method": "segmentation_mask", "mask_path": d["mask_path"], "mask_sha256": d["mask_sha256"],
      "mask_dimensions_px": list(survival.size), "survival_category": survival_category(metrics["surviving_fraction"])})
  return regions


def region_summary(regions):
  area = sum(r["source_region_area_px"] for r in regions)
  return {"metric_name": "segmentation_mask_pixel_survival", "geometry_method": "segmentation_mask",
    "total_regions": len(regions), "measurement_status": "measured" if regions else "no_detected_regions",
    "region_survival_fraction": distribution(r["surviving_fraction"] for r in regions),
    "area_weighted_surviving_fraction": sum(r["surviving_area_px"] for r in regions) / area if area else None,
    "interpretation_note": "Overlap with model-derived masks only; zero detections do not establish absent content."}


def page_evidence(page):
  return {"source_sha256": page["source_sha256"], "source_asset_id": page["db_ids"]["image_asset_id"],
    "segmentation_run_id": page["stored_run"]["db_segmentation_run_id"],
    "run_identity_sha256": page["model"]["run_identity_sha256"],
    "artifacts": sorted(page["artifacts"], key=lambda a: a["path"])}


def build_specification(pages):
  """Never resplit, replace an invalid page, or include a train/test source."""
  validation = sorted((p for p in pages if p["split"] == "validation"), key=lambda p: p["page_id"])
  if len({p["page_id"] for p in validation}) != len(validation):
    raise ValueError("duplicate_validation_page")
  selected, rejected, tasks = [], [], []
  for page in validation:
    if page["errors"]:
      rejected.append({"page_id": page["page_id"], "reasons": sorted(page["errors"])})
      continue
    evidence = page_evidence(page)
    evidence_sha = digest(evidence)
    selected.append({"page_id": page["page_id"], "manuscript_id": page["manuscript_id"], "split": "validation",
                     "evidence_sha256": evidence_sha, "evidence": evidence,
                     "layout_status": "no_detected_regions" if not page["detections"] else "model_masks_available"})
    for family in MASK_FAMILIES:
      for severity in SEVERITIES:
        seed = stable_seed(EXPERIMENT_VERSION, page["page_id"], family, BASE_SEED,
                           requested_severity=severity, variant=evidence_sha)
        descriptor = {"experiment_version": EXPERIMENT_VERSION, "page_id": page["page_id"],
                      "evidence_sha256": evidence_sha, "mask_family": family, "severity": severity, "seed": seed}
        config = GenerationConfig("afv02_" + digest(descriptor)[:24], family, severity, seed,
                                  task_group=EXPERIMENT_VERSION)
        tasks.append({"page_id": page["page_id"], "evidence_sha256": evidence_sha, **asdict(config)})
  return {"experiment_version": EXPERIMENT_VERSION, "generator_version": GENERATION_VERSION,
          "validation_page_count": len(validation), "selected_page_count": len(selected),
          "matrix_task_count": len(tasks), "mask_families": list(MASK_FAMILIES), "severities": list(SEVERITIES),
          "base_seed": BASE_SEED, "rotation_degrees": 0.0, "scale": 1.0,
          "survival_thresholds": SURVIVAL_THRESHOLDS,
          "zero_detection_policy": "include_page_metrics; region_survival_undefined; never infer zero content",
          "test_policy": "frozen_and_excluded", "selected_pages": selected, "rejected_pages": rejected, "tasks": tasks}


def task_paths(root, task_id):
  out = root / OUTPUT / "tasks" / task_id
  return ArtifactPaths(out / "fragment.png", out / "observed_mask.png", out / "survival.png", out / "damage.png", out / "metadata.json")


def generate_task(root, page, entry):
  if page["split"] != "validation" or page["errors"]:
    raise ValueError("only_valid_validation_pages_may_generate")
  if digest(page_evidence(page)) != entry["evidence_sha256"]:
    raise ValueError("experiment_evidence_changed")
  config = GenerationConfig(**{k: entry[k] for k in GenerationConfig.__dataclass_fields__})
  source_record = deepcopy(page["source_record"])
  source = SourcePage(page["page_id"], "complete_corpus_page", "e-codices",
    source_record["image"].get("download_url"), page["source_path"],
    source_record["image"].get("rights_review_status"), page.get("database_asset", {}).get("access_level", "internal"),
    page["db_ids"], {}, {"corpus_id": page["corpus_id"], "manuscript_id": page["manuscript_id"],
      "split": page["split"], "rights": deepcopy(source_record["image"])},
    {"corpus_page": source_record, "database_asset": deepcopy(page.get("database_asset", {}))})
  provenance = {**page["model"], "sample_id": page["page_id"], "orig_shape": list(reversed(page["dimensions_px"])),
    "raw_output_path": page["result"]["raw_output_path"], "db_segmentation_run_id": page["stored_run"]["db_segmentation_run_id"],
    "evidence_sha256": entry["evidence_sha256"], "geometry_method": "segmentation_mask"}
  paths = task_paths(root, config.task_id)
  # Generate with no legacy region estimator: measure the authoritative full masks below.
  task = generate_fragment_task(root=root, source_page=source, config=config, artifacts=paths,
                               layout_detections=[], segmentation_run_provenance=provenance)
  with Image.open(paths.source_survival_mask) as survival:
    regions = measure_regions(root, page["detections"], survival, provenance["db_segmentation_run_id"])
  task["layout_survival_estimate"] = {"geometry_method": "segmentation_mask", "regions": regions,
    "summary": region_summary(regions), "segmentation_run_provenance": provenance}
  task["experiment_version"] = EXPERIMENT_VERSION
  task["manuscript_id"] = page["manuscript_id"]
  task["split_name"] = "validation"
  task["artificial_fragment_task_mapping"]["split_name"] = "validation"
  task["parameters"]["experiment"] = {"version": EXPERIMENT_VERSION, "evidence_sha256": entry["evidence_sha256"],
                                        "survival_thresholds": SURVIVAL_THRESHOLDS}
  task["actual_removed_pixel_fraction"] = task["measured_severity"]
  task["actual_surviving_pixel_fraction"] = task["surviving_fraction"]
  task["artifacts"].pop("metadata")
  write_stable(paths.metadata, task)
  task["artifacts"]["metadata"] = {"path": paths.metadata.relative_to(root).as_posix(), "sha256": sha256_file(paths.metadata)}
  return task


def load_task(root, ref):
  validate_artifact(root, "task_metadata", ref)
  task = json.loads((root / ref["path"]).read_text())
  task["artifacts"]["metadata"] = ref
  return task


def registration_records(root, specification, tasks):
  selected = {p["page_id"]: p for p in specification["selected_pages"]}
  expected = {t["task_id"]: t for t in specification["tasks"]}
  if len(tasks) != len(expected) or {t["task_id"] for t in tasks} != set(expected):
    raise ValueError("incomplete_or_duplicate_experiment_matrix")
  records = []
  for task in sorted(tasks, key=lambda t: t["task_id"]):
    entry = expected[task["task_id"]]
    if task["experiment_version"] != EXPERIMENT_VERSION or task["split_name"] != "validation":
      raise ValueError("v02_registration_requires_validation_split")
    if task["source_sample_id"] != entry["page_id"]:
      raise ValueError("experiment_source_mismatch")
    for key in ("mask_family", "random_seed", "requested_severity", "rotation_degrees", "scale", "task_group"):
      if task[key] != entry[key]:
        raise ValueError(f"experiment_parameter_mismatch:{key}")
    layout = task["layout_survival_estimate"]
    evidence = selected[entry["page_id"]]["evidence"]
    if (task["source_image_asset_id"] != evidence["source_asset_id"]
        or task["source_sha256"] != evidence["source_sha256"]
        or layout["segmentation_run_provenance"]["db_segmentation_run_id"] != evidence["segmentation_run_id"]):
      raise ValueError("experiment_source_or_run_binding_mismatch")
    evidence_artifacts = {a["path"]: a["sha256"] for a in evidence["artifacts"]}
    for region in layout["regions"]:
      if evidence_artifacts.get(region["mask_path"]) != region["mask_sha256"]:
        raise ValueError("experiment_region_mask_binding_mismatch")
    if layout["geometry_method"] != "segmentation_mask" or any(r["geometry_method"] != "segmentation_mask" for r in layout["regions"]):
      raise ValueError("v02_requires_segmentation_masks")
    if layout["segmentation_run_provenance"]["evidence_sha256"] != entry["evidence_sha256"]:
      raise ValueError("experiment_segmentation_evidence_mismatch")
    records.append(_validate_full_task(root, task, task["artifacts"]["metadata"]))
  if len({r.database_id for r in records}) != len(records):
    raise ValueError("duplicate_scientific_identity")
  return records


def aggregate(tasks):
  tasks = sorted(tasks, key=lambda t: t["task_id"])
  groups = {name: defaultdict(list) for name in ("mask_family", "requested_severity", "manuscript", "page", "layout_class")}
  for t in tasks:
    for name, key in (("mask_family", "mask_family"), ("requested_severity", "requested_severity"), ("manuscript", "manuscript_id"), ("page", "source_sample_id")):
      groups[name][str(t[key])].append(t)
    for label in sorted({r["label"] for r in t["layout_survival_estimate"]["regions"]}):
      groups["layout_class"][label].append(t)
  summaries = {}
  for name, group in groups.items():
    summaries[name] = {}
    for value, group_tasks in sorted(group.items()):
      regions = [r for t in group_tasks for r in t["layout_survival_estimate"]["regions"] if name != "layout_class" or r["label"] == value]
      counts = Counter(survival_category(r["surviving_fraction"]) for r in regions)
      n = len(regions)
      summaries[name][value] = {"task_count": len(group_tasks), "region_measurement_count": n,
        "page_surviving_fraction": distribution(t["surviving_fraction"] for t in group_tasks),
        "region_surviving_fraction": distribution(r["surviving_fraction"] for r in regions),
        "survival_categories": {c: {"count": counts[c], "fraction": counts[c] / n if n else None}
          for c in ("almost_complete", "partial", "mostly_destroyed", "fully_removed", "undefined")}}
  return {"experiment_version": EXPERIMENT_VERSION, "task_count": len(tasks),
    "region_measurement_count": sum(len(t["layout_survival_estimate"]["regions"]) for t in tasks),
    "tasks_without_detected_regions": sum(not t["layout_survival_estimate"]["regions"] for t in tasks),
    "survival_thresholds": SURVIVAL_THRESHOLDS, "groups": summaries,
    "statistics_note": "Population SD; null for fewer than two observations. Region statistics weight instances equally; class task counts count only tasks containing that class. Repeated tasks are controlled transformations, not independent manuscript observations."}


def measurements_markdown(summary):
  lines = ["# Artificial Fragment Experiment v0.2 measurements", "",
    f"{summary['task_count']} validation tasks; {summary['region_measurement_count']} mask-region survival measurements; {summary['tasks_without_detected_regions']} tasks with no detected regions.", "",
    "Survival is observed pixel retention under a controlled synthetic transformation, not recoverability. Regions are model outputs and may omit or mislabel visible content.", "",
    "Categories: fully removed = 0; mostly destroyed = (0, 0.05]; partial = (0.05, 0.95); almost complete = [0.95, 1].", ""]
  for name, groups in summary["groups"].items():
    lines += [f"## By {name.replace('_', ' ')}", "", "| Group | Tasks | Regions | Page mean survival | Region mean | Region median | Min | Max | Population SD |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for key, value in groups.items():
      d = value["region_surviving_fraction"]
      def fmt(v): return "undefined" if v is None else f"{v:.6f}"
      lines.append(f"| {key} | {value['task_count']} | {value['region_measurement_count']} | {fmt(value['page_surviving_fraction']['mean'])} | " + " | ".join(fmt(d[k]) for k in ("mean", "median", "minimum", "maximum", "population_standard_deviation")) + " |")
    lines.append("")
  lines += [summary["statistics_note"], "", "Exact category frequencies and page-level distribution statistics are in the machine-readable measurements artifact.", ""]
  return "\n".join(lines)
