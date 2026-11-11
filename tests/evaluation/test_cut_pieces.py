"""Tests for the page cutter (synthetic fragments for matching experiments)."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from src.evaluation.cut_pieces import BACKGROUND, LONG_SIDE, MIN_INK, cut_page, leaf_mask


def fake_page(width: int = 900, height: int = 1300) -> Image.Image:
    """A parchment leaf with lines of 'writing' on black, plus a colour card and a white caption band."""
    img = Image.new("RGB", (width, height), (8, 8, 8))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 60, 50, width - 160, height - 140
    d.rectangle((x0, y0, x1, y1), fill=(214, 190, 150))            # warm parchment
    for row in range(y0 + 60, y1 - 50, 34):                          # two columns of text lines
        d.rectangle((x0 + 50, row, (x0 + x1) // 2 - 25, row + 12), fill=(60, 45, 35))
        d.rectangle(((x0 + x1) // 2 + 25, row, x1 - 50, row + 12), fill=(60, 45, 35))
    d.rectangle((width - 120, 200, width - 40, 520), fill=(250, 220, 40))   # yellow colour-card patch
    d.rectangle((0, height - 70, width, height), fill=(250, 250, 250))       # white caption band
    return img


def test_leaf_mask_excludes_background_card_and_caption() -> None:
    img = fake_page()
    leaf = leaf_mask(img)
    assert leaf[600, 400]                       # inside the leaf
    assert not leaf[10, 10]                     # black background
    assert not leaf[350, img.width - 80]        # colour card
    assert not leaf[img.height - 30, 400]       # caption band
    assert 0.6 < leaf.mean() < 0.8


def test_three_pieces_partition_the_leaf_without_overlap() -> None:
    pieces, meta = cut_page(fake_page(), "test-seed")
    assert len(pieces) == 3 and meta["layout"] in ("top_then_split_bottom", "left_then_split_right")
    masks = [p.mask for p in pieces]
    assert all(not (a & b).any() for i, a in enumerate(masks) for b in masks[i + 1:])
    assert max(meta["leaf_size"]) == LONG_SIDE
    assert all(p.ink_fraction >= MIN_INK and p.area_fraction >= 0.18 for p in pieces)
    assert meta["visual_realism_validated"] is False and meta["historical_damage_claim"] is False


def test_photograph_uses_the_neutral_background_and_matching_survival_mask() -> None:
    pieces, _ = cut_page(fake_page(), "test-seed")
    for p in pieces:
        assert p.photo.size == p.survival.size
        assert p.photo.getpixel((1, 1)) == BACKGROUND
        surv = np.asarray(p.survival)
        assert set(np.unique(surv)) <= {0, 255} and 0.3 < (surv == 255).mean() < 0.95
        assert abs(p.rotation_deg) <= 6.0


def test_cutting_is_deterministic_per_seed() -> None:
    a, _ = cut_page(fake_page(), "same")
    b, _ = cut_page(fake_page(), "same")
    c, _ = cut_page(fake_page(), "other")
    assert all((x.mask == y.mask).all() and x.rotation_deg == y.rotation_deg for x, y in zip(a, b))
    assert any(not (x.mask == y.mask).all() for x, y in zip(a, c))
