# Fragment Autocomplete — Full Pilot Segmentation Report

## Purpose
Document the full 10-item pilot segmentation run and the subsequent PostgreSQL/PostGIS storage step.

## Scope
Segmentation was run on the 10-item pilot dataset only. No training was performed, and no artificial fragment generation, reconstruction, retrieval, MSI workflow, or CoMMA workflow was implemented here.

## Input Dataset
- Pilot run ID: `segmentation_pilot_v0_1`
- Pilot inputs: `data/metadata/segmentation_pilot_inputs.yaml`
- Pilot results: `data/metadata/segmentation_pilot_results.yaml`

## Model Used
- Model ID: `best_emanuskript_segmentation`
- Model path: `model weights/best_emanuskript_segmentation.pt`

## Inference Settings
- Device: `cpu`
- Confidence threshold: `0.25`
- Image size: `320`

## Per-sample Results Table

| Sample | Kind | Regions | Labels | Status | Warnings |
| --- | --- | ---: | --- | --- | --- |
| `fp_01_clean_simple` | `full_page` | 102 | Main script black, Plain initial - Black | `matched_and_refreshed` |  |
| `fp_02_clean_simple` | `full_page` | 31 | Main script black | `matched_and_refreshed` |  |
| `fp_03_complex_layout` | `full_page` | 82 | Embellished, Main script black, Plain initial - Highlighted | `matched_and_refreshed` |  |
| `fp_04_complex_layout` | `full_page` | 34 | Embellished, Main script black, Music, Plain initial - Black | `matched_and_refreshed` |  |
| `fp_05_iiif_rights` | `full_page` | 91 | Embellished, Gloss, Main script black, Main script coloured, Plain initial - Black, Plain initial- coloured, Variant script coloured | `matched_and_refreshed` |  |
| `fr_01_binding_strip` | `fragment` | 40 | Illustrations, Main script black | `matched_and_refreshed` |  |
| `fr_02_text_block` | `fragment` | 98 | Main script black | `matched_and_refreshed` |  |
| `fr_03_marginal_gloss` | `fragment` | 24 | Main script black, Music | `matched_and_refreshed` |  |
| `fr_04_decoration_initial` | `fragment` | 115 | Embellished, Main script black, Main script coloured, Music, Plain initial - Highlighted, Zoo - Anthropomorphic | `matched_and_refreshed` |  |
| `fr_05_damaged_irregular` | `fragment` | 24 | Main script black | `matched_and_refreshed` |  |

## Detected Labels Summary
- Unique labels across the pilot run: Embellished, Gloss, Illustrations, Main script black, Main script coloured, Music, Plain initial - Black, Plain initial - Highlighted, Plain initial- coloured, Variant script coloured, Zoo - Anthropomorphic

## Output Paths
- `fp_01_clean_simple` raw: `outputs/segmentation_pilot/raw/fp_01_clean_simple.json`
- `fp_01_clean_simple` overlay: `outputs/segmentation_pilot/overlays/fp_01_clean_simple_overlay.jpg`
- `fp_02_clean_simple` raw: `outputs/segmentation_pilot/raw/fp_02_clean_simple.json`
- `fp_02_clean_simple` overlay: `outputs/segmentation_pilot/overlays/fp_02_clean_simple_overlay.jpg`
- `fp_03_complex_layout` raw: `outputs/segmentation_pilot/raw/fp_03_complex_layout.json`
- `fp_03_complex_layout` overlay: `outputs/segmentation_pilot/overlays/fp_03_complex_layout_overlay.jpg`
- `fp_04_complex_layout` raw: `outputs/segmentation_pilot/raw/fp_04_complex_layout.json`
- `fp_04_complex_layout` overlay: `outputs/segmentation_pilot/overlays/fp_04_complex_layout_overlay.jpg`
- `fp_05_iiif_rights` raw: `outputs/segmentation_pilot/raw/fp_05_iiif_rights.json`
- `fp_05_iiif_rights` overlay: `outputs/segmentation_pilot/overlays/fp_05_iiif_rights_overlay.jpg`
- `fr_01_binding_strip` raw: `outputs/segmentation_pilot/raw/fr_01_binding_strip.json`
- `fr_01_binding_strip` overlay: `outputs/segmentation_pilot/overlays/fr_01_binding_strip_overlay.jpg`
- `fr_02_text_block` raw: `outputs/segmentation_pilot/raw/fr_02_text_block.json`
- `fr_02_text_block` overlay: `outputs/segmentation_pilot/overlays/fr_02_text_block_overlay.jpg`
- `fr_03_marginal_gloss` raw: `outputs/segmentation_pilot/raw/fr_03_marginal_gloss.json`
- `fr_03_marginal_gloss` overlay: `outputs/segmentation_pilot/overlays/fr_03_marginal_gloss_overlay.jpg`
- `fr_04_decoration_initial` raw: `outputs/segmentation_pilot/raw/fr_04_decoration_initial.json`
- `fr_04_decoration_initial` overlay: `outputs/segmentation_pilot/overlays/fr_04_decoration_initial_overlay.jpg`
- `fr_05_damaged_irregular` raw: `outputs/segmentation_pilot/raw/fr_05_damaged_irregular.json`
- `fr_05_damaged_irregular` overlay: `outputs/segmentation_pilot/overlays/fr_05_damaged_irregular_overlay.jpg`

## Database Storage Summary
- Stored sample count: `10`
- Tables written: `segmentation_run`, `layout_region`
- Geometry strategy: SRID 0 polygons derived from bbox coordinates where persisted mask polygons were unavailable.

## Viewer Update
The local Streamlit viewer now lists both smoke-test and full-pilot segmentation runs, supports filtering by run type, and allows selecting multiple runs for the same sample.

## Known Issues
- The pilot run preserves outputs locally and in PostgreSQL/PostGIS only; it does not provide a production UI.
- The viewer is for local development/demo use and remains read-only.

## What Has Not Been Implemented
- No artificial fragment generation was implemented.
- No reconstruction was implemented.
- No retrieval was implemented.
- No MSI or CoMMA workflow was implemented.

## Next Step
Build the artificial fragment generator for complete-page samples.
