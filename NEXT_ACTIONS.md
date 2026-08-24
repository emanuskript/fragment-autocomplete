# NEXT_ACTIONS

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Next recommended task

Expand the validated source corpus toward approximately 100 manuscripts / 500 selected pages while preserving manuscript-level splits and conservative rights status.

## Acceptance criteria

- Manually sample the 45 explicit validation rejections and a cross-manuscript sample of retained candidates; keep uncertain pages as candidates unless a reviewed rule is justified.
- Confirm institutional storage policy and estimate the full acquisition and optional segmentation footprint from the 15-page validation before adding approximately 95 manifests.
- Confirm a source-by-source rights-review workflow. Do not change `training_allowed` until approval is explicit and recorded.
- Expand the committed corpus specification toward approximately 100 distinct manuscripts while retaining the seeded maximum of 5 pages/manuscript and manuscript-level 70/15/15 splits.
- Rerun the builder in bounded batches and validate checksums, duplicate prevention, resume behavior, metadata completeness, and split isolation after each batch.
- Run acquisition in bounded, resumable batches. Keep the existing eManuSkript integration optional, and retain the deterministic corpus/model/config identity whenever segmentation is requested.
- Keep all mask binaries, raw predictions, and overlays as ignored local artifacts; commit only compact provenance, statistics, and validation records.
- Do not begin model training during acquisition or rights review.
- Do not begin reconstruction, retrieval, LLM integration, or UI expansion as part of corpus preparation.
