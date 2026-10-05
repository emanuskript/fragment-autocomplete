# Fragment Autocomplete

> **External-review notice:** This repository is currently shared for research evaluation and collaboration discussion. No software licence has yet been selected; reuse or redistribution permission should not be assumed.

## Overview

Fragment Autocomplete is a research codebase for testing how computer vision and machine-learning methods can support the study of damaged or fragmented manuscript pages. The current approach is layout- and morphology-first: surviving pixels are evidence, eManuSkript ("Manuskripte digital lesen lernen") provides the central layout-analysis backbone, and controlled synthetic damage makes evaluation possible when the undamaged source page is known.

The project does not treat generated content as recovered history. Any future reconstruction output must remain a candidate scholarly hypothesis with visible uncertainty, source provenance, and comparators. Observed pixels, model-derived evidence, synthetic ground truth, and inference are kept distinct.

CoMMA is treated as a possible text and metadata resource, not as the visual training dataset.

## Current status

Implemented and tested:

- IIIF Presentation API v2/v3 manifest normalization and PostgreSQL/PostGIS registration;
- conservative rights and provenance handling, including `rights_review_status` and `training_allowed`;
- deterministic e-codices corpus selection, acquisition, resume checks, manuscript-level splits, and registration;
- eManuSkript/Ultralytics segmentation runners, source-coordinate mask restoration, storage, and a local read-only Streamlit viewer;
- deterministic artificial-fragment generation with rectangular and irregular masks, known transforms, source-space survival/damage masks, and layout-survival measurements;
- structured synthetic-damage families and versioned experiments (`v0.1.1`, `v0.2`, and `v0.3`);
- idempotent artificial-fragment task registration;
- corpus, determinism, storage, rights, provenance, and experiment audit infrastructure;
- committed compact experiment specifications, provenance records, statistics, and validation results.

Not implemented:

- reconstruction or manuscript-content completion;
- candidate/proposal generation, ranking, acceptance/rejection APIs, or proposal exchange;
- retrieval or embedding services;
- model training or fine-tuning;
- CoMMA, MPO, Swedish National Archives, CODICUM, or Manuscript Workbench integration;
- MSI processing;
- a production backend, frontend, deployment, or public scholarly interface.

Database tables exist for several planned concepts, including reconstruction candidates, retrieval embeddings, evaluations, and exports. Their presence is schema groundwork, not an implemented workflow. See [ROADMAP_STATUS.md](ROADMAP_STATUS.md) for milestone evidence and [NEXT_ACTIONS.md](NEXT_ACTIONS.md) for the next bounded engineering decision.

## Repository structure

```text
.
├── data/
│   ├── metadata/        # committed compact specs, provenance, audits, and results
│   ├── raw/             # ignored downloaded source images/manifests
│   └── processed/       # reserved; ignored except .gitkeep
├── docs/                # architecture, quickstart, plans, and milestone reports
├── infra/db/            # Docker Compose, SQL migrations, and seed data
├── models/              # model registry metadata; no checkpoints
├── outputs/             # ignored generated artifacts; one architecture PDF is tracked
├── scripts/             # CLIs, validators, database helpers, and report builders
├── src/
│   ├── evaluation/      # damage generation, masks, audits, and experiment logic
│   └── ingestion/       # IIIF, database, and corpus logic
└── tests/               # unit and integration-oriented tests with local fixtures
```

The numbered documents in `docs/` are dated milestone records. Some describe the state and next action at the time they were generated; use this README, `docs/IMPLEMENTATION_STATUS_2026-10.md`, `docs/ARCHITECTURE.md`, `ROADMAP_STATUS.md`, and `NEXT_ACTIONS.md` for the current summary.

### Historical architecture draft

[Architecture Draft v0.2 (2026-05-06)](outputs/Fragment_Autocomplete_Architecture_Draft_v0.2_2026-05-06.pdf) and its Markdown source, [docs/01_architecture_overview.md](docs/01_architecture_overview.md), preserve the original planned architecture. They are historical design documents, not a statement that every illustrated subsystem is implemented. The PDF's historical contents have not been revised during the October 2026 preflight. See [docs/IMPLEMENTATION_STATUS_2026-10.md](docs/IMPLEMENTATION_STATUS_2026-10.md) for a subsystem-by-subsystem comparison with the current repository.

## Installation

Python 3.11 is recommended for a clean collaborator environment. The recorded segmentation environment used Python 3.9.6, Torch 2.7.1, Torchvision 0.22.1, and Ultralytics 8.4.51. Python 3.14 is not currently supported by the pinned inference stack.

