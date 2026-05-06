# Fragment Autocomplete: Virtual Reconstruction of Medieval Manuscripts using Machine Learning

## Purpose

This repository is the workspace foundation for the Pro*Niedersachsen research software project "Fragment Autocomplete: Virtual Reconstruction of Medieval Manuscripts using Machine Learning". The project aims to support scholarly reconstruction of medieval manuscript fragments while keeping uncertainty, provenance, and comparator evidence visible at every stage.

This repository currently contains project scaffolding only. It does not yet implement a backend, frontend, database, IIIF pipeline, machine learning model, or reconstruction workflow.

## Layout-first MVP strategy

The near-term technical strategy is layout-first reconstruction rather than premature full-image generation. Early work should focus on extracting, storing, validating, and reusing manuscript layout structure so later reconstruction steps can be conditioned on document organization instead of guessing pixel content directly.

## Role of eManuSkript

eManuSkript and the "Manuskripte digital lesen lernen" layout analysis work are the central technical backbone of the project. Their layout outputs, including roughly 21 manuscript layout labels, are expected to support later segmentation, pseudo-labeling, layout priors, retrieval keys, UI overlays, evaluation, and downstream conditioning for candidate reconstructions.

## Role of CoMMA

CoMMA is treated as a text, transcription, and metadata resource. It is important for contextualization and alignment, but it should not be treated as the core visual reconstruction dataset.

## Current project phase

The broader project is around Week 6 after start. The current repository milestone is limited to establishing a clean, professional workspace foundation so later architecture, schema, ingestion, and evaluation work can proceed in a controlled way.

## Repository structure

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
|-- models/
|-- outputs/
|-- scripts/
|-- src/
`-- tests/
```

Key directories:

- `docs/`: planning, architecture, data source, evaluation, and decision records
- `src/`: future code boundaries for backend, frontend, ingestion, ML, evaluation, and shared utilities
- `data/`: placeholder structure for raw, processed, and metadata assets
- `models/`: placeholder for model artifacts outside git
- `outputs/`: placeholder for generated research outputs outside git
- `scripts/`: reproducible project utilities such as workspace validation
- `tests/`: future validation and automated checks

## Setup instructions

1. Clone the repository once it exists remotely, or continue locally in this folder.
2. Review [README.md](/Users/mobasuony/Desktop/Fragments/README.md), [AGENTS.md](/Users/mobasuony/Desktop/Fragments/AGENTS.md), and [ROADMAP_STATUS.md](/Users/mobasuony/Desktop/Fragments/ROADMAP_STATUS.md).
3. Run the workspace validation script:

```bash
bash scripts/check_workspace.sh
```

4. Use the roadmap and next-actions files to guide the next planning task.

No runtime dependencies are required yet because no application components are implemented at this stage.

## Next immediate task

Draft the technical architecture and database schema, including clear system boundaries, storage direction, and first entity definitions, without implementing the application itself.
