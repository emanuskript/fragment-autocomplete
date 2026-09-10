# Artificial Fragment Experiment v0.3 — Codicologically Structured Damage

Status: implementation and initial generation in progress; final validation results are recorded below only after successful execution.

## Scientific purpose and boundaries

The experiment asks how the position and topology of controlled synthetic page loss affect retention of known layout evidence at equal nominal severity. Source rasters remain known source truth. eManuSkript / “Manuskripte digital lesen lernen” supplies the central layout-analysis backbone; its segmentation masks are model evidence, with uncertainty about omissions and labels. CoMMA remains text/metadata support.

This milestone creates evaluation data only. No training, reconstruction, inpainting, palaeographical prediction, missing historical content inference, Batch 02 acquisition, or bifolium inference is performed. These damage mechanisms are geometric comparators for scholarly discussion, not validated historical damage distributions. Any future reconstruction must remain a candidate scholarly hypothesis with evidence and inference separated.

## Relationship to v0.2

The branch starts at completed v0.2 commit `223c92837e4a9929422ca4a2852eb967c7ac3743`. At branch creation, `origin/main` was `5e8f36a8ea6a9202a27b8cccd4c859912747b5ae`. v0.1's 23 tasks and v0.2's 44 tasks, specifications, measurements, reports and database rows remain historical controls. The old rectangular and irregular generator implementations are unchanged.

v0.2 used 11 of 13 validation pages and produced 604 region observations. It recorded eleven unavailable source files, including two validation pages. It also found four `fmb-cb-0902` segmentation outliers, 91.94% Main script black dominance, and four observed classes absent from validation. Historical v0.2 reports continue to describe their original availability state; they are not rewritten to reflect restoration.

## Exact-source restoration

`data/metadata/artificial_fragment_v03_availability.json` records all 85 registered sources, including asset/page/manuscript identity, split, original path, registered checksum, acquisition URL, initial/current availability, exact local-copy candidates and restoration outcome. The status vocabulary is `available`, `restored_checksum_verified`, `unavailable_local`, `restoration_failed`, and `requires_manual_action`.

All eleven unavailable paths existed as Darwin/iCloud dataless placeholders. No checksum-identical alternative was found under the project's data tree. The existing `training_corpus.download_resumable` helper downloaded each registered URL into temporary ignored staging. Each result passed the original SHA-256, byte size and readable-image dimensions before atomic promotion to its original path. Staging was removed, original mtimes were preserved, and no alternate persistent source records or paths were introduced. A readable but mismatched existing asset is never overwritten automatically. Network failures and unsupported restoration paths receive explicit deterministic statuses.

The result is 74 already available sources, 11 restored with exact checksum verification, and zero still unavailable. Restored pages are `sbs-gen0020` 55v and 32v (validation); `bcj-A2437` 161, `bke-0056` 72v and 92r, `ubb-F-I-0021` 75r, `bc-b-0067` 42v, `ubb-A-II-0013` 95v and 100r, `kba-Wett0004` 9v, and `bbb-AA0091` 31r (train). No test source required restoration.

Restoration is explicitly separated from subsequent frozen-source checks. The ignored `before_restoration.json` snapshot permits only the eleven verified source replacements; `invariants_before.json` then freezes the restored state for v0.3. The historical v0.2 baseline is preserved, including its unavailable-source entries. Re-running the historical v0.2 audit after restoration would encounter a changed availability baseline and is intentionally not part of v0.3 validation.

## Outlier review support

| Page | Regions | Existing classification | Technical status |
| --- | ---: | --- | --- |
| 8r | 0 | probable_segmentation_failure | Source and overlay available; zero masks do not establish absent content. |
| 11v | 0 | probable_segmentation_failure | Source and overlay available; visible content still requires specialist assessment. |
| 14r | 0 | probable_segmentation_failure | Source and overlay available; model omissions remain unresolved. |
| 16v | 2 | requires_human_review | Mean confidence 0.3848845; mask union covers 4.3352% of the raster. |

