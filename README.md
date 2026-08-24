# Fragment Autocomplete: Virtual Reconstruction of Medieval Manuscripts using Machine Learning

Fragment Autocomplete is a two-year Pro*Niedersachsen research software project hosted at the Institute for Digital Humanities, University of Göttingen. The project aims to build an open-source and open-access AI-based toolchain that helps scholars generate and evaluate candidate page-level reconstruction hypotheses from surviving medieval manuscript fragments.

The system must preserve the distinction between observed evidence and inference. Reconstruction outputs are candidate scholarly hypotheses with uncertainty, provenance, and comparators; they are not claims that the original manuscript page, text, or decoration has been recovered.

## Technical Strategy

The project follows a layout-first MVP strategy. Early work should estimate page canvas, margins, columns, semantic layout zones, and plausible fragment placement before any experimental full-image generation is considered.

eManuSkript / "Manuskripte digital lesen lernen" is the central technical backbone. Its manuscript layout-analysis model, with roughly 21 manuscript layout labels, should later support segmentation, pseudo-labeling, layout priors, retrieval keys, UI overlays, evaluation signals, and optional conditioning maps.

CoMMA is a text, transcription, and metadata resource. It can support text search, metadata enrichment, witness discovery, and IIIF manifest discovery, but it is not the core visual reconstruction dataset.

## Current Status

This repository currently contains project documentation, PostgreSQL/PostGIS migrations, IIIF ingestion code, provenance-preserving training-source corpus construction, local dataset metadata registration, controlled segmentation runs, segmentation storage, a minimal local segmentation viewer, and deterministic artificial-fragment generation with source-space ground truth. It does not implement reconstruction, retrieval, model training, MSI workflows, CoMMA ingestion, production backend/frontend deployment, or a final scholarly interface.

## Repository Structure

```text
.
|-- AGENTS.md
|-- CHANGELOG.md
|-- NEXT_ACTIONS.md
|-- PROJECT_BOARD.md
|-- README.md
|-- ROADMAP_STATUS.md
|-- data/
|-- docs/
|   |-- 01_architecture_overview.md
|   |-- architecture_build_notes.md
|   `-- figures/architecture/
|-- models/
|-- outputs/
|-- scripts/
|-- src/
`-- tests/
```

Key directories:

- `docs/`: project planning, architecture, evaluation, data-source, and decision documents.
- `docs/figures/architecture/`: Mermaid figure sources and rendered SVG architecture diagrams.
- `src/`: future application code boundaries for backend, frontend, ingestion, ML, evaluation, and shared utilities.
- `data/`: raw, processed, and metadata asset structure. Large data is excluded from git.
- `models/`: model registry metadata. Model binaries are excluded from git.
- `outputs/`: generated reports and exports.
- `scripts/`: reproducible validation and document build scripts.

## Building the Architecture Document

Render the architecture figures:

```bash
bash scripts/render_architecture_figures.sh
```

Build the architecture PDF, or HTML fallback if PDF dependencies are unavailable:

```bash
bash scripts/build_architecture_pdf.sh
```

Validate the workspace:

```bash
bash scripts/check_workspace.sh
```

The expected output is:

```text
outputs/Fragment_Autocomplete_Architecture_Draft.pdf
```

If PDF generation is unavailable, the fallback output is:

```text
outputs/Fragment_Autocomplete_Architecture_Draft.html
```

## IIIF ingestion proof of concept

Install the minimal Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the local PostgreSQL/PostGIS database:

```bash
bash scripts/db_start.sh
```

Apply migrations and seed values:

```bash
bash scripts/db_migrate.sh
```

Ingest a local IIIF fixture:

```bash
python3 scripts/ingest_iiif_manifest.py \
  --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json \
  --repository "Fixture Repository"
```

Dry-run a manifest without database writes:

```bash
python3 scripts/ingest_iiif_manifest.py \
  --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json \
  --repository "Fixture Repository" \
  --dry-run
```

Validate the IIIF ingestion proof of concept:

```bash
bash scripts/validate_iiif_ingestion.sh
```

The ingestion proof of concept registers manifest, repository, manuscript, canvas, and image asset metadata. It does not download full-resolution image sets by default.

## HSP/German metadata standards alignment

Extract the HSP/German controlled vocabularies and metadata mapping from the local source files:

```bash
python3 scripts/extract_hsp_metadata_standards.py --verbose
```

