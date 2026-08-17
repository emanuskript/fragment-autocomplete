# NEXT_ACTIONS

## Next recommended task

Add idempotent PostgreSQL storage for Artificial Fragment Generator v0.1.1 task metadata.

## Acceptance criteria

- Read and validate the compact `data/metadata/artificial_fragment_generation_results.yaml` index and each referenced, checksummed per-task JSON metadata file.
- Insert or match the 20 core pilot and three transformation-sanity records in `artificial_fragment_task` without rerunning generation.
- Preserve source canvas/image IDs, source SHA-256, mask paths and semantics, requested/measured severity, crop transforms, random seeds, ground-truth placement, and bbox-based layout-survival provenance in the existing JSONB fields.
- Keep `geometry_method: rasterized_bbox_xyxy` and `layout_survival_estimate` terminology; do not imply pixel-accurate segmentation-mask survival.
- Do not store generated image binaries in PostgreSQL.
- Do not add a migration unless a concrete incompatibility with the existing table is demonstrated.
- Do not train any model or run reconstruction.
- Add a validation script that confirms stored task counts and required provenance fields.
- Keep evidence, generated evaluation tasks, and later reconstruction inference clearly separated.
