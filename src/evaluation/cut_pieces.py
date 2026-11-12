"""Cut a complete manuscript page into several torn pieces ("fake fragments").

Unlike the damage operators, which keep one page and remove material from it, this splits
one leaf into non-overlapping pieces, as a binder or dealer cutting up a book would. Every
piece is a synthetic comparator for fragment-matching experiments; it is never presented as
a real fragment, and its edges are an engineering approximation (``visual_realism_validated``
is false), using the same multi-scale noise as the ``paper_edge_v1`` profile.

Steps per page:

1. Leaf mask: the largest bright connected region, so photographic background, rulers and
   colour cards are not carried into any piece (they would identify the photograph).
2. Normalise the leaf to a fixed long side, so pixel resolution does not identify the photograph.
3. Partition the leaf with two torn lines into three pieces (one of two layouts), retrying
   until each piece holds enough writing (dark-ink fraction) and area.
4. "Photograph" each piece: transparent outside the piece, a small rotation, a uniform
   neutral background and margin, saved as JPEG plus a PNG survival mask.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage

from .matrix_synthesis import _normalised_noise

VERSION = "cut_pieces_v1"
LONG_SIDE = 2000
BACKGROUND = (24, 24, 24)
MARGIN = 0.05
MAX_ROTATION_DEG = 6.0
MIN_PIECE_AREA = 0.18      # of the leaf
MIN_INK = 0.04             # dark-ink fraction inside a piece (rejects blank margin strips)
LAYOUTS = ("top_then_split_bottom", "left_then_split_right")
# Cutter profile -> ageing profile in aged_pieces ("realistic" keeps its pilot v3 meaning).
PROFILES = {"clean": None, "realistic": "realistic_v1", "realistic_v2": "realistic_v2"}


@dataclass
class Piece:
    index: int
    mask: np.ndarray                 # bool, leaf frame
    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1 in leaf frame
    area_fraction: float
    ink_fraction: float
    rotation_deg: float
    photo: Image.Image = field(repr=False)        # RGB on neutral background
    survival: Image.Image = field(repr=False)     # L, 255 = piece material, photo frame
    damage: dict[str, Any] = field(default_factory=dict)   # realistic profile: what was applied

    def record(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("mask", "photo", "survival"):
            d.pop(k)
        return d


def _rng(seed: str, salt: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()[:16], 16) % (2**32))


def leaf_mask(image: Image.Image) -> np.ndarray:
    """The leaf: the largest warm-toned connected region (parchment or paper), holes filled.

    Photographic surrounds are neutral (black, white or grey), so colour separates them where
    brightness cannot: white mounts, grey cards, colour checkers and library caption bands
    (e.g. Gallica's "Source gallica.bnf.fr / BnF" strip) all fall outside the leaf.
    """
    full_w, full_h = image.size
    small = image.convert("RGB").copy()
    small.thumbnail((600, 600))
    hsv = np.asarray(small.convert("HSV"), dtype=np.float32) / 255.0
    hue, sat, val = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    warm_hue = (hue < 70) | (hue > 330)

    def largest(mask: np.ndarray) -> np.ndarray | None:
        # Writing breaks the parchment mask into islands on dense pages; bridge it first.
        mask = ndimage.binary_closing(mask, iterations=4)
        mask = ndimage.binary_opening(mask, iterations=2)
        labels, n = ndimage.label(mask)
        if n == 0:
            return None
        sizes = ndimage.sum(mask, labels, range(1, n + 1))
        return labels == (int(np.argmax(sizes)) + 1)

    # Pass 1 finds the leaf roughly; pass 2 sets the saturation floor from the leaf itself
    # (half its median), so a cream or pinkish mount (S ~0.1 beside parchment at ~0.3) drops out
    # while pale pages (S ~0.09) keep the 0.07 floor. Saturated colour-card patches are cut;
    # pigments enclosed by the leaf come back when holes are filled.
    first = largest((sat > 0.07) & (val > 0.30) & warm_hue)
    if first is None:
        return np.ones((full_h, full_w), dtype=bool)
    floor = max(0.07, 0.5 * float(np.median(sat[first])))
    leaf = largest((sat > floor) & (sat < 0.65) & (val > 0.30) & warm_hue)
    if leaf is None:
        leaf = first
    leaf = ndimage.binary_fill_holes(ndimage.binary_closing(leaf, iterations=6))
    leaf = ndimage.binary_erosion(leaf, iterations=2)  # stay just inside the leaf edge
    mask = Image.fromarray((leaf * 255).astype(np.uint8)).resize((full_w, full_h), Image.BILINEAR)
    return np.asarray(mask) > 127


def normalise(image: Image.Image, leaf: np.ndarray) -> tuple[Image.Image, np.ndarray, float]:
    ys, xs = np.nonzero(leaf)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop = image.crop((x0, y0, x1, y1))
    m = Image.fromarray((leaf[y0:y1, x0:x1] * 255).astype(np.uint8))
    scale = LONG_SIDE / max(crop.size)
    size = (max(1, round(crop.size[0] * scale)), max(1, round(crop.size[1] * scale)))
    crop = crop.resize(size, Image.LANCZOS)
    m = m.resize(size, Image.NEAREST)
    return crop, np.asarray(m) > 127, scale


def ink_map(image: Image.Image, leaf: np.ndarray) -> np.ndarray:
    """Pixels clearly darker than the parchment around them (ink, decoration)."""
    g = np.asarray(image.convert("L"), dtype=np.float32)
    local = ndimage.uniform_filter(g, size=61)
    return (g < local - 28) & leaf


def _tear(length: int, position: float, amplitude: float, rng: np.random.Generator) -> np.ndarray:
    """A torn line: position (pixels) plus correlated multi-scale noise along `length`."""
    # Broad wander, a softer medium ripple and a faint fibrous fringe: torn, not sawn.
    line = (amplitude * (1.0 * _normalised_noise(rng, length, max(8, length / 7))
                         + .28 * _normalised_noise(rng, length, max(4, length / 30))
                         + .06 * _normalised_noise(rng, length, max(1.5, length / 220))))
    return position + line


def _knife(length: int, position: float, rng: np.random.Generator) -> np.ndarray:
    """A knife cut: a straight line at a small angle, with a sub-pixel waver of the blade."""
    slope = float(rng.uniform(-.035, .035))
    t = np.arange(length, dtype=np.float32) - length / 2
    return position + slope * t + 0.6 * _normalised_noise(rng, length, max(4, length / 40))


def partition(shape: tuple[int, int], layout: str, rng: np.random.Generator,
              knife_p: float | None = None) -> list[np.ndarray]:
    """Three pieces. ``knife_p=None`` is cut_pieces_v1 (two torn lines); otherwise each line is a
    straight knife cut with probability ``knife_p`` and a gentler tear otherwise."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]

    def cut(length: int, position: float, amplitude: float) -> np.ndarray:
        if knife_p is None:
            return _tear(length, position, amplitude, rng)
        if rng.random() < knife_p:
            return _knife(length, position, rng)
        return _tear(length, position, amplitude * .45, rng)

    if layout == "top_then_split_bottom":
        cut1 = cut(w, h * rng.uniform(.36, .58), h * .035)        # y as a function of x
        cut2 = cut(h, w * rng.uniform(.38, .62), w * .045)        # x as a function of y
        first = yy < cut1[None, :]
        rest = ~first
        a = rest & (xx < cut2[:, None])
        return [first, a, rest & ~a]
    cut1 = cut(h, w * rng.uniform(.34, .56), w * .04)            # x as a function of y
    cut2 = cut(w, h * rng.uniform(.38, .62), h * .035)           # y as a function of x
    first = xx < cut1[:, None]
    rest = ~first
    a = rest & (yy < cut2[None, :])
    return [first, a, rest & ~a]


def _photograph(leaf_img: Image.Image, mask: np.ndarray, rotation: float) -> tuple[Image.Image, Image.Image, tuple]:
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    rgba = leaf_img.crop((x0, y0, x1, y1)).convert("RGBA")
    alpha = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8))
    rgba.putalpha(alpha)
    rgba = rgba.rotate(rotation, resample=Image.BICUBIC, expand=True)
    pad = int(MARGIN * max(rgba.size))
    canvas = Image.new("RGB", (rgba.size[0] + 2 * pad, rgba.size[1] + 2 * pad), BACKGROUND)
    canvas.paste(rgba, (pad, pad), rgba)
    survival = Image.new("L", canvas.size, 0)
    survival.paste(rgba.getchannel("A").point(lambda v: 255 if v > 127 else 0), (pad, pad))
    return canvas, survival, (x0, y0, x1, y1)


