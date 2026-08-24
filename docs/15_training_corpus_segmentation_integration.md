# Training Corpus → eManuSkript Integration Validation

## Scope

The existing eManuSkript/Ultralytics inference, source-dimension mask restoration, mask serialization, and PostgreSQL `segmentation_run`/`layout_region` storage paths were run against exactly the 15 selected validation-corpus pages. No segmentation logic was added to the corpus builder, and no model training, artificial-fragment generation, reconstruction, retrieval, LLM, e-rara, HisFrag20, UI, or database migration work was performed.

Source manuscript splits and rights remain evidence from corpus registration, not segmentation inference. Mask and region outputs are model-derived layout evidence rather than manual ground truth.

## Reproducible identity

- Corpus: `ecodices_training_source_validation_v0_1`
- Run identity SHA-256: `22153377b95aef2aa9376873eb832449d9bce2af63a238445bc03fac4d7ce09f`
- Model: `best_emanuskript_segmentation`
- Model SHA-256: `9f0b03cc64c830d337a01ddac6a04616a385d573e3b923a86fc4c74c16416511`
- Configuration identity includes the 15 source image checksums/DB identities, manuscript splits, model checksum, device, confidence threshold, image size, software versions, retina-mask setting, and source-dimension restoration method.

## Validation result

- Attempted pages: 15
- Successful pages: 15
- Failed pages: 0
- Detected regions: 872
- Regions/page: min 0, max 125, mean 58.1333, median 55
- Confidence: min 0.250429, max 0.881027, mean 0.635561, median 0.67616
- Source-sized mask artifacts: 872 files, 4874819 bytes
- Stable segmentation runs after storage rerun: 15
- Stable region sets after storage rerun: 15

## Manuscript-isolated split statistics

- train: 9 attempted, 9 successful, 0 failed, 611 regions
- validation: 3 attempted, 3 successful, 0 failed, 64 regions
- test: 3 attempted, 3 successful, 0 failed, 197 regions

## Label distribution

- Embellished: 1
- Gloss: 10
- Main script black: 793
- Main script coloured: 4
- Music: 36
- Page Number: 7
- Plain initial - Black: 7
- Plain initial - Highlighted: 6
- Plain initial- coloured: 1
- Running header: 1
- Variant script coloured: 6

## Explicit failures

No page failed in this validation run.

## Invariants confirmed

- All successful detections retain class ID, label, confidence, bbox, source-sized binary mask path, mask SHA-256, mask area, and model/run provenance.
- Every stored mask matches its registered source-image dimensions and remains an ignored local PNG artifact.
- Every stored run resolves to its original `image_asset`, `canvas`, and manuscript; the same run identity reuses the same 15 `segmentation_run` rows and replaces rather than duplicates their regions.
- Source image checksums, source metadata hashes, `training_allowed`, `rights_review_status`, `publication_allowed`, and manuscript split assignments match the pre-inference snapshot.

## Next engineering step

Expand the source corpus toward approximately 100 manuscripts / 500 selected pages in bounded batches while preserving manuscript-level train/validation/test isolation, checksum-resumable assets, and `pending_review` rights until explicit approval. Do not begin model training as part of acquisition.
