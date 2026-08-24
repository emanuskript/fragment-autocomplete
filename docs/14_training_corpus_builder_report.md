# Training Corpus Builder v0.1 — Validation Report

## Scope and safety boundary

This milestone acquires and registers complete-page source representations from e-codices IIIF manifests. It does not train a model, generate artificial fragments, run reconstruction or retrieval, or assert that any source is approved for training. eManuSkript remains the optional downstream layout-analysis backbone.

The corpus manifest distinguishes source evidence from selection inference: every normalized canvas remains recorded as a candidate, selected page, or rejected page; every rejection carries the explicit comparator/rule evidence that triggered it. Pages without an obvious exclusion stay candidates rather than being silently discarded.

## Reproducible pipeline

1. Read the committed YAML specification and reject duplicate manuscript identifiers or manifest URLs.
2. Fetch each official IIIF manifest with the existing IIIF client; normalize v2/v3 metadata and HSP-aligned manuscript fields with the existing ingestion code.
3. Record explicit obvious exclusions, deterministically rank remaining candidates from the recorded seed, and select at most the configured page limit.
4. Assign train/validation/test at manuscript level from a separate recorded seed. Pages never receive an independent split.
5. Download selected complete-page representations atomically, calculate SHA-256, and reuse checksum-verified existing assets on rerun.
6. Register selected canvases through the existing `ingest_manifest()` repository/manuscript/cache/canvas/image-asset upserts. Downloaded bytes remain on the filesystem.

Raw IIIF manifests and source-page binaries are under ignored `data/raw/`. Full raw manifest JSON is checksummed and also preserved in `iiif_manifest_cache.manifest_json` when registration is enabled. The compact committed corpus manifest carries raw normalized metadata, source references, selection decisions, downloads, checksums, database identifiers, rights, and split provenance.

## Commands

One-manuscript dry run (harvest/selection only):

```bash
python3 scripts/build_training_corpus.py --dry-run --limit-manuscripts 1 --max-pages 1
```

Required five-manuscript validation acquisition and registration:

```bash
bash scripts/db_migrate.sh
python3 scripts/build_training_corpus.py --register
bash scripts/validate_training_corpus.sh
```

Prepare, but do not automatically run, the existing eManuSkript workflow:

```bash
python3 scripts/build_training_corpus.py --register --prepare-segmentation
```

Add `--run-segmentation` only when an explicit segmentation run is intended. The command delegates to `scripts/run_segmentation_pilot.py`; it does not duplicate model inference.

## Validation result

The validation build was rerun unchanged after initial download. All selected assets reported `verified_existing`, demonstrating that checksum-verified representations were not downloaded again. The database validator confirmed local paths, checksums, canvas/image relationships, `pending_review` rights state, and `training_allowed = false`.

- Corpus: `ecodices_training_source_validation_v0_1`
- Manuscripts: 5
- Selected pages: 15
- Pages/manuscript: min 3, max 3, mean 3.0
- Download dimensions available: 15 (width 2000–2000 px; height 2666–3166 px)

## Corpus statistics

### Repository distribution

- Aarau, Aargauer Kantonsbibliothek: 1
- Basel, Universitätsbibliothek: 1
- St. Gallen, Stiftsbibliothek: 3

### Rights review status

- pending_review: 15
- Explicitly training-allowed pages: 0

### Manuscript-isolated splits

- train: 3 manuscripts, 9 pages
- validation: 1 manuscripts, 3 pages
- test: 1 manuscripts, 3 pages

### Metadata completeness

- repository: 5/5 (100.0%)
- shelfmark: 5/5 (100.0%)
- title: 5/5 (100.0%)
- date: 5/5 (100.0%)
- language: 5/5 (100.0%)
- script: 0/5 (0.0%)
- material: 5/5 (100.0%)
- rights_statement: 5/5 (100.0%)
- license: 5/5 (100.0%)
- attribution: 5/5 (100.0%)

### Canvas decisions

- candidate: 1265
- rejected: 45
- selected: 15

All rejected canvases retain an explicit rule match and evidence in the corpus manifest. Unselected eligible canvases remain recorded as candidates.

## Validation interpretation and next boundary

This validates source acquisition and registration at 5 manuscripts × 3 pages. It does not complete the approximately 100-manuscript target and it does not authorize model training. Before expanding the specification, review the 45 explicit rejections, sample the retained candidates, confirm storage expectations, and conduct source-by-source rights review. The eventual training dataset must query only assets explicitly changed to `approved_for_training` and `training_allowed = true` through a separate reviewed process.
