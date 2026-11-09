"""Content-mask-calibrated synthetic loss, separate from frozen v0.1-v0.3 runs."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from .damage_matrix import AREA_PROXIES, OPERATORS, fingerprint, immutable_write, plan, write_json
from .segmentation_masks import validate_binary_mask
from .structured_damage import DamageRejected, MIN_DIMENSION, _shape_score, parameters, topology

VERSION = "matrix_synthesis_v1"
PAPER_PROFILE_VERSION = "matrix_synthesis_v2_paper_profile"
REALISM_PROFILES = ("geometric_v1", "paper_edge_v1")


def _normalised_noise(generator, length, sigma, *, mode="reflect"):
    """Return deterministic correlated noise without a repeating wave signature."""
    values = ndimage.gaussian_filter1d(generator.normal(size=length), sigma=sigma, mode=mode)
    values -= values.mean()
    deviation = values.std()
    return values / deviation if deviation else values


def _paper_profile(length, seed, *, irregular):
    """Deterministic multi-scale edge variation with connected cross-sections."""
    generator = np.random.default_rng(int(seed[:16], 16) % (2**32))
    if irregular:
        profile = (
            1
            + .16 * _normalised_noise(generator, length, max(8, length / 13))
            + .065 * _normalised_noise(generator, length, max(3, length / 52))
            + .018 * _normalised_noise(generator, length, max(1, length / 210))
        )
        return np.clip(profile, .52, 1.52)
    profile = (
        1
        + .024 * _normalised_noise(generator, length, max(8, length / 10))
        + .007 * _normalised_noise(generator, length, max(2, length / 75))
    )
    return np.clip(profile, .91, 1.09)


def _radial_paper_profile(angle, seed):
    """Sample a seamless, non-periodic-looking radial boundary around a hole."""
    bins = 2048
    generator = np.random.default_rng(int(seed[16:32], 16) % (2**32))
    profile = (
        1
        + .11 * _normalised_noise(generator, bins, bins / 18, mode="wrap")
        + .045 * _normalised_noise(generator, bins, bins / 55, mode="wrap")
        + .012 * _normalised_noise(generator, bins, bins / 180, mode="wrap")
    )
    profile = np.clip(profile, .66, 1.34)
    position = ((angle + np.pi) / (2 * np.pi) * bins) % bins
    low = np.floor(position).astype(int)
    high = (low + 1) % bins
    weight = position - low
    return profile[low] * (1 - weight) + profile[high] * weight


def _paper_shape_score(size, p, identity):
    """Organic but topologically controlled masks; visual realism remains unvalidated."""
    w, h = size
    x = (np.arange(w, dtype=np.float64)[None, :] + .5) / w
    y = (np.arange(h, dtype=np.float64)[:, None] + .5) / h
    guard = np.zeros((h, w), dtype=bool)
    family = p["family"]
    if family in ("edge_loss", "edge_tear"):
        edge = p["edge"]
        depth = y if edge == "top" else 1-y if edge == "bottom" else x if edge == "left" else 1-x
        transverse_length = w if edge in ("top", "bottom") else h
        profile = _paper_profile(transverse_length, identity, irregular=family == "edge_tear")
        profile = profile[None, :] if edge in ("top", "bottom") else profile[:, None]
        score = np.broadcast_to(depth / profile, (h, w)).copy()
        if edge in ("top", "bottom"):
            guard[:, [0, -1]] = True
            guard[-1 if edge == "top" else 0, :] = True
        else:
            guard[[0, -1], :] = True
            guard[:, -1 if edge == "left" else 0] = True
    elif family == "internal_hole":
        cx, cy = p["center_normalized"]
        ratio = p["ellipse_axis_ratio"]
        dx, dy = (x-cx) / ratio, (y-cy) * ratio
        angle = np.arctan2(dy, dx)
        radial = np.sqrt(dx**2 + dy**2)
        score = radial / _radial_paper_profile(angle, identity)
        guard[[0, -1], :] = True
        guard[:, [0, -1]] = True
    else:
        raise DamageRejected("paper_profile_unsupported_family")
    score[guard] = np.inf
    return score


def _paper_topology(mask, p):
    """Validate connected material loss while allowing fibre-scale boundary variation."""
    removed = np.asarray(mask) > 0
    structure = ndimage.generate_binary_structure(2, 1)
    _, component_count = ndimage.label(removed, structure=structure)
    touched = [
        edge for edge, values in (
            ("top", removed[0]), ("bottom", removed[-1]),
            ("left", removed[:, 0]), ("right", removed[:, -1]),
        ) if values.any()
    ]
    checks = {
        "nonempty": bool(removed.any()),
        "not_entire_page": not bool(removed.all()),
        "one_removed_component": int(component_count) == 1,
    }
    details = {"connectivity": 4, "removed_components": int(component_count), "touched_edges": touched}
    if p["family"] in ("edge_loss", "edge_tear"):
        edge = p["edge"]
        checks["exactly_intended_edge"] = set(touched) == {edge}
        slices = removed.T if edge in ("top", "bottom") else removed
        active_slices = slices[slices.any(axis=1)]
        transitions = np.count_nonzero(
            np.diff(np.pad(active_slices.astype(np.uint8), ((0, 0), (1, 1))), axis=1), axis=1,
        ) if len(active_slices) else np.array([])
        checks["contiguous_edge_cross_sections"] = bool(len(transitions) and np.all(transitions == 2))
        depths = removed.sum(axis=0 if edge in ("top", "bottom") else 1)
        positive = depths[depths > 0]
        variation = float(np.std(positive) / np.mean(positive)) if len(positive) else 0.
        levels = int(len(np.unique(positive)))
        details.update(positive_depth_levels=levels, depth_variation_fraction=variation)
        if p["family"] == "edge_loss":
            checks["predominantly_straight_front"] = levels >= 3 and variation <= .12
        else:
            checks["irregular_inward_front"] = levels >= 8 and variation >= .08
    else:
        checks["strictly_interior"] = not touched
    return {**details, "checks": checks, "passed": all(checks.values())}


def content_damage(size, target, family, fraction, identity, *, realism_profile="geometric_v1"):
    """Calibrate against content pixels; maintain the existing page-level topology tests."""
    validate_binary_mask(target, size)
    if min(size) < MIN_DIMENSION or not 0 < fraction < 1 or realism_profile not in REALISM_PROFILES:
        raise DamageRejected("unsupported_dimensions_or_fraction")
    content = np.asarray(target) == 255
    count = int(content.sum())
    goal = round(count * fraction)
    if not 0 < goal < count:
        raise DamageRejected("target_too_small_or_empty")
    p = parameters(identity, identity, family, fraction)
    if family == "internal_hole":
        yy, xx = np.nonzero(content)
        p["center_normalized"] = [float((xx.mean() + .5) / size[0]), float((yy.mean() + .5) / size[1])]
    if realism_profile == "paper_edge_v1":
        p.update(realism_profile=realism_profile, realism_review_status="unvalidated_synthetic_approximation")
        score = _paper_shape_score(size, p, identity)
    else:
        score = _shape_score(size, p)
    target_indices = np.flatnonzero(content.ravel() & np.isfinite(score.ravel()))
    if len(target_indices) < goal:
        raise DamageRejected("target_area_exceeds_topological_capacity")
    # Global row-major tie breaking keeps one advancing shape, not disconnected target-only holes.
    ordered = target_indices[np.argsort(score.ravel()[target_indices], kind="stable")]
    last = int(ordered[goal - 1])
    threshold = float(score.ravel()[last])
    removed = (score < threshold) | ((score == threshold) & (np.arange(score.size).reshape(score.shape) <= last))
    damage = Image.fromarray(removed.astype(np.uint8) * 255)
    checks = _paper_topology(damage, p) if realism_profile == "paper_edge_v1" else topology(damage, p)
    if not checks["passed"]:
        raise DamageRejected("topology_failed:" + ",".join(k for k, v in checks["checks"].items() if not v))
    affected = int((removed & content).sum())
    if affected != goal:
        raise DamageRejected("content_calibration_failed")
    result = {
        "parameters": p, "target_pixels": count, "removed_target_pixels": affected,
        "target_area_fraction_proxy": fraction, "measured_target_loss": affected / count,
        "measured_page_loss": float(removed.mean()), "rounding_tolerance": .5 / count,
        "topology": checks, "semantic_severity_validated": False,
    }
    if realism_profile == "paper_edge_v1":
        result.update(realism_profile=realism_profile, visual_realism_validated=False,
                      historical_damage_claim=False)
    return damage, result


def png_bytes(image):
    stream = BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def resolve_input(base, value):
    path = Path(value)
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def validate_sources(config, base):
    """Enforce manuscript and duplicate-image split isolation before any outputs are written."""
    pages = config.get("pages", [])
    if not pages:
        raise ValueError("no_source_pages")
    ids, manuscripts, hashes = set(), {}, {}
    for registered in config.get("split_registry", []):
        mid, split, checksum = (registered[k] for k in ("manuscript_id", "split", "source_sha256"))
        if split not in {"train", "validation", "test"}:
            raise ValueError("invalid_registry_split")
        if manuscripts.setdefault(mid, split) != split:
            raise ValueError("manuscript_split_leakage")
        if hashes.setdefault(checksum, split) != split:
            raise ValueError("duplicate_image_split_leakage")
    prepared = []
    for page in pages:
        required = ("page_id", "manuscript_id", "split", "source_image", "content_mask", "content_id", "content_basis")
        if any(not page.get(k) for k in required):
            raise ValueError("missing_source_fields")
        if page["page_id"] in ids:
            raise ValueError("duplicate_page_id")
        ids.add(page["page_id"])
        if page["split"] not in {"train", "validation", "test"}:
            raise ValueError("invalid_split")
        if page["content_basis"] not in {"model_derived", "expert_reviewed", "synthetic_fixture"}:
            raise ValueError("invalid_content_basis")
        if page["content_basis"] == "model_derived" and not page.get("segmentation_provenance"):
            raise ValueError("model_mask_requires_segmentation_provenance")
        previous = manuscripts.setdefault(page["manuscript_id"], page["split"])
        if previous != page["split"]:
            raise ValueError("manuscript_split_leakage")
        # Test pages stay frozen, including their image/mask files: no opening or generation.
        if page["split"] == "test":
            if not page.get("source_sha256"):
                raise ValueError("test_page_requires_registered_source_sha256")
            if hashes.setdefault(page["source_sha256"], "test") != "test":
                raise ValueError("duplicate_image_split_leakage")
            prepared.append(dict(page, excluded_test=True))
            continue
        source_path = resolve_input(base, page["source_image"])
        mask_path = resolve_input(base, page["content_mask"])
        source_bytes, mask_bytes = source_path.read_bytes(), mask_path.read_bytes()
        source_hash, mask_hash = sha256(source_bytes).hexdigest(), sha256(mask_bytes).hexdigest()
        if page.get("source_sha256", source_hash) != source_hash or page.get("mask_sha256", mask_hash) != mask_hash:
            raise ValueError("input_checksum_mismatch")
        previous = hashes.setdefault(source_hash, page["split"])
        if previous != page["split"]:
            raise ValueError("duplicate_image_split_leakage")
        with Image.open(BytesIO(source_bytes)) as opened:
            source = opened.convert("RGBA")
        if source.getchannel("A").getextrema() != (255, 255):
            raise ValueError("source_must_be_an_opaque_complete_page")
        with Image.open(BytesIO(mask_bytes)) as opened:
            target = opened.copy()
        validate_binary_mask(target, source.size)
        if target.histogram()[255] == 0:
            raise ValueError("empty_content_mask")
        prepared.append(dict(page, source_path=source_path, mask_path=mask_path,
                             source_hash=source_hash, mask_hash=mask_hash, source=source, target=target))
    # Handles a test record listed AFTER a train record, without opening test files.
    for page in prepared:
        checksum = page.get("source_hash", page.get("source_sha256"))
        if hashes[checksum] != page["split"]:
            raise ValueError("duplicate_image_split_leakage")
    return prepared


def generate_dataset(matrix, config, base, output, *, include_edge_cases=False):
    pages = validate_sources(config, Path(base))
    if Path(output).is_symlink():
        raise ValueError("output_must_not_be_a_symlink")
    output = Path(output).resolve()
    seed = config.get("seed", 42)
    if type(seed) is not int:
        raise ValueError("seed_must_be_integer")
    damage_ids = config.get("damage_ids", ["D2-01", "D2-02", "D2-03"])
    severities = config.get("severities", ["S2", "S3", "S4"])
    if not damage_ids or any(d not in OPERATORS for d in damage_ids):
        raise ValueError("unknown_or_empty_damage_selection")
    if not severities or any(s not in AREA_PROXIES for s in severities):
        raise ValueError("unknown_or_empty_severity_selection")
    if len(set(damage_ids)) != len(damage_ids) or len(set(severities)) != len(severities):
        raise ValueError("duplicate_damage_or_severity_selection")
    realism_profile = config.get("realism_profile", "geometric_v1")
    if realism_profile not in REALISM_PROFILES:
        raise ValueError("unknown_realism_profile")
    selection = {"seed": seed, "damage_ids": damage_ids, "severities": severities,
                 "include_edge_cases": include_edge_cases}
    if realism_profile != "geometric_v1":
        selection["realism_profile"] = realism_profile
    inputs = [{k: p[k] for k in ("page_id", "manuscript_id", "split", "content_id", "content_basis")}
              | ({"source_sha256": p["source_hash"], "mask_sha256": p["mask_hash"],
                  "segmentation_provenance": p.get("segmentation_provenance")} if not p.get("excluded_test") else {})
              for p in pages]
    run = {"version": PAPER_PROFILE_VERSION if realism_profile != "geometric_v1" else VERSION,
           "matrix_sha256": fingerprint(matrix), "selection": selection, "inputs": inputs,
           "split_registry_sha256": fingerprint(config.get("split_registry", []))}
    # Prevent repurposing a populated output directory for a different run.
    write_json(output / "run.json", run)
    tasks, skipped = [], []
    for page in pages:
        if page.get("excluded_test"):
            skipped.append({"page_id": page["page_id"], "reason": "test_split_frozen"})
            continue
        entries = plan(matrix, content_id=page["content_id"], include_edge_cases=include_edge_cases)["entries"]
        lookup = {(e["damage_id"], e["severity"]): e for e in entries if e["damage_id"]}
        for damage_id in damage_ids:
            for severity in severities:
                entry = lookup.get((damage_id, severity))
                brief = {"page_id": page["page_id"], "damage_id": damage_id, "severity": severity}
                if entry is None or entry["status"] != "eligible":
                    skipped.append({**brief, "reason": entry["status"] if entry else "no_matrix_row"})
                    continue
                descriptor = {**brief, "version": VERSION, "matrix_sha256": run["matrix_sha256"],
                              "source_sha256": page["source_hash"], "mask_sha256": page["mask_hash"],
                              "manuscript_id": page["manuscript_id"], "split": page["split"],
                              "content_id": page["content_id"], "content_basis": page["content_basis"],
                              "segmentation_provenance": page.get("segmentation_provenance"), "seed": seed}
                if realism_profile != "geometric_v1":
                    descriptor.update(version=PAPER_PROFILE_VERSION, realism_profile=realism_profile,
                                      visual_realism_validated=False)
                identity = fingerprint(descriptor)
                task_id = "matrix_" + identity[:24]
                try:
                    damage, stats = content_damage(page["source"].size, page["target"], entry["family"],
                                                   entry["target_area_fraction_proxy"], identity,
                                                   realism_profile=realism_profile)
                except DamageRejected as exc:
                    skipped.append({**brief, "reason": str(exc)})
                    continue
                removed = np.asarray(damage) == 255
                survival = Image.fromarray((~removed).astype(np.uint8) * 255)
                fragment = Image.composite(page["source"], Image.new("RGBA", page["source"].size), survival)
                pixels, original = np.asarray(fragment), np.asarray(page["source"])
                if not np.array_equal(pixels[~removed], original[~removed]):
                    raise ValueError("surviving_source_pixels_changed")
                artifacts = {}
                for folder, name, image in (
                    ("observed", "fragment", fragment), ("observed", "survival", survival),
                    ("targets", "damage", damage), ("targets", "content", page["target"]),
                ):
                    relative = f"{task_id}/{folder}/{name}.png"
                    data = png_bytes(image)
                    destination = output / relative
                    if destination.resolve() in {page["source_path"], page["mask_path"]}:
                        raise ValueError("output_overlaps_input")
                    immutable_write(destination, data)
                    artifacts[name] = {"path": relative, "sha256": sha256(data).hexdigest()}
                # Teacher/source information lives outside the observed model-input directory.
                record = {"task_id": task_id, **descriptor, "matrix_entry": entry, "statistics": stats,
                          "cohort": entry["cohort"], "artifacts": artifacts,
                          "source_image": str(page["source_path"]), "content_mask": str(page["mask_path"]),
                          "source_provenance": page.get("source_provenance", {}),
                          "coordinate_space": "source_page", "source_to_fragment": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                          "synthetic_damage": True, "historical_damage_claim": False,
                          "layout_labels": "supplied mask; no new Mergen inference", "source_integrity_verified": True}
                if realism_profile != "geometric_v1":
                    record["realism_review_status"] = "synthetic_shape_only; specialist_validation_pending"
                write_json(output / task_id / "targets" / "record.json", record)
                tasks.append({"task_id": task_id, "split": page["split"], "cohort": entry["cohort"],
                              "observed_image": artifacts["fragment"]["path"],
                              "observed_mask": artifacts["survival"]["path"],
                              "target_record": f"{task_id}/targets/record.json"})
        if sha256(page["source_path"].read_bytes()).hexdigest() != page["source_hash"]:
            raise ValueError("source_changed_during_generation")
        if sha256(page["mask_path"].read_bytes()).hexdigest() != page["mask_hash"]:
            raise ValueError("content_mask_changed_during_generation")
    report = {**run, "tasks": tasks, "skipped": skipped,
              "generated_count": len(tasks), "skip_counts": dict(Counter(s["reason"] for s in skipped)),
              "semantic_severity_validated": False, "training_performed": False}
    write_json(output / "dataset.json", report)
    return report


def prepare_corpus_sources(root, *, split, label, content_id, limit):
    """Read existing corpus artifacts; the caller explicitly declares the label-to-content mapping."""
    from .corpus_audit import inspect_page, load_corpus

    if split not in {"train", "validation"} or limit < 1:
        raise ValueError("preparation_requires_train_or_validation_and_positive_limit")
    pages, _, inputs = load_corpus(root)
    registry = [{"manuscript_id": p["manuscript_id"], "split": p["split"],
                 "source_sha256": p["source_sha256"]} for p in pages]
    selected, skipped = [], []
    for raw in pages:
        if raw["split"] != split:
            continue
        page = inspect_page(root, raw)
        if page["errors"]:
            skipped.append({"page_id": page["page_id"], "reasons": page["errors"]})
            continue
        detections = [d for d in page["detections"] if d["label"] == label]
        if not detections:
            skipped.append({"page_id": page["page_id"], "reasons": ["requested_label_not_detected"]})
            continue
        detection = sorted(detections, key=lambda d: (-d["mask_pixel_area"], d["index"]))[0]
        selected.append({
            "page_id": page["page_id"], "manuscript_id": page["manuscript_id"], "split": page["split"],
            "source_image": str((root / page["source_path"]).resolve()),
            "content_mask": str((root / detection["mask_path"]).resolve()),
            "source_sha256": page["source_sha256"], "mask_sha256": detection["mask_sha256"],
            "content_id": content_id, "content_basis": "model_derived",
            "segmentation_provenance": {**page["model"], "stored_run": page["stored_run"],
                "region_index": detection["index"], "label": label, "confidence": detection.get("confidence"),
                "mapping_basis": "caller_declared_label_to_content; not expert-verified", "selection": "largest_matching_region"},
            "source_provenance": {"corpus_id": page["corpus_id"], "database_ids": page["db_ids"],
                                  "source_record": page["source_record"]},
        })
        if len(selected) == limit:
            break
    if not selected:
        raise ValueError("no_usable_corpus_pages:" + str(skipped))
    return {"seed": 42, "pages": selected, "split_registry": registry,
            "preparation": {"inputs": inputs, "skipped": skipped, "limit": limit,
                            "label": label, "content_id": content_id}}


def make_demo(directory):
    """Small schematic fixture; not a real manuscript or scientific training corpus."""
    directory = Path(directory)
    source = Image.new("RGB", (192, 256), (231, 218, 188))
    draw = ImageDraw.Draw(source)
    for y in range(36, 220, 9):
        draw.line((32, y, 158, y), fill=(65, 44, 34), width=2)
    target = Image.new("L", source.size)
    ImageDraw.Draw(target).rectangle((28, 30, 163, 224), fill=255)
    immutable_write(directory / "page.png", png_bytes(source))
    immutable_write(directory / "content.png", png_bytes(target))
    config = {"seed": 42, "pages": [{"page_id": "schematic-demo", "manuscript_id": "fixture-only",
              "split": "train", "source_image": "page.png", "content_mask": "content.png",
              "content_id": "CT-01", "content_basis": "synthetic_fixture"}]}
    write_json(directory / "sources.json", config)
    return config
