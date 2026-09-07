# NEXT_ACTIONS

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Completed milestone

Artificial Fragment Experiment v0.2 — segmentation-aware controlled validation is complete for every locally eligible validation page. The corpus audit derives 85 pages, 19 page-bearing manuscripts, 59/13/13 page splits, 85 segmentation runs and 4,230 masks. Eleven of the 13 validation pages generated 44 tasks and 604 full-mask region survival measurements. Two validation sources are unavailable iCloud placeholders and have explicit rejections; no pages were substituted. All four Batch 01 outliers are retained: three probable segmentation failures and one requiring human review. Model-derived labels have not been changed.

Full recomputation produced byte-identical artifacts, registration matched 44 rows without duplicates or timestamp churn, frozen source/segmentation/legacy/test invariants passed, and all 133 tests passed. Source rights remain `pending_review` and `training_allowed: false`. No training or reconstruction has begun. See `docs/19_artificial_fragment_experiment_v02.md`.

## Next recommended engineering step

Design a new immutable complete-page expansion batch targeting the measured layout-class and provider/repository gaps. The corpus uses one provider; 91.94% of detected regions are Main script black, and validation contains no Border, Illustrations, Running header or Table detections. Establish explicit rights review and expert segmentation-quality review alongside candidate selection. Preserve all existing splits and the test set.

## Acceptance criteria for the next decision

- Restore reliable local availability and backup for eleven existing iCloud placeholder sources, including the two rejected `sbs-gen0020` validation pages. Verify original checksums before any future use. Do not silently extend or overwrite the saved v0.2 experiment.
- Obtain human review of the four flagged `fmb-cb-0902` pages, and inspect the additional existing zero-detection `ubb-F-IX-0068` page reported by the combined audit.
- Record which measured coverage gaps each proposed expansion candidate addresses. Missing script metadata must remain missing until supported by source evidence.
- Review rectangular/irregular damage assumptions with manuscript specialists. Do not interpret mask survival as semantic recoverability or historical reconstruction.
- Before training, establish a separately reviewed source subset with `rights_review_status: approved_for_training` and `training_allowed: true`; source licenses and segmentation success do not imply authorization.
- Keep raw sources under ignored `data/raw/`, generated artifacts under ignored `outputs/`, and only compact provenance/statistics metadata in Git. Resolve institutional GWDG/object-storage backup, retention and quota policy.
- Begin neither expansion acquisition nor a reconstruction/completion baseline automatically; use the audit and expert/rights review to authorize the next bounded milestone.
