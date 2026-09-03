# Fragment Autocomplete — Database Schema and Storage Plan

## 1. Purpose

This document describes the concrete PostgreSQL/PostGIS database foundation for Fragment Autocomplete. The schema supports source registration, manuscript/page metadata, image and MSI asset references, fragment geometry, annotations, eManuSkript-style segmentation outputs, artificial-fragment task records, reconstruction candidates, retrieval descriptors, text/metadata links, evaluation runs, and export bundles.

This milestone implements the database foundation only. It does not implement IIIF ingestion, eManuSkript integration, artificial-fragment generation, reconstruction, retrieval, ML, backend API, frontend UI, MSI viewer, CoMMA ingestion, or deployment.

## 2. Why PostgreSQL/PostGIS

PostgreSQL is the primary relational database because the project needs durable metadata, explicit provenance, rights fields, constraints, JSONB flexibility, and stable relational joins across manuscripts, pages, fragments, segmentation outputs, and reconstruction candidates.

PostGIS is enabled for page-local geometry. Fragment contours, bounding boxes, layout regions, page estimates, and placement geometries are not geographic coordinates, but they benefit from geometry types, GiST indexes, and spatial validation/query capabilities.

`pgcrypto` is enabled for `gen_random_uuid()` so all main tables use UUID primary keys without a backend framework or ORM.

## 3. What Belongs in the Database

The database stores:

- Normalized source, repository, manuscript, witness, canvas/page, and asset metadata.
- Source provenance, raw external metadata snapshots, rights, and access-control fields.
- URIs, local paths, checksums, dimensions, media types, and processing versions.
- Fragment contours, bounding boxes, layout regions, and candidate placement geometry.
- Segmentation run metadata and layout region records.
- Artificial-fragment generation parameters and ground-truth links.
- Reconstruction jobs and first-class reconstruction candidates.
- Retrieval descriptors and vector arrays for early retrieval support.
- CoMMA or other text/metadata links.
- Evaluation and export metadata.

## 4. What Does Not Belong in the Database

The database should not store large binary payloads as blobs. The following belong in object/file storage:

- Full manuscript images.
- Fragment images.
- MSI layers and MSI stacks.
- Masks and pixel-level segmentation outputs.
- Generated overlays.
- Exported PDFs, images, JSON bundles, PAGE-XML, ALTO, TEI, or RDF files.
- Model binaries and training artifacts.
- Large generated datasets.

The database stores paths, URIs, checksums, rights, metadata, and provenance for these files.

## 5. Object/File Storage Strategy

The schema assumes external object/file storage with stable path or URI references. The validated local prototype uses these concrete paths:

- `data/raw/<corpus>/<manuscript>/`: acquired source JPEGs.
- `data/raw/<corpus>/_manifests/`: raw IIIF manifest snapshots.
- `outputs/training_corpus_segmentation/`: eManuSkript segmentation masks, raw predictions, and overlays.
- `outputs/`: other generated binary artifacts and reports.
- `data/metadata/`: compact committed specifications, manifests, provenance, statistics, and validation records.
- `models/`: model artifacts kept outside git.

`data/processed/` remains available for other normalized derivatives, but it is not the destination of the validated segmentation-mask workflow. Existing files do not need to be moved to conform to an older planned layout. Source and generated binaries remain git-ignored.

Batch 01 contains 15 assigned manifests, of which 14 are active in the final selection. Its 70 acquired source JPEGs occupy 96,587,059 bytes. This local acquisition is not blocked by the still-unresolved institutional choices for GWDG or other object storage, backup, retention, and quota.

Every stored file reference should include checksum, media type, source provenance, rights, and version metadata when available.

## 6. Coordinate and Geometry Strategy

PostGIS geometry uses SRID `0` because coordinates are page-local pixel or normalized page coordinates, not geographic coordinates.

Geometry columns include:

- `fragment.contour_geom`
- `fragment.bbox_geom`
- `annotation.geometry_geom`
- `layout_region.region_geom`
- `layout_region.bbox_geom`
- `reconstruction_candidate.estimated_canvas_geom`
- `reconstruction_candidate.estimated_fragment_geom`

The first schema uses `geometry(Polygon, 0)` for contours, bounding boxes, layout regions, and candidate estimates. `annotation.geometry_geom` uses `geometry(Geometry, 0)` to allow points, lines, polygons, or mixed annotation geometries.

## 7. Rights and Access-Control Strategy

Rights fields are included on asset and output tables where publication or training permissions matter:

- `rights_statement`
- `license`
- `attribution`
- `training_allowed`
- `publication_allowed`
- `demo_allowed`
- `access_level`

`access_level` is constrained to:

- `private`
- `internal`
- `restricted`
- `public`

Default permissions are conservative. Training, publication, and demo flags default to `false`; access defaults to `private`.

