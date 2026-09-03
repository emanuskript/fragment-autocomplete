# Data Directory

This directory is for registered project data only.

- `raw/<corpus>/<manuscript>/`: source JPEGs kept outside git except placeholders.
- `raw/<corpus>/_manifests/`: raw IIIF manifest snapshots kept outside git.
- `metadata/`: compact committed specifications, manifests, provenance, statistics, and validation records.
- `processed/`: reserved for other normalized derivatives; the validated segmentation pipeline does not store its masks here.

Segmentation masks, raw predictions, and overlays live under ignored `outputs/training_corpus_segmentation/`; other generated binaries live under ignored `outputs/`. Do not commit large source images, raw manifests, bulk derivatives, generated binaries, or model artifacts into this repository.
