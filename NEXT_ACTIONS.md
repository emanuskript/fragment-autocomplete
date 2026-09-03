# NEXT_ACTIONS

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Next recommended task

Batch 01 → eManuSkript Segmentation at Expanded Scale.

Training Corpus Expansion Batch 01 acquisition and registration has passed. The immutable Batch 01 assignment contains 15 manuscripts, with 14 active manuscripts and 70 selected pages after eight explicit manual decisions, seven Batch 01 page rejects, three deterministic same-manuscript replacements, and the suitability exclusion of `cea-FaZellweger-90A-01-2`. The selected pages remain isolated as 50/10/10 train/validation/test pages. Acquisition registered 15 manifest records and 70 image assets totaling 96,587,059 bytes; an unchanged rerun reused all 70 assets. Every Batch 01 asset remains `pending_review`, and `training_allowed` remains false for all 70.

## Acceptance criteria

- Run the existing eManuSkript segmentation implementation over exactly the 70 acquired Batch 01 pages; do not introduce another ingestion or segmentation path.
- Verify that every successful page produces source-sized masks and retains complete source-image, IIIF, model, configuration, and run provenance.
- Record explicit failures and deterministic corpus/model/config identities, then rerun unchanged to prove output and database-storage idempotency.
- Preserve the 11/2/2 manuscript assignment and 50/10/10 active page isolation throughout segmentation.
- Preserve source checksums, source relationships, repository/manuscript/canvas metadata, `rights_review_status`, and `training_allowed` unchanged.
- Keep source images and raw IIIF manifests under ignored `data/raw/`, masks and generated artifacts under ignored `outputs/`, and commit only compact provenance/statistics/validation metadata under `data/metadata/`.
- Treat institutional GWDG/object-storage backup, retention, and quota details as an open, non-blocking operations item; do not move the validated local assets unnecessarily.
- Do not train a model, generate Batch 01 artificial fragments, implement reconstruction or retrieval, introduce LLM agents, ingest HisFrag20, mine e-rara, or build new UI in this milestone.
