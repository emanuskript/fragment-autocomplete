# NEXT_ACTIONS

## Next recommended task

Run the first controlled eManuSkript segmentation smoke test.

## Acceptance criteria

- Install or verify the required `ultralytics` dependency in a controlled environment.
- Load `model weights/best_emanuskript_segmentation.pt`.
- Run inference on only the 2 prepared inputs.
- Save raw outputs, rendered overlays, and logs.
- Do not run on the full dataset.
- Do not store outputs in the database yet unless explicitly requested later.
- Produce a smoke-test report.