```bash
git clone <repository-url>
cd Fragments
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

System requirements by workflow:

- Docker with Compose: PostgreSQL/PostGIS workflows;
- model checkpoints and source images: segmentation and full experiment reruns;
- Node.js/`npx` or Mermaid CLI: architecture figure rendering;
- Pandoc plus a PDF engine, or Node.js: architecture PDF rebuilding.

The model checkpoints are not distributed. Their expected filenames and checksums are documented in `models/model_registry.yaml`.

## Running the project

### Tests and lint

These commands work without the ignored image corpus or model checkpoints:

```bash
python -m pytest -q
python -m ruff check src scripts tests
bash scripts/check_workspace.sh
```

No project-wide static type checker or autoformatter is configured yet. `ruff` is intentionally limited to correctness-focused `F` rules so external-sharing cleanup does not reformat the scientific codebase.

### IIIF normalization

Parse the included IIIF v3 fixture without a database write:

```bash
python scripts/ingest_iiif_manifest.py \
  --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json \
  --repository "Fixture Repository" \
  --dry-run
```

### Database-backed workflows

Choose a local password and make it available both to Docker Compose and Python:

```bash
cp .env.example .env
# Edit .env, then export the same value in the current shell:
export FRAGMENT_DB_PASSWORD='your-local-value'
bash scripts/db_start.sh
bash scripts/db_migrate.sh
bash scripts/db_validate.sh
```

`.env` is ignored. No database password is committed.

### Corpus preparation

This bounded dry run reads the committed e-codices specification and writes only to ignored `tmp/` paths. It requires network access but does not download page binaries or register database rows:

```bash
python scripts/build_training_corpus.py \
  --dry-run \
  --limit-manuscripts 1 \
  --max-pages 1 \
  --manifest tmp/corpus_manifest.yaml \
  --statistics tmp/corpus_statistics.yaml \
  --report tmp/corpus_report.md
```

The full acquisition and registration validators require PostgreSQL and network access. See `docs/14_training_corpus_builder_report.md` and `docs/17_training_corpus_expansion_batch_01.md` before running them.

### Segmentation

Segmentation is implemented but cannot run from a bare clone because the source images and eManuSkript checkpoint are intentionally excluded. With registered local inputs and the checksum-matched checkpoint in place:

```bash
python scripts/run_segmentation_pilot.py \
  --device cpu \
  --conf 0.25 \
  --imgsz 320 \
  --verbose
```

Outputs are written below ignored `outputs/`; compact manifests are written below `data/metadata/`. See `docs/15_training_corpus_segmentation_integration.md` and `docs/18_training_corpus_expansion_batch_01_segmentation.md` for the larger validated runs.

### Artificial-fragment generation

With the five pilot pages, stored segmentation metadata, and mask artifacts present, generate one controlled task into ignored scratch paths:

```bash
python scripts/generate_artificial_fragments.py \
  --sample fp_01_clean_simple \
  --mask irregular \
  --severity 0.5 \
  --seed 42 \
  --output-dir tmp/artificial_fragments \
  --metadata tmp/artificial_fragment_result.yaml
