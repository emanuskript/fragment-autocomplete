# NEXT_ACTIONS

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Next recommended task

Batch 01 segmentation quality review and explicit scale-path decision.

Training Corpus Expansion Batch 01 now passes acquisition, registration, and expanded-scale eManuSkript segmentation. Exactly 70 pages remain isolated as 50/10/10 train/validation/test and produced 70 successful page outcomes, 3,358 detected regions, and 3,358 binary source-sized masks. The unchanged inference rerun reused all 70 page outputs without artifact churn; unchanged database storage preserved 70 run rows and 3,358 region rows without duplicates or timestamp churn. Three `fmb-cb-0902` pages produced zero above-threshold detections, and one additional page from that manuscript has very low mean confidence; these are retained review signals, not corpus-selection changes. Every Batch 01 source remains `pending_review` and `training_allowed: false`.

## Acceptance criteria

- Review overlays/masks for the three zero-detection `fmb-cb-0902` pages and the low-confidence `fmb-cb-0902` page recorded in `data/metadata/training_corpus_expansion_batch_01_segmentation_statistics.yaml`; preserve them unless an explicit later scholarly/corpus decision says otherwise.
- Assess whether 70 newly segmented pages provide enough script/layout/repository/date diversity to begin controlled artificial-fragment work, or whether another immutable complete-page acquisition batch should move the corpus toward roughly 300–500 pages first.
- Before any artificial-fragment milestone, obtain expert review of the damage model and keep generated ground truth separate from source evidence and model-derived segmentation evidence.
- Before any training run, establish an explicitly reviewed source subset with `rights_review_status: approved_for_training` and `training_allowed: true`; do not infer approval from source licenses or segmentation success.
- Continue to keep raw sources under ignored `data/raw/`, segmentation artifacts under ignored `outputs/`, and only compact provenance/statistics/validation metadata under `data/metadata/`.
- Treat institutional GWDG/object-storage backup, retention, and quota details as an open operations item.
- Do not automatically begin either expansion or artificial-fragment generation/model training until this decision is made.
