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

# Profile parameters. realistic_v1 is the profile of pilot set v3, unchanged. realistic_v2 was
# tuned against the 18 real fragments of the initial email (FragmentJoin
# scripts/compare_realism.py): the real material is warmer (CIE b* about 19), its edges are
# barely darker than its interior (about 0.96), its outline is nearly straight (knife-trimmed
# for reuse in bindings, with small nibbles and chips; 1 - area/hull about 0.015), it carries
# small holes, and its surface is evenly grimed and finely mottled rather than blotched by
# large stains. v2 therefore cuts mostly with straight knife lines, wears the edges lightly,
# bites a few small chips out of them, ages the leaf warmer, soils edges less, adds a fine
# mottle, and uses fewer, lighter stains.
PROFILES: dict[str, dict[str, Any]] = {
    "realistic_v1": {
        "tone": (.06, .2), "tone_rgb": (150, 116, 74), "grime": .14, "page_soil": (.25, .45),
        "page_reach": (.05, .11), "fold_p": .55, "mottle": 0.0, "wear": 16, "trim_p": .45, "bites": (0, 0),
        "n_damage": (2, 4), "damages": SURFACE_DAMAGES, "strength": 1.0, "hole_p": .6, "worm_holes": (1, 5),
        "piece_soil": (.25, .45), "piece_reach": (.015, .035), "knife_p": None, "worm_r": (.008, .03), "ink_share": None,
    },
    "realistic_v2": {
        "tone": (.2, .34), "tone_rgb": (164, 126, 64), "grime": .34, "grime_centred": True, "page_soil": (.06, .16),
        "page_reach": (.03, .07), "fold_p": .45, "mottle": .07, "wear": 4, "trim_p": .3, "bites": (1, 4),
        "n_damage": (1, 3), "damages": ("D2-09", "D2-12", "D2-11", "D2-17"), "strength": .6, "hole_p": .9,
        "worm_holes": (3, 7), "piece_soil": (.14, .26), "piece_reach": (.008, .02), "knife_p": .8, "worm_r": (.014, .04), "ink_share": (.85, .7, .5),
    },
}


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

def age_leaf(leaf_img: Image.Image, leaf: np.ndarray, rng: np.random.Generator,
             prm: dict[str, Any] | None = None) -> tuple[Image.Image, dict[str, Any]]:
    prm = prm or PROFILES["realistic_v1"]
    arr = np.asarray(leaf_img, dtype=np.float32)
    h, w = leaf.shape
    tone = float(rng.uniform(*prm["tone"]))
    arr = arr * (1 - tone) + np.array(prm["tone_rgb"], dtype=np.float32) * tone
    grime = _lowfreq((h, w), rng, 9)
    if prm.get("grime_centred"):
        # Uneven ageing that lightens as much as it darkens: patchier without a darker mean.
        arr *= (1 + prm["grime"] * (grime - .5))[..., None]
    else:
        arr *= (1 - prm["grime"] + prm["grime"] * grime)[..., None]
    # Soiling towards the leaf edge: handled, rubbed and dusty where it was exposed.
    dist = ndimage.distance_transform_edt(leaf).astype(np.float32)
    reach = max(h, w) * float(rng.uniform(*prm["page_reach"]))
    edge = np.clip(1 - dist / reach, 0, 1) ** 1.6 * (0.6 + 0.4 * _lowfreq((h, w), rng, 14))
    soil = float(rng.uniform(*prm["page_soil"]))
    arr = arr * (1 - soil * edge[..., None]) + np.array([70, 52, 34], dtype=np.float32) * (soil * edge[..., None] * .35)
    rec: dict[str, Any] = {"tone": round(tone, 3), "edge_soiling": round(soil, 3)}
    if prm["mottle"]:
        # Fine mottle of handled parchment: two scales of small, soft variation in tone.
        m = .6 * _lowfreq((h, w), rng, 70) + .4 * _lowfreq((h, w), rng, 180)
        arr *= (1 - prm["mottle"] * m)[..., None]
        rec["mottle"] = prm["mottle"]
    if rng.random() < prm["fold_p"]:  # one old fold across the leaf
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

def wear_edges(mask: np.ndarray, rng: np.random.Generator, depth_max: float = 16) -> np.ndarray:
    """Round and nibble the edge: keep pixels deeper than a slowly varying wear depth."""
    dist = ndimage.distance_transform_edt(mask).astype(np.float32)
    h, w = mask.shape
    depth = 2 + depth_max * _lowfreq((h, w), rng, 18) * float(rng.uniform(.5, 1.2))
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


