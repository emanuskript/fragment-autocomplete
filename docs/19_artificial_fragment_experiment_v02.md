# Artificial Fragment Experiment v0.2 — segmentation-aware controlled validation

## Motivation and scope

This milestone measures how much of an acquired complete-page raster and its eManuSkript layout evidence survives controlled artificial fragmentation. It reuses the complete-page corpus, the unchanged `artificial_fragment_generator_v0_1_1`, and existing source-sized segmentation masks. It introduces no inference, model training, reconstruction, inpainting, retrieval, database migration, or manuscript content. CoMMA remains text/metadata support and is not a visual training dataset.

Surviving source pixels are evidence. Artificial removal is a reproducible experimental transformation, not a claim about historical damage. Segmentation masks are model-derived evidence, not manually annotated ground truth. Future reconstruction outputs would remain candidate scholarly hypotheses requiring external evidence and explicit uncertainty.

## Outlier review

The four Batch 01 flags were taken from the existing segmentation statistics, joined to registered pages and stored runs, and visually inspected using locally available source/overlay/mask evidence. The review is an assistant's documented evidence assessment, not human scholarly adjudication. Its decisions are bound to the exact artifact checksums; changed evidence invalidates the saved assessment and yields `requires_human_review`.

| Manuscript | Page | Sample identifier | Regions | Review classification | Evidence and limits |
| --- | --- | --- | ---: | --- | --- |
| fmb-cb-0902 | 8r | `6c1543ed764a6265f96a` | 0 | `probable_segmentation_failure` | Branching drawings and faint writing are visible despite no detections. |
| fmb-cb-0902 | 11v | `95c524bbf6593575149b` | 0 | `probable_segmentation_failure` | Diagonal writing and drawings remain unsegmented. |
| fmb-cb-0902 | 14r | `6538cbcb609973816c5a` | 0 | `probable_segmentation_failure` | A coloured drawing, cross-like shape and writing are visible despite no detections. |
| fmb-cb-0902 | 16v | `5e6ff8c7c454a2c27b94` | 2 | `requires_human_review` | Mean confidence 0.384884; individual confidences 0.292637 and 0.477132. A text mask covers part of a line; the `Embellished` mask covers a drawn head. Class correctness and completeness require expert assessment. |

All four are 2000 × 2666 acquired rasters in validation. No source, segmentation label, corpus membership, split, or rights decision was changed. The review JSON records source/canvas/manuscript asset IDs, registered run ID, model and run checksums, confidence statistics, artifact paths/checksums, flag reasons, observations and classification. No transcription, attribution, date, script or material identification was inferred from the images.

The combined corpus also contains an existing zero-detection validation page `a57947d883c928bdeae4` from `ubb-F-IX-0068`. The audit exposes it separately; it is not silently folded into the four Batch 01 reviews.

## Corpus diversity audit

The audit joins the immutable 15-page corpus and 70-page Batch 01 manifests to PostgreSQL. It checks the effective source set, source/canvas/manuscript relationships, rights, manuscript splits, declared segmentation runs, region identifiers and mask metadata. The separate original five-page/23-task pilot is protected as a legacy experiment, outside this 85-page corpus definition.

- **85 pages**, **19 page-bearing manuscripts**, **20 assigned manuscripts**; one assigned manuscript has zero selected pages.
- Derived page splits: **59 train / 13 validation / 13 test**. Page-bearing manuscript splits: **13 / 3 / 3**; assigned manuscript splits: **14 / 3 / 3**.
- All pages come through e-codices, representing ten recorded repositories. St. Gallen contributes 19/85 pages (22.35%). No individual manuscript contributes more than five pages (5.88%).
- All acquired widths are 2000 pixels; heights range 2471–3626, aspect ratios 0.551572–0.809389. These are raster dimensions, not physical manuscript dimensions.
- **85 stored segmentation runs**, **4230 model regions**, **4230 verified binary masks**. Regions/page: min 0, median 42, mean 49.764706, max 125. Union-mask coverage averages 0.316013 of the source raster; overlapping instances are counted once for coverage.
- `Main script black` accounts for **3889/4230 regions (91.94%)**. Border and Table each occur only once. Validation has no detected Border, Illustrations, Running header or Table regions. Test lacks six observed corpus classes; it remains frozen despite those gaps.
- All 20 assigned manuscripts lack populated script metadata. No palaeographical diversity conclusion follows from the stored data.

