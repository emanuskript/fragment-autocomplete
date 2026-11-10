#!/usr/bin/env python3
"""Build deterministic review previews for the 14 non-loss damage types.

These images are interface-review prototypes. They are not specialist-validated
models of historical damage and are kept under ignored ``outputs/``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATASET = ROOT / "outputs/synthetic_data/paper_profile_public_demo_v2/dataset"
MATRIX = ROOT / "data/metadata/jeremy_damage_matrix_v3.json"
OUTPUT = ROOT / "outputs/synthetic_data/damage_review_prototype_v2"
MANIFEST = OUTPUT / "prototype.json"
PROTOTYPE_DAMAGE_IDS = {
    "D2-04",
    "D2-06",
    "D2-07",
    "D2-08",
    "D2-09",
    "D2-10",
    "D2-11",
    "D2-12",
    "D2-13",
    "D2-14",
    "D2-16",
    "D2-17",
    "D2-18",
    "D2-19",
}

OPERATOR_INFO = {
    "D2-04": ("surface-appearance", "ink-following material-loss approximation"),
    "D2-06": ("surface-appearance", "clouded coating field"),
    "D2-07": ("surface-appearance", "translucent aged adhesive strip"),
    "D2-08": ("surface-appearance", "discrete particulate deposits"),
    "D2-09": ("surface-appearance", "diffuse stain with tide line"),
    "D2-10": ("surface-appearance", "additional ink strokes"),
    "D2-11": ("surface-appearance", "spatially varying pigment fade"),
    "D2-12": ("surface-appearance", "abraded surface field"),
    "D2-13": ("surface-appearance", "localized rubbed erasure"),
    "D2-14": ("paired-surface-proxy", "mirrored low-opacity transfer proxy"),
    "D2-16": ("paired-surface-proxy", "ink-corrosion halo proxy"),
    "D2-17": ("paired-surface-proxy", "registered reverse-side bleed proxy"),
    "D2-18": ("leaf-deformation", "shared fold and crease shading"),
    "D2-19": ("leaf-deformation", "shared cockling warp and shading"),
}


def _seed(page_id: str, damage_id: str) -> int:
    return int(sha256(f"{page_id}:{damage_id}:prototype-v1".encode()).hexdigest()[:16], 16)


def _image_bytes(image: Image.Image, *, png: bool) -> bytes:
    stream = BytesIO()
    if png:
        image.save(stream, format="PNG", compress_level=9)
    else:
        image.convert("RGB").save(
            stream,
            format="JPEG",
            quality=90,
            optimize=True,
            subsampling=0,
        )
    return stream.getvalue()


def _write_if_changed(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def _organic_region(content: np.ndarray, rng: np.random.Generator, fraction: float = 0.35) -> np.ndarray:
    height, width = content.shape
    small = rng.integers(0, 256, size=(max(12, height // 80), max(12, width // 80)), dtype=np.uint8)
    noise = Image.fromarray(small).resize((width, height), Image.Resampling.BICUBIC)
    noise = noise.filter(ImageFilter.GaussianBlur(max(8, min(width, height) / 35)))
    values = np.asarray(noise, dtype=np.float32)
    target_values = values[content]
    if not len(target_values):
        raise ValueError("empty_content_mask")
    threshold = float(np.quantile(target_values, 1 - fraction))
    return content & (values >= threshold)


def _blend(source: np.ndarray, colour: tuple[float, float, float], alpha: np.ndarray) -> np.ndarray:
    mixed = source.astype(np.float32) * (1 - alpha[..., None])
    mixed += np.asarray(colour, dtype=np.float32) * alpha[..., None]
    return np.clip(mixed, 0, 255).astype(np.uint8)


def _ink_signal(gray: np.ndarray, content: np.ndarray) -> np.ndarray:
    """Page-relative ink darkness (0 = paper, 1 = darkest ink) so pale ink still registers."""
    values = gray[content] if content.any() else gray.ravel()
    paper = float(np.quantile(values, 0.8))
    ink = float(np.quantile(values, 0.03))
    span = max(18.0, paper - ink)
    return np.clip((paper - gray.astype(np.float32)) / span, 0, 1)


def _mask_image(alpha: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(alpha * 255, 0, 255).astype(np.uint8))


def _content_bbox(content: np.ndarray) -> tuple[int, int, int, int]:
    yy, xx = np.nonzero(content)
    if not len(xx):
        raise ValueError("empty_content_mask")
    return int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())


def apply_prototype_effect(
    source: Image.Image,
    content_mask: Image.Image,
    damage_id: str,
    seed: int,
) -> tuple[Image.Image, Image.Image, dict[str, Any]]:
    """Return a deterministic preview, effect mask, and explicit review metadata."""
    if damage_id not in PROTOTYPE_DAMAGE_IDS:
        raise ValueError(f"unsupported_prototype_damage:{damage_id}")
    source = source.convert("RGB")
    content_mask = content_mask.convert("L")
    if source.size != content_mask.size:
        raise ValueError("source_mask_dimension_mismatch")
    arr = np.asarray(source, dtype=np.uint8)
    gray = np.asarray(source.convert("L"), dtype=np.uint8)
    content = np.asarray(content_mask) > 0
    height, width = content.shape
    rng = np.random.default_rng(seed)
    region = _organic_region(content, rng)
    ink_signal = _ink_signal(gray, content)
    effect_kind, operator_label = OPERATOR_INFO[damage_id]

    if damage_id == "D2-04":
        ink_threshold = min(155, int(np.quantile(gray[content], 0.42)))
        affected = region & (gray <= ink_threshold)
        background = np.asarray(source.filter(ImageFilter.GaussianBlur(5)), dtype=np.uint8)
        out = arr.copy()
        out[affected] = np.clip(background[affected] * 0.35 + 238 * 0.65, 0, 255)
        alpha = affected.astype(np.float32)
    elif damage_id == "D2-06":
        texture = rng.normal(0, 0.06, size=(height, width)).astype(np.float32)
        alpha = np.clip(region.astype(np.float32) * (0.5 + texture), 0, 0.66)
        out = _blend(arr, (218, 211, 185), alpha)
    elif damage_id == "D2-07":
        x0, y0, x1, y1 = _content_bbox(content)
        tape = Image.new("L", source.size, 0)
        draw = ImageDraw.Draw(tape)
        tape_width = max(22, int((x1 - x0) * 0.1))
        centre = int(x0 + (x1 - x0) * rng.uniform(0.35, 0.7))
        lean = int((y1 - y0) * rng.uniform(-0.08, 0.08))
        draw.polygon(
            [(centre - tape_width, y0), (centre + tape_width, y0),
             (centre + tape_width + lean, y1), (centre - tape_width + lean, y1)],
            fill=220,
        )
        tape_array = np.asarray(tape.filter(ImageFilter.GaussianBlur(2)), dtype=np.float32) / 255
        alpha = tape_array * 0.52
        out = _blend(arr, (196, 140, 52), alpha)
        edge = np.asarray(tape.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)), dtype=np.float32) / 255
        out = _blend(out, (104, 66, 24), np.clip(edge * 0.6, 0, 0.6))
    elif damage_id == "D2-08":
        x0, y0, x1, y1 = _content_bbox(content)
        deposits = Image.new("L", source.size, 0)
        draw = ImageDraw.Draw(deposits)
        scale = max(3, min(width, height) // 260)
        for _ in range(240):
            x = int(rng.integers(x0, x1 + 1))
            y = int(rng.integers(y0, y1 + 1))
            radius = int(rng.integers(scale, scale * 6 + 1))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=int(rng.integers(100, 230)))
        alpha = np.asarray(deposits.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255 * 0.88
        out = _blend(arr, (58, 42, 28), alpha)
    elif damage_id == "D2-09":
        base = region.astype(np.float32)
        soft = np.asarray(_mask_image(base).filter(ImageFilter.GaussianBlur(34)), dtype=np.float32) / 255
        alpha = np.clip(soft * 0.54, 0, 0.54)
        out = _blend(arr, (135, 82, 35), alpha)
        tide = np.clip(np.abs(soft - 0.42) < 0.045, 0, 1).astype(np.float32) * 0.16
        out = _blend(out, (104, 68, 28), tide)
        alpha = np.maximum(alpha, tide)
    elif damage_id == "D2-10":
        x0, y0, x1, y1 = _content_bbox(content)
        strokes = Image.new("L", source.size, 0)
        draw = ImageDraw.Draw(strokes)
        line_width = max(3, min(width, height) // 330)
        for _ in range(24):
            y = int(rng.integers(y0, y1 + 1))
            points = []
            for step in range(9):
                x = int(x0 + (x1 - x0) * step / 8)
                points.append((x, y + int(np.sin(step * 1.7 + rng.random()) * line_width * 4)))
            draw.line(points, fill=int(rng.integers(130, 220)), width=int(rng.integers(line_width, line_width * 3 + 1)))
        alpha = np.asarray(strokes.filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32) / 255 * 0.92
        out = _blend(arr, (32, 24, 18), alpha)
    elif damage_id == "D2-11":
        paper = tuple(float(np.quantile(arr[..., channel][content], 0.85)) for channel in range(3))
        fade_region = _organic_region(content, rng, fraction=0.6)
        alpha = fade_region.astype(np.float32) * np.clip(ink_signal * 1.25, 0, 1) * 0.92
        out = _blend(arr, paper, alpha)
    elif damage_id == "D2-12":
        noise = rng.random((height, width)).astype(np.float32)
        alpha = region.astype(np.float32) * np.clip(0.45 + noise * 0.4, 0, 0.85)
        neutral = np.repeat(gray[..., None], 3, axis=2).astype(np.float32)
        grime = rng.normal(0, 1, size=(max(4, height // 6), max(4, width // 6))).astype(np.float32)
        grime = np.asarray(Image.fromarray(np.clip(128 + grime * 40, 0, 255).astype(np.uint8)).resize((width, height), Image.Resampling.BICUBIC), dtype=np.float32)
        abraded = neutral * 0.35 + np.array([206, 194, 168], dtype=np.float32) * 0.65
        abraded += ((grime - 128) * 0.35)[..., None]
        lift = np.clip(alpha + ink_signal * region * 0.5, 0, 0.92)
        out = np.clip(arr * (1 - lift[..., None]) + abraded * lift[..., None], 0, 255).astype(np.uint8)
        alpha = lift
    elif damage_id == "D2-13":
        x0, y0, x1, y1 = _content_bbox(content)
        erase = Image.new("L", source.size, 0)
        draw = ImageDraw.Draw(erase)
        rx, ry = int((x1 - x0) * 0.22), int((y1 - y0) * 0.06)
        for _ in range(4):
            cx = int(rng.uniform(x0 + (x1 - x0) * 0.2, x0 + (x1 - x0) * 0.8))
            cy = int(rng.uniform(y0 + (y1 - y0) * 0.1, y0 + (y1 - y0) * 0.9))
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=240)
        alpha = np.asarray(erase.filter(ImageFilter.GaussianBlur(max(4, ry / 4))), dtype=np.float32) / 255 * 0.85
        out = _blend(arr, (226, 216, 188), alpha)
    elif damage_id == "D2-14":
        mirrored = np.asarray(source.transpose(Image.Transpose.FLIP_LEFT_RIGHT), dtype=np.uint8)
        mirrored_gray = np.asarray(Image.fromarray(mirrored).convert("L"), dtype=np.uint8)
        signal = _ink_signal(mirrored_gray, content[:, ::-1])
        alpha = region.astype(np.float32) * np.clip(signal * 1.3, 0, 1) * 0.72
        out = _blend(arr, (55, 43, 32), alpha)
    elif damage_id == "D2-16":
        dark = (ink_signal > 0.45).astype(np.uint8) * 255
        ink = Image.fromarray(dark)
        outer = np.asarray(ink.filter(ImageFilter.GaussianBlur(9)), dtype=np.float32) / 255
        inner = np.asarray(ink.filter(ImageFilter.GaussianBlur(2)), dtype=np.float32) / 255
        halo = np.clip(outer - inner * 0.55, 0, 1) * region.astype(np.float32)
        alpha = np.clip(halo * 1.4, 0, 0.8)
        out = _blend(arr, (110, 56, 24), alpha)
    elif damage_id == "D2-17":
        reverse = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT).convert("L").filter(ImageFilter.GaussianBlur(3.5))
        signal = _ink_signal(np.asarray(reverse, dtype=np.uint8), content[:, ::-1])
        alpha = region.astype(np.float32) * np.clip(signal * 1.3, 0, 1) * 0.66
        out = _blend(arr, (78, 52, 36), alpha)
    elif damage_id == "D2-18":
        yy, xx = np.mgrid[0:height, 0:width]
        alpha = np.zeros((height, width), dtype=np.float32)
        shading = np.zeros((height, width), dtype=np.float32)
        x0, y0, x1, y1 = _content_bbox(content)
        centre_x = (x0 + x1) / 2
        centre_y = (y0 + y1) / 2
        for slope, offset in ((0.22, -0.08), (-0.16, 0.12)):
            line = centre_y + (y1 - y0) * offset + slope * (xx - centre_x)
            distance = yy - line
            band = np.exp(-((distance / max(8, height * 0.022)) ** 2))
            alpha = np.maximum(alpha, band.astype(np.float32))
            shading += np.tanh(distance / max(3, height * 0.006)) * band * 46
        out = np.clip(arr.astype(np.float32) + shading[..., None], 0, 255).astype(np.uint8)
        alpha *= 0.76
    else:  # D2-19
        out = np.empty_like(arr)
        amplitude = max(3, width // 170)
        for y in range(height):
            shift = int(round(amplitude * np.sin(y / max(18, height / 22))))
            out[y] = np.roll(arr[y], shift, axis=0)
        yy, xx = np.mgrid[0:height, 0:width]
        waves = np.sin(xx / max(20, width / 13) + np.sin(yy / max(30, height / 9)))
        shading = waves.astype(np.float32) * 15
        out = np.clip(out.astype(np.float32) + shading[..., None], 0, 255).astype(np.uint8)
        alpha = np.clip(np.abs(waves) * 0.52, 0, 0.52).astype(np.float32)

    display = (DISPLAY_WIDTH, max(1, round(height * DISPLAY_WIDTH / width)))
    before = np.asarray(source.resize(display, Image.Resampling.BOX), dtype=np.int16)
    after = np.asarray(Image.fromarray(out).resize(display, Image.Resampling.BOX), dtype=np.int16)
    visible_change = np.abs(after - before).mean(axis=2) > VISIBLE_DIFF_THRESHOLD
    effect_mask = _mask_image(alpha)
    affected = np.asarray(effect_mask) > 12
    target_pixels = int(content.sum())
    affected_target = int((affected & content).sum())
    statistics = {
        "target_pixels": target_pixels,
        "affected_target_pixels": affected_target,
        "measured_effect_coverage": affected_target / target_pixels if target_pixels else 0,
        "measured_page_coverage": float(affected.mean()),
        "visible_page_change": float(visible_change.mean()),
        "effect_kind": effect_kind,
        "operator_label": operator_label,
        "visual_realism_validated": False,
        "historical_damage_claim": False,
    }
    return Image.fromarray(out), effect_mask, statistics


def _base_pages() -> list[dict[str, Any]]:
    dataset = json.loads((SOURCE_DATASET / "dataset.json").read_text(encoding="utf-8"))
    pages: dict[str, dict[str, Any]] = {}
    for task in dataset["tasks"]:
        record = json.loads((SOURCE_DATASET / task["target_record"]).read_text(encoding="utf-8"))
        if record["severity"] == "S3":
            pages.setdefault(record["page_id"], record)
    if len(pages) != 10:
        raise ValueError(f"expected_10_demo_pages:found_{len(pages)}")
    return list(pages.values())


MIN_VISIBLE_PAGE_CHANGE = 0.02
VISIBLE_DIFF_THRESHOLD = 12
DISPLAY_WIDTH = 500  # approximate on-screen width of the compare view


def _writing_area(page: dict[str, Any], selected: Image.Image) -> tuple[Image.Image, dict[str, Any]]:
    """Union every detected main-script region; the selected region alone is too small to see."""
    raw_path = ROOT / page["segmentation_provenance"]["stored_run"]["raw_output_path"]
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    union = np.asarray(selected.convert("L")) > 0
    indices: list[int] = []
    for region in raw["detections"]:
        if not str(region.get("label", "")).startswith("Main script"):
            continue
        with Image.open(ROOT / region["mask_path"]) as opened:
            mask = np.asarray(opened.convert("L")) > 0
        if mask.shape != union.shape:
            raise ValueError(f"region_mask_dimension_mismatch:{page['page_id']}:{region['index']}")
        union |= mask
        indices.append(int(region["index"]))
    info = {
        "basis": "union_of_detected_main_script_regions",
        "region_indices": sorted(indices),
        "pixels": int(union.sum()),
        "page_fraction": float(union.mean()),
        "label_mapping": "model-detected layout labels; not expert-verified",
    }
    return Image.fromarray(union.astype(np.uint8) * 255), info


def _matrix_rows() -> dict[str, dict[str, Any]]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    rows = {
        row["damage_id"]: row
        for row in matrix["rows"]
        if row["content_id"] == "CT-01" and row["damage_id"] in PROTOTYPE_DAMAGE_IDS
    }
    if rows.keys() != PROTOTYPE_DAMAGE_IDS:
        raise ValueError("prototype_matrix_coverage_mismatch")
    return rows


def build() -> dict[str, Any]:
    rows = _matrix_rows()
    records: list[dict[str, Any]] = []
    for page in _base_pages():
        with Image.open(page["source_image"]) as opened:
            source = opened.convert("RGB")
        with Image.open(page["content_mask"]) as opened:
            selected_mask = opened.convert("L")
        content_mask, effect_domain = _writing_area(page, selected_mask)
        relative_domain = Path(page["page_id"]) / "writing_area.png"
        domain_bytes = _image_bytes(content_mask, png=True)
        _write_if_changed(OUTPUT / relative_domain, domain_bytes)
        effect_domain = {
            **effect_domain,
            "mask_path": relative_domain.as_posix(),
            "mask_sha256": sha256(domain_bytes).hexdigest(),
        }
        for damage_id in sorted(PROTOTYPE_DAMAGE_IDS, key=lambda value: int(value.split("-")[1])):
            preview, effect_mask, stats = apply_prototype_effect(
                source,
                content_mask,
                damage_id,
                _seed(page["page_id"], damage_id),
            )
            relative_preview = Path(page["page_id"]) / f"{damage_id}_S3_preview.jpg"
            relative_mask = Path(page["page_id"]) / f"{damage_id}_S3_effect.png"
            preview_bytes = _image_bytes(preview, png=False)
            mask_bytes = _image_bytes(effect_mask, png=True)
            _write_if_changed(OUTPUT / relative_preview, preview_bytes)
            _write_if_changed(OUTPUT / relative_mask, mask_bytes)
            row = rows[damage_id]
            level = row["levels"]["S3"]
            task_id = "review_" + sha256(f"{page['page_id']}:{damage_id}".encode()).hexdigest()[:24]
            records.append(
                {
                    "task_id": task_id,
                    "page_id": page["page_id"],
                    "manuscript_id": page["manuscript_id"],
                    "damage_id": damage_id,
                    "severity": "S3",
                    "family": f"prototype_{damage_id.lower().replace('-', '_')}",
                    "cohort": level["cohort"],
                    "effect_kind": stats["effect_kind"],
                    "operator_label": stats["operator_label"],
                    "preview_path": relative_preview.as_posix(),
                    "effect_mask_path": relative_mask.as_posix(),
                    "preview_sha256": sha256(preview_bytes).hexdigest(),
                    "effect_mask_sha256": sha256(mask_bytes).hexdigest(),
                    "source_sha256": page["source_sha256"],
                    "content_mask": page["content_mask"],
                    "content_basis": page["content_basis"],
                    "effect_domain": effect_domain,
                    "matrix_entry": {
                        "source_row": row["source_row"],
                        "content_id": row["content_id"],
                        "damage_id": damage_id,
                        "damage_type": row["damage_type"],
                        "visual_class": row["visual_class"],
                        "severity": "S3",
                        "family": f"prototype_{damage_id.lower().replace('-', '_')}",
                        "decision": level["decision"],
                        "cohort": level["cohort"],
                        "note": level["note"],
                        "status": "review_prototype_ready",
                        "semantic_severity_validated": False,
                    },
                    "statistics": stats,
                    "visual_realism_validated": False,
                    "historical_damage_claim": False,
                    "review_status": "ready_for_specialist_visual_review",
                }
            )
    payload = {
        "version": "damage_review_prototype_v2",
        "purpose": "public interface review; not training data or historical damage evidence",
        "source_dataset": str(SOURCE_DATASET.relative_to(ROOT)),
        "record_count": len(records),
        "page_count": len({record["page_id"] for record in records}),
        "damage_type_count": len({record["damage_id"] for record in records}),
        "records": records,
    }
    _write_if_changed(
        MANIFEST,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return validate()


def validate() -> dict[str, Any]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    counts = Counter(record["damage_id"] for record in payload["records"])
    if payload["record_count"] != 140 or payload["page_count"] != 10 or payload["damage_type_count"] != 14:
        problems.append("manifest_count_mismatch")
    if set(counts) != PROTOTYPE_DAMAGE_IDS or set(counts.values()) != {10}:
        problems.append("per_damage_coverage_mismatch")
    for record in payload["records"]:
        for path_key, hash_key in (
            ("preview_path", "preview_sha256"),
            ("effect_mask_path", "effect_mask_sha256"),
        ):
            path = OUTPUT / record[path_key]
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != record[hash_key]:
                problems.append(f"artifact_mismatch:{record['task_id']}:{path_key}")
        domain = record.get("effect_domain", {})
        domain_path = OUTPUT / domain.get("mask_path", "missing")
        if not domain_path.is_file() or sha256(domain_path.read_bytes()).hexdigest() != domain.get("mask_sha256"):
            problems.append(f"effect_domain_mismatch:{record['task_id']}")
        if record["statistics"].get("visible_page_change", 0) < MIN_VISIBLE_PAGE_CHANGE:
            problems.append(f"effect_not_visible:{record['task_id']}:{record['damage_id']}")
        if record["visual_realism_validated"] or record["historical_damage_claim"]:
            problems.append(f"invalid_claim:{record['task_id']}")
    if problems:
        raise ValueError("prototype_validation_failed:" + ",".join(problems[:10]))
    return {
        "status": "passed",
        "records": payload["record_count"],
        "pages": payload["page_count"],
        "damage_types": payload["damage_type_count"],
        "per_damage": dict(sorted(counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = validate() if args.validate_only else build()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