Acquisition and training authorization are separate operations. Ordinary ingestion may refresh harvested source fields such as license, rights statement, attribution, and repository-supplied access information. It must not overwrite human-reviewed `rights_review_status` or `training_allowed`, and it must preserve the associated reviewer, authority/source, reason, timestamp, and version provenance. New acquisitions remain `pending_review` and `training_allowed = false`; no source license automatically approves model training.

The existing columns already represent the reviewed status and authorization flag, while versioned review provenance is stored in `image_asset.raw_metadata.rights_review`. The rights-persistence fix therefore requires no schema migration.

## 8. Core Entity Overview

The schema centers on these entity groups:

- Source and descriptive metadata: `repository`, `manuscript`, `witness`, `iiif_manifest_cache`, `canvas`.
- Assets and fragments: `image_asset`, `msi_asset`, `fragment`.
- Human or system interpretation: `annotation`, `segmentation_run`, `layout_region`.
- Controlled evaluation data: `artificial_fragment_task`, `evaluation_run`.
- Reconstruction workflow: `reconstruction_job`, `reconstruction_candidate`.
- Retrieval and text support: `retrieval_embedding`, `text_witness_link`.
- Outputs: `export_bundle`.

## 9. Table-by-Table Explanation

`repository` stores source institutions or digital repositories such as SUB Göttingen / GDZ, Fragmentarium, e-codices, Biblissima, Gallica / BnF, Digital Bodleian, and CoMMA.

`manuscript` stores codicological manuscript groupings linked to repositories when known.

`witness` stores textual or manuscript witnesses, including possible CoMMA links and text URLs.

`iiif_manifest_cache` stores raw IIIF manifest JSON and fetch provenance.

`canvas` stores IIIF canvas or local manuscript page records with pixel and physical dimensions.

`image_asset` stores registered image file or IIIF image-service references, not image blobs.

`image_asset.rights_review_status` records whether a source is still pending review, explicitly approved for later training use, not approved, or needs review. Training Corpus Builder v0.1 creates assets conservatively as `pending_review` with `training_allowed = false`. On later ingestion reruns, reviewed training authorization and its versioned `raw_metadata.rights_review` provenance take precedence over harvested defaults.

`msi_asset` stores aligned MSI layer or stack references linked to an image asset.

`fragment` stores surviving manuscript fragment records, including contour and bounding-box geometry.

`annotation` stores expert or system annotations against polymorphic targets.

`segmentation_run` stores eManuSkript or other layout-model run metadata.

`layout_region` stores detected manuscript layout regions, labels, confidence values, polygons, bounding boxes, and mask paths.

`artificial_fragment_task` stores synthetic fragment generation metadata from complete pages.

`reconstruction_job` stores candidate-generation job metadata.

`reconstruction_candidate` stores ranked reconstruction hypotheses as first-class records.

`retrieval_embedding` stores early retrieval vectors as `FLOAT8[]` and descriptor JSON. `pgvector` can be added later if needed.

`text_witness_link` stores CoMMA or other text/metadata links.

`evaluation_run` stores metric batches, expert rubrics, and failure taxonomies.

`export_bundle` stores generated export package metadata and rights status.

## 10. How the Schema Supports IIIF Ingestion

The schema supports IIIF ingestion through:

- `repository` for source ownership.
- `iiif_manifest_cache` for raw manifest JSON, fetch status, ETag, and last-modified metadata.
- `canvas` for manifest canvases or local page records.
- `image_asset` for IIIF Image API service URLs and registered image references.
- JSONB fields for raw source metadata while normalized fields remain queryable.

The local IIIF parser and manifest-cache path are implemented and reused by Training Corpus Builder v0.1. The builder filters the normalized manifest to selected canvases, then calls the existing ingestion transaction; it does not introduce a parallel source model. Raw IIIF manifests remain in `iiif_manifest_cache.manifest_json` and as checksummed snapshots under the corpus `_manifests/` directory, while `image_asset.local_path` and `checksum_sha256` identify the downloaded filesystem representation. Batch 01 registers 15 assigned manuscript manifests and 70 selected pages from 14 active manuscripts through this same path.

## 11. How the Schema Supports eManuSkript Outputs

The schema supports eManuSkript outputs through:

- `segmentation_run` for model name, version, parameters, status, output paths, and raw output metadata.
- `layout_region` for semantic layout labels, label IDs, confidence values, polygons, bounding boxes, reading order, area, mask paths, and raw region payloads.
- GiST indexes on layout-region geometry.

The controlled eManuSkript pilot is implemented and stored. Complete-page regions retain source-sized binary instance-mask paths as authoritative model evidence, while bounding boxes remain queryable metadata and an explicit fallback for legacy maskless runs.

## 12. How the Schema Supports Artificial Fragments

`artificial_fragment_task` links generated fragment tasks to complete source pages and images. It records mask family, random seed, crop transform, degradation profile, ground-truth placement, split name, generation version, and parameters.

