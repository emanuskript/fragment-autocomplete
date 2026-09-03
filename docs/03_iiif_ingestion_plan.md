# Fragment Autocomplete — IIIF Ingestion Proof of Concept

## 1. Purpose

This document describes the IIIF ingestion foundation for Fragment Autocomplete. The implementation reads IIIF Presentation manifests, normalizes key manifest/canvas/image fields, caches the raw manifest JSON, and registers repository, manuscript, canvas/page, and image asset records in PostgreSQL. Training Corpus Builder v0.1 reuses this path for bounded e-codices source acquisition rather than introducing a parallel registrar.

## 2. Scope of the Proof of Concept

The scope is intentionally narrow:

- Load a manifest from a local JSON file or remote URL.
- Normalize common IIIF Presentation API v2 and v3 structures.
- Cache raw manifest JSON.
- Create or update normalized database records.
- Register image URLs and IIIF Image API service URLs.
- Preserve rights, attribution, and raw metadata.
- Avoid downloading full-resolution image sets.

## 3. Supported IIIF Versions

The proof of concept supports common IIIF Presentation API v2 and v3 manifest patterns.

For v2 it reads `sequences[0].canvases`, canvas dimensions, `images[0].resource`, resource image URLs, format, dimensions, and `resource.service`.

For v3 it reads `items` as canvases, annotation pages, image annotation bodies, body image URLs, format, dimensions, and image service entries.

## 4. What Is Extracted From Manifests

The normalizer extracts:

- Manifest identifier.
- Manifest label/title.
- Manifest metadata.
- Rights/license.
- Attribution or provider statement.
- Canvas identifiers.
- Canvas labels.
- Canvas width and height.
- Canvas sequence index.
- Image URL.
- IIIF Image API service URL.
- Media type.
- Image width and height.
- Raw source metadata.

## 5. Database Write Path

The ingestion path writes to:

- `repository`
- `manuscript`
- `iiif_manifest_cache`
- `canvas`
- `image_asset`

The raw manifest is cached in `iiif_manifest_cache.manifest_json`. Normalized manuscript, canvas, and image records retain raw source payloads in JSONB `raw_metadata` fields.

## 6. Rights and Attribution Handling

Rights handling is conservative. Public web access does not imply training, publication, or demo permission.

Defaults:

- `training_allowed = false`
- `publication_allowed = false`
- `demo_allowed = false`
- `access_level = internal`
- `rights_review_status = pending_review`

If the manifest contains clearly open rights such as CC0, Public Domain Mark, or CC BY, the ingestion code may set `publication_allowed` and `demo_allowed` to `true`. `training_allowed` remains `false` until project policy is reviewed.

Acquisition is allowed independently from training approval. Harvested source fields such as license, rights statement, attribution, and repository-supplied access information may be refreshed on ingestion. Human-reviewed training fields have precedence: ordinary ingestion must preserve `rights_review_status`, `training_allowed`, and the versioned reviewer, authority/source, reason, timestamp, and decision provenance stored in `image_asset.raw_metadata.rights_review`. A CC0 or CC BY-NC source is therefore not automatically training-approved.

The existing `image_asset` columns and JSONB `raw_metadata` can represent this separation, so the persistence fix requires no schema migration.

## 7. Idempotency Strategy

The ingestion code avoids duplicate records through:

- `repository.name` upsert.
- `iiif_manifest_cache.manifest_url` upsert.
- Manuscript lookup by repository and manifest key stored in `raw_metadata`.
- Canvas lookup by manifest cache and canvas identifier.
- Image asset lookup by canvas, source URL, and IIIF image service URL.

Running the same fixture twice should update or confirm existing rows rather than create duplicate normalized records.

The corpus builder adds file-level resume protection: a selected local representation is reused only when its recorded SHA-256 still matches. Manifest and canvas duplicate checks run before registration, and all pages from a manuscript inherit one deterministic dataset split.

An ingestion rerun may refresh harvested rights metadata, but it does not reset or promote reviewed training authorization. A checksum mismatch is reported rather than accepted as an unchanged local asset.

