# Fragment Autocomplete — Minimal Segmentation Viewer

## Purpose

Provide a small local read-only interface for visually inspecting the two stored segmentation smoke-test samples and their database-backed metadata.

## Scope

This viewer is a local development tool, not the final project UI. It displays the already stored smoke-test segmentation outputs and related metadata from PostgreSQL/PostGIS plus local file paths for the original image and overlay.

## What the viewer displays

- The two stored smoke-test samples.
- The original local image referenced by `image_asset.local_path`.
- The saved segmentation overlay image referenced by stored smoke-test metadata.
- `segmentation_run` metadata including model name/path, status, output path, parameters, confidence summary, and timestamps.
- A `layout_region` table with label, confidence, reading order, region area, bbox/region WKT, and raw region JSON preview.

## Data sources

- PostgreSQL/PostGIS tables: `segmentation_run`, `layout_region`, `image_asset`
- Local files under `autocomplete-test-dataset/`
- Local smoke-test outputs under `outputs/segmentation_smoke_test/`

## How to run

Start the database if it is not already running:

```bash
bash scripts/db_start.sh
```

Validate the viewer data:

```bash
python3 scripts/validate_segmentation_viewer_data.py
```

Run the viewer:

```bash
bash scripts/run_segmentation_viewer.sh
```

## How to validate

```bash
bash scripts/validate_segmentation_viewer.sh
```

## Current samples available

- `fp_01_clean_simple`
- `fr_02_text_block`

## Known limitations

- This is a local development viewer only.
- No inference is run by the viewer.
- No reconstruction is implemented.
- No artificial fragment generation is implemented.
- No retrieval, MSI, or CoMMA features are implemented.
- The viewer reads already stored segmentation outputs from the database and local files; it does not edit database records.

## Next step

Build the artificial fragment generator for complete-page samples.