All 85 source checksums are recorded, but only **74 source files could be byte-verified locally**. Eleven files are macOS iCloud dataless placeholders. Read attempts timed out; macOS accepted download requests but did not make them locally readable during this milestone. The audit detects that state without repeated blocking reads and records deterministic path-specific errors. All segmentation predictions, overlays and masks remain locally available, so layout distributions cover all 85 pages. Image-size distributions use the existing acquired-image metadata, validated against local files where accessible. No byte-integrity claim is made for the unavailable eleven sources.

The existing database's width/height fields preserve advertised IIIF dimensions for all 85 pages. They differ from the acquired rasters. The audit verifies them against the original manifest dimensions; measurements use the checksummed local raster and its matching masks. The registration adapter supplies those verified acquired dimensions to the existing relationship validator, while retaining the complete original database source record. It does not rewrite source dimensions.

See [the generated diversity report](19a_corpus_diversity_audit.md) and `data/metadata/artificial_fragment_v02_corpus_audit.json` for distributions, per-page density, class counts by split and explicit availability gaps.

## Validation selection and frozen test policy

The stored validation split contains 13 pages across `ubb-F-IX-0068`, `fmb-cb-0902` and `sbs-gen0020`. Eligibility requires an accessible, checksum-verified source; a successful registered segmentation; matching dimensions and relationships; predictions/overlay; and a verified full-sized binary mask for every detected region. A successful empty detection set is retained with no region measurements.

Two validation pages have explicit `unavailable_local_artifact_icloud_dataless` rejections:

- `219352470825ee97ee12`: `sbs-gen0020`, 55v, `0113_sbs-gen0020_0055v.jpg`.
- `62eacd9afde4dc6a4efe`: `sbs-gen0020`, 32v, `0067_sbs-gen0020_0032v.jpg`.

They remain corpus members with their original splits; no other pages replace them. The selected set therefore contains **11 pages**, including all four Batch 01 outliers. The test set receives no v0.2 tasks. Test artifacts and metadata are inspected only for the requested structural/integrity audit, without changes, tuning or reconstruction experiments.

## Core experiment and measurement

The matrix is derived from eligible validation pages:

```text
11 eligible validation pages × 2 existing mask families × 2 severities = 44 tasks
```

Canonical families are `rectangular` and `irregular`; requested removed-pixel fractions are 0.30 and 0.60. Rotation is 0°, scale is 1. The rectangular generator retains a sampled rectangular crop. The irregular generator retains its existing calibrated polygon. These are controlled synthetic masks; they are not validated models of physical manuscript damage.

Seeds derive from the experiment version, page identity, fixed base seed 20260907, family, severity and an evidence fingerprint containing source/run/artifact checksums. Task names are deterministic, and registration uses the existing canonical scientific SHA-256/UUID5 convention. The generator version is retained separately from the v0.2 experiment version. Changing segmentation evidence changes v0.2 seeds and identities rather than overwriting an earlier scientific task.

For source-sized binary region mask `R` and survival mask `S`:

```text
source region area = count(R = 255)
surviving region area = count((R = 255) AND (S = 255))
removed region area = source region area − surviving region area
surviving fraction = surviving region area / source region area
removed fraction = removed region area / source region area
```

The entire segmentation raster is used, including any foreground pixels beyond its recorded bounding box. Mask binary values, checksum, dimensions and recorded area are checked before measurement. Missing/invalid masks never fall back to boxes. The legacy generator and its bbox-compatible estimator are unchanged; v0.2 calls generation without legacy region estimates and adds its separately validated full-raster measurements.

