# Collaborator Quickstart

## What this project does

Fragment Autocomplete tests layout-first methods for supporting manuscript-fragment reconstruction research. Surviving image pixels are evidence. Mergen/eManuSkript-derived layout regions supply model evidence, and artificial damage applied to known complete pages supplies controlled ground truth for evaluation. The repository does not currently reconstruct missing content.

## What works today

- IIIF Presentation API v2/v3 parsing and normalized registration.
- Provenance- and rights-aware corpus selection/acquisition.
- Mergen/Ultralytics segmentation with source-sized masks.
- PostgreSQL/PostGIS storage for sources, geometry, segmentation runs, and artificial-fragment tasks.
- A local read-only segmentation viewer.
- Deterministic synthetic-fragment experiments, task registration, measurements, and audit checks.

Reconstruction candidates, ranking, review exchange, external-tool exports, MPO ingestion, and CODICUM/Manuscript Workbench integration are proposals only.

## Ten-minute local check

Use Python 3.11. The test and lint checks do not require Docker, images, or model weights.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check src scripts tests
bash scripts/check_workspace.sh
```

Then parse an included IIIF fixture without database writes:

```bash
python scripts/ingest_iiif_manifest.py \
  --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json \
  --repository "Fixture Repository" \
  --dry-run
```

Database, segmentation, and full experiment runs need additional local state. Copy `.env.example`, choose a local database password, and read the relevant numbered milestone document before running those workflows. Mergen source is at <https://github.com/emanuskript/Mergen>; obtain the three external checkpoints from the [GWDG Mergen Weights directory](https://owncloud.gwdg.de/index.php/apps/files/?dir=/Mergen%20Weights&fileid=4279218283) and verify them against `models/model_registry.yaml`.

## Main data flow

```text
External IIIF/local references
        |
        v
IIIF normalization + corpus selection
        |
        +------> PostgreSQL/PostGIS metadata, stable IDs, rights state
        |
        +------> ignored data/raw/ source files + committed checksums/specs
        |
        v
Mergen/eManuSkript segmentation runner
        |
        +------> ignored masks/predictions/overlays
        +------> segmentation_run + layout_region records
        |
        v
Corpus audit + deterministic artificial damage
        |
        +------> ignored generated images/masks/task files
        +------> committed compact experiment/audit metadata
        +------> artificial_fragment_task records
        |
        v
Layout-survival measurements and scholarly review inputs

[future] retrieval -> multiple candidate proposals -> expert review -> export
```

## Architectural map

- `src/ingestion/`: IIIF client/normalizer/registrar and corpus builder.
- `src/evaluation/`: masks, artificial-fragment generation, task identity, audits, structured damage, and measurements.
- `scripts/`: command-line orchestration, validation, segmentation inference, storage, and viewer entry points.
- `infra/db/`: PostgreSQL/PostGIS schema and local service definition.
- `data/metadata/`: compact committed specifications, provenance, checksums, decisions, and run summaries.
- `outputs/` and `data/raw/`: ignored binary artifacts and downloaded sources.
- `tests/`: synthetic/local fixtures and regression tests for the implemented boundaries.

See [IMPLEMENTATION_STATUS_2026-10.md](IMPLEMENTATION_STATUS_2026-10.md) for the historical-plan/current-code comparison, [ARCHITECTURE.md](ARCHITECTURE.md) for the current component/data model, and [INTEGRATION_NOTES.md](INTEGRATION_NOTES.md) for proposed collaboration seams. The May 2026 Architecture Draft v0.2 is a historical plan rather than a current implementation claim.

## Important limitations

- A bare clone cannot reproduce segmentation or binary experiment outputs because source images, checkpoints, masks, and local database state are deliberately excluded.
- Current corpus image sources are e-codices-based; the pilot fragment metadata references Fragmentarium.
- All acquired corpus sources remain `rights_review_status: pending_review` and `training_allowed: false`.
- Segmentation labels and masks are model outputs, not manual scholarly annotations.
- Synthetic damage measures pixel/layout survival, not semantic recoverability or historical likelihood.
- The repository has no software licence yet; access alone does not grant reuse rights.

## Where an external integration could attach

The cleanest boundaries are:

1. IIIF manifest/canvas ingestion in `src/ingestion/` using stable source identifiers.
2. PostgreSQL source, canvas, image, segmentation, and provenance records.
3. A future candidate-ranking service that consumes layout evidence without modifying source pixels.
4. A future proposal exchange payload with candidates, confidence/uncertainty, evidence, provenance, rights, and review status.
5. A future export adapter for scholarly tools.

These are integration directions, not claims of existing CODICUM or Manuscript Workbench compatibility.
