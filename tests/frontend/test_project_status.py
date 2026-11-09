from pathlib import Path

from src.frontend.project_status import exportable_snapshot, load_project_snapshot


ROOT = Path(__file__).resolve().parents[2]


def test_snapshot_matches_committed_corpus_and_matrix_evidence():
    snapshot = load_project_snapshot(ROOT)

    assert snapshot["corpus"]["pages"] == 85
    assert snapshot["corpus"]["valid_masks"] == 4230
    assert snapshot["corpus"]["splits"] == {"train": 59, "validation": 13, "test": 13}
    assert snapshot["corpus"]["training_allowed"] is False

    matrix = snapshot["matrix"]
    assert matrix["row_count"] == 187
    assert matrix["named_damage_types"] == 17
    assert matrix["content_types"] == 15
    assert matrix["implemented_operators"] == 3
    assert matrix["unimplemented_operators"] == 14
    assert len(matrix["rows"]) == 187 * 4
    assert sum(matrix["plan_counts"].values()) == 187 * 4


def test_snapshot_distinguishes_operational_and_future_schema():
    snapshot = load_project_snapshot(ROOT)
    tables = {row["table"]: row["status"] for row in snapshot["database"]["tables"]}

    assert snapshot["database"]["table_count"] == 22
    assert snapshot["database"]["implemented_table_count"] == 16
    assert snapshot["database"]["future_table_count"] == 6
    assert tables["segmentation_run"] == "implemented storage"
    assert tables["layout_region"] == "implemented storage"
    assert tables["reconstruction_candidate"] == "schema groundwork"
    assert tables["retrieval_embedding"] == "schema groundwork"


def test_snapshot_preserves_pipeline_and_claim_boundaries():
    snapshot = load_project_snapshot(ROOT)
    stages = {stage["name"]: stage["status"] for stage in snapshot["pipeline"]}

    assert stages["Mergen segmentation"] == "implemented"
    assert stages["Synthetic damage"] == "partial"
    assert stages["Retrieval"] == "not built"
    assert stages["Candidate reconstruction"] == "not built"
    assert any("not fine-tuned" in item["boundary"] for item in snapshot["ledger"])
    assert any("hypotheses" in step["detail"] for step in snapshot["next_steps"])


def test_status_export_omits_only_the_large_matrix_explorer():
    snapshot = load_project_snapshot(ROOT)
    exported = exportable_snapshot(snapshot)

    assert "rows" not in exported["matrix"]
    assert len(exported["matrix"]["operators"]) == 17
    assert exported["corpus"] == snapshot["corpus"]
    assert exported["ledger"] == snapshot["ledger"]