The ignored `outputs/artificial_fragments/v0_3/review/index.html` provides four lightweight contact images showing source, existing overlay and union of full-sized masks, with metadata, confidence, classes, coverage and unchanged historical review text. All evidence is checksummed. No human scholarly decision is fabricated or overridden. These pages remain eligible for page-level synthetic metrics; empty successful segmentation runs yield undefined region survival. An additional existing zero-detection `ubb-F-IX-0068` validation page is retained under the same rule.

## Damage taxonomy and topology

Definitions and constraints are centralized in `src/evaluation/structured_damage.py`. All components use four-neighbor connectivity on the actual source-sized binary damage mask. One connected removed component and a nonempty surviving raster are required for every family.

| Family | Geometric definition | Automatic checks |
| --- | --- | --- |
| `edge_loss` | Straight inward slab from a selected top/bottom/left/right edge; one-pixel guards exclude adjacent and opposite boundaries. | Exactly the intended edge; straight depth front allowing one raster rounding level. |
| `corner_loss` | Expanding rectangle anchored to a selected corner, with deterministic axis ratio and opposite-edge guards. | Exactly the two corresponding adjacent edges. |
| `internal_hole` | Expanding elliptical hole with deterministic near-center position and axis ratio. | No border contact; connected interior loss. |
| `edge_tear` | Edge-connected loss whose inward depth follows two sinusoidal frequencies with deterministic phase. | Exactly the intended edge; one component; at least three positive depth levels. |
| `strip_loss` | Full-span vertical/horizontal strip, positioned at the start edge, interior, or end edge of its transverse axis. | Intended spanning/placement edges, contiguous cross-sections, normalized elongation at least 1.25. |
| `connected_piece_loss` | Union of three expanding overlapping elliptical lobes along a deterministic diagonal, possibly clipped at page edges. | One removed component; bounding-box fill below 0.95 to reject rectangular pieces. |

These are materially different shape constructions. The corner rectangle is corner-anchored, while the edge slab touches one boundary only; strips span the page and therefore touch opposite boundaries. An internal elliptical hole differs from a multi-lobed lost piece. Edge tears use an explicitly varying depth front. The irregularity checks are geometric sanity checks, not image understanding or historical authentication.

Strip elongation is measured in normalized page coordinates: full longitudinal span divided by fractional transverse width. At 60% loss a horizontal strip on a tall page can have a physically tall bounding box; this is explicitly allowed and does not change the orientation definition. Surviving material may comprise separate pieces, especially after strip or large connected-piece loss. Binary masks preserve all components and holes.

## Severity, calibration and identity

Requested severity is removed source-raster pixels divided by all source-raster pixels, at 0.30 and 0.60. The named tolerance is `SEVERITY_TOLERANCE = 0.005` (half a percentage point), tighter than the unchanged v0.1/v0.2 tolerance of 0.02. The supported minimum image dimension is 16 pixels.

Each family defines a shape score. Calibration selects `round(width × height × severity)` pixels by ascending score, with deterministic row-major tie handling and round-half-even target rounding. This is area calibration, not a radius/depth proxy. Metadata retains the target count, realized loss/survival, absolute error, threshold, topological capacity, tolerance and every topology check. Insufficient capacity, unsupported dimensions, or failed topology produces an explicit rejected task with its reason; no fallback shape or relaxed tolerance is used.

SHA-256 assignment uses experiment version, page ID, source checksum, family and requested severity. Metadata stores the assigned edge/corner/orientation/placement/diagonal and all geometry parameters. A separate scientific task descriptor binds source/segmentation evidence. Registration reuses the existing UUID5 identity convention, with the new generation version and full mask parameters. No process-global random state or random task UUID is used.

## Selection and measurement

Eligibility comes from current immutable corpus manifests, readable checksum-valid sources, segmentation artifacts and live PostgreSQL source/run/region relationships. Only validation pages may generate or register. Neither train nor test pages substitute for rejected inputs. Rights, source provenance, advertised IIIF dimensions, and split assignments are compared with database records. Downloaded raster dimensions are used for geometry; native advertised dimensions in the database are preserved.

