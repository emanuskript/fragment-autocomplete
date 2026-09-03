# Data Directory

This directory is for registered project data only.

- `raw/<corpus>/<manuscript>/`: source JPEGs kept outside git except placeholders.
- `raw/<corpus>/_manifests/`: raw IIIF manifest snapshots kept outside git.
- `metadata/`: compact committed specifications, manifests, provenance, statistics, and validation records.
- `processed/`: reserved for other normalized derivatives; the validated segmentation pipeline does not store its masks here.

Segmentation masks, raw predictions, and overlays live under ignored `outputs/training_corpus_segmentation/`; Batch 01 uses the collision-free `outputs/training_corpus_segmentation/batch_01/` subtree. Compact run specifications, results, statistics, and validation records stay under `data/metadata/`. Other generated binaries live under ignored `outputs/`. Do not commit large source images, raw manifests, bulk derivatives, generated binaries, or model artifacts into this repository.