The controlled v0.1.1 pilot now registers 20 core tasks and three transformation-sanity tasks through `scripts/register_artificial_fragment_tasks.py`. Each task ID is a deterministic UUIDv5 derived from a canonical SHA-256 identity over the source sample/checksum, generator version, mask family, seed, requested severity, rotation, scale, and realized mask parameters. The identity payload and digest are also retained in JSONB. This provides idempotency without a new uniqueness migration: an unchanged rerun matches the same row and does not change `updated_at`; duplicate configurations in one input manifest are rejected before database writes.

`source_canvas_id` and `source_image_asset_id` are checked against the registered source relationship, and the eManuSkript segmentation-run provenance must resolve to the same image asset. Source files and every referenced fragment/mask/metadata artifact are checked locally against recorded paths, dimensions, and SHA-256 values before insertion. A conflicting non-null source checksum in `image_asset` is rejected.

Only paths, checksums, dimensions, transforms, provenance, generation settings, per-region layout-survival measurements, and summaries are stored. The approximately 730 MB of generated image and mask binaries remain ignored filesystem artifacts. `generated_fragment_image_asset_id` remains null because no generated binary asset is registered in this milestone.

## 13. How the Schema Supports Reconstruction Candidates

`reconstruction_candidate` is a first-class table. It links to a `reconstruction_job` and a `fragment`, supports ranked candidates, stores canvas estimates, physical dimensions, placement transforms, estimated geometries, layout JSON, score, uncertainty, provenance, linked analogues, output paths, and review status.

This design allows a fragment to have multiple competing scholarly hypotheses rather than a single final answer.

## 14. How the Schema Supports Evaluation

`evaluation_run` stores metric outputs, expert rubric payloads, failure taxonomy data, evaluator identity, dataset split, and timing metadata. It can target artificial-fragment tasks, reconstruction candidates, model runs, or other entities through `target_type` and `target_id`.

The detailed evaluation rubric remains a later documentation and implementation task.

## 15. How the Schema Supports Export

`export_bundle` stores export package metadata for PDF, image, JSON, PAGE-XML, ALTO, TEI, or later RDF/LOD outputs. It records whether the bundle includes observed evidence, inferred structure, or illustrative fill.

Exports remain linked to fragment and/or reconstruction candidate records and preserve rights metadata.

## 16. HSP / German Normdata Metadata Alignment

The schema now includes a metadata standards extension for HSP-aligned catalogue data and German library controlled vocabularies.

The extension adds:

- `controlled_vocabulary` and `controlled_term` for `SCRP`, `FORM`, `CODC`, `BNDG`, and simplified HSP values.
- `metadata_controlled_term_assignment` for validated controlled-term assignments to project records.
- HSP/GND identity fields on `repository`.
- HSP-aligned manuscript fields for object status/form, material, format, origin/date, script, layout, decoration, persons, and organisations.
- Page-level observation fields on `canvas`.
- rights URI and processing fields on `image_asset`.
- fragment-specific codicological fields and `fragment_location`.

The standards alignment does not replace `raw_metadata`. Source metadata remains preserved there, while normalized fields are populated only when values are detectable or reviewed.

## 17. Migration and Validation Commands

Start the local database:

```bash
bash scripts/db_start.sh
```

Apply migrations and seed values:

```bash
bash scripts/db_migrate.sh
```

Validate the schema:

```bash
bash scripts/db_validate.sh
```

Import and validate HSP/German normdata:

```bash
python3 scripts/extract_hsp_metadata_standards.py --verbose
python3 scripts/import_hsp_normdata.py --verbose
bash scripts/validate_hsp_metadata_alignment.sh
```

Register and validate the artificial-fragment task pilot:

```bash
python3 scripts/register_artificial_fragment_tasks.py --verbose
bash scripts/validate_artificial_fragment_task_registration.sh
```

Reset the local database volume:

```bash
bash scripts/db_reset.sh --yes
```

Run full workspace validation:

```bash
bash scripts/check_workspace.sh
```

## 18. Known Limitations and Next Steps

Known limitations:

- The local storage convention is fixed for the current prototype, but the GWDG or other institutional object-storage target, backup policy, retention policy, and quota still need confirmation. This does not block validated local acquisition.
- `pgvector` is not enabled yet; retrieval vectors are stored as `FLOAT8[]` and descriptor JSON for now.
- Polymorphic references such as `annotation.target_id` and `evaluation_run.target_id` are not enforced by foreign keys.
- The schema supports IIIF, eManuSkript outputs, artificial fragments, reconstruction candidates, evaluation, and export. IIIF ingestion, pilot segmentation, segmentation-mask storage, the local viewer, artificial-fragment generation, and idempotent task registration exist as local proof-of-concept workflows; reconstruction, retrieval, training, MSI, CoMMA ingestion, and deployment remain unimplemented.
- HSP/normdata fields are available, but most pilot sample metadata is still `needs_review` until cataloguing values are reviewed or imported from authoritative source records.

Next step:

Run the existing eManuSkript segmentation, source-sized mask, provenance, and database-storage pipeline over the 70 acquired Batch 01 pages. Preserve source checksums, manuscript-isolated splits, and pending rights review, and do not begin model training.
