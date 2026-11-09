"""Matrix policy, target calibration, provenance and split isolation."""
from copy import deepcopy
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.evaluation.damage_matrix import AREA_PROXIES, import_matrix, plan, write_json
from src.evaluation.matrix_synthesis import content_damage, generate_dataset, make_demo, validate_sources


@pytest.fixture
def matrix():
    return json.loads((ROOT / "data/metadata/jeremy_damage_matrix_v3.json").read_text())


def test_supplied_matrix_preserves_all_rows_and_flags_incomplete_records(matrix):
    assert matrix["summary"]["row_count"] == 187
    assert matrix["summary"]["named_damage_types"] == 17
    assert matrix["summary"]["rows_needing_review"] == [187, 188]
    result = plan(matrix)
    assert sum(result["counts"].values()) == 187 * 4
    assert result["counts"]["matrix_review_required"] == 8
    assert all(e["cohort"] == "general" for e in result["entries"] if e["status"] == "eligible")
    assert all(e["damage_id"] in {"D2-01", "D2-02", "D2-03"}
               for e in result["entries"] if e["status"] == "eligible")


def test_matrix_import_bom_and_reordered_columns(tmp_path, matrix):
    row = matrix["rows"][0]
    source = {"Damage type": row["damage_type"], "Content type": row["content_type"],
              "Content ID": row["content_id"], "Damage ID": row["damage_id"], "Visual class": row["visual_class"]}
    for s, level in row["levels"].items():
        source.update({f"{s} decision": level["decision"], f"{s} severity note": level["note"],
                       f"{s} example (Fragmentarium)": level["example_url"]})
    path = tmp_path / "matrix.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, list(source))
        writer.writeheader()
        writer.writerow(source)
    result = import_matrix(path)
    assert result["rows"][0]["levels"] == row["levels"]
    assert result["source"]["sha256"] == sha256(path.read_bytes()).hexdigest()
    with path.open("a", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, list(source)).writerow(source)
    with pytest.raises(ValueError, match="duplicate_matrix_key"):
        import_matrix(path)


@pytest.mark.parametrize("family", ["internal_hole", "edge_loss", "edge_tear"])
@pytest.mark.parametrize("severity", ["S2", "S3", "S4"])
def test_content_calibration_and_topology_are_deterministic(family, severity):
    target = Image.new("L", (192, 256))
    ImageDraw.Draw(target).rectangle((28, 30, 163, 224), fill=255)
    damage, stats = content_damage(target.size, target, family, AREA_PROXIES[severity], "a" * 64)
    again, repeated = content_damage(target.size, target, family, AREA_PROXIES[severity], "a" * 64)
    assert damage.tobytes() == again.tobytes() and stats == repeated
    assert stats["topology"]["passed"]
    assert abs(stats["measured_target_loss"] - AREA_PROXIES[severity]) <= stats["rounding_tolerance"] + 1e-12
    assert not stats["semantic_severity_validated"]


def test_target_area_is_not_page_area():
    target = Image.new("L", (128, 128))
    ImageDraw.Draw(target).rectangle((64, 48, 112, 80), fill=255)
    _, stats = content_damage(target.size, target, "internal_hole", .35, "b" * 64)
    assert abs(stats["measured_target_loss"] - .35) < .001
    assert abs(stats["measured_page_loss"] - .35) > .10


def test_generation_preserves_pixels_provenance_and_mtimes(tmp_path, matrix):
    base = tmp_path / "input"
    config = make_demo(base)
    original = (base / "page.png").read_bytes()
    output = tmp_path / "dataset"
    result = generate_dataset(matrix, config, base, output)
    assert result["generated_count"] == 9 and not result["training_performed"]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in output.rglob("*") if p.is_file()}
    repeated = generate_dataset(matrix, config, base, output)
    assert result == repeated
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in output.rglob("*") if p.is_file()}
    assert (base / "page.png").read_bytes() == original
    with Image.open(base / "page.png") as image:
        source = np.asarray(image.convert("RGBA"))
    for task in result["tasks"]:
        with Image.open(output / task["observed_image"]) as image:
            generated = np.asarray(image)
        with Image.open(output / task["observed_mask"]) as image:
            survives = np.asarray(image) > 0
        assert np.array_equal(source[survives], generated[survives])
        assert np.all(generated[~survives, 3] == 0)
        record = json.loads((output / task["target_record"]).read_text())
        assert record["content_basis"] == "synthetic_fixture"
        assert record["source_sha256"] == sha256(original).hexdigest()
        assert not list((output / task["task_id"] / "observed").glob("*.json"))
    changed = deepcopy(config)
    changed["seed"] = 99
    with pytest.raises(ValueError, match="refusing_to_overwrite"):
        generate_dataset(matrix, changed, base, output)


