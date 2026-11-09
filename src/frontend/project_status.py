"""Assemble the committed evidence used by the project-status dashboard.

The dashboard is intentionally metadata-first. It reads the compact, versioned
records committed to the repository and does not require the ignored image
corpus, model checkpoints, generated artifacts, or a running PostgreSQL service.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

import yaml

from src.evaluation.damage_matrix import OPERATORS, plan


ROOT = Path(__file__).resolve().parents[2]
STATUS_AS_OF = "2026-11-09"


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _read_yaml(root: Path, relative: str) -> dict[str, Any]:
    return yaml.safe_load((root / relative).read_text(encoding="utf-8"))


def _schema_tables(root: Path) -> list[str]:
    pattern = re.compile(r"CREATE TABLE IF NOT EXISTS\s+([a-z_]+)", re.IGNORECASE)
    tables: set[str] = set()
    for migration in sorted((root / "infra/db/migrations").glob("*.sql")):
        tables.update(pattern.findall(migration.read_text(encoding="utf-8")))
    return sorted(tables)


def _implementation_ledger() -> list[dict[str, Any]]:
    return [
        {
            "name": "Repository and reproducibility foundation",
            "status": "implemented",
            "what": (
                "The repository has a documented structure, environment-driven configuration, an ignore policy for "
                "large or restricted artifacts, correctness linting, unit tests, and a workspace presence check."
            ),
            "evidence": ["README.md", "AGENTS.md", "pyproject.toml", "scripts/check_workspace.sh"],
            "boundary": "A clean clone contains code and compact records, not the external image corpus or model weights.",
        },
        {
            "name": "PostgreSQL/PostGIS data model",
            "status": "implemented",
            "what": (
                "Versioned migrations define source, manuscript, canvas, image, fragment, annotation, segmentation, "
                "synthetic-task, controlled-vocabulary, and spatial-geometry records. Binary images remain on disk."
            ),
            "evidence": ["infra/db/migrations/001_init.sql", "infra/db/migrations/002_hsp_normdata_metadata_alignment.sql"],
            "boundary": "Six future-facing tables are schema groundwork; they do not prove retrieval or reconstruction exists.",
        },
        {
            "name": "IIIF v2/v3 ingestion and provenance",
            "status": "implemented",
            "what": (
                "Local or remote IIIF manifests are normalized and registered idempotently with stable repository, "
                "manuscript, canvas, image-service, URL, checksum, raw-metadata, and rights fields."
            ),
            "evidence": ["src/ingestion/iiif_normalizer.py", "src/ingestion/iiif_ingest.py", "tests/ingestion/"],
            "boundary": "Harvested rights text is evidence; human training authorization remains a separate decision.",
        },
        {
            "name": "HSP metadata and controlled vocabularies",
            "status": "implemented",
            "what": (
                "HSP/German normdata terms and field mappings are extracted into controlled vocabularies and linked "
                "without replacing the raw source metadata."
            ),
            "evidence": ["data/metadata/hsp_normdata_terms.yaml", "docs/12_metadata_standards_alignment.md"],
            "boundary": "CoMMA remains possible text/metadata support, not a visual training dataset.",
        },
        {
            "name": "Initial local sample registration",
            "status": "implemented",
            "what": (
                "The five-fragment local sample was inventoried and registered with source identifiers, local paths, "
                "rights fields, checksums, and complete-page versus fragment roles."
            ),
            "evidence": ["data/metadata/initial_sample_dataset_resolved.yaml", "docs/04_initial_sample_dataset_report.md"],
            "boundary": "The underlying images remain ignored and retain their original source rights.",
        },
        {
            "name": "Mergen model registry and compatibility",
            "status": "implemented",
            "what": (
                "The eManuSkript/Mergen source, three external checkpoints, expected filenames, framework compatibility, "
                "and verified SHA-256 values are recorded without committing model binaries."
            ),
            "evidence": ["models/model_registry.yaml", "docs/06_model_weights_compatibility_report.md"],
            "boundary": "The current work runs registered checkpoints; it has not fine-tuned a new layout model.",
        },
        {
            "name": "Layout segmentation and masks",
            "status": "implemented",
            "what": (
                "Isolated runners execute Mergen on smoke, pilot, validation, and Batch 01 pages; detections and masks "
                "are restored to source-page coordinates with model, parameter, confidence, and checksum provenance."
            ),
            "evidence": ["scripts/run_segmentation_pilot.py", "data/metadata/training_corpus_expansion_batch_01_segmentation_statistics.yaml"],
            "boundary": "Mergen labels and masks are model-derived layout evidence, not expert ground truth.",
        },
        {
            "name": "Segmentation storage and local inspection",
            "status": "implemented",
            "what": (
                "Segmentation runs and layout-region geometry are stored in PostgreSQL/PostGIS while images, masks, "
                "overlays, and predictions stay as filesystem artifacts. A read-only Streamlit viewer inspects runs."
            ),
            "evidence": ["scripts/store_segmentation_outputs.py", "scripts/view_segmentation_results.py"],
            "boundary": "This is a technical inspection tool, not an expert reconstruction-review interface.",
        },
        {
            "name": "Versioned e-codices training corpus",
            "status": "implemented",
            "what": (
                "Specifications retain selected, rejected, and replacement candidates; acquisition is resumable and "
                "checksum-aware; splits are assigned by manuscript to prevent page leakage."
            ),
            "evidence": ["src/ingestion/training_corpus.py", "docs/17_training_corpus_expansion_batch_01.md"],
            "boundary": "All current corpus assets remain pending rights review with training_allowed set to false.",
        },
        {
            "name": "Artificial-fragment pilot v0.1.1",
            "status": "implemented",
            "what": (
                "Twenty-three deterministic tasks test controlled loss on the initial sample, keep the clean source and "
                "damage masks separate, and register compact task provenance without storing binaries in PostgreSQL."
            ),
            "evidence": ["data/metadata/artificial_fragment_generation_results.yaml", "docs/13_artificial_fragment_generator_report.md"],
            "boundary": "Synthetic loss is experiment ground truth, not evidence of the manuscript's historical damage.",
        },
        {
            "name": "Segmentation-aware evaluation v0.2",
            "status": "implemented",
            "what": (
                "The first validation-only experiment generated 44 tasks on 11 then-available pages and measured 604 "
                "region-survival observations while freezing the test split and historical artifacts."
            ),
            "evidence": ["docs/19_artificial_fragment_experiment_v02.md", "data/metadata/artificial_fragment_v02_validation.json"],
            "boundary": "Region survival is a technical comparator, not semantic recoverability.",
        },
        {
            "name": "Structured damage evaluation v0.3",
            "status": "implemented",
            "what": (
                "Six calibrated material-loss families produced 156 tasks and 2,424 observations on all 13 validation "
                "pages, with topology, determinism, database, rights, and frozen-artifact invariants."
            ),
            "evidence": ["docs/20_artificial_fragment_experiment_v03.md", "data/metadata/artificial_fragment_v03_determinism.json"],
            "boundary": "The experiment tests controlled transformations; it neither trains nor reconstructs a manuscript.",
        },
        {
            "name": "Jeremy matrix-driven synthetic data",
            "status": "partial",
            "what": (
                "All 187 matrix rows and 17 damage types are preserved. Three content-mask-calibrated material-loss "
                "operators generate paired observed/target artifacts; exclusions and edge-case cohorts remain explicit."
            ),
            "evidence": ["data/metadata/jeremy_damage_matrix_v3.json", "src/evaluation/matrix_synthesis.py", "docs/SYNTHETIC_DATA_WORKFLOW.md"],
            "boundary": "Fourteen operators and specialist validation of the S1-S4 severity semantics are still pending.",
        },
        {
            "name": "Research documentation and onboarding",
            "status": "implemented",
            "what": (
                "Current architecture, historical architecture, experiment reports, collaborator quickstart, project "
                "study report, and notebook-style study guide are kept as separate evidence layers."
            ),
            "evidence": ["docs/ARCHITECTURE.md", "docs/COLLABORATOR_QUICKSTART.md", "output/pdf/Fragment_Autocomplete_Project_Study_Guide.pdf"],
            "boundary": "Historical planning documents are not silently relabelled as current implementation.",
        },
    ]


def _next_steps() -> list[dict[str, str]]:
    return [
        {
            "priority": "1",
            "title": "Review the matrix pilot with Jeremy",
            "kind": "decision gate",
            "detail": (
                "Confirm the Mergen-label-to-content mapping, inspect shapes, resolve rows 187/188 in a new matrix "
                "revision, and agree how qualitative S1-S4 language relates to the engineering area presets."
            ),
        },
        {
            "priority": "2",
            "title": "Implement one appearance operator",
            "kind": "next engineering step",
            "detail": (
                "Add staining or fading with a visibility-mask contract and tests. Do not imitate it with a hole, because "
                "obscured/degraded content has different supervision semantics from absent material."
            ),
        },
        {
            "priority": "3",
            "title": "Approve a training subset before scaling",
            "kind": "rights and quality gate",
            "detail": (
                "Human-review source rights, the four flagged Batch 01 pages, and measured class/provider gaps; preserve "
                "manuscript-level splits and keep test data frozen."
            ),
        },
        {
            "priority": "4",
            "title": "Build retrieval and same-manuscript search",
            "kind": "future milestone",
            "detail": (
                "Retrieve comparable layouts/pages first and evaluate ranking quality. This evidence layer should precede "
                "any model that proposes missing structure or pixels."
            ),
        },
        {
            "priority": "5",
            "title": "Add candidate reconstruction and expert review",
            "kind": "future milestone",
            "detail": (
                "Present multiple candidate scholarly hypotheses with comparators, uncertainty, and provenance; never "
                "collapse uncertain alternatives into a recovered historical truth."
            ),
        },
        {
            "priority": "6",
            "title": "Integrate with Fragmentarium",
            "kind": "deployment milestone",
            "detail": (
                "Agree the API, identity, rights, review, export, retention, and operations boundary with Bill Duba and "
                "the Fragmentarium team before production deployment."
            ),
        },
    ]


def load_project_snapshot(root: Path | str = ROOT) -> dict[str, Any]:
    """Load a coherent, testable status snapshot from committed project records."""
    root = Path(root)
    matrix = _read_json(root, "data/metadata/jeremy_damage_matrix_v3.json")
    matrix_plan = plan(matrix)
    matrix_plan_with_edges = plan(matrix, include_edge_cases=True)
    validation_seg = _read_yaml(root, "data/metadata/training_corpus_segmentation_statistics.yaml")
    batch_seg = _read_yaml(root, "data/metadata/training_corpus_expansion_batch_01_segmentation_statistics.yaml")
    corpus_audit = _read_json(root, "data/metadata/artificial_fragment_v03_corpus_audit.json")
    pilot = _read_yaml(root, "data/metadata/segmentation_pilot_results.yaml")
    v01 = _read_yaml(root, "data/metadata/artificial_fragment_generation_results.yaml")
    v02_spec = _read_json(root, "data/metadata/artificial_fragment_v02_specification.json")
    v02_validation = _read_json(root, "data/metadata/artificial_fragment_v02_validation.json")
    v03_spec = _read_json(root, "data/metadata/artificial_fragment_v03_specification.json")
    v03_validation = _read_json(root, "data/metadata/artificial_fragment_v03_validation.json")
    v03_determinism = _read_json(root, "data/metadata/artificial_fragment_v03_determinism.json")
    schema_tables = _schema_tables(root)

    label_counts: Counter[str] = Counter(validation_seg["label_distribution"])
    label_counts.update(batch_seg["detected_label_distribution"])
    implemented_operator_count = sum(1 for operator in OPERATORS.values() if operator[2])
    future_tables = {
        "reconstruction_job",
        "reconstruction_candidate",
        "retrieval_embedding",
        "text_witness_link",
        "evaluation_run",
        "export_bundle",
    }

    matrix_rows = []
    for row in matrix["rows"]:
        for severity, level in row["levels"].items():
            planned = next(
                entry
                for entry in matrix_plan["entries"]
                if entry["source_row"] == row["source_row"] and entry["severity"] == severity
            )
            matrix_rows.append(
                {
                    "source_row": row["source_row"],
                    "content_id": row["content_id"] or "—",
                    "content_type": row["content_type"] or "—",
                    "damage_id": row["damage_id"] or "—",
                    "damage_type": row["damage_type"] or "—",
                    "visual_class": row["visual_class"] or "—",
                    "severity": severity,
                    "decision": level["decision"] or "missing",
                    "generation_status": planned["status"],
                    "note": level["note"] or "—",
                }
            )

    operators = [
        {
            "damage_id": damage_id,
            "damage_type": definition[0],
            "visual_class": definition[1],
            "operator": definition[2] or "—",
            "status": "implemented" if definition[2] else "not implemented",
        }
        for damage_id, definition in OPERATORS.items()
    ]

    segmentation_runs = [
        {
            "scope": "Initial local pilot",
            "pages_or_results": len(pilot["results"]),
            "regions_or_masks": pilot["mask_artifact_count"],
            "status": "stored",
            "note": "10 page/fragment results across five selected full-page samples",
        },
        {
            "scope": "e-codices validation set",
            "pages_or_results": validation_seg["successful_pages"],
            "regions_or_masks": validation_seg["total_detected_regions"],
            "status": "passed",
            "note": "15 of 15 pages segmented; 0 failed",
        },
        {
            "scope": "e-codices Batch 01",
            "pages_or_results": batch_seg["successful_pages"],
            "regions_or_masks": batch_seg["total_detected_regions"],
            "status": "passed",
            "note": "70 of 70 pages processed; three zero-detection pages retained",
        },
    ]

    experiments = [
        {
            "version": "v0.1.1",
            "title": "Controlled pilot",
            "tasks": v01["generated_task_count"],
            "observations": "—",
            "pages": v01["source_full_page_count"],
            "finding": "Deterministic source/mask separation and database registration proved the experiment loop.",
        },
        {
            "version": "v0.2",
            "title": "Segmentation-aware validation",
            "tasks": v02_spec["matrix_task_count"],
            "observations": v02_validation["region_measurement_count"],
            "pages": v02_validation["validation_pages"],
            "finding": "All then-available validation sources were used; unavailable pages were rejected, never substituted.",
        },
        {
            "version": "v0.3",
            "title": "Structured material loss",
            "tasks": v03_spec["matrix_task_count"],
            "observations": v03_validation["region_measurement_count"],
            "pages": v03_validation["selected_validation_pages"],
            "finding": "Six mask families passed topology and reproducibility checks across the full validation split.",
        },
        {
            "version": "matrix v1",
            "title": "Jeremy's decision matrix",
            "tasks": 9,
            "observations": "pilot samples",
            "pages": 1,
            "finding": "Three of 17 operators run; the remaining operator gap is explicit rather than simulated away.",
        },
    ]

    schema = [
        {
            "table": table,
            "status": "schema groundwork" if table in future_tables else "implemented storage",
        }
        for table in schema_tables
    ]

    pipeline = [
        {"name": "Source + provenance", "status": "implemented", "detail": "IIIF/local sources, checksums, rights"},
        {"name": "Database storage", "status": "implemented", "detail": "PostGIS metadata and geometry"},
        {"name": "Mergen segmentation", "status": "implemented", "detail": "85 pages, 4,230 masks"},
        {"name": "Synthetic damage", "status": "partial", "detail": "3 of 17 matrix operators"},
        {"name": "Bounded evaluation", "status": "implemented", "detail": "v0.1.1-v0.3 invariants"},
        {"name": "Retrieval", "status": "not built", "detail": "same-manuscript search"},
        {"name": "Candidate reconstruction", "status": "not built", "detail": "multiple hypotheses"},
        {"name": "Expert review + deploy", "status": "not built", "detail": "Fragmentarium integration"},
    ]

    return {
        "as_of": STATUS_AS_OF,
        "headline": (
            "The ingestion, storage, layout analysis, and controlled-experiment foundation is real; "
            "retrieval and candidate reconstruction are still future milestones."
        ),
        "corpus": {
            "pages": corpus_audit["structure"]["total_pages"],
            "page_bearing_manuscripts": corpus_audit["structure"]["page_bearing_manuscripts"],
            "splits": corpus_audit["structure"]["pages_per_split"],
            "layout_regions": corpus_audit["segmentation"]["total_layout_regions"],
            "valid_masks": corpus_audit["segmentation"]["valid_mask_count"],
            "zero_detection_pages": len(corpus_audit["segmentation"]["zero_region_pages"]),
            "rights_state": "pending_review",
            "training_allowed": False,
        },
        "matrix": {
            **matrix["summary"],
            "implemented_operators": implemented_operator_count,
            "unimplemented_operators": len(OPERATORS) - implemented_operator_count,
            "plan_counts": matrix_plan["counts"],
            "plan_counts_with_edges": matrix_plan_with_edges["counts"],
            "rows": matrix_rows,
            "operators": operators,
        },
        "segmentation": {
            "model": validation_seg["model_id"],
            "model_sha256": validation_seg["model_sha256"],
            "runs": segmentation_runs,
            "labels": [
                {"label": label, "count": count}
                for label, count in label_counts.most_common()
            ],
            "successful_pages": validation_seg["successful_pages"] + batch_seg["successful_pages"],
            "failed_pages": validation_seg["failed_pages"] + batch_seg["failed_pages"],
        },
        "database": {
            "table_count": len(schema_tables),
            "implemented_table_count": len(schema_tables) - len(future_tables),
            "future_table_count": len(future_tables),
            "tables": schema,
            "binary_policy": "Images, masks, checkpoints and generated batches stay outside PostgreSQL and Git.",
        },
        "experiments": experiments,
        "determinism": {
            "compared_artifacts": v03_determinism["compared_artifact_count"],
            "frozen_files": v03_validation["frozen_file_count"],
            "byte_identical": v03_determinism["byte_identical_artifacts_and_unchanged_file_mtimes"],
        },
        "pipeline": pipeline,
        "ledger": _implementation_ledger(),
        "next_steps": _next_steps(),
    }


def exportable_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a compact status export without the 748-row matrix view."""
    matrix = {key: value for key, value in snapshot["matrix"].items() if key not in {"rows"}}
    return {
        "as_of": snapshot["as_of"],
        "headline": snapshot["headline"],
        "corpus": snapshot["corpus"],
        "matrix": matrix,
        "segmentation": snapshot["segmentation"],
        "database": snapshot["database"],
        "experiments": snapshot["experiments"],
        "determinism": snapshot["determinism"],
        "pipeline": snapshot["pipeline"],
        "ledger": snapshot["ledger"],
        "next_steps": snapshot["next_steps"],
    }
