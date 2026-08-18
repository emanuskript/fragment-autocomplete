# NEXT_ACTIONS

## Next recommended task

Expand the training corpus from complete manuscript pages.

## Acceptance criteria

- Define a controlled expansion manifest for complete manuscript pages before downloading or processing bulk data.
- Record repository, manuscript, canvas, image-service, rights/access, and source-checksum provenance for every candidate page.
- Establish explicit inclusion/exclusion criteria for layout diversity, manuscript/source diversity, image quality, and permitted training use.
- Reuse the eManuSkript segmentation-mask workflow and retain restored instance masks as model evidence rather than manual ground truth.
- Keep complete pages, artificial-fragment evaluation tasks, and real damaged fragments as distinct dataset roles and splits.
- Add bounded dry-run and pilot modes before any large acquisition or processing run.
- Estimate storage and compute requirements before expansion and continue excluding downloaded pages, masks, and derived binaries from Git.
- Do not begin reconstruction, retrieval, LLM integration, or UI expansion as part of corpus preparation.