Apply the database migration, then import the controlled vocabularies:

```bash
bash scripts/db_migrate.sh
python3 scripts/import_hsp_normdata.py --verbose
```

Validate the metadata alignment layer:

```bash
bash scripts/validate_hsp_metadata_alignment.sh
```

The alignment layer adds controlled vocabularies for `SCRP`, `FORM`, `CODC`, `BNDG`, and simplified HSP values. It also adds selected HSP-aligned metadata fields while keeping source metadata in `raw_metadata` for provenance.

## Local asset inventory

The local asset inventory expects these folders when available:

- `autocomplete-test-dataset/`
- `model weights/`

Run the inventory script:

```bash
python3 scripts/inventory_local_assets.py
```

The script writes:

- `data/metadata/local_assets_manifest.yaml`
- `docs/05_local_assets_inventory.md`
- `models/model_registry.yaml`

Do not commit local dataset images or model weights. These folders and common large model/data extensions are ignored by `.gitignore`; only inventory metadata should be committed.

## Initial sample dataset registration

Register the local pilot sample dataset:

```bash
python3 scripts/register_initial_sample_dataset.py --verbose
```

Dry-run registration without database writes:

```bash
python3 scripts/register_initial_sample_dataset.py --dry-run --verbose
```

Validate registered records:

```bash
bash scripts/validate_initial_sample_dataset.sh
```

This registers local metadata and database records for the pilot full pages and fragments. It does not run eManuSkript, load model weights, run segmentation, or download large image sets.

## Model weights compatibility inspection

Inspect the local `.pt` checkpoints without running inference:

```bash
python3 scripts/inspect_model_weights.py --verbose
```

The script writes:

- `data/metadata/model_weights_compatibility.yaml`
- `docs/06_model_weights_compatibility_report.md`
- `models/model_registry.yaml`

This inspection does not run inference or segmentation. It performs static archive inspection and safe CPU-side checkpoint checks only. Do not commit the model weights themselves.

## Controlled segmentation test inputs

Prepare the two controlled inputs for the first future smoke test:

```bash
python3 scripts/prepare_segmentation_test_inputs.py --verbose
```

Validate the prepared inputs:

```bash
bash scripts/validate_segmentation_test_inputs.sh
```

This step does not run segmentation, inference, or model loading. It only verifies local file paths, database links, and the selected model path.

## Segmentation smoke test

Run the controlled smoke test on the two prepared inputs:

```bash
python3 scripts/run_segmentation_smoke_test.py --device cpu --verbose
```

Validate the emitted results:

```bash
bash scripts/validate_segmentation_smoke_test.sh
```

Outputs are written under `outputs/segmentation_smoke_test/`, while the machine-readable summary and report are written to:

- `data/metadata/segmentation_smoke_test_results.yaml`
- `docs/08_segmentation_smoke_test_report.md`

## Segmentation output storage

Store the existing smoke-test outputs in PostgreSQL/PostGIS:

```bash
python3 scripts/store_segmentation_outputs.py --verbose
```

Validate the stored `segmentation_run` and `layout_region` records:

```bash
bash scripts/validate_segmentation_storage.sh
```

This step stores metadata and region geometry for the two smoke-test samples only. It does not rerun inference, and it does not build the local UI viewer.

## Minimal segmentation viewer

Start the local PostgreSQL/PostGIS database:

```bash
bash scripts/db_start.sh
```

Validate that the stored viewer data and local image paths are available:

```bash
python3 scripts/validate_segmentation_viewer_data.py
```

Run the local read-only viewer:

```bash
bash scripts/run_segmentation_viewer.sh
```

You can also run the combined viewer validation:

```bash
bash scripts/validate_segmentation_viewer.sh
```

This viewer is local-only and read-only. It displays already stored segmentation outputs from PostgreSQL/PostGIS and local files; it does not run inference, store new results, or build the final project UI.

## Full pilot segmentation run

Prepare the 10 pilot inputs from the registered initial sample dataset:

```bash
python3 scripts/prepare_segmentation_pilot_inputs.py --verbose
```

Validate the prepared pilot inputs:

```bash
bash scripts/validate_segmentation_pilot_inputs.sh
```

Run the full pilot segmentation on CPU:

```bash
python3 scripts/run_segmentation_pilot.py --device cpu --conf 0.25 --imgsz 320 --verbose
```

