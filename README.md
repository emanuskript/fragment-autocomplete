# Fragment Autocomplete: Virtual Reconstruction of Medieval Manuscripts using Machine Learning

Fragment Autocomplete is a two-year Pro*Niedersachsen research software project hosted at the Institute for Digital Humanities, University of Göttingen. The project aims to build an open-source and open-access AI-based toolchain that helps scholars generate and evaluate candidate page-level reconstruction hypotheses from surviving medieval manuscript fragments.

The system must preserve the distinction between observed evidence and inference. Reconstruction outputs are candidate scholarly hypotheses with uncertainty, provenance, and comparators; they are not claims that the original manuscript page, text, or decoration has been recovered.

## Technical Strategy

The project follows a layout-first MVP strategy. Early work should estimate page canvas, margins, columns, semantic layout zones, and plausible fragment placement before any experimental full-image generation is considered.

eManuSkript / "Manuskripte digital lesen lernen" is the central technical backbone. Its manuscript layout-analysis model, with roughly 21 manuscript layout labels, should later support segmentation, pseudo-labeling, layout priors, retrieval keys, UI overlays, evaluation signals, and optional conditioning maps.

CoMMA is a text, transcription, and metadata resource. It can support text search, metadata enrichment, witness discovery, and IIIF manifest discovery, but it is not the core visual reconstruction dataset.

## Current Status

This repository currently contains project documentation, architecture planning, figure sources, generated architecture figures, and build scripts. It does not implement the backend, frontend, database, IIIF ingestion pipeline, eManuSkript integration, ML pipeline, retrieval system, MSI viewer, or deployment.

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
- `data/`: placeholder structure for raw, processed, and metadata assets. Large data is excluded from git.
- `models/`: placeholder for model artifacts. Model binaries are excluded from git.
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

## Next Task

Create concrete PostgreSQL/PostGIS database schema and migrations.