Each task stores requested/actual damage, surviving fraction and exact pixel counts, fragment dimensions, source-to-fragment/inverse transforms, source checksum, generated fragment/mask checksums, source/run provenance, and per-region IDs/classes/confidences/areas/fractions. Geometry is explicitly `segmentation_mask`. Source-page coordinates mean the acquired raster's coordinate system. Hidden complete-page evidence is kept distinct from observed fragment pixels and future inference.

Zero detected regions produce an empty list and `no_detected_regions`, with undefined area-weighted layout survival. They never count as fully removed manuscript content. Empty individual mask artifacts are rejected; the low-level overlap helper explicitly returns undefined fractions for a zero-area denominator.

Categories are defined once in `SURVIVAL_THRESHOLDS`: fully removed = 0; mostly destroyed = (0, 0.05]; partial = (0.05, 0.95); almost complete = [0.95, 1]. Aggregates group by family, requested severity, manuscript, page and region class, with task/region counts, mean, median, min, max and population standard deviation (undefined for fewer than two observations). Region statistics weight detected instances equally. A class's task count includes only tasks containing that class. Repeated transformations of one page are not independent manuscript observations.

## Artifacts and commands

Run with a Python environment containing the repository requirements. On this host the compatible interpreter is `/usr/bin/python3`; the other `python3` on PATH lacks PyYAML.

```bash
/usr/bin/python3 scripts/artificial_fragment_experiment.py audit
/usr/bin/python3 scripts/artificial_fragment_experiment.py generate
/usr/bin/python3 scripts/artificial_fragment_experiment.py register
/usr/bin/python3 scripts/artificial_fragment_experiment.py report
/usr/bin/python3 scripts/artificial_fragment_experiment.py check-determinism
/usr/bin/python3 scripts/artificial_fragment_experiment.py verify
# Explicit full recomputation, as distinct from verified reuse:
/usr/bin/python3 scripts/artificial_fragment_experiment.py generate --regenerate
```

Every command has `--help`. Unchanged `generate` validates and reuses existing tasks; `--regenerate` recomputes all eligible tasks with the same identities. Scientific JSON/Markdown contains no new timestamps. Stable writers preserve unchanged report bytes and mtimes. Explicit recomputation may rewrite generated binary mtimes; source/segmentation/legacy artifact mtimes remain protected.

Committed compact metadata uses prefix `data/metadata/artificial_fragment_v02_`: `review_decisions.json`, `outlier_review.json`, `corpus_audit.json`, `specification.json`, `generation.json`, `measurements.json`, `registration.json`, `validation.json`, and `determinism.json`. Full task JSON, source-space survival/damage masks, observed masks and fragments live under ignored `outputs/artificial_fragments/v0_2/tasks/`. The ignored `invariants_before.json` baseline records complete frozen-table hashes and available artifact hashes/sizes/mtimes; unavailable sources have explicit unverified availability records.

Generation/registration recheck validation-source state against the saved specification. The initial audit baseline is not silently refreshed if inputs change; changed source availability or evidence requires an explicit later experiment decision. Thus rehydrating the two rejected pages does not silently expand this saved experiment.

## Database registration and verification

The existing `artificial_fragment_task` table suffices. Measurements are queryable in `parameters.layout_survival_measurements`, with summaries, masks/checksums, transforms, complete source provenance, and experiment details under existing JSONB fields. Full metadata files are referenced by path and SHA-256. No binary data or duplicate source assets are inserted into PostgreSQL.

Registration checks that each source is still an eligible validation source and that its original rights/provenance record matches. It uses deterministic task UUIDs, rejects duplicate scientific configurations, and refuses updates to an existing v0.2 measurement row. All work occurs in one transaction; an error rolls it back. A second registration within the transaction must match every row without writes or timestamp churn. Frozen source/manuscript/canvas/repository/manifest/segmentation/region and legacy task table snapshots must remain identical.

## Execution results

The first generation produced **44 tasks and 604 per-region survival measurements**, all using full segmentation-mask overlap. Sixteen tasks (four source pages × four conditions) have no detected regions and contribute page-pixel metrics only. PostgreSQL inserted 44 task rows; the immediate unchanged rerun matched all 44 with zero inserts or updates.