def cut_page(image: Image.Image, seed: str, *, n_pieces: int = 3, tries: int = 40,
             profile: str = "clean") -> tuple[list[Piece], dict[str, Any]]:
    """Cut one page. ``profile="clean"`` is cut_pieces_v1 unchanged; ``"realistic"`` adds ageing,
    worn and trimmed edges, combined damage and archive photography (see ``aged_pieces``)."""
    if n_pieces != 3:
        raise ValueError("cut_pieces_v1 cuts exactly three pieces")
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {', '.join(PROFILES)}")
    aged = None if profile == "clean" else PROFILES[profile]
    image = image.convert("RGB")
    leaf = leaf_mask(image)
    leaf_img, leaf_n, scale = normalise(image, leaf)
    ink = ink_map(leaf_img, leaf_n)   # measured on the undamaged leaf: the cut must hold writing
    page_damage = None
    if aged:
        from . import aged_pieces
        prm = aged_pieces.PROFILES[aged]
        leaf_img, page_damage = aged_pieces.age_leaf(leaf_img, leaf_n, _rng(seed, "age"), prm)
    leaf_area = leaf_n.sum()
    # Sparse pages (wide margins, short lines) cannot give every piece 4 % ink; the realistic
    # profile asks for half the page's own ink density instead. The clean profile is unchanged.
    # realistic_v2 first asks every piece for most of the page's ink density (a piece that is
    # mostly blank margin identifies nothing) and relaxes step by step if no cut qualifies.
    density = float(ink.sum() / max(leaf_n.sum(), 1))
    shares = (prm.get("ink_share") or (.5,)) if aged else (None,)
    rng = _rng(seed, "layout")
    first = LAYOUTS[int(rng.integers(len(LAYOUTS)))]
    found = None
    for share in shares:
        min_ink = MIN_INK if share is None else min(MIN_INK, share * density)
        # Try the drawn layout first; a page whose writing sits to one side (a wide decorated
        # border, say) may only cut validly the other way.
        for layout in (first, *[x for x in LAYOUTS if x != first]):
            for attempt in range(tries):
                knife = prm.get("knife_p") if aged else None
                parts = [p & leaf_n for p in partition(leaf_n.shape, layout, _rng(seed, f"{layout}:cut{attempt}"), knife)]
                stats = [(p.sum() / leaf_area, ink[p].sum() / max(p.sum(), 1)) for p in parts]
                if all(a >= MIN_PIECE_AREA and i >= min_ink for a, i in stats):
                    found = (layout, attempt, parts, stats)
                    break
            if found:
                break
        if found:
            break
    if not found:
        raise RuntimeError(f"no valid cut after {tries} tries in each layout")
    layout, attempt, parts, stats = found
    pieces = []
    rot_rng = _rng(seed, "rotation")
    for k, (p, (area, inkf)) in enumerate(zip(parts, stats)):
        # keep the largest connected part of each piece (a tear never leaves floating crumbs)
        lab, n = ndimage.label(p)
        if n > 1:
            p = lab == (int(np.argmax(ndimage.sum(p, lab, range(1, n + 1)))) + 1)
        rotation = round(float(rot_rng.uniform(-MAX_ROTATION_DEG, MAX_ROTATION_DEG)), 2)
        if aged:
            prng = _rng(seed, f"piece{k + 1}")
            piece_img, p, damage = aged_pieces.damage_piece(leaf_img, p, prng, int(prng.integers(2**31)), prm)
            photo, survival, bbox, shot = aged_pieces.photograph(piece_img, p, rotation, prng, MARGIN)
            area = p.sum() / leaf_area
            piece = Piece(k + 1, p, bbox, round(float(area), 4), round(float(inkf), 4), rotation, photo, survival)
            piece.damage = {**damage, "photograph": shot}
        else:
            photo, survival, bbox = _photograph(leaf_img, p, rotation)
            piece = Piece(k + 1, p, bbox, round(float(area), 4), round(float(inkf), 4), rotation, photo, survival)
        pieces.append(piece)
    meta = {"version": VERSION, "profile": aged or "clean", "layout": layout,
            "attempts": attempt + 1, "leaf_size": list(leaf_img.size),
            "scale_from_source": round(scale, 5), "long_side": LONG_SIDE, "background": list(BACKGROUND),
            "visual_realism_validated": False, "historical_damage_claim": False}
    if page_damage is not None:
        meta["page_damage"] = page_damage
    return pieces, meta
