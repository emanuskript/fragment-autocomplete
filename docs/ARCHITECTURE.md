# Architecture

## Scope

This document describes the architecture that exists in the repository now and marks proposed components explicitly. The fuller [Architecture Draft v0.2 (2026-05-06)](../outputs/Fragment_Autocomplete_Architecture_Draft_v0.2_2026-05-06.pdf) and its source, `docs/01_architecture_overview.md`, are historical design records; their diagrams include future-state elements that are not all implemented. The October 2026 comparison is in [IMPLEMENTATION_STATUS_2026-10.md](IMPLEMENTATION_STATUS_2026-10.md).

The governing boundary is evidence versus inference. Source pixels, source metadata, model-derived layout evidence, synthetic experiment ground truth, and future reconstruction hypotheses must remain distinguishable and traceable.

## Current component view

```text
                    +--------------------------+
IIIF/local refs --->| src/ingestion            |
                    | normalize, select, store |
                    +-------------+------------+
                                  |
                   +--------------+----------------+
                   |                               |
                   v                               v
         PostgreSQL/PostGIS                 data/raw/ (ignored)
         IDs, rights, JSONB,                manifests + images
         source geometry                           |
                   |                               |
                   +---------------+---------------+
                                   v
                    scripts/run_segmentation_*.py
                    isolated model inference
                                   |
                   +---------------+----------------+
                   |                                |
                   v                                v
     segmentation_run/layout_region       outputs/ (ignored)
     provenance + geometry                masks, JSON, overlays
                   |                                |
                   +---------------+----------------+
                                   v
                      src/evaluation + experiment CLIs
                      audits, synthetic damage, tasks,
                      layout survival, determinism
                                   |
                   +---------------+----------------+
                   |                                |
                   v                                v
       artificial_fragment_task           data/metadata/ (tracked)
       paths + JSON provenance             compact specs/results
```

There is no running backend service, job queue, production frontend, reconstruction engine, retrieval index, or external integration API.

## Major modules

### Ingestion

- `iiif_client.py` loads local or remote JSON.
- `iiif_manifest.py` defines normalized manifest/canvas/image structures.
- `iiif_normalizer.py` handles common IIIF Presentation v2/v3 shapes.
- `iiif_ingest.py` performs idempotent PostgreSQL registration and preserves reviewed training authorization during source refreshes.
- `training_corpus.py` validates corpus specifications, assigns manuscript-level splits, records all selection decisions, downloads selected representations resumably, verifies checksums, registers sources, and prepares segmentation inputs.
- `db.py` is the shared environment-driven connection boundary.

### Layout inference and storage

Model execution is isolated in `scripts/run_segmentation_smoke_test.py` and `scripts/run_segmentation_pilot.py`. The corpus orchestration reuses this runner rather than implementing a second inference path. The runner records model/checkpoint identity, inference parameters, source dimensions, detections, confidence values, and restored source-sized binary instance masks.

`scripts/store_segmentation_outputs.py` and `scripts/store_segmentation_pilot_outputs.py` translate run artifacts into `segmentation_run` and `layout_region` records. Generated mask/image bytes stay on the filesystem; PostgreSQL stores paths, geometry, structured metadata, and provenance.

### Evaluation and synthetic experiments

- `artificial_fragments.py` implements deterministic pilot masks/transforms and artifact generation.
- `structured_damage.py` implements the v0.3 structured damage families.
- `segmentation_masks.py` validates and restores binary masks in source coordinates.
- `layout_survival.py` measures retained model-derived layout evidence.
- `artificial_fragment_registration.py` defines deterministic task identity and storage records.
- `corpus_audit.py`, `experiment_database.py`, `artificial_fragment_experiment.py`, and `structured_fragment_experiment.py` implement audits, invariants, registration checks, and measurement aggregation.
- `scripts/artificial_fragment_experiment.py` exposes v0.2 and v0.3 experiment commands; `scripts/structured_fragment_workflow.py` contains the v0.3 orchestration behind that public CLI.

### Local inspection UI

`scripts/view_segmentation_results.py` is a read-only Streamlit view over stored local segmentation runs and filesystem images. It is not the planned scholarly reconstruction interface.

## Pipeline stages

