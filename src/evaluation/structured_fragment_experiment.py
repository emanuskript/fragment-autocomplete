"""Validation-only v0.3 experiment, using the existing registration and mask-overlap contracts."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from io import BytesIO

from PIL import Image, ImageChops

from .artificial_fragment_experiment import (
  SURVIVAL_THRESHOLDS, aggregate, measure_regions, page_evidence, region_summary,
  registration_records as legacy_registration_records, survival_category,
)
from .artificial_fragment_registration import resolve_local_path, sha256_file
from .corpus_audit import artifact, digest, distribution, write_stable
from .structured_damage import (
  VERSION, GENERATOR_VERSION, FAMILIES, TAXONOMY, SEVERITIES, SEVERITY_TOLERANCE,
  DamageRejected, parameters, build_damage_mask, topology,
)

OUTPUT = "outputs/artificial_fragments/v0_3"


def build_specification(pages):
  validation = sorted((p for p in pages if p["split"] == "validation"), key=lambda p: p["page_id"])
  if len({p["page_id"] for p in validation}) != len(validation):
    raise ValueError("duplicate_validation_page")
  selected, rejected, tasks, rejected_tasks = [], [], [], []
  for page in validation:
    if page["errors"]:
      rejected.append({"page_id": page["page_id"], "reasons": sorted(page["errors"])})
      continue
    evidence = page_evidence(page)
    evidence_sha = digest(evidence)
    selected.append({"page_id": page["page_id"], "manuscript_id": page["manuscript_id"], "split": "validation",
      "evidence_sha256": evidence_sha, "evidence": evidence,
      "layout_status": "model_masks_available" if page["detections"] else "no_detected_regions"})
    for family in FAMILIES:
      for severity in SEVERITIES:
        params = parameters(page["page_id"], page["source_sha256"], family, severity)
        descriptor = {"version": VERSION, "page_id": page["page_id"], "evidence_sha256": evidence_sha,
                      "parameters": params, "severity": severity}
        entry = {"task_id": "afv03_" + digest(descriptor)[:24], "page_id": page["page_id"],
          "evidence_sha256": evidence_sha, "mask_family": family, "random_seed": params["seed"],
          "requested_severity": severity, "rotation_degrees": 0.0, "scale": 1.0, "task_group": VERSION,
          "mask_parameters": params}
        try:
          _, stats = build_damage_mask(tuple(page["dimensions_px"]), params, severity)
          entry["calibration"] = stats
          tasks.append(entry)
        except DamageRejected as exc:
          rejected_tasks.append({**entry, "reason": str(exc)})
    print(f"Planned validation page {page['page_id']}", flush=True)
  return {"experiment_version": VERSION, "generator_version": GENERATOR_VERSION,
    "synthetic_damage": True, "taxonomy": TAXONOMY, "mask_families": list(FAMILIES),
    "severities": list(SEVERITIES), "severity_tolerance": SEVERITY_TOLERANCE,
    "validation_page_count": len(validation), "selected_page_count": len(selected),
    "conceptual_matrix_task_count": len(selected)*len(FAMILIES)*len(SEVERITIES), "matrix_task_count": len(tasks),
    "selected_pages": selected, "rejected_pages": rejected, "tasks": tasks, "rejected_tasks": rejected_tasks,
    "survival_thresholds": SURVIVAL_THRESHOLDS, "test_policy": "frozen_and_excluded",
    "zero_detection_policy": "include_page_metrics; region_survival_undefined; never infer absent content"}


def save_image(path, im):
  stream = BytesIO()
  im.save(stream, format="PNG", compress_level=9)
  data = stream.getvalue()
  path.parent.mkdir(parents=True, exist_ok=True)
  if not path.exists() or path.read_bytes() != data:
    path.write_bytes(data)


def generate_task(root, page, entry):
  if page["split"] != "validation" or page["errors"]:
    raise ValueError("only_valid_validation_pages_may_generate")
  if page["page_id"] != entry["page_id"] or digest(page_evidence(page)) != entry["evidence_sha256"]:
    raise ValueError("experiment_evidence_changed")
  expected_params = parameters(page["page_id"], page["source_sha256"], entry["mask_family"], entry["requested_severity"])
  if entry["mask_parameters"] != expected_params:
    raise ValueError("scientific_parameters_changed")
  source_path = resolve_local_path(root, page["source_path"])
  before = sha256_file(source_path)
  if before != page["source_sha256"]:
    raise ValueError("source_checksum_changed")
  with Image.open(source_path) as im:
    source = im.convert("RGBA")
  if list(source.size) != page["dimensions_px"]:
    raise ValueError("source_dimensions_changed")
  damage, stats = build_damage_mask(source.size, expected_params, entry["requested_severity"])
  if stats != entry["calibration"]:
    raise ValueError("calibration_changed")
  survival = ImageChops.invert(damage)
  source = Image.composite(source, Image.new("RGBA", source.size, (0, 0, 0, 0)), survival)
  # Keep the entire source coordinate frame. Holes and disconnected surviving pieces cannot
  # be faithfully reduced to a single contour. The binary mask remains authoritative.
  artifacts = {}
  for name, filename, im in (("fragment_image", "fragment.png", source),
      ("observed_fragment_survival_mask", "observed_mask.png", survival),
      ("source_survival_mask", "survival.png", survival), ("source_damage_mask", "damage.png", damage)):
    path = resolve_local_path(root, f"{OUTPUT}/tasks/{entry['task_id']}/{filename}")
    if path == source_path:
      raise ValueError("generated_artifact_must_not_overwrite_source")
    save_image(path, im)
    artifacts[name] = {**artifact(root, path.relative_to(root).as_posix()), "dimensions_px": list(im.size),
      "coordinate_space": "source_page", "mode": im.mode}
  run_id = page["stored_run"]["db_segmentation_run_id"]
  provenance = {**page["model"], "sample_id": page["page_id"], "orig_shape": list(reversed(page["dimensions_px"])),
    "raw_output_path": page["result"]["raw_output_path"], "db_segmentation_run_id": run_id,
    "evidence_sha256": entry["evidence_sha256"], "geometry_method": "segmentation_mask"}
  regions = measure_regions(root, page["detections"], survival, run_id)
  source_record = deepcopy(page["source_record"])
  database_asset = deepcopy(page.get("database_asset", {}))
  identity_matrix = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
  w, h = source.size
  generator_parameters = {"mask_parameters": expected_params, "mask_statistics": stats,
    "coordinate_convention": "Pixel centers; origin at top left; x right, y down. Source-sized export, identity transform.",
    "experiment": {"version": VERSION, "evidence_sha256": entry["evidence_sha256"], "survival_thresholds": SURVIVAL_THRESHOLDS},
    "synthetic_damage": True, "geometry_method": "calibrated_binary_damage_mask"}
  after = sha256_file(source_path)
  if after != before:
    raise ValueError("source_changed_during_generation")
  task = {k: entry[k] for k in ("task_id", "task_group", "mask_family", "random_seed", "requested_severity", "rotation_degrees", "scale")}
  task.update(experiment_version=VERSION, generation_version=GENERATOR_VERSION,
    generation_fingerprint_sha256=digest({"source_sha256": before, "parameters": generator_parameters}),
    source_sample_id=page["page_id"], manuscript_id=page["manuscript_id"], split_name="validation",
    source_image_asset_id=page["db_ids"]["image_asset_id"], source_canvas_id=page["db_ids"]["canvas_id"],
    source_path=page["source_path"], source_sha256=before, source_sha256_after_generation=after, source_integrity_verified=True,
    original_image_dimensions_px=[w, h], generated_fragment_dimensions_px=[w, h],
    measured_severity=stats["measured_severity"], surviving_fraction=stats["surviving_fraction"],
    actual_removed_pixel_fraction=stats["measured_severity"], actual_surviving_pixel_fraction=stats["surviving_fraction"],
    absolute_severity_error=stats["absolute_severity_error"], topology_validation=stats["topology"],
    artifacts=artifacts, parameters=generator_parameters,
    mask_semantics={"survival_mask": "255=observed source pixel survives; 0=synthetically removed",
      "damage_mask": "255=synthetically removed; 0=survives", "severity_definition": "removed source pixels / total source pixels",
      "synthetic_damage": True, "source_image_role": "known_source_ground_truth"},
    source_provenance={"source": "e-codices", "source_url": source_record["image"].get("download_url"),
      "category": "complete_corpus_page", "database_ids": page["db_ids"],
      "registered_source_record": {"corpus_page": source_record, "database_asset": database_asset},
      "source_metadata": {"corpus_id": page["corpus_id"], "manuscript_id": page["manuscript_id"], "split": page["split"]},
      "rights_review_status": source_record["image"].get("rights_review_status"), "access_level": database_asset.get("access_level", "internal")},
    fragment_contour={"source_page_xy_px": [], "observed_fragment_xy_px": [],
      "representation": "source_survival_mask is authoritative for all components and holes; no single polygon asserted"},
    fragment_bounding_box={"source_page_bbox_xyxy_px": list(survival.getbbox()), "observed_fragment_bbox_xyxy_px": list(survival.getbbox())},
    crop_transform={"source_bbox_xyxy_px": [0, 0, w, h], "source_to_observed_fragment_matrix": identity_matrix,
      "observed_fragment_to_source_matrix": identity_matrix, "exported_dimensions_px": [w, h], "rotation_degrees": 0., "scale": 1.},
    ground_truth_placement={"coordinate_space": "source_page", "placement_is_known": True,
      "source_canvas_id": page["db_ids"]["canvas_id"], "source_image_asset_id": page["db_ids"]["image_asset_id"],
      "source_page_dimensions_px": [w, h], "source_survival_mask_path": artifacts["source_survival_mask"]["path"],
      "source_damage_mask_path": artifacts["source_damage_mask"]["path"], "scientific_role": "hidden_ground_truth"},
    layout_survival_estimate={"geometry_method": "segmentation_mask", "regions": regions, "summary": region_summary(regions),
                             "segmentation_run_provenance": provenance},
    degradation_profile={"profile": "synthetic_structured_material_loss", "contains_inferred_or_reconstructed_content": False,
      "note": "Controlled synthetic removal of known source pixels; mechanism is a geometric comparator, not an inferred historical event."})
  path = root / OUTPUT / "tasks" / entry["task_id"] / "metadata.json"
  write_stable(path, task)
  task["artifacts"]["metadata"] = artifact(root, path.relative_to(root).as_posix())
  return task


def registration_records(root, specification, tasks):
  entries = {e["task_id"]: e for e in specification["tasks"]}
  for t in tasks:
    e = entries.get(t["task_id"])
    if e is None or t["parameters"]["mask_parameters"] != e["mask_parameters"]:
      raise ValueError("structured_task_parameters_mismatch")
    if t["parameters"]["mask_statistics"] != e["calibration"] or not t["topology_validation"]["passed"]:
      raise ValueError("structured_calibration_mismatch")
    stats = e["calibration"]
    for key, expected in (("measured_severity", stats["measured_severity"]),
        ("actual_removed_pixel_fraction", stats["measured_severity"]),
        ("surviving_fraction", stats["surviving_fraction"]),
        ("actual_surviving_pixel_fraction", stats["surviving_fraction"]),
        ("absolute_severity_error", stats["absolute_severity_error"])):
      if t[key] != expected:
        raise ValueError("structured_reported_severity_mismatch")
    if t["generation_version"] != GENERATOR_VERSION or t["absolute_severity_error"] > SEVERITY_TOLERANCE:
      raise ValueError("structured_generator_or_severity_mismatch")
    with Image.open(root / t["artifacts"]["source_damage_mask"]["path"]) as damage:
      if topology(damage, e["mask_parameters"]) != t["topology_validation"]:
        raise ValueError("structured_topology_changed")
      removed = damage.histogram()[255]
      if removed != e["calibration"]["removed_pixels"] or sum(damage.histogram()[1:255]):
        raise ValueError("structured_damage_pixels_changed")
      with Image.open(root / t["artifacts"]["source_survival_mask"]["path"]) as survival:
        if ImageChops.difference(ImageChops.invert(damage), survival).getbbox():
          raise ValueError("damage_survival_masks_not_complements")
  return legacy_registration_records(root, specification, tasks, experiment_version=VERSION)


def metrics(tasks, label=None):
  regions = [r for t in tasks for r in t["layout_survival_estimate"]["regions"] if label is None or r["label"] == label]
  n = len(regions)
  counts = Counter(survival_category(r["surviving_fraction"]) for r in regions)
  rate = lambda key: counts[key]/n if n else None
  return {"task_count": len(tasks), "region_measurement_count": n,
    "actual_page_loss": distribution(t["measured_severity"] for t in tasks),
    "severity_error": distribution(abs(t["measured_severity"]-t["requested_severity"]) for t in tasks),
    "region_survival": distribution(r["surviving_fraction"] for r in regions),
    "fully_removed_region_rate": rate("fully_removed"), "mostly_removed_region_rate": rate("mostly_destroyed"),
    "partially_surviving_region_rate": rate("partial"), "mostly_surviving_region_rate": rate("almost_complete"),
    "almost_complete_survival_rate": rate("almost_complete")}


def summarize(tasks):
  result = aggregate(tasks)
  result["experiment_version"] = tasks[0]["experiment_version"] if tasks else VERSION
  result["overall"] = metrics(tasks)
  result["family_severity"] = {}
  for family in sorted({t["mask_family"] for t in tasks}):
    for severity in sorted({t["requested_severity"] for t in tasks}):
      group = [t for t in tasks if t["mask_family"] == family and t["requested_severity"] == severity]
      result["family_severity"][f"{family}:{severity:.2f}"] = {**metrics(group), "layout_classes": {
        label: metrics([t for t in group if any(r["label"] == label for r in t["layout_survival_estimate"]["regions"])], label)
        for label in sorted({r["label"] for t in group for r in t["layout_survival_estimate"]["regions"]})}}
  result["rate_semantics"] = "Reuse v0.2 categories: 0 fully removed; (0,.05] mostly destroyed; (.05,.95) partial; [.95,1] almost complete. Mostly surviving is an explicit alias of almost complete, not a fifth category; do not sum both rates."
  return result


def compare(tasks, controls):
  common = sorted({t["source_sample_id"] for t in tasks} & {t["source_sample_id"] for t in controls})
  matched = [t for t in tasks if t["source_sample_id"] in common]
  matched_controls = [t for t in controls if t["source_sample_id"] in common]
  return {"all_v03": summarize(tasks), "matched_page_ids": common,
    "matched_comparison": {VERSION: summarize(matched), "artificial_fragment_experiment_v0_2": summarize(matched_controls)},
    "comparison_note": "Descriptive matched-page comparison at nominal severity. v0.2 and v0.3 orientation/shape assignments differ. Repeated region observations are not independent samples; no historical likelihood or causal content-recovery claim."}
