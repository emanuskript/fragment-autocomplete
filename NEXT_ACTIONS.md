# NEXT_ACTIONS

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Next recommended task

Review the 5-manuscript Training Corpus Builder validation and prepare the approximately 100-manuscript expansion specification.

## Acceptance criteria

- Manually sample the 45 explicit validation rejections and a cross-manuscript sample of retained candidates; keep uncertain pages as candidates unless a reviewed rule is justified.
- Confirm institutional storage policy and estimate the full acquisition footprint from the 22 MB / 15-page validation representation before adding approximately 95 manifests.
- Confirm a source-by-source rights-review workflow. Do not change `training_allowed` until approval is explicit and recorded.
- Expand the committed corpus specification toward approximately 100 distinct manuscripts while retaining the seeded maximum of 5 pages/manuscript and manuscript-level 70/15/15 splits.
- Rerun the builder in bounded batches and validate checksums, duplicate prevention, resume behavior, metadata completeness, and split isolation after each batch.
- Invoke the existing eManuSkript segmentation workflow only as an optional later source-analysis step; do not begin model training.
- Do not begin reconstruction, retrieval, LLM integration, or UI expansion as part of corpus preparation.
