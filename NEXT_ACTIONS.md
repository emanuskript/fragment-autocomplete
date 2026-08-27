# NEXT_ACTIONS

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Next recommended task

Resolve the eight explicit page-review exceptions before acquiring or registering expansion batch 01.

## Acceptance criteria

- Review the one blank-like historical validation page and seven batch-01 thumbnail exceptions in `data/metadata/training_corpus_expansion_readiness_review.yaml`; record an explicit keep or reject decision for every page.
- Keep uncertain pages as candidates. If a page is rejected, preserve the visual evidence/reason and choose any replacement from the unchanged seeded order rather than silently substituting it.
- Rerun `PYTHON_BIN=/usr/bin/python3 bash scripts/validate_training_corpus_expansion_batch.sh` and require byte-identical dry-run outputs, zero baseline overlap, 11/2/2 batch splits, and a cleared acquisition gate.
- Confirm institutional storage policy before download. The observed source-image mean projects approximately 105 MB for batch 01 and 699 MB for 500 pages, excluding manifests, safety margin, segmentation, and database overhead.
- Confirm the source-by-source rights-review workflow. Do not change `training_allowed` or `pending_review` during acquisition.
- Only after those gates pass, acquire/register batch 01 through the existing builder and rerun unchanged to prove checksum-resumable behavior.
- Continue with separate immutable batches toward approximately 100 manuscripts / 500 pages; never rewrite the frozen validation corpus or already registered batch membership/splits.
- Keep the existing eManuSkript integration optional, and retain the deterministic corpus/model/config identity whenever segmentation is requested.
- Keep all mask binaries, raw predictions, and overlays as ignored local artifacts; commit only compact provenance, statistics, and validation records.
- Do not begin model training during acquisition or rights review.
- Do not begin reconstruction, retrieval, LLM integration, or UI expansion as part of corpus preparation.
