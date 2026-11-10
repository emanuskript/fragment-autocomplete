"""Determinism and evidence-boundary tests for the public review previews."""

from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_damage_review_prototype import (
    MANIFEST,
    MIN_VISIBLE_PAGE_CHANGE,
    OPERATOR_INFO,
    PROTOTYPE_DAMAGE_IDS,
    apply_prototype_effect,
    validate,
)


def review_fixture() -> tuple[Image.Image, Image.Image]:
    source = Image.new("RGB", (192, 240), (210, 184, 132))
    draw = ImageDraw.Draw(source)
    # Word-like dashes at staggered positions, so mirrored (recto/verso) proxies
    # do not land exactly on the existing ink.
    for row, y in enumerate(range(52, 198, 14)):
        for x in range(38 + (row * 7) % 19, 150, 26):
            draw.line((x, y, x + 11 + row % 4, y), fill=(42, 32, 22), width=3)
    mask = Image.new("L", source.size, 0)
    ImageDraw.Draw(mask).rectangle((30, 38, 166, 210), fill=255)
    return source, mask


def test_operator_registry_covers_all_non_loss_types():
    assert set(OPERATOR_INFO) == PROTOTYPE_DAMAGE_IDS
    assert len(PROTOTYPE_DAMAGE_IDS) == 14


@pytest.mark.parametrize("damage_id", sorted(PROTOTYPE_DAMAGE_IDS))
def test_review_operator_is_deterministic_visible_and_claim_safe(damage_id):
    source, mask = review_fixture()
    result, effect, stats = apply_prototype_effect(source, mask, damage_id, 20261110)
    repeated, repeated_effect, repeated_stats = apply_prototype_effect(
        source, mask, damage_id, 20261110
    )

    assert result.size == source.size and effect.size == source.size
    assert result.tobytes() == repeated.tobytes()
    assert effect.tobytes() == repeated_effect.tobytes()
    assert stats == repeated_stats
    assert result.tobytes() != source.tobytes()
    assert np.asarray(effect).max() > 12
    assert stats["measured_effect_coverage"] > 0
    assert stats["visible_page_change"] > 0
    assert stats["operator_label"] == OPERATOR_INFO[damage_id][1]
    assert stats["effect_kind"] == OPERATOR_INFO[damage_id][0]
    assert stats["visual_realism_validated"] is False
    assert stats["historical_damage_claim"] is False


@pytest.mark.skipif(not MANIFEST.is_file(), reason="review prototypes not generated locally")
def test_every_generated_review_image_is_visibly_changed_at_display_scale():
    """Guard against effects too faint to see in the compare view (the old single-region bug)."""
    import json

    assert validate()["status"] == "passed"
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))["records"]
    assert len(records) == 140
    for record in records:
        assert record["statistics"]["visible_page_change"] >= MIN_VISIBLE_PAGE_CHANGE, record["damage_id"]
        assert record["effect_domain"]["basis"] == "union_of_detected_main_script_regions"
