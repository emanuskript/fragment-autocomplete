# Fragment Autocomplete — Segmentation Smoke Test Report

## Purpose

This report documents the first controlled segmentation smoke test on the two prepared pilot inputs.

## Scope

Inference was run only on the two prepared inputs. No training was done, no segmentation output was stored in the database, and no UI was built.

## Model used

- Model ID: `best_emanuskript_segmentation`
- Model path: `model weights/best_emanuskript_segmentation.pt`

## Inputs used

- `fp_01_clean_simple` (full_page) -> `autocomplete-test-dataset/full_pages/fp_01_clean_simple/e-codices_csg-0300_0005_max.jpg`
- `fr_02_text_block` (fragment) -> `autocomplete-test-dataset/fragments/fr_02_text_block/fragmentarium_F-sf5d_Stams_STA_Frg_235_01r02r.jpg_max.jpg`

## Environment and dependencies

- Python: `3.9.6`
- PyTorch: `2.7.1`
- Ultralytics: `8.4.51`
- Device: `cpu`
- Inference image size: `320`

## Inference settings

- Confidence threshold: `0.25`
- Inference image size: `320`
- Output directory: `outputs/segmentation_smoke_test`

## Output files

- Raw outputs: `outputs/segmentation_smoke_test/raw/`
- Overlays: `outputs/segmentation_smoke_test/overlays/`
- Logs: `outputs/segmentation_smoke_test/logs/`

## Per-sample results

### `fp_01_clean_simple`

- Status: `success`
- Detected regions: 102
- Detected labels: Main script black, Plain initial - Black
- Raw output: `outputs/segmentation_smoke_test/raw/fp_01_clean_simple.json`
- Overlay: `outputs/segmentation_smoke_test/overlays/fp_01_clean_simple_overlay.jpg`

### `fr_02_text_block`

- Status: `success`
- Detected regions: 98
- Detected labels: Main script black
- Raw output: `outputs/segmentation_smoke_test/raw/fr_02_text_block.json`
- Overlay: `outputs/segmentation_smoke_test/overlays/fr_02_text_block_overlay.jpg`

## Detected labels summary

- Unique labels across both samples: Main script black, Plain initial - Black

## Visual overlay paths

- `fp_01_clean_simple`: `outputs/segmentation_smoke_test/overlays/fp_01_clean_simple_overlay.jpg`
- `fr_02_text_block`: `outputs/segmentation_smoke_test/overlays/fr_02_text_block_overlay.jpg`

## Known issues

- This was a smoke test only; it confirms model execution and basic output format, not evaluation quality.
- Outputs remain on the local filesystem and have not yet been stored in the database.

## Next step

Store segmentation smoke-test outputs in the database.