Store the pilot outputs in PostgreSQL/PostGIS:

```bash
python3 scripts/store_segmentation_pilot_outputs.py --verbose
```

Validate the pilot run and storage:

```bash
bash scripts/validate_segmentation_pilot_run.sh
bash scripts/validate_segmentation_pilot_storage.sh
python3 scripts/validate_segmentation_viewer_data.py
```

Run the local viewer manually:

```bash
bash scripts/run_segmentation_viewer.sh
```

Pilot segmentation outputs are stored in PostgreSQL/PostGIS and can be inspected in the local read-only viewer. Artificial-fragment generation consumes the five full-page outputs as a separate evaluation-groundwork step; reconstruction, retrieval, MSI workflows, and CoMMA ingestion remain later work.

## Artificial fragment generation

Generate the controlled 20-task pilot from the five registered full-page samples, plus three separate transformation sanity cases:

```bash
python3 scripts/generate_artificial_fragments.py --verbose
```

Validate the generated local outputs and metadata:

```bash
bash scripts/validate_artificial_fragments.sh
```

Generate one configured task:

```bash
python3 scripts/generate_artificial_fragments.py \
  --sample fp_01_clean_simple \
  --mask irregular \
  --severity 0.5 \
  --seed 42
```

The core pilot is five pages × rectangular/irregular masks × severity 0.30/0.60, with rotation 0 and scale 1. The separate sanity tasks cover positive rotation, negative rotation, and non-unit scale.

The generator writes local PNG fragments, source-coordinate survival/damage masks, observed-coordinate masks, and per-task JSON under `outputs/artificial_fragments/v0_1_1/`, plus the metadata manifest at `data/metadata/artificial_fragment_generation_results.yaml`. Generated binaries are local outputs and should not be committed. Metadata records source SHA-256, requested/measured severity, deterministic seeds, source provenance, contours, exact forward/inverse transforms, and known ground-truth placement.

Register the 20 core and three transformation-sanity tasks in PostgreSQL, then validate their identities, source relationships, and local artifact references:

```bash
python3 scripts/register_artificial_fragment_tasks.py --verbose
bash scripts/validate_artificial_fragment_task_registration.sh
```

Registration is idempotent. Scientific generation parameters produce a deterministic identity hash and UUIDv5 primary key; an unchanged rerun matches the same 23 rows without updating them. PostgreSQL stores paths, checksums, dimensions, transforms, provenance, and layout-survival JSON, never the generated image or mask bytes.

Current full-page layout survival values use the restored, source-sized eManuSkript instance masks (`geometry_method: segmentation_mask`). Bounding boxes remain recorded, and `rasterized_bbox_xyxy` is retained only as an explicit fallback for legacy runs without mask artifacts. Because the five pages were temporarily downscaled for inference, the masks are authoritative model outputs restored to source coordinates, not manual pixel-level annotations.

This step creates controlled evaluation tasks only. It does not train a model, run reconstruction, infer missing manuscript content, or claim that generated fragments are historical evidence.

## Training Corpus Builder v0.1

The validation specification identifies five e-codices manuscripts by official IIIF manifest and selects at most three complete pages per manuscript from a recorded seed:

```bash
python3 scripts/build_training_corpus.py --dry-run --limit-manuscripts 1 --max-pages 1
```

Apply the additive rights-review migration, acquire/register the 5 × 3 validation corpus, and validate it:

```bash
bash scripts/db_migrate.sh
python3 scripts/build_training_corpus.py --register --verbose
PYTHON_BIN=python3 bash scripts/validate_training_corpus.sh
```

The unchanged rerun is resumable: a local asset is reused only when its recorded SHA-256 still matches. Raw manifests and downloaded page binaries remain ignored under `data/raw/`; the committed specification, corpus manifest, statistics, and validation report preserve provenance and every candidate/selected/rejected decision. `training_allowed` remains false and `rights_review_status` remains `pending_review` until a separate explicit review.

Prepare the selected registered pages for the existing eManuSkript segmentation workflow without running inference:

```bash
python3 scripts/build_training_corpus.py --register --prepare-segmentation
```

Use `--run-segmentation` only for an explicitly intended later segmentation run. The corpus builder delegates to the existing runner and does not implement a second segmentation path.

## Next Task

Review validation-corpus decisions and storage/rights policy, then expand the manifest specification toward approximately 100 distinct manuscripts without beginning model training.
