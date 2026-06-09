# Fragment Autocomplete — Segmentation Test Inputs

## Purpose

This document records the two controlled inputs selected for the first future eManuSkript/Ultralytics segmentation smoke test.

## Selected samples

- Full page: `fp_01_clean_simple`
- Fragment: `fr_02_text_block`

## Why these samples were selected

- `fp_01_clean_simple`: Preferred registered sample with local image path and verified DB records.
- `fr_02_text_block`: Preferred registered sample with local image path and verified DB records.

## Model chosen for future smoke test

- Model ID: `best_emanuskript_segmentation`
- Model path: `model weights/best_emanuskript_segmentation.pt`

## Local file readiness

- `fp_01_clean_simple` local path: `autocomplete-test-dataset/full_pages/fp_01_clean_simple/e-codices_csg-0300_0005_max.jpg`
- `fr_02_text_block` local path: `autocomplete-test-dataset/fragments/fr_02_text_block/fragmentarium_F-sf5d_Stams_STA_Frg_235_01r02r.jpg_max.jpg`

## Database record readiness

- `fp_01_clean_simple` image asset: `4f2aa890-aac2-4813-acc9-47b68cd7967b`, canvas: `a9fecfcf-2e44-4d0e-bd18-89c368400b47`
- `fr_02_text_block` image asset: `2d04e20b-a8f9-4f40-89fe-0ea3ac6d7a49`, fragment: `c0017254-558f-4cb6-ab17-3d959d2ace1a`

## Rights/access status

- Rights review status remains `pending_review` for both inputs.
- Training, publication, and demo flags remain false.
- Access level remains `internal`.

## What has not been run

- No inference was run.
- No segmentation was produced.
- Model weights were not loaded.
- This preparation step only selected controlled inputs for the first smoke test.

## Next step

Run the first controlled eManuSkript segmentation smoke test.
