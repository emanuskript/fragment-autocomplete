# NEXT_ACTIONS

## Next recommended task

Create concrete PostgreSQL/PostGIS database schema and migrations.

## Acceptance criteria

- PostgreSQL selected as primary DB.
- PostGIS extension enabled.
- SQL migrations created.
- Tables created for `repository`, `manuscript`, `witness`, `iiif_manifest_cache`, `canvas/page`, `image_asset`, `msi_asset`, `fragment`, `annotation`, `segmentation_run`, `layout_region`, `artificial_fragment_task`, `reconstruction_job`, `reconstruction_candidate`, `retrieval_embedding`, `text_witness_link`, `evaluation_run`, and `export_bundle`.
- Geometry/polygon representation defined.
- Rights fields included: `training_allowed`, `publication_allowed`, `demo_allowed`, `access_level`.
- Schema validation command added.
- No large images, MSI assets, generated datasets, or model binaries committed.
- No backend, frontend, IIIF ingestion, eManuSkript integration, retrieval system, or ML pipeline implementation bundled into this schema task unless explicitly requested.
