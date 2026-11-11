"""The "realistic" profile for cut pieces: aged leaves, worn and trimmed edges, combined damage,
archive-style photography.

Built after comparing the clean cut pieces with the real fragments in the Fragmentarium /
CODICUM / Riksarkivet pilot (the fragments named in the initial email): real fragments are
darkened and soiled towards their edges, their edges are worn and rounded or knife-trimmed
(reused as covers), they carry stains, abrasion, holes and folds together, and they are
photographed on grey, blue-grey or black grounds, often beside a scale bar.

Every effect here is an engineering approximation for matching experiments. Nothing is a
model of a specific historical damage; ``visual_realism_validated`` stays false until a
specialist review. The surface effects reuse the 14 review operators in
``scripts/build_damage_review_prototype.py`` (Jeremy's damage matrix ids), blended at partial
strength and combined two or three per piece.

Order of work, per page and piece (all seeded, so a run is reproducible):

1. Page: ageing (tone shift, low-frequency grime, soiling towards the leaf edge) and, for some
   leaves, one old fold — damage the leaf had before it was cut up, shared by its pieces.
2. Piece: worn edges; on some pieces one straight knife trim; two or three surface damages
   from the matrix; holes (worm holes or a row of sewing holes) on some pieces; dirt along the
   piece's own edges — the life each piece had after the leaf was cut.
3. Photograph: one of four archive grounds, a soft shadow, sometimes a grey-scale bar.
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

PROFILE = "realistic_v1"
# D2-08 (deposits) and D2-06 (coating) were tried and dropped: at piece scale they read as
# polka dots and flat blobs, unlike the fragments they were compared with. Fine dust specks are
# added in soil_edges instead.
SURFACE_DAMAGES = ("D2-09", "D2-12", "D2-11", "D2-16", "D2-17")
# Strength ranges: blending the operator's output back over the piece. Fading and abrasion are
# kept lighter so the script stays partly legible, as on most surviving fragments.
STRENGTH = {"D2-09": (.55, .9), "D2-12": (.35, .6), "D2-11": (.3, .55), "D2-08": (.35, .7),
            "D2-16": (.45, .8), "D2-06": (.35, .6), "D2-17": (.35, .6)}
GROUNDS = {"black": (22, 22, 22), "grey": (92, 96, 100), "blue_grey": (58, 70, 88), "light_grey": (196, 196, 192)}


@lru_cache(maxsize=1)
def _operators():
    path = Path(__file__).resolve().parents[2] / "scripts" / "build_damage_review_prototype.py"
    spec = importlib.util.spec_from_file_location("damage_review_prototype", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lowfreq(shape: tuple[int, int], rng: np.random.Generator, cells: int) -> np.ndarray:
    """Smooth noise in [0, 1] with about `cells` blobs across the longer side."""
    h, w = shape
    gh, gw = max(2, round(cells * h / max(h, w))), max(2, round(cells * w / max(h, w)))
    small = rng.random((gh, gw)).astype(np.float32)
    big = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), dtype=np.float32) / 255
    return np.clip(big, 0, 1)


# ------------------------------------------------------------------ page level

def age_leaf(leaf_img: Image.Image, leaf: np.ndarray, rng: np.random.Generator) -> tuple[Image.Image, dict[str, Any]]:
    arr = np.asarray(leaf_img, dtype=np.float32)
    h, w = leaf.shape
    tone = float(rng.uniform(.06, .2))
    arr = arr * (1 - tone) + np.array([150, 116, 74], dtype=np.float32) * tone
    grime = _lowfreq((h, w), rng, 9)
    arr *= (0.86 + 0.14 * grime)[..., None]
    # Soiling towards the leaf edge: handled, rubbed and dusty where it was exposed.
    dist = ndimage.distance_transform_edt(leaf).astype(np.float32)
    reach = max(h, w) * float(rng.uniform(.05, .11))
    edge = np.clip(1 - dist / reach, 0, 1) ** 1.6 * (0.6 + 0.4 * _lowfreq((h, w), rng, 14))
    soil = float(rng.uniform(.25, .45))
    arr = arr * (1 - soil * edge[..., None]) + np.array([70, 52, 34], dtype=np.float32) * (soil * edge[..., None] * .35)
    rec: dict[str, Any] = {"tone": round(tone, 3), "edge_soiling": round(soil, 3)}
    if rng.random() < .55:  # one old fold across the leaf
        yy, xx = np.mgrid[0:h, 0:w]
        horizontal = rng.random() < .5
        pos = float(rng.uniform(.35, .65)) * (h if horizontal else w)
        slope = float(rng.uniform(-.04, .04))
        d = (yy - (pos + slope * (xx - w / 2))) if horizontal else (xx - (pos + slope * (yy - h / 2)))
        band = np.exp(-(d / (max(h, w) * .006)) ** 2)
        shade = np.tanh(d / (max(h, w) * .003)) * band * 28 - band * 18
        arr += shade[..., None]
        rec["fold"] = "horizontal" if horizontal else "vertical"
    out = np.clip(arr, 0, 255).astype(np.uint8)
    out[~leaf] = np.asarray(leaf_img)[~leaf]
    return Image.fromarray(out), rec


# ------------------------------------------------------------------ piece level

def wear_edges(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Round and nibble the edge: keep pixels deeper than a slowly varying wear depth."""
    dist = ndimage.distance_transform_edt(mask).astype(np.float32)
    h, w = mask.shape
    depth = 2 + 16 * _lowfreq((h, w), rng, 18) * float(rng.uniform(.5, 1.2))
    fibres = rng.random((h, w)).astype(np.float32) * 3
    worn = mask & (dist > depth + fibres)
    worn = ndimage.binary_opening(worn, iterations=3)
    lab, n = ndimage.label(worn)
    if n > 1:
        worn = lab == (int(np.argmax(ndimage.sum(worn, lab, range(1, n + 1)))) + 1)
    return worn