All 13 validation pages are eligible. Zero pages and zero planned family/severity configurations were rejected. The derived matrix is `13 × 6 × 2 = 156`: 26 tasks per family and 78 per severity. No orientation cross-product expands this matrix.

Exports use the full source coordinate frame and an identity transform. Source-sized damage and survival masks remain authoritative; no single contour is asserted for holes or multiple surviving components. Removed RGB and alpha are zeroed, so transparent pixels do not expose the hidden source content. Ground-truth source references stay separate from the synthetic observed fragment. Sources are never output destinations.

Region survival reuses the v0.2 full-mask overlap implementation, including portions outside detection bounding boxes. Every region retains its segmentation-run/index identifier, database region ID, class, confidence, original mask path/checksum/dimensions, source pixel area, surviving/removed area and fractions. No bounding-box substitution is used. Zero detections produce page metrics and explicitly undefined region metrics.

Category boundaries remain: fully removed = 0; mostly destroyed = (0, 0.05]; partial = (0.05, 0.95); almost complete = [0.95, 1]. The requested “mostly surviving” rate is explicitly an alias of almost complete, not a new fifth category. Do not sum the alias and original rate.

## Recto/verso groundwork

The audit inspected all 85 registered page records, live canvas/manuscript metadata, folio/page fields, the current schema, and all 20 cached source IIIF manifests including their object keys and metadata labels. No explicit physical-leaf relationship was found; all 85 database `folio_number` fields are null. Page labels containing r/v are insufficient to establish a physical pair.

`artificial_fragment_v03_pairing.json` records the inspected manifest checksums, keys, metadata labels and database metadata digest. Paired-leaf support was not implemented. A future shared damage specification requires explicit physical-leaf identity, side membership and a documented coordinate/mirroring convention, while preserving each image's checksum and segmentation measurements. No pair is inferred from filenames, sequence position, page-label suffixes or adjacent pages.

## Results and comparison

All 156 tasks passed topology validation and yielded 2,424 region observations (202 source regions × 12 transformations). Each family has 26 tasks and 404 region observations; each severity has 78 tasks and 1,212 observations. Four zero-detection pages yield 48 tasks with page metrics and undefined region survival. Every task realized exactly 0.30 or 0.60 loss: mean, median, population SD, minimum and maximum absolute severity error are all zero.

The matched comparison contains 132 v0.3 tasks / 1,812 observations and the unchanged 44 v0.2 controls / 604 observations on the same 11 pages. Mean region survival is:

| Family | At 30% raster loss | At 60% raster loss |
| --- | ---: | ---: |
| rectangular | 93.8674% | 70.4365% |
| irregular | 94.3766% | 63.8878% |
| edge_loss | 82.0086% | 28.6100% |
| corner_loss | 72.6324% | 23.8704% |
| internal_hole | 35.8476% | 7.8237% |
| edge_tear | 79.3331% | 25.0730% |
| strip_loss | 78.6489% | 42.0223% |
| connected_piece_loss | 45.6115% | 16.8812% |

At 30% loss, edge loss retains 82.01% of model-region pixels on average, versus 35.85% for an internal hole, a descriptive difference of 46.16 percentage points. At 60%, the corresponding values are 28.61% and 7.82%. The v0.2 controls preferentially preserve central evidence under their retained-area geometry; their higher survival does not imply a more historically plausible damage model.

Across all 13 v0.3 pages and both severities, mean region survival is 43.6085%, median 32.8479%, and population SD 0.3993111822. Fully removed, mostly removed, partial, and almost-complete rates are 25.4125%, 3.5479%, 47.2360%, and 23.8036%. These pooled values mix deliberately different experimental conditions.

The corpus remains 85 pages in 19 page-bearing manuscripts, with 59/13/13 splits and 4,230 model masks. Train contains all 14 observed classes; validation and v0.3 contain 10; test contains eight. Border (one corpus region), Illustrations (six), Running header (five), and Table (one) remain absent from validation and all generated v0.3 tasks. Main script black contributes 3,889/4,230 corpus detections (91.9385%); validation has 106/202 (52.4752%). Generation repeats the existing labels and supplies no new class evidence. Provider coverage remains one provider, e-codices; all 20 manuscript assignments lack recorded script metadata.

