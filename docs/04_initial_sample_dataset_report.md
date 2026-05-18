# Fragment Autocomplete — Initial Sample Dataset Report

## 1. Purpose

This report documents registration of the initial pilot sample dataset from `autocomplete-test-dataset/`. It prepares metadata and database records for later eManuSkript segmentation testing.

This is a pilot sample dataset, not the full 5,000-10,000-page project dataset. eManuSkript has not been run, and model weights have not been loaded.

## 2. Dataset summary

- Dataset ID: `initial_sample_dataset_v0_1`
- Full-page samples: 5
- Fragment samples: 5
- Local files mapped: 10

## 3. Full-page samples

| ID | Category | Source | Local mapping | IIIF status | Purpose |
| --- | --- | --- | --- | --- | --- |
| `fp_01_clean_simple` | clean_simple | e-codices | matched | not_attempted | Simple full-page baseline for segmentation and artificial-fragment generation. |
| `fp_02_clean_simple` | clean_simple | e-codices | matched | not_attempted | Simple full-page baseline for segmentation and artificial-fragment generation. |
| `fp_03_complex_layout` | complex_layout | e-codices | matched | not_attempted | Complex page for testing glosses, initials, music, illustration, or multi-zone layout. |
| `fp_04_complex_layout` | complex_layout | e-codices | matched | not_attempted | Complex page for testing glosses, initials, music, illustration, or multi-column layout. |
| `fp_05_iiif_rights` | iiif_rights_metadata | e-codices | matched | not_attempted | Validate IIIF manifest extraction, image service extraction, rights metadata, and attribution. |

## 4. Fragment samples

| ID | Category | Source | Local mapping | IIIF status | Purpose |
| --- | --- | --- | --- | --- | --- |
| `fr_01_binding_strip` | binding_strip | Fragmentarium | matched | not_attempted | Real fragment case: binding strip or narrow reused fragment. |
| `fr_02_text_block` | text_block | Fragmentarium | matched | not_attempted | Real fragment case: visible main text block. |
| `fr_03_marginal_gloss` | marginal_gloss | Fragmentarium | matched | not_attempted | Real fragment case: marginal, gloss, or secondary text material. |
| `fr_04_decoration_initial` | decoration_initial | Fragmentarium | matched | not_attempted | Real fragment case: decoration, initials, or visually distinctive layout element. |
| `fr_05_damaged_irregular` | damaged_irregular | Fragmentarium | matched | not_attempted | Real fragment case: difficult damaged or irregular fragment. |

## 5. Local file mapping

Local images were matched by expected sample directory name. Unmatched items would be marked `missing` or `needs_review` in the resolved metadata.

## 6. IIIF resolution status

- Resolved: 0
- Unresolved: 0
- Not attempted: 10

Human viewer URLs were preserved for all samples. IIIF resolution can be repeated later with `--attempt-iiif-resolution`; unresolved viewer URLs do not block local registration.

## 7. Database registration summary

- Repositories inserted/matched: 0 / 2
- Manuscripts inserted/matched: 0 / 5
- Canvases inserted/matched: 0 / 5
- Image assets inserted/matched: 0 / 10
- Fragments inserted/matched: 0 / 5

## 8. Rights and access status

Rights are conservatively marked `pending_review`. Training, publication, and demo flags are false by default, and access level is `internal`.

## 9. Known issues / unresolved items

- Source URLs are human viewer URLs and may need further IIIF manifest resolution.
- Rights require explicit review before publication, demo use, or training use.
- Local file checksums are available in `data/metadata/local_assets_manifest.yaml`.

## 10. Readiness for eManuSkript segmentation test

The registered sample records are ready for model compatibility inspection and a controlled first eManuSkript segmentation test. No segmentation has been run yet.

## 11. Next steps

Inspect model weights compatibility and prepare the eManuSkript segmentation test.
