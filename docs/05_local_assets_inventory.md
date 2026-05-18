# Fragment Autocomplete — Local Assets Inventory

## 1. Purpose

This report inventories local dataset and model-weight inputs added to the repository working tree. It documents paths, sizes, file types, checksums, and git-protection status before dataset registration or model execution.

No eManuSkript run, model inference, dataset registration, IIIF downloading, reconstruction, retrieval, UI work, or ML training was performed.

## 2. Asset roots inspected

- `autocomplete-test-dataset`: exists
- `model weights`: exists

## 3. Summary table

| Asset root | Exists | Files | Directories | Total size |
| --- | --- | ---: | ---: | ---: |
| `autocomplete-test-dataset` | True | 14 | 12 | 73.1 MB |
| `model weights` | True | 3 | 0 | 543.2 MB |

## 4. Dataset folder inventory

Path: `autocomplete-test-dataset`

- Files: 14
- Directories: 12
- Total size: 73.1 MB
- Extensions: `.jpg` (10), `.md` (1), `[no extension]` (3)

## 5. Model weights inventory

Path: `model weights`

- Files: 3
- Directories: 0
- Total size: 543.2 MB
- Extensions: `.pt` (3)

## 6. File type summary

| Extension | Count |
| --- | ---: |
| `.jpg` | 10 |
| `.md` | 1 |
| `.pt` | 3 |
| `[no extension]` | 3 |

## 7. Largest files

| Path | Size | Kind |
| --- | ---: | --- |
| `model weights/best_catmus.pt` | 347.9 MB | model_weight |
| `model weights/best_emanuskript_segmentation.pt` | 116.6 MB | model_weight |
| `model weights/best_zone_detection.pt` | 78.8 MB | model_weight |
| `autocomplete-test-dataset/fragments/fr_04_decoration_initial/fragmentarium_F-5el0_amds_01_03a5_0001v.jp2_max.jpg` | 14.3 MB | image |
| `autocomplete-test-dataset/fragments/fr_02_text_block/fragmentarium_F-sf5d_Stams_STA_Frg_235_01r02r.jpg_max.jpg` | 10.6 MB | image |
| `autocomplete-test-dataset/full_pages/fp_02_clean_simple/e-codices_kba-Wett0004_009r_max.jpg` | 10.1 MB | image |
| `autocomplete-test-dataset/full_pages/fp_05_iiif_rights/e-codices_csg-0314_0003_max.jpg` | 9.6 MB | image |
| `autocomplete-test-dataset/full_pages/fp_03_complex_layout/e-codices_csg-0059_0002_max.jpg` | 9.0 MB | image |
| `autocomplete-test-dataset/full_pages/fp_01_clean_simple/e-codices_csg-0300_0005_max.jpg` | 8.5 MB | image |
| `autocomplete-test-dataset/fragments/fr_01_binding_strip/fragmentarium_F-cpkx_F19a_r.jp2_max.jpg` | 6.4 MB | image |
| `autocomplete-test-dataset/full_pages/fp_04_complex_layout/e-codices_ubb-F-IX-0068_0002r_max.jpg` | 3.3 MB | image |
| `autocomplete-test-dataset/fragments/fr_05_damaged_irregular/fragmentarium_F-knxa_LE_15_1_F_knxa_r.png_max.jpg` | 742.9 KB | image |
| `autocomplete-test-dataset/fragments/fr_03_marginal_gloss/fragmentarium_F-0dfk_hm52g0pw5h_00003_00000_voorplatv.jpg_max.jpg` | 352.4 KB | image |
| `autocomplete-test-dataset/fragments/.DS_Store` | 10.0 KB | unknown |
| `autocomplete-test-dataset/full_pages/.DS_Store` | 10.0 KB | unknown |
| `autocomplete-test-dataset/.DS_Store` | 6.0 KB | unknown |
| `autocomplete-test-dataset/Sample Dataset for Architecture Testing.md` | 1.2 KB | metadata_text |

## 8. Checksums and provenance

Structured checksums are recorded in `data/metadata/local_assets_manifest.yaml`. Checksums are computed with streaming SHA256 reads, so binary files are not loaded into memory.

The inventory records local filesystem evidence only. Repository/source provenance and rights-review status still need to be captured during initial sample dataset registration.

## 9. Git protection / ignored paths

The local asset roots and common large model/data extensions are ignored in `.gitignore`. The committed inventory files are metadata only and do not include dataset images or model-weight binaries.

Ignored local roots:

- `autocomplete-test-dataset/`
- `model weights/`

## 10. Risks and notes

- Local files may not yet have authoritative source provenance or rights metadata.
- Model-weight files are inventory-only; they have not been loaded, inspected internally, or executed.
- Dataset files should be registered into metadata before any segmentation test.
- Checksums identify local files but do not establish usage rights.

Detected likely model-weight files:

- `model weights/best_catmus.pt`
- `model weights/best_emanuskript_segmentation.pt`
- `model weights/best_zone_detection.pt`

## 11. Recommended next step

Register the initial sample dataset from `autocomplete-test-dataset/`.