def test_no_generation_for_excluded_unimplemented_or_missing_combinations(tmp_path, matrix):
    config = make_demo(tmp_path / "input")
    config.update(damage_ids=["D2-01", "D2-09"], severities=["S1", "S2"])
    result = generate_dataset(matrix, config, tmp_path / "input", tmp_path / "out")
    assert result["generated_count"] == 1
    assert result["skip_counts"] == {"do_not_generate": 1, "operator_not_implemented": 2}


def test_edge_cases_require_opt_in(tmp_path, matrix):
    config = make_demo(tmp_path / "input")
    config["pages"][0]["content_id"] = "CT-03"
    config.update(damage_ids=["D2-01"], severities=["S2"])
    result = generate_dataset(matrix, config, tmp_path / "input", tmp_path / "out")
    assert result["skip_counts"] == {"edge_case_opt_in_required": 1}
    enabled = generate_dataset(matrix, config, tmp_path / "input", tmp_path / "edge", include_edge_cases=True)
    assert enabled["generated_count"] == 1 and enabled["tasks"][0]["cohort"] == "edge_case"


def test_manuscript_and_duplicate_image_split_leakage(tmp_path):
    config = make_demo(tmp_path)
    second = dict(config["pages"][0], page_id="second", split="validation")
    config["pages"].append(second)
    with pytest.raises(ValueError, match="manuscript_split_leakage"):
        validate_sources(config, tmp_path)
    second["manuscript_id"] = "different"
    with pytest.raises(ValueError, match="duplicate_image_split_leakage"):
        validate_sources(config, tmp_path)


def test_test_split_is_excluded_without_opening_files_and_checksum_is_checked(tmp_path, matrix):
    config = make_demo(tmp_path / "input")
    test = dict(config["pages"][0], page_id="test", manuscript_id="held-out", split="test",
                source_image="missing.png", content_mask="missing-mask.png", source_sha256="a" * 64)
    config["pages"].append(test)
    result = generate_dataset(matrix, config, tmp_path / "input", tmp_path / "out")
    assert result["skip_counts"] == {"test_split_frozen": 1}
    test["source_sha256"] = sha256((tmp_path / "input/page.png").read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="duplicate_image_split_leakage"):
        validate_sources(config, tmp_path / "input")


def test_registry_prevents_reassignment_of_known_test_source(tmp_path):
    config = make_demo(tmp_path)
    config["split_registry"] = [{"manuscript_id": "held-out", "split": "test",
                                  "source_sha256": sha256((tmp_path / "page.png").read_bytes()).hexdigest()}]
    with pytest.raises(ValueError, match="duplicate_image_split_leakage"):
        validate_sources(config, tmp_path)


def test_bad_mask_and_missing_model_provenance_rejected(tmp_path):
    config = make_demo(tmp_path)
    config["pages"][0]["content_basis"] = "model_derived"
    with pytest.raises(ValueError, match="segmentation_provenance"):
        validate_sources(config, tmp_path)
    config["pages"][0]["segmentation_provenance"] = {"model": "fixture"}
    Image.new("L", (10, 10), 100).save(tmp_path / "content.png")
    with pytest.raises(ValueError, match="dimension mismatch"):
        validate_sources(config, tmp_path)


def test_immutable_metadata_does_not_replace_existing_content(tmp_path):
    path = tmp_path / "record.json"
    write_json(path, {"seed": 1})
    with pytest.raises(ValueError, match="refusing_to_overwrite"):
        write_json(path, {"seed": 2})
