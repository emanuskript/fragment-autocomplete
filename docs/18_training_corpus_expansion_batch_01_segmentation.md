# Training Corpus Expansion Batch 01 → eManuSkript Segmentation

## Outcome

Exactly 70 acquired Batch 01 pages were passed through the existing eManuSkript/Ultralytics inference, source-coordinate mask-restoration, and PostgreSQL storage workflow. Segmentation outputs are model-derived layout evidence, not manual ground truth and not training approval.

- Successful pages: 70
- Failed pages: 0
- Detected regions / source-sized masks: 3358 / 3358
- Regions/page: min 0, max 114, mean 47.971429, median 42.0
- Confidence: min 0.250027, max 0.983595, mean 0.587399, median 0.611494
- Mask bytes: 20646297
- Total ignored segmentation artifact bytes: 122385911

## Model and configuration

- Model: `best_emanuskript_segmentation`
- Checkpoint: `model weights/best_emanuskript_segmentation.pt`
- Model SHA-256: `9f0b03cc64c830d337a01ddac6a04616a385d573e3b923a86fc4c74c16416511`
- Run identity SHA-256: `1750add1dbeab7becbf42cb40f7dde6745260b7c159eaf8d09b1a55364a9908e`
- Device: `cpu`; confidence `0.25`; image size `320`; retina masks enabled.
- Inputs larger than 2048 pixels on their longest side use the existing temporary downscaled inference copy; masks and boxes are restored to original source-image coordinates.

## Split coverage

- train: 50 attempted, 50 successful, 0 failed, 2692 regions
- validation: 10 attempted, 10 successful, 0 failed, 138 regions
- test: 10 attempted, 10 successful, 0 failed, 528 regions

## Label distribution

- Border: 1
- Embellished: 9
- Gloss: 23
- Illustrations: 6
- Main script black: 3096
- Main script coloured: 7
- Music: 56
- Page Number: 12
- Plain initial - Black: 39
- Plain initial - Highlighted: 44
- Plain initial- coloured: 36
- Running header: 4
- Table: 1
- Variant script coloured: 24

## Idempotency and integrity

- The unchanged inference rerun preserved 3498 raw/overlay/mask artifacts byte-for-byte and without mtime churn.
- The storage rerun reused 70 logical `segmentation_run` rows and 3358 `layout_region` rows without duplicate or timestamp churn.
- Every mask is an ignored local binary PNG, matches its source dimensions, contains only 0/255 values, and matches its recorded SHA-256 and pixel area.
- Source image hashes, dimensions, byte sizes, mtimes, database relationships, manuscript splits, and rights metadata match the pre-inference snapshot.
- All 70 Batch pages remain `pending_review`; `training_allowed` remains false. Segmentation did not approve rights.

## Performance

- Initial wall duration: 282.38517 seconds
- Approximate wall time/page: 4.034074 seconds
- Requested device: `cpu`
- Downscaled temporary inference images: 70 pages
- Observed child-process max RSS: 3768991744 bytes (getrusage_RUSAGE_CHILDREN_ru_maxrss)

## Explicit failures and outliers

- No page failed.
- unusually_low_region_counts: `6538cbcb609973816c5a`, `6c1543ed764a6265f96a`, `95c524bbf6593575149b`
- very_low_mean_confidence: `5e6ff8c7c454a2c27b94`

Outliers remain in the corpus and are recorded for later human review; no page was automatically excluded or replaced.

## Artifact layout

- Local ignored outputs: `outputs/training_corpus_segmentation/batch_01/`
- Compact results: `data/metadata/training_corpus_expansion_batch_01_segmentation_results.yaml`
- Compact statistics: `data/metadata/training_corpus_expansion_batch_01_segmentation_statistics.yaml`
- Validation: `data/metadata/training_corpus_expansion_batch_01_segmentation_validation.yaml`

## Next decision (not implemented)

Choose between another complete-page corpus expansion batch and controlled artificial-fragment generation plus a first training-pipeline smoke test only after reviewing segmentation quality, the damage model, corpus diversity, and rights approvals. Actual model training remains blocked until an explicitly rights-approved subset exists.