def bite_edges(mask: np.ndarray, rng: np.random.Generator, n: int) -> tuple[np.ndarray, int]:
    """Small chips and nibbles out of the edge (a corner knocked off, a bite at the fold)."""
    if n <= 0:
        return mask, 0
    edge = mask & ~ndimage.binary_erosion(mask)
    ys, xs = np.nonzero(edge)
    if len(xs) == 0:
        return mask, 0
    size = max(xs.max() - xs.min(), ys.max() - ys.min())
    bites = Image.new("L", (mask.shape[1], mask.shape[0]), 0)
    draw = ImageDraw.Draw(bites)
    for _ in range(n):
        i = int(rng.integers(len(xs)))
        cx, cy = float(xs[i]), float(ys[i])
        r = size * float(rng.uniform(.01, .024))
        pts = [(cx + r * (0.5 + 0.8 * rng.random()) * np.cos(a), cy + r * (0.5 + 0.8 * rng.random()) * np.sin(a))
               for a in np.linspace(0, 2 * np.pi, 13)[:-1]]
        draw.polygon(pts, fill=255)
    out = mask & ~(np.asarray(bites) > 0)
    return out, n


def punch_holes(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator,
                worm: tuple[int, int] = (1, 5), worm_r: tuple[float, float] = (.008, .03)) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
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
        for _ in range(int(rng.integers(*worm))):
            r = size * float(rng.uniform(*worm_r))
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


def soil_edges(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator,
               reach_range: tuple[float, float] = (.015, .035), soil: tuple[float, float] = (.25, .45)) -> np.ndarray:
    """Dirt along the piece's own edges, and a fine dust of dark specks."""
    specks = (rng.random(mask.shape) < float(rng.uniform(2e-4, 8e-4))) & mask
    specks = ndimage.binary_dilation(specks, iterations=1)
    img = img.copy()
    img[specks] = (img[specks].astype(np.float32) * .45 + np.array([50, 38, 26]) * .55).astype(np.uint8)
    dist = ndimage.distance_transform_edt(mask).astype(np.float32)
    reach = max(mask.shape) * float(rng.uniform(*reach_range))
    band = np.clip(1 - dist / reach, 0, 1) * mask
    k = float(rng.uniform(*soil))
    out = img.astype(np.float32) * (1 - k * band[..., None]) + np.array([62, 46, 30], dtype=np.float32) * (k * band[..., None] * .5)
    return np.clip(out, 0, 255).astype(np.uint8)


def surface_damage(img: np.ndarray, mask: np.ndarray, rng: np.random.Generator, seed: int,
                   prm: dict[str, Any] | None = None) -> tuple[np.ndarray, list[dict[str, Any]]]:
    prm = prm or PROFILES["realistic_v1"]
    ops = _operators()
    k = int(rng.integers(*prm["n_damage"]))
    chosen = list(rng.choice(prm["damages"], size=k, replace=False))
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    crop = img[y0:y1, x0:x1].copy()
    cm = mask[y0:y1, x0:x1]
    records = []
    for i, dmg in enumerate(chosen):
        lo, hi = STRENGTH[dmg]
        s = float(rng.uniform(lo, hi)) * prm["strength"]
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


def damage_piece(leaf_img: Image.Image, mask: np.ndarray, rng: np.random.Generator, seed: int,
                 prm: dict[str, Any] | None = None) -> tuple[Image.Image, np.ndarray, dict[str, Any]]:
    prm = prm or PROFILES["realistic_v1"]
    rec: dict[str, Any] = {}
    mask = wear_edges(mask, rng, prm["wear"])
    if rng.random() < prm["trim_p"]:
        mask, side = trim_straight(mask, rng)
        rec["trimmed"] = side
    if prm["bites"][1]:
        mask, rec["edge_bites"] = bite_edges(mask, rng, int(rng.integers(*prm["bites"])))
    img = np.asarray(leaf_img).copy()
    img, rec["surface"] = surface_damage(img, mask, rng, seed, prm)
    if rng.random() < prm["hole_p"]:
        img, mask, rec["holes"] = punch_holes(img, mask, rng, prm["worm_holes"], prm["worm_r"])
    img = soil_edges(img, mask, rng, prm["piece_reach"], prm["piece_soil"])
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