1. Resolve a local manifest or URL and normalize IIIF source structures.
2. Register repository, manuscript, manifest, canvas, and image-asset metadata with stable upstream identifiers.
3. Select corpus pages from a versioned specification; retain selected, rejected, and replacement decisions.
4. Acquire selected images to ignored storage, verify SHA-256 values, and register conservative rights state.
5. Prepare an explicit input manifest for eManuSkript inference.
6. Run segmentation in the isolated runner; restore masks to source coordinates and record the complete run configuration.
7. Store run/region metadata and geometry in PostgreSQL while keeping binaries outside the database.
8. Audit corpus composition, source availability, rights, splits, masks, and database relationships.
9. Generate deterministic synthetic damage tasks from complete validation pages, retaining source-space ground truth separately from the observed fragment.
10. Register task metadata idempotently and compute layout-survival comparators.

Candidate reconstruction, retrieval, expert accept/reject workflows, and external export follow only as proposed later stages.

## Data model

The implemented database schema is defined by `infra/db/migrations/`.

Source/provenance entities:

- `repository`, `manuscript`, `witness`;
- `iiif_manifest_cache`, `canvas`, `image_asset`, `msi_asset`, `fragment`;
- HSP-alignment tables and fields: `controlled_vocabulary`, `controlled_term`, `metadata_controlled_term_assignment`, and `fragment_location`.

Analysis/evaluation entities:

- `annotation`;
- `segmentation_run`, `layout_region`;
- `artificial_fragment_task`.

Future-facing schema groundwork:

- `reconstruction_job`, `reconstruction_candidate`;
- `retrieval_embedding`, `text_witness_link`;
- `evaluation_run`, `export_bundle`.

The future-facing tables do not establish implemented reconstruction, retrieval, CoMMA, export, or review functionality.

## Experiment and task registration

Corpus configurations and experiment specifications are versioned files under `data/metadata/`. Artificial-fragment tasks derive identity from scientific inputs rather than timestamps. Registration checks source/database relationships and either inserts a new record or verifies an exact match; validated unchanged reruns must not create duplicates or update timestamps.

Experiment `v0.1.1` is the controlled pilot. `v0.2` is a validation-only segmentation-aware experiment over then-available sources. `v0.3` adds six calibrated structured damage families and exact-source restoration/auditing. Historical v0.2 availability conclusions remain part of that experiment's record rather than being rewritten after v0.3 restoration.

## Storage and generated artifacts

| Location | Role | Git policy |
| --- | --- | --- |
| `data/metadata/` | compact specifications, checksums, provenance, decisions, statistics, validation records | tracked JSON/YAML |
| `data/raw/` | downloaded IIIF manifests and page images | ignored except `.gitkeep` |
| `data/processed/` | reserved derivative area | ignored except `.gitkeep` |
| `outputs/` | masks, predictions, overlays, generated fragments, reports | ignored except `.gitkeep` and the architecture PDF |
| `model weights/` | local checkpoints | entirely ignored |
| PostgreSQL/PostGIS | normalized metadata, JSONB provenance, geometry, task/run state | local service; database files ignored |

Large images, masks, checkpoints, and bulk outputs are referenced by path and checksum rather than stored as database blobs or committed to Git.

## Provenance and rights

Raw upstream metadata is retained in JSONB alongside normalized fields. Stable manifest, canvas, image-service, and source URLs are retained where supplied. Files and generated artifacts use SHA-256 checksums. Inference/experiment records include model, version, configuration, seed, source identity, transforms, and output references.

Acquisition, publication, demonstration, and training authorization are distinct states. New corpus assets default to `rights_review_status: pending_review` and `training_allowed: false`. An open source licence does not automatically approve training. Ordinary IIIF refreshes may update harvested source-rights metadata but must preserve versioned human review decisions.

## Evidence boundaries

- Source RGB pixels are observed evidence.
- eManuSkript masks and labels are model-derived evidence.
- Synthetic damage masks and the hidden complete source are experiment ground truth only.
- Layout-survival scores are technical comparators, not semantic recovery or historical probability.
- Future candidates must retain multiple plausible alternatives, uncertainty, comparators, and provenance.

## Integration boundaries

Current stable attachment points are IIIF normalization, stable source/canvas identifiers, database source/segmentation records, filesystem artifacts plus checksums, and versioned task/audit metadata. Proposed candidate and review exchange is described in [INTEGRATION_NOTES.md](INTEGRATION_NOTES.md). No private endpoints or partner-specific assumptions are encoded.
