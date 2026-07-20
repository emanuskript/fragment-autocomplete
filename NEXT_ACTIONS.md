# NEXT_ACTIONS

## Next recommended task

Add PostgreSQL storage for generated artificial-fragment task metadata.

## Acceptance criteria

- Read `data/metadata/artificial_fragment_generation_results.yaml`.
- Insert or match rows in `artificial_fragment_task`.
- Preserve source canvas/image IDs, mask paths, crop transforms, random seeds, and ground-truth placement JSON.
- Do not store generated image binaries in PostgreSQL.
- Do not train any model or run reconstruction.
- Add a validation script that confirms stored task counts and required provenance fields.
- Keep evidence, generated evaluation tasks, and later reconstruction inference clearly separated.