def trim_straight(mask: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, str]:
    """One knife cut along a side, removing a thin strip (reuse as a binding)."""
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    side = str(rng.choice(["top", "bottom", "left", "right"]))
    frac = float(rng.uniform(.03, .09))
    angle = float(rng.uniform(-.03, .03))
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    if side == "top":
        keep = yy > y0 + (y1 - y0) * frac + angle * (xx - x0)
    elif side == "bottom":
        keep = yy < y1 - (y1 - y0) * frac + angle * (xx - x0)
    elif side == "left":
        keep = xx > x0 + (x1 - x0) * frac + angle * (yy - y0)
    else:
        keep = xx < x1 - (x1 - x0) * frac + angle * (yy - y0)
    return mask & keep, side


def punch_holes(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Worm holes (a few irregular holes) or a row of sewing holes; each with a darkened rim."""
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    size = max(x1 - x0, y1 - y0)
    holes = Image.new("L", (mask.shape[1], mask.shape[0]), 0)
    draw = ImageDraw.Draw(holes)
    kind = "sewing" if rng.random() < .4 else "worm"
    n = 0
    if kind == "sewing":
        vertical = rng.random() < .5
        k = int(rng.integers(3, 6))
        r = size * float(rng.uniform(.006, .011))
        for i in range(k):
            t = (i + 1) / (k + 1)
            cx = x0 + (x1 - x0) * (.06 if vertical else t)
            cy = y0 + (y1 - y0) * (t if vertical else .06)
            draw.ellipse((cx - r, cy - r * 1.3, cx + r, cy + r * 1.3), fill=255)
            n += 1
    else:
        for _ in range(int(rng.integers(1, 5))):
            r = size * float(rng.uniform(.008, .03))
            cx, cy = rng.uniform(x0 + r, x1 - r), rng.uniform(y0 + r, y1 - r)
            pts = [(cx + r * (0.7 + 0.5 * rng.random()) * np.cos(a), cy + r * (0.7 + 0.5 * rng.random()) * np.sin(a))
                   for a in np.linspace(0, 2 * np.pi, 11)[:-1]]
            draw.polygon(pts, fill=255)
            n += 1
    hole = (np.asarray(holes) > 0) & mask
    rim = ndimage.binary_dilation(hole, iterations=max(2, int(size * .004))) & mask & ~hole
    out = img.astype(np.float32)
    out[rim] = out[rim] * .55 + np.array([60, 42, 26], dtype=np.float32) * .45
    return np.clip(out, 0, 255).astype(np.uint8), mask & ~hole, {"kind": kind, "count": n}


def soil_edges(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Dirt along the piece's own edges, and a fine dust of dark specks."""
    specks = (rng.random(mask.shape) < float(rng.uniform(2e-4, 8e-4))) & mask
    specks = ndimage.binary_dilation(specks, iterations=1)
    img = img.copy()
    img[specks] = (img[specks].astype(np.float32) * .45 + np.array([50, 38, 26]) * .55).astype(np.uint8)
    dist = ndimage.distance_transform_edt(mask).astype(np.float32)
    reach = max(mask.shape) * float(rng.uniform(.015, .035))
    band = np.clip(1 - dist / reach, 0, 1) * mask
    k = float(rng.uniform(.25, .45))
    out = img.astype(np.float32) * (1 - k * band[..., None]) + np.array([62, 46, 30], dtype=np.float32) * (k * band[..., None] * .5)
    return np.clip(out, 0, 255).astype(np.uint8)


def surface_damage(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator, seed: int) -> tuple[np.ndarray, list[dict[str, Any]]]:
    ops = _operators()
    k = int(rng.integers(2, 4))
    chosen = list(rng.choice(SURFACE_DAMAGES, size=k, replace=False))
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    crop = img[y0:y1, x0:x1].copy()
    cm = mask[y0:y1, x0:x1]
    records = []
    for i, dmg in enumerate(chosen):
        lo, hi = STRENGTH[dmg]
        s = float(rng.uniform(lo, hi))
        out, _, stats = ops.apply_prototype_effect(Image.fromarray(crop), Image.fromarray((cm * 255).astype(np.uint8)),
                                                   dmg, seed + 7919 * (i + 1))
        out = np.asarray(out, dtype=np.float32)
        # Feather where the operator acted, so no effect ends in a hard contour.
        changed = (np.abs(out - crop.astype(np.float32)).mean(axis=2) > 3).astype(np.float32)
        sigma = max(4.0, 0.012 * max(cm.shape))
        weight = np.clip(ndimage.gaussian_filter(changed, sigma) * 1.6, 0, 1) * s * cm
        crop = (crop.astype(np.float32) * (1 - weight[..., None]) + out * weight[..., None]).astype(np.uint8)
        records.append({"damage_id": dmg, "operator": ops.OPERATOR_INFO[dmg][1], "strength": round(s, 3),
                        "coverage": round(float(stats["measured_effect_coverage"]), 3)})
    img = img.copy()
    img[y0:y1, x0:x1] = crop
    return img, records


def damage_piece(leaf_img: Image.Image, mask: np.ndarray, rng: np.random.Generator, seed: int
                 ) -> tuple[Image.Image, np.ndarray, dict[str, Any]]:
    rec: dict[str, Any] = {}
    mask = wear_edges(mask, rng)
    if rng.random() < .45:
        mask, side = trim_straight(mask, rng)
        rec["trimmed"] = side
    img = np.asarray(leaf_img).copy()
    img, rec["surface"] = surface_damage(img, mask, rng, seed)
    if rng.random() < .6:
        img, mask, rec["holes"] = punch_holes(img, mask, rng)
    img = soil_edges(img, mask, rng)
    lab, n = ndimage.label(mask)
    if n > 1:
        mask = lab == (int(np.argmax(ndimage.sum(mask, lab, range(1, n + 1)))) + 1)
    return Image.fromarray(img), mask, rec


# ------------------------------------------------------------------ photograph

def _scale_bar(width: int, rng: np.random.Generator) -> Image.Image:
    h = max(18, width // 22)
    bar = Image.new("RGB", (width, h), (240, 240, 236))
    d = ImageDraw.Draw(bar)
    n = 10
    for i in range(n):
        if i % 2 == 0:
            d.rectangle((i * width / n, 0, (i + 1) * width / n, h * .55), fill=(20, 20, 20))
    for i in range(n * 5 + 1):
        x = i * width / (n * 5)
        d.line((x, h * .55, x, h * (.95 if i % 5 == 0 else .75)), fill=(30, 30, 30), width=1)
    return bar


def photograph(leaf_img: Image.Image, mask: np.ndarray, rotation: float, rng: np.random.Generator, margin: float
               ) -> tuple[Image.Image, Image.Image, tuple, dict[str, Any]]:
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    rgba = leaf_img.crop((x0, y0, x1, y1)).convert("RGBA")
    alpha = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.8))
    rgba.putalpha(alpha)
    rgba = rgba.rotate(rotation, resample=Image.BICUBIC, expand=True)
    ground_name = str(rng.choice(list(GROUNDS), p=[.3, .3, .25, .15]))
    ground = GROUNDS[ground_name]
    pad = int(margin * max(rgba.size))
    with_bar = rng.random() < .35
    bar_h = int(max(rgba.size) * .07) if with_bar else 0
    canvas = Image.new("RGB", (rgba.size[0] + 2 * pad, rgba.size[1] + 2 * pad + bar_h), ground)
    # Soft shadow so the piece lies on the ground rather than floating on it.
    shadow = Image.new("L", canvas.size, 0)
    shadow.paste(rgba.getchannel("A"), (pad + 6, pad + 8))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * .45))
    canvas = Image.composite(Image.new("RGB", canvas.size, tuple(int(c * .45) for c in ground)), canvas, shadow)
    canvas.paste(rgba, (pad, pad), rgba)
    if with_bar:
        bar = _scale_bar(int(rgba.size[0] * .45), rng)
        canvas.paste(bar.resize((bar.size[0], max(10, bar_h // 2))), (pad, rgba.size[1] + pad + bar_h // 4))
    # Light sensor noise, as on a real capture.
    arr = np.asarray(canvas, dtype=np.float32) + rng.normal(0, 2.2, (canvas.size[1], canvas.size[0], 1))
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    survival = Image.new("L", canvas.size, 0)
    survival.paste(rgba.getchannel("A").point(lambda v: 255 if v > 127 else 0), (pad, pad))
    return canvas, survival, (x0, y0, x1, y1), {"ground": ground_name, "scale_bar": with_bar}