```

The generator preserves the source image, emits explicit survival/damage masks, and records the transform and seed. Synthetic damage is controlled experimental ground truth, not evidence about historical loss.

### Experiments and evaluation

Inspect the available experiment commands with:

```bash
python scripts/artificial_fragment_experiment.py --help
python scripts/artificial_fragment_experiment.py v03 --help
```

Full `v0.2`/`v0.3` verification requires the ignored source images, segmentation masks, generated artifacts, and registered local database state identified by the committed checksums. A bare clone can run the unit tests and inspect the committed audit/measurement records, but it cannot honestly reproduce the binary experiment without those external artifacts.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `FRAGMENT_DB_HOST` | `localhost` | PostgreSQL host for Python clients |
| `FRAGMENT_DB_PORT` | `55432` | host port mapped to PostgreSQL 5432 |
| `FRAGMENT_DB_NAME` | `fragment` | database name |
| `FRAGMENT_DB_USER` | `fragment` | database user |
| `FRAGMENT_DB_PASSWORD` | none; required | local database password |
| `HSP_NORMDATA_WORKBOOK` | none | optional external HSP vocabulary workbook |
| `HSP_METADATA_MAPPING` | none | optional external HSP field-mapping Markdown |
| `PYTHON_BIN` | `python3` in shell validators | interpreter override for orchestration scripts |

Important committed configuration and registries:

- `data/metadata/training_corpus_validation_spec.yaml`;
- `data/metadata/training_corpus_expansion_batch_01_spec.yaml`;
- `data/metadata/training_corpus_expansion_batch_01_segmentation_spec.yaml`;
- `models/model_registry.yaml`;
- `infra/db/docker-compose.yml` and `infra/db/migrations/`;
- `pyproject.toml` for test discovery and the narrow lint gate.

## Data

The repository includes metadata and tiny synthetic IIIF fixtures, not a redistributable image corpus.

| Source/resource | Current use | Included in Git? | Rights/training state |
| --- | --- | --- | --- |
| e-codices | IIIF source metadata and the complete-page validation/Batch 01 corpus specifications | URLs, metadata, checksums, decisions, and compact results only | downloaded images are ignored; all current corpus assets remain `pending_review` and `training_allowed: false` |
| Fragmentarium | metadata references for the local five-fragment pilot | metadata only | local images are ignored; reuse/publication must follow source rights |
| eManuSkript | layout-analysis checkpoint and label backbone | registry metadata and derived compact results only | checkpoints are not distributed; model-derived masks are evidence, not manual ground truth |
| HSP/German normdata inputs | controlled vocabulary and field-alignment extraction | extracted terms/mapping plus input filenames and SHA-256 values | source workbook/Markdown are external and not distributed |
| CoMMA | possible future text/metadata support | no ingestion or dataset | not a visual training dataset |
| MPO / Swedish National Archives | possible future collaboration source/integration boundary | no MPO data or private endpoints | no compatibility or rights claim is made |

Do not redistribute ignored local images, IIIF downloads, model checkpoints, private datasets, MSI files, or generated bulk outputs merely because a local checkout contains them. Software licensing and each source image/dataset licence are separate questions.

## Reproducibility

- Seeds, source checksums, task identities, mask families, severities, transforms, model checksums, inference parameters, and software versions are recorded in the committed metadata for validated runs.
- Dataset splits are assigned by manuscript, not page.
- Corpus decisions retain selected, rejected, and replacement candidates with reasons.
- Acquisition and registration paths are checksum-aware and designed to be idempotent.
- Artificial-fragment tasks use deterministic identifiers; the v0.2/v0.3 records include frozen-invariant and byte-determinism audits.
- Large binaries stay outside Git. Reproducing binary results therefore also requires access to the exact checksum-matched external inputs listed in the metadata.

## Tests

Run the full suite with `python -m pytest -q`. Major coverage areas include:

- IIIF v2/v3 normalization and rights persistence;
- corpus selection, resume behavior, acquisition invariants, and manuscript splits;
- segmentation-mask restoration and corpus/segmentation integration;
- artificial-fragment masks, task identity, registration, measurements, structured damage, and determinism boundaries;
- HSP controlled-vocabulary extraction results;
- environment-only database credential handling.

Database shell validators and full model runs are separate because they require Docker, ignored binaries, and local state.

## Research principles and evidence boundaries

- Generated reconstructions, if implemented, are hypotheses rather than historical fact.
- Surviving pixels must not be overwritten, hidden, or presented as generated content.
- Provenance, identifiers, transforms, comparators, and model/data versions must remain attached to outputs.
- Synthetic damage is controlled experimental data, not a claim about a manuscript's actual history.
- Uncertainty and multiple plausible candidates should remain visible.
- Model-derived segmentation labels are provisional evidence and may require expert review.
- Missing manuscript text, decoration, or page structure must not be described as recovered without external scholarly evidence for that specific claim.

## Interoperability and IIIF

Current IIIF support normalizes common Presentation API v2/v3 manifests, preserves manifest/canvas/image-service identifiers and raw metadata, and registers repository, manuscript, canvas, and image-asset records. The corpus builder reuses that ingestion model. It does not implement the full IIIF specification, nested collections, annotation exchange, a IIIF viewer, or an external proposal API.

No compatibility with CODICUM or the Manuscript Workbench is claimed. Potential interoperability boundaries are documented in `docs/INTEGRATION_NOTES.md`.

## Roadmap

The next recommended milestone is a deliberately bounded decision around Targeted Training Corpus Expansion Batch 02, preceded by durable artifact storage, human review of flagged segmentation outputs, and explicit source-by-source rights review. Reconstruction and retrieval remain later work. See `NEXT_ACTIONS.md` for acceptance criteria.

## Citation, contact, and licence

No formal citation, DOI, or release publication is defined yet. Before a public release, add a `CITATION.cff` or equivalent record with approved project authorship, institutional contact details, and the preferred repository citation.

This repository currently has no software licence. External access does not automatically grant reuse, modification, or redistribution rights. Maintainers should choose an explicit software licence before public release. Dataset, manuscript-image, model-weight, and metadata rights must be reviewed separately and are not granted by any future software licence.
