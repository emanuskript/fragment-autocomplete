# Project status dashboard

## Purpose

The Fragment Autocomplete Evidence Observatory is a read-only Streamlit dashboard
for understanding the repository as it exists now. It answers three questions:

1. What is implemented and backed by committed evidence?
2. What is partial or schema-only?
3. What should happen next, and which scholarly or rights decision gates come first?

The dashboard is metadata-first. It reads versioned JSON/YAML records and SQL
migrations from the repository, so it can run without the ignored manuscript
image corpus, generated artifacts, Mergen checkpoints, or a live database.

## Run it

Install the normal project requirements, then run:

```bash
bash scripts/run_project_dashboard.sh
```

Or invoke Streamlit directly:

```bash
python -m streamlit run scripts/view_project_dashboard.py
```

The dashboard is separate from `scripts/view_segmentation_results.py`. The older
viewer queries PostgreSQL and inspects individual stored segmentation runs. This
new dashboard explains the whole project from compact committed evidence.

## Views

### Overview

Shows the complete pipeline from source ingestion through the future
Fragmentarium review/deployment boundary. Implemented, partial and not-built
stages are labelled explicitly. The evidence chain separates source pixels,
model-derived Mergen masks, synthetic experiment targets and future candidate
inference.

### Damage matrix

Shows Jeremy's 187-row matrix, 17 damage types, 15 content types, decision totals,
operator coverage and the two incomplete source rows. The matrix explorer exposes
all 748 severity cells. It intentionally distinguishes a matrix decision from an
implemented generator: only D2-01, D2-02 and D2-03 have working procedural
operators.

### Segmentation

Summarizes the initial pilot, 15-page validation set and 70-page Batch 01 run. It
shows the combined Mergen label distribution and explains the preparation,
inference, source-coordinate restoration and storage path. Mergen predictions are
labelled as model-derived layout evidence rather than expert ground truth.

### Storage and provenance

Explains the separation between PostgreSQL/PostGIS, tracked compact metadata,
ignored large artifacts and external model weights. The schema ledger marks six
future-facing tables as groundwork so their presence is not mistaken for working
retrieval, reconstruction, export or review services.

### Experiments

Follows the controlled experiment line from v0.1.1 through v0.2, v0.3 and the
matrix-driven pilot. The page explains what topology, calibration, pixel
preservation, split isolation, idempotence and frozen-invariant checks prove—and
what they do not prove.

### Implementation ledger

Explains fourteen capability groups with their repository evidence and claim
boundary. It covers the workspace, database, IIIF, HSP metadata, sample
registration, Mergen model registry, segmentation, storage/viewer, corpus,
artificial-fragment experiments, matrix workflow and onboarding documentation.

### Next steps

Places Jeremy's expert review first, then one appearance operator, rights/quality
approval, retrieval, candidate reconstruction with multiple hypotheses, expert
review and Fragmentarium integration. It does not suggest training or deployment
before those gates are met.

## Data contract and validation

`src/frontend/project_status.py` is the testable adapter between repository
records and UI presentation. It derives corpus counts, matrix coverage, schema
tables, label distributions and experiment summaries from committed files.
`tests/frontend/test_project_status.py` locks the key totals and verifies that
future schema is not reported as implemented functionality.

Validate the dashboard data and the wider repository with:

```bash
python -m pytest -q tests/frontend/test_project_status.py
python -m pytest -q
python -m ruff check src scripts tests
bash scripts/check_workspace.sh
```

The interface does not write to the database or modify experiment records. Its
JSON download is a compact status export; it omits only the 748-row matrix table.

## Visual system

The dashboard uses a light framed-sheet layout for long research sessions: a
quiet blue-grey frame, a white working sheet, flat surfaces, one evidence hue,
tabular figures and no decorative dashboard gradients. Colour is paired with
text labels. Mobile layouts fold grids to one or two columns, and reduced-motion
preferences disable non-essential transitions.
