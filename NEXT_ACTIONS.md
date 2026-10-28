# NEXT_ACTIONS

The repository has completed an external-sharing hygiene and documentation pass. The active documentation now identifies Mergen as the eManuSkript layout-analysis component, records its canonical GitHub repository and GWDG OwnCloud weight directory in `models/model_registry.yaml`, and keeps the three checkpoints outside Git with verified checksums. Historical run manifests retain their original model IDs and paths as provenance. No committed scientific result or important generated artifact was removed or altered.

## Mergen dependency maintenance

- Treat `models/model_registry.yaml` as the canonical local record for the Mergen source repository, external weight directory, expected filenames, checksums, and ignored paths.
- Before any new inference run, obtain the three files from the registered GWDG directory and verify all SHA-256 checksums. Do not silently substitute newer checkpoints under the existing model IDs.
- If Mergen publishes changed weights, register them as new versioned model entries and keep historical run provenance unchanged.

## Before an external handoff

- Choose and add an explicit software licence; repository access without a licence does not grant reuse rights.
- Add approved citation/authorship and project contact information without inventing a DOI or publication record.
- Share from a fresh Git clone or Git archive. Do not copy the current working directory, which contains ignored source images, model checkpoints, raw IIIF downloads, databases/outputs, and research artifacts with separate rights.
- Decide whether collaborators need only the metadata/code repository or also checksum-matched external artifacts, then document a rights-approved transfer channel and access scope.
- On a Docker-enabled host, run the PostgreSQL/PostGIS validators with a locally chosen `FRAGMENT_DB_PASSWORD` before the handoff.

## Current study artifact

- `output/pdf/Fragment_Autocomplete_Study_Report.pdf` is the verified three-page project briefing as of 2026-08-23.
- Refresh it after the next material milestone while preserving evidence/inference separation and candidate-hypothesis language.

## Completed milestone

Artificial Fragment Experiment v0.3 — structured synthetic material-loss validation is complete for all 13 validation pages. Six distinct calibrated mask families produced 156 tasks and 2,424 full-mask region observations. The saved determinism audit confirms 795 byte-identical artifacts with unchanged file mtimes and database rows/timestamps after full recomputation; 4,873 frozen artifact files and all 67 historical task rows passed invariant checks. These controlled transformations are technical comparators and candidate experimental conditions, not inferred historical damage or recovered manuscript content. See `docs/20_artificial_fragment_experiment_v03.md`.

Artificial Fragment Experiment v0.2 — segmentation-aware controlled validation is complete for every locally eligible validation page. The corpus audit derives 85 pages, 19 page-bearing manuscripts, 59/13/13 page splits, 85 segmentation runs and 4,230 masks. Eleven of the 13 validation pages generated 44 tasks and 604 full-mask region survival measurements. At the time of v0.2, two validation sources were unavailable iCloud placeholders and received explicit rejections; no pages were substituted. All four Batch 01 outliers are retained: three probable segmentation failures and one requiring human review. Model-derived labels have not been changed.

Full recomputation produced byte-identical artifacts, registration matched 44 rows without duplicates or timestamp churn, frozen source/segmentation/legacy/test invariants passed, and all 133 tests passed. Source rights remain `pending_review` and `training_allowed: false`. No training or reconstruction has begun. See `docs/19_artificial_fragment_experiment_v02.md`.

## Next recommended engineering step

First keep the exact source and experiment artifacts available on durable storage. The 2026-09-10 resumption restored 63 iCloud placeholders and journaled/restored 216 sub-microsecond mtime differences after full byte/database verification. The original frozen baseline remains unchanged; see `data/metadata/artificial_fragment_v03_storage_resumption.json`.

Design Targeted Training Corpus Expansion Batch 02 as a new immutable complete-page batch addressing measured layout-class and provider/repository gaps. The corpus uses one provider; 91.94% of detected regions are Main script black, and validation contains no Border, Illustrations, Running header or Table detections. Establish explicit rights review and expert segmentation-quality review alongside candidate selection. Preserve all existing splits and the test set. The workspace checker now includes the v0.2/v0.3 milestone files; its presence check does not replace checksum, database-invariant, or scholarly review.

## Acceptance criteria for the next decision

- Preserve reliable local availability and establish backup for the eleven checksum-restored sources, including the two `sbs-gen0020` validation pages. Reverify registered checksums before future use, and do not silently extend or overwrite the saved v0.2 experiment.
- Obtain human review of the four flagged `fmb-cb-0902` pages, and inspect the additional existing zero-detection `ubb-F-IX-0068` page reported by the combined audit.
- Record which measured coverage gaps each proposed expansion candidate addresses. Missing script metadata must remain missing until supported by source evidence.
- Review rectangular/irregular damage assumptions with manuscript specialists. Do not interpret mask survival as semantic recoverability or historical reconstruction.
- Before training, establish a separately reviewed source subset with `rights_review_status: approved_for_training` and `training_allowed: true`; source licenses and segmentation success do not imply authorization.
- Keep raw sources under ignored `data/raw/`, generated artifacts under ignored `outputs/`, and only compact provenance/statistics metadata in Git. Resolve institutional GWDG/object-storage backup, retention and quota policy.
- Begin neither expansion acquisition nor a reconstruction/completion baseline automatically; use the audit and expert/rights review to authorize the next bounded milestone.
