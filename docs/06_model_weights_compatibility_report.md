# Fragment Autocomplete — Model Weights Compatibility Report

## Purpose

This report documents a compatibility inspection of the local model weight files in `model weights/`.

## Scope

This inspection is limited to static archive/pickle analysis and safe CPU-side checkpoint introspection. No inference was run, no segmentation was produced, no training was performed, and no model weights were committed.

## Model files inspected

- `model weights/best_catmus.pt`
- `model weights/best_emanuskript_segmentation.pt`
- `model weights/best_zone_detection.pt`

## Safety policy

- `trusted_pickle_load_used`: `false`
- Default inspection avoids arbitrary pickle execution.
- Safe `torch.load(..., weights_only=True, map_location='cpu')` is used only to detect whether the checkpoint can be interpreted without trusted globals.
- No model forward pass or prediction call was executed.

## Inspection method

- Reused SHA256 checksums from `data/metadata/local_assets_manifest.yaml` where available.
- Verified that the `.pt` files are zipped PyTorch archives.
- Parsed `data.pkl` strings with `pickletools` to identify embedded class names, task hints, and model-family strings.
- Used PyTorch safe weights-only loading to capture whether trusted pickle loading would still be required.

## Compatibility summary table

| Model | Size | Framework | Task | Safe load | Labels | Compatibility |
| --- | ---: | --- | --- | --- | ---: | --- |
| `best_catmus` | 347.9 MB | ultralytics_yolo_pytorch | segmentation | safe_weights_only_load_blocked | 19 | compatible_secondary_candidate |
| `best_emanuskript_segmentation` | 116.6 MB | ultralytics_yolo_pytorch | segmentation | safe_weights_only_load_blocked | 22 | recommended_for_first_smoke_test |
| `best_zone_detection` | 78.8 MB | ultralytics_yolo_pytorch | detection | safe_weights_only_load_blocked | 11 | compatible_for_detection_only |

## Per-model findings

### `best_catmus`

- Path: `model weights/best_catmus.pt`
- SHA256: `260297f0ef2f4acf007fdebc764cb1d23c7479799dc9cb9c283e156943400818`
- Likely framework: `ultralytics_yolo_pytorch`
- Detected task: `segmentation`
- Safe load status: `safe_weights_only_load_blocked`
- Trusted load required: `true`
- Detected keys: model, names, args, train_args, yaml, yaml_file, task, mode, data, epoch, optimizer, ema, updates, date, version, license
- Compatibility status: `compatible_secondary_candidate`

Findings:
- Weights only load failed. This file can still be loaded, to do so you have two options, do those steps only if you trust the source of the checkpoint. 
- Safe weights-only load was blocked by unsupported global `ultralytics.nn.tasks.SegmentationModel`.
- Static inspection used zip member `archive/data.pkl`.
- Detected 19 embedded class labels from static pickle strings.
- Unsupported global during safe load: `ultralytics.nn.tasks.SegmentationModel`.
- Future checkpoint deserialization will require either a trusted pickle load or an explicit safe-global allowlist.
- Segmentation checkpoint detected, but the checkpoint appears CATMuS-oriented rather than the primary eManuSkript baseline.

### `best_emanuskript_segmentation`

- Path: `model weights/best_emanuskript_segmentation.pt`
- SHA256: `9f0b03cc64c830d337a01ddac6a04616a385d573e3b923a86fc4c74c16416511`
- Likely framework: `ultralytics_yolo_pytorch`
- Detected task: `segmentation`
- Safe load status: `safe_weights_only_load_blocked`
- Trusted load required: `true`
- Detected keys: model, names, args, train_args, yaml, yaml_file, task, mode, data, epoch, optimizer, ema, updates, date, version, license
- Compatibility status: `recommended_for_first_smoke_test`

Findings:
- Weights only load failed. This file can still be loaded, to do so you have two options, do those steps only if you trust the source of the checkpoint. 
- Safe weights-only load was blocked by unsupported global `ultralytics.nn.tasks.SegmentationModel`.
- Static inspection used zip member `best/data.pkl`.
- Detected 22 embedded class labels from static pickle strings.
- Unsupported global during safe load: `ultralytics.nn.tasks.SegmentationModel`.
- Future checkpoint deserialization will require either a trusted pickle load or an explicit safe-global allowlist.
- Filename and embedded strings both point to the direct eManuSkript segmentation checkpoint.

### `best_zone_detection`

- Path: `model weights/best_zone_detection.pt`
- SHA256: `45afebac8a7dab15aed3c0716f4cf3c44705f63a81258c5dfa949f745c9330de`
- Likely framework: `ultralytics_yolo_pytorch`
- Detected task: `detection`
- Safe load status: `safe_weights_only_load_blocked`
- Trusted load required: `true`
- Detected keys: model, names, args, train_args, yaml, yaml_file, task, mode, data, epoch, optimizer, ema, updates, date, version, license
- Compatibility status: `compatible_for_detection_only`

Findings:
- Weights only load failed. This file can still be loaded, to do so you have two options, do those steps only if you trust the source of the checkpoint. 
- Safe weights-only load was blocked by unsupported global `ultralytics.nn.tasks.DetectionModel`.
- Static inspection used zip member `archive/data.pkl`.
- Detected 11 embedded class labels from static pickle strings.
- Unsupported global during safe load: `ultralytics.nn.tasks.DetectionModel`.
- Future checkpoint deserialization will require either a trusted pickle load or an explicit safe-global allowlist.
- Detection checkpoint detected; useful for zone detection but not the first segmentation smoke test.

## Detected labels/classes if any

### `best_catmus`

- Detected 19 labels: DamageZone, DefaultLine, DigitizationArtefactZone, DropCapitalLine, DropCapitalZone, GraphicZone, HeadingLine, InterlinearLine, MainZone, MarginTextZone, MusicLine, MusicZone, NumberingZone, QuireMarksZone, RunningTitleZone, SealZone, StampZone, TironianSignLine, TitlePageZone

### `best_emanuskript_segmentation`

- Detected 22 labels: Border, Table, Diagram, Music, Main script black, Main script coloured, Variant script black, Variant script coloured, Historiated, Inhabited, Zoo - Anthropomorphic, Embellished, Plain initial- coloured, Plain initial - Highlighted, Plain initial - Black, Page Number, Quire Mark, Running header, Catchword, Gloss, Illustrations, Ignore

### `best_zone_detection`

- Detected 11 labels: DigitizationArtefactZone, DropCapitalZone, GraphicZone, MainZone, MarginTextZone, MusicZone, NumberingZone, QuireMarksZone, RunningTitleZone, StampZone, TitlePageZone

## Required dependencies

- PyTorch is required for safe `weights_only=True` inspection and any future CPU-only smoke test.
- `ultralytics` is required before any trusted checkpoint deserialization or later segmentation smoke test can be attempted.
- The project should keep all checkpoint loading on CPU during the first controlled test.

## Recommended first model for segmentation test

- Model: `best_emanuskript_segmentation`
- Reason: It is a segmentation checkpoint, it appears directly tied to eManuSkript, and static inspection exposed embedded layout labels without requiring a trusted load.

## Risks and blockers

- All three checkpoints require trusted checkpoint deserialization or an explicit safe-global allowlist to load beyond static inspection.
- `ultralytics` is not currently installed in the environment, which blocks a controlled checkpoint load even if the files are trusted later.
- Static inspection alone does not prove runtime compatibility with the current Ultralytics version; it only identifies likely family, task, and labels.

## Next step

Prepare controlled segmentation test inputs.