## 8. What Is Intentionally Not Implemented

This proof of concept does not:

- Download full-resolution image sets.
- Implement a web UI.
- Implement a backend API.
- Run eManuSkript.
- Register curated project sample data beyond fixture/demo validation records.
- Generate artificial fragments.
- Run reconstruction, retrieval, or ML models.
- Ingest CoMMA data.
- Deploy any service.

## 9. How to Run Ingestion From a Local File

Install the minimal Python dependencies first:

```bash
python3 -m pip install -r requirements.txt
```

```bash
python3 scripts/ingest_iiif_manifest.py \
  --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json \
  --repository "Fixture Repository"
```

## 10. How to Run Ingestion From a URL

```bash
python3 scripts/ingest_iiif_manifest.py \
  --url "https://example.org/iiif/manifest.json" \
  --repository "Example Repository"
```

## 11. How to Run Dry-Run Mode

```bash
python3 scripts/ingest_iiif_manifest.py \
  --file tests/ingestion/fixtures/iiif_v3_minimal_manifest.json \
  --repository "Fixture Repository" \
  --dry-run
```

Dry-run mode parses and normalizes the manifest without writing to the database.

## 12. How to Validate Ingestion

Start the database and apply migrations:

```bash
bash scripts/db_start.sh
bash scripts/db_migrate.sh
```

Run validation:

```bash
bash scripts/validate_iiif_ingestion.sh
```

The validation script runs normalizer tests, ingests the local v2 and v3 fixtures, and checks that fixture records exist in the database.

## 13. Known Limitations

- The normalizer handles common v2/v3 patterns, not the full IIIF specification.
- It does not resolve nested collections.
- It does not download or tile images.
- It does not infer shelfmarks or dates beyond simple manifest metadata labels.
- It does not perform rights-policy review beyond conservative defaults and simple open-license detection.
- It does not create fragment records.

## 14. Corpus Builder Extension

The committed five-manuscript validation specification is `data/metadata/training_corpus_validation_spec.yaml`. `scripts/build_training_corpus.py` harvests the same normalized IIIF records, preserves raw manifests under ignored `data/raw/`, records candidate/selected/rejected canvases with reasons, downloads selected representations atomically, stores SHA-256 and rights-review state in `image_asset`, and emits the corpus manifest/statistics report.

```bash
python3 scripts/build_training_corpus.py --register
PYTHON_BIN=python3 bash scripts/validate_training_corpus.sh
```

The validation run acquires source pages only. It does not approve them for training or run eManuSkript automatically.

Batch 01 uses the same builder, downloader, and registration path with explicit manual-review decisions:

```bash
PYTHON_BIN=/usr/bin/python3 bash scripts/validate_training_corpus_expansion_batch.sh
PYTHON_BIN=/usr/bin/python3 bash scripts/validate_training_corpus_expansion_batch_01_acquisition.sh
```

The final batch retains 15 assigned manifests and their 11/2/2 manuscript split. One train-split manuscript is explicitly unsuitable for the training corpus, leaving 14 active manuscripts, 70 acquired pages, and active manuscript/page splits of 10/2/2 and 50/10/10. The 70 checksum-verified JPEGs occupy 96,587,059 bytes. The acquisition rerun reuses unchanged local assets and reconciles existing database relationships rather than creating duplicate files or rows.

The implemented local layout is `data/raw/<corpus>/<manuscript>/` for source JPEGs, `data/raw/<corpus>/_manifests/` for raw manifests, `outputs/training_corpus_segmentation/` for later segmentation artifacts, `outputs/` for other generated binaries, and `data/metadata/` for compact committed records. GWDG or other institutional object storage, backup, retention, and quota remain unresolved operational questions, but they do not block local acquisition.

## 15. Next Steps

Run the already validated eManuSkript segmentation and source-sized mask/storage workflow over the 70 acquired Batch 01 pages. Do not introduce a parallel segmentation implementation or begin model training.
