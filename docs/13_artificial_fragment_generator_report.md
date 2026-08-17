# Fragment Autocomplete — Artificial Fragment Generator v0.1.1 Report

## Purpose and scientific role

Version `artificial_fragment_generator_v0_1_1` creates deterministic artificial fragments from the five registered complete e-codices pages. The exported fragment is observed evidence composed only of source-page pixels. The complete page, source-coordinate masks, placement, and layout-survival values are hidden ground truth for later evaluation. No missing content is inferred, reconstructed, generated, or blended into the observed fragment.

## Implementation

The implementation extends `src/evaluation/artificial_fragments.py` and adds the focused `src/evaluation/layout_survival.py` helper. It supports rectangular and irregular masks, requested severity, deterministic seeds, crop extraction, positive or negative rotation, uniform scale, SHA-256 provenance, and forward/inverse affine transforms. The CLI supports both a controlled pilot and a single task:

```bash
python3 scripts/generate_artificial_fragments.py \
  --sample fp_01_clean_simple \
  --mask irregular \
  --severity 0.5 \
  --seed 42
```

Source images are opened read-only. Their SHA-256 values are calculated before and after generation, and output paths are rejected if they resolve to the source file.

## Coordinate spaces and mask semantics

Source page coordinate space contains the damage/survival masks, ground-truth contour and bounding box, and all layout-survival calculations. Observed fragment coordinate space contains the cropped, rotated, and scaled exported fragment and its local survival mask.

- Source survival mask: `255` means an observed source pixel survives; `0` means missing.
- Source damage mask: `255` means a source pixel was removed; `0` means it survives.
- Severity: damaged source pixels divided by all source-page pixels.
- Requested severity, measured severity, surviving fraction, pixel counts, and absolute severity error are stored for every task.

The metadata contains `source_to_observed_fragment_matrix` and `observed_fragment_to_source_matrix`. Matrices use continuous pixel-boundary coordinates with a top-left origin, x increasing right, and y increasing down. Expanded rotation dimensions follow Pillow's exact canvas-rounding rule.

## Pilot

The core pilot contains exactly 20 tasks:

```text
5 source pages × 2 mask families × 2 severities (0.30 and 0.60)
```

All core tasks use `rotation=0` and `scale=1`. Each page has one rectangular and one irregular task at each severity. Seeds are deterministically derived from the dataset ID, source sample, mask family, requested severity, base seed, and task group, then stored explicitly.

Measured severity stayed very close to each target. Across the core pilot, 0.30 targets measured from `0.2998980238` to `0.3000199540`, and 0.60 targets measured from `0.5999428107` to `0.6000242903`, well inside the absolute tolerance of `0.02`.

Three separate transformation sanity tasks use `fp_01_clean_simple` at severity `0.45`:

| Case | Rotation | Scale | Exported dimensions |
| --- | ---: | ---: | ---: |
| Positive rotation | 12° | 1.0 | 6034 × 7213 |
| Negative rotation | -9° | 1.0 | 5663 × 6946 |
| Non-unit scale | 0° | 0.8 | 3842 × 5076 |

These cases test transformation behavior without confounding the core mask/severity pilot.

## Metadata and artifacts

The compact committed manifest is `data/metadata/artificial_fragment_generation_results.yaml`. It indexes every task, its parameters, summaries, transforms, artifact paths, and checksums. Full per-task JSON beside the ignored outputs contains the complete region list. Together they preserve:

- Source sample, source path, image asset/canvas IDs, complete registered-source record, normalized metadata availability, rights/access metadata, source dimensions, and source SHA-256.
- Generation version, deterministic seed, mask family and family-specific parameters, requested/measured severity, surviving fraction, rotation, and scale.
- Source and observed contours/bounding boxes plus forward/inverse transforms.
- Artifact paths, dimensions, coordinate-space labels, and SHA-256 checksums.
- Database-ready mappings for the existing `artificial_fragment_task` fields; `database_write` remains false. A later importer should follow each checksummed per-task metadata path from the compact manifest.
- Per-region layout survival estimates and a per-fragment summary.

Each task writes a transparent fragment PNG, an observed-fragment survival mask, a full-page source survival mask, a full-page source damage mask, and JSON metadata under `outputs/artificial_fragments/v0_1_1/`. These generated binaries are git-ignored and must not be committed.

## Layout survival estimate

The stored eManuSkript pilot output currently provides detection bounding boxes, not pixel-level region masks. Consequently, the implementation uses:

```yaml
geometry_method: rasterized_bbox_xyxy
metric_name: layout_survival_estimate
```

Every bounding box is clipped to source bounds and rasterized as a half-open pixel rectangle before intersection with the source-coordinate survival mask. Every source region retains its source index/identifier, label, class ID, confidence, original and clipped bbox, original rasterized area, surviving area/fraction, complete-loss flag, geometry method, and segmentation-run provenance.

The per-fragment summary reports total, completely visible, partially visible, and completely lost region counts; labels completely lost; labels containing lost regions; and area-weighted surviving fractions grouped by label. These values are bbox-based structural estimates. They are not pixel-accurate segmentation-mask survival measurements.

## Validation

The complete repository test suite passes with 27 tests, including 16 generator-specific tests. The artifact validator also passes across the 20 core and three sanity tasks. Validation covers deterministic generation, source integrity, binary complementary masks, severity tolerance, bbox clipping, known and completely lost regions, transform round trips, rotation/scale dimensions, segmentation/source dimension agreement, source-overwrite prevention, task matrix coverage, checksums, and provenance fields.

## Known limitations

- Current layout survival is based on rasterized bounding boxes because the stored pilot output does not expose per-region segmentation masks.
- Irregular masks are controlled synthetic polygons and do not model the full physical, chemical, biological, binding, or handling damage found in real manuscript fragments.
- Rotation and scaling are image-space transformations; they do not model camera calibration, physical dimensions, or parchment deformation.
- Full-page ground-truth masks make the local pilot auditable but produce approximately 730 MB of ignored output. A later iteration may add lossless compact mask encoding while retaining the current PNG reference behavior.
- HSP-normalized metadata is preserved when present; the current resolved five-page registry does not contain populated HSP-normalized values, which is recorded explicitly rather than inferred.
- No database rows, reconstruction, retrieval, model training, LLM integration, recto/verso reasoning, or bifolium modelling are included.

## Next recommended iteration

Add idempotent PostgreSQL storage for the generated task metadata using the existing `artificial_fragment_task` table. Store paths and JSON provenance only, not image or mask binaries, and preserve the distinction between observed fragment evidence, hidden ground truth, bbox-based layout estimates, and future reconstruction inference.