`docs/20a_artificial_fragment_v03_measurements.md` and `data/metadata/artificial_fragment_v03_measurements.json` contain the detailed aggregates; `artificial_fragment_v03_coverage.json` gives every split/class count and future Batch 02 selection criteria.

The central comparison uses only the 11 page identities common to historical v0.2 and v0.3. All-13-page v0.3 results are reported separately so restoration does not confound the control comparison. Reports group by experiment version, family, severity, manuscript, page and layout class, and additionally family/severity/class. Statistics include count, mean, median, population SD, minimum and maximum, plus removal/survival category rates. Region instances receive equal weight; repeated tasks are controlled transformations, not independent manuscript observations. Class-specific task counts include only tasks containing that class.

## Reproducible commands

From the repository root, using a Python environment installed from `requirements.txt` (the validated local runtime is `/usr/bin/python3`: Python 3.9.6, Pillow 11.3.0, NumPy 2.0.2, SciPy 1.13.1). Byte reproducibility was checked in this environment; different image-library versions require fresh verification:

```sh
python3 scripts/artificial_fragment_experiment.py v03 availability --dry-run
python3 scripts/artificial_fragment_experiment.py v03 availability --restore
python3 scripts/artificial_fragment_experiment.py v03 review
python3 scripts/artificial_fragment_experiment.py v03 spec
python3 scripts/artificial_fragment_experiment.py v03 generate
python3 scripts/artificial_fragment_experiment.py v03 register --dry-run
python3 scripts/artificial_fragment_experiment.py v03 register
python3 scripts/artificial_fragment_experiment.py v03 report
python3 scripts/artificial_fragment_experiment.py v03 verify
python3 scripts/artificial_fragment_experiment.py v03 check-determinism
python3 -m pytest -q tests/evaluation/test_structured_fragment_experiment.py
python3 -m pytest -q
```

`availability` is inspection-only unless `--restore` is supplied; `--dry-run` suppresses restoration and report/baseline writes. `register --dry-run` validates without database writes. Existing top-level CLI commands retain their v0.2 behavior. `generate` performs real mask/image/region recomputation and writes only changed bytes; `check-determinism` repeats source verification, the full corpus audit, specification, review artifacts, generation, measurements, reports and guarded registration before comparing outputs and timestamps. No separate command framework or schema migration was introduced.

Registration uses the existing JSONB task table, deterministic UUID5 identities and paths/checksums, with no binary storage. It verifies live source relationships and full provenance, rolls back attempted updates to existing v0.3 measurements, and requires a second pass to match every row. Complete row hashes include timestamps. Frozen database snapshots include all source, segmentation and historical v0.1/v0.2 task rows; file snapshots include masks, source assets, input metadata and historical experiment outputs.

## Limitations and next milestone decision

Severity measures image-raster loss, including margins/background, not a separately segmented parchment/paper support area. Idealized edge slabs, rectangles, sinusoids and ellipses do not establish historical damage realism. Finite-pixel guards and deterministic single-orientation sampling are declared experimental choices. Assignment includes severity, so the 30% and 60% masks on a page need not be nested. Per-family comparisons combine layout, orientation and shape placement; no inferential significance or historical likelihood is asserted. Model masks may omit visible content or misclassify drawings, and four validation pages have no detected regions.

The next milestone recommendation is **Targeted Training Corpus Expansion Batch 02**. Validation and the generated experiment still miss four of 14 observed classes, despite restoring every source and producing 2,424 region observations. Four of 13 validation pages also have zero detections. These measured coverage and quality gaps take priority over extending geometric realism in v0.4 or starting Reconstruction Baseline v0.1. Selection criteria should target the validation classes absent from the current corpus split, underrepresented structures and manuscripts with less Main script black dominance; include human segmentation-quality and rights review, provider/repository diversity, and explicit physical-leaf relationships where source metadata supplies them. Preserve existing splits and the test set. Do not implement Batch 02, v0.4 or a reconstruction baseline in this milestone. Technical availability must never change `training_allowed: false` or replace human rights authorization.
