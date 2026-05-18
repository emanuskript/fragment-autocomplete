# Fragment Autocomplete — Segmentation Storage Report

## Purpose
Store the existing two-sample segmentation smoke-test outputs in PostgreSQL/PostGIS as structured `segmentation_run` and `layout_region` records.

## Scope
This step stores only the already-generated smoke-test outputs for one full page and one fragment. No inference was rerun, no training was performed, and no UI was built.

## Inputs Used
- Smoke-test results: `data/metadata/segmentation_smoke_test_results.yaml`
- Prepared inputs: `data/metadata/segmentation_test_inputs.yaml`
- Smoke-test ID: `segmentation_smoke_test_v0_1`

## Database Tables Written
- `segmentation_run`
- `layout_region`

## Segmentation Runs Created or Matched
- `fp_01_clean_simple`: run `519f5e06-5ccb-421b-a54d-0db5d3d86fec` (matched_and_refreshed)
- `fr_02_text_block`: run `7329ee6d-f45e-4b96-b4b5-51dc76d8201d` (matched_and_refreshed)

## Layout Regions Created or Matched
- `fp_01_clean_simple`: `102` layout regions stored
- `fr_02_text_block`: `98` layout regions stored

## Geometry Strategy
The raw smoke-test JSON did not include persisted mask polygons. Each region was therefore stored as a page-local SRID 0 polygon derived from the detected bounding box, and the same polygon was written to both `region_geom` and `bbox_geom`.

## Labels and Confidence Summary
- `fp_01_clean_simple`: labels `Main script black, Plain initial - Black`
- `fr_02_text_block`: labels `Main script black`

## Output Paths Preserved
- `fp_01_clean_simple` raw output: `outputs/segmentation_smoke_test/raw/fp_01_clean_simple.json`
- `fp_01_clean_simple` overlay: `outputs/segmentation_smoke_test/overlays/fp_01_clean_simple_overlay.jpg`
- `fr_02_text_block` raw output: `outputs/segmentation_smoke_test/raw/fr_02_text_block.json`
- `fr_02_text_block` overlay: `outputs/segmentation_smoke_test/overlays/fr_02_text_block_overlay.jpg`

## Validation Result
- Storage status: `stored`
- Database write: `true`

## What Has Not Been Implemented
- No inference was rerun.
- No training was performed.
- No database-backed UI viewer exists yet.
- Artificial fragments and reconstruction are not implemented here.

## Next Step
Build a minimal local UI viewer for the stored segmentation outputs.
