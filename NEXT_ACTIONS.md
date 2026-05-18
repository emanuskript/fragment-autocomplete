# NEXT_ACTIONS

## Next recommended task

Inspect model weights compatibility and prepare the eManuSkript segmentation test.

## Acceptance criteria

- Inspect local `.pt` files without training.
- Identify likely framework and loading requirements.
- Identify label mapping if available.
- Create model compatibility report.
- Do not run full segmentation until sample images and model compatibility are confirmed.
- If compatibility is confirmed, prepare a controlled first segmentation run on 1-2 registered sample images.
- Do not implement reconstruction, retrieval, ML training, frontend UI, CoMMA ingestion, or deployment as part of this compatibility task unless explicitly requested.
