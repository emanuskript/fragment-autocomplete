# Fragment Autocomplete - Artificial Fragment Generator Report

## Purpose

Document the first reproducible local artificial-fragment generation pass for complete-page samples.

## Scope

This step generates controlled local crop/mask tasks for evaluation groundwork. It does not train a model, write to PostgreSQL, run reconstruction, infer missing manuscript content, or claim that generated fragments are historical evidence.

## Summary

- Generation version: `artificial_fragment_generator_v0_1`
- Dataset ID: `initial_sample_dataset_v0_1`
- Source full pages: `5`
- Generated tasks: `10`
- Output directory: `outputs/artificial_fragments`
- Database write: `false`

## Generated Tasks

| Task | Source page | Mask family | Fragment | Mask |
| --- | --- | --- | --- | --- |
| `af_fp_01_clean_simple_rectangular` | `fp_01_clean_simple` | `rectangular` | `outputs/artificial_fragments/fragments/af_fp_01_clean_simple_rectangular.png` | `outputs/artificial_fragments/masks/af_fp_01_clean_simple_rectangular_mask.png` |
| `af_fp_01_clean_simple_irregular` | `fp_01_clean_simple` | `irregular` | `outputs/artificial_fragments/fragments/af_fp_01_clean_simple_irregular.png` | `outputs/artificial_fragments/masks/af_fp_01_clean_simple_irregular_mask.png` |
| `af_fp_02_clean_simple_rectangular` | `fp_02_clean_simple` | `rectangular` | `outputs/artificial_fragments/fragments/af_fp_02_clean_simple_rectangular.png` | `outputs/artificial_fragments/masks/af_fp_02_clean_simple_rectangular_mask.png` |
| `af_fp_02_clean_simple_irregular` | `fp_02_clean_simple` | `irregular` | `outputs/artificial_fragments/fragments/af_fp_02_clean_simple_irregular.png` | `outputs/artificial_fragments/masks/af_fp_02_clean_simple_irregular_mask.png` |
| `af_fp_03_complex_layout_rectangular` | `fp_03_complex_layout` | `rectangular` | `outputs/artificial_fragments/fragments/af_fp_03_complex_layout_rectangular.png` | `outputs/artificial_fragments/masks/af_fp_03_complex_layout_rectangular_mask.png` |
| `af_fp_03_complex_layout_irregular` | `fp_03_complex_layout` | `irregular` | `outputs/artificial_fragments/fragments/af_fp_03_complex_layout_irregular.png` | `outputs/artificial_fragments/masks/af_fp_03_complex_layout_irregular_mask.png` |
| `af_fp_04_complex_layout_rectangular` | `fp_04_complex_layout` | `rectangular` | `outputs/artificial_fragments/fragments/af_fp_04_complex_layout_rectangular.png` | `outputs/artificial_fragments/masks/af_fp_04_complex_layout_rectangular_mask.png` |
| `af_fp_04_complex_layout_irregular` | `fp_04_complex_layout` | `irregular` | `outputs/artificial_fragments/fragments/af_fp_04_complex_layout_irregular.png` | `outputs/artificial_fragments/masks/af_fp_04_complex_layout_irregular_mask.png` |
| `af_fp_05_iiif_rights_rectangular` | `fp_05_iiif_rights` | `rectangular` | `outputs/artificial_fragments/fragments/af_fp_05_iiif_rights_rectangular.png` | `outputs/artificial_fragments/masks/af_fp_05_iiif_rights_rectangular_mask.png` |
| `af_fp_05_iiif_rights_irregular` | `fp_05_iiif_rights` | `irregular` | `outputs/artificial_fragments/fragments/af_fp_05_iiif_rights_irregular.png` | `outputs/artificial_fragments/masks/af_fp_05_iiif_rights_irregular_mask.png` |

## Provenance and Ground Truth

Each task records the source page, source database identifiers, source metadata, HSP-aligned normalized metadata when available, rights/access status, mask family, random seed, crop transform, and exact ground-truth placement on the source canvas. These records prepare for later insertion into `artificial_fragment_task`.

## Known Limitations

- Generated fragment PNGs and masks are local outputs and should not be committed.
- The first pass uses simple rectangular and irregular crop masks only.
- No degradation, reconstruction, retrieval, MSI, CoMMA workflow, or model training is implemented here.

## Next Step

Add PostgreSQL storage for `artificial_fragment_task` records after reviewing the local generation metadata.
