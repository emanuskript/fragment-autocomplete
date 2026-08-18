# NEXT_ACTIONS

## Next recommended task

Add idempotent PostgreSQL storage for Artificial Fragment Generator v0.1.1 task metadata.

## Acceptance criteria

- Read and validate the compact `data/metadata/artificial_fragment_generation_results.yaml` index and each referenced, checksummed per-task JSON metadata file.
- Insert or match the 20 core pilot and three transformation-sanity records in `artificial_fragment_task` without rerunning generation.
- Preserve source canvas/image IDs, source SHA-256, mask paths and semantics, requested/measured severity, crop transforms, random seeds, ground-truth placement, and segmentation-mask layout-survival provenance in the existing JSONB fields.
- Preserve `geometry_method: segmentation_mask` for the refreshed full-page evidence and retain `rasterized_bbox_xyxy` only for explicitly identified legacy fallback records.
- Do not store generated image binaries in PostgreSQL.
- Do not add a migration unless a concrete incompatibility with the existing table is demonstrated.
- Do not train any model or run reconstruction.
- Add a validation script that confirms stored task counts and required provenance fields.
- Keep evidence, generated evaluation tasks, and later reconstruction inference clearly separated.
