# NEXT_ACTIONS

## Next recommended task

Store segmentation smoke-test outputs in the database.

## Acceptance criteria

- Parse smoke-test raw outputs.
- Create `segmentation_run` records.
- Create `layout_region` records where polygons, boxes, labels, and confidences are available.
- Link outputs to `image_asset`, `fragment`, and `canvas`.
- Preserve model name, version/path, parameters, confidence, output paths, and provenance.
- Validate database records.