Mean page-pixel survival is 0.700070 at requested severity 0.30 and 0.400051 at requested severity 0.60. Corresponding mean detected-region survival is 0.941220 and 0.671621. The rectangular and irregular families have mean detected-region survival 0.821520 and 0.791322, respectively. These descriptive statistics reflect the sampled masks and detected region positions; they do not establish that one family is more realistic or content is recoverable. See [the complete measurements report](19b_artificial_fragment_v02_measurements.md).

Full regeneration compared **229 artifacts**, including all **176 generated PNGs** and **44 full task JSON files**, and found identical bytes/checksums/identities. All 44 database rows and their timestamps matched the first registration. Recomputed aggregate summaries are identical. The deterministic result is saved in `artificial_fragment_v02_determinism.json`.

Validation commands:

```bash
/usr/bin/python3 -m pytest -q tests/evaluation/test_artificial_fragment_experiment.py tests/evaluation/test_artificial_fragments.py tests/evaluation/test_artificial_fragment_registration.py
/usr/bin/python3 -m pytest -q
```

The final full suite passes **133 tests** (including **30 new synthetic tests**), with one existing urllib3/LibreSSL environment warning. Coverage includes validation-only selection, derived matrix size, explicit missing-source rejection with preserved mask audit evidence, full-mask overlap outside bounding boxes, zero/full/partial survival, class aggregation and thresholds, deterministic generation/IDs/checksums, duplicate prevention, source/run/mask binding, DB rights/split/provenance checks, advertised/acquired dimensions, stable audits/reviews, and all existing v0.1 tests.

Final `verify` passed: all frozen database rows (including timestamps), the 4608 recorded artifact/availability entries, available source/segmentation/legacy checksums and mtimes, corpus assignments, rights, and the original 23 v0.1 tasks remained unchanged. All 13 test sources remained unchanged, and no test page generated a v0.2 task. The eleven unavailable sources retain explicit limits on byte verification. Fresh audit, outlier-review and aggregate results match their saved artifacts. The registration remains exactly 44 rows; no duplicates or timestamp churn occurred. Results are in `artificial_fragment_v02_validation.json`.

## Limitations and recommended next milestone

The substrate supports reproducible geometric measurement, but it is not sufficient evidence to begin a reconstruction baseline. Prioritize **a new immutable complete-page expansion batch targeting measured layout-class and repository/provider coverage gaps**, with explicit source-rights review and expert checking of eManuSkript class/coverage outliers. Separately restore reliable local availability/backup for existing source artifacts and review the physical plausibility of the simple damage families with manuscript specialists.

The evaluation is biased toward one provider and one dominant model class; four retained validation pages have zero detections, and two validation sources are unavailable. Coverage fractions include all pixels in the acquired raster, including photographic background and pre-existing visible loss; they are not physical page-support measurements. Mask restoration cannot recover detail absent from the inference raster. No mask/label/geometry result establishes semantic recoverability.

Training remains blocked by unchanged `pending_review` / `training_allowed: false` source authorization. No model training or reconstruction has begun. Expert review, corpus balance, damage-model validity, rights approval, and institutional storage/backup policy remain prerequisites for later decisions.

## Repository change inventory

Added implementation: `scripts/artificial_fragment_experiment.py`, `src/evaluation/corpus_audit.py`, `src/evaluation/artificial_fragment_experiment.py`, `src/evaluation/experiment_database.py`.

Added tests: `tests/evaluation/test_artificial_fragment_experiment.py`.

Added reports: this milestone report, `docs/19a_corpus_diversity_audit.md`, and `docs/19b_artificial_fragment_v02_measurements.md`.

Added nine compact metadata JSON artifacts listed in the artifact section. Modified `NEXT_ACTIONS.md` and `ROADMAP_STATUS.md`. Existing generator/registration code, schema, corpus manifests, splits and rights records are unchanged. Generated binaries, predictions, overlays, source assets, caches, model weights and database files are not part of the commit.
