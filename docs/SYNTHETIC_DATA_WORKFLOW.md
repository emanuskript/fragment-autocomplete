# Synthetic data from the supplied damage matrix

## What runs now

Use `scripts/synthetic_data.py` as the entry point. The supplied v3 matrix is
preserved in `data/metadata/jeremy_damage_matrix_v3.json`, with its CSV filename,
checksum, 187 content/damage rows, four severity decisions per row, notes and
example links. Its 17 named damage types cover 15 content types. Rows 187/188
lack damage IDs and other fields; they remain visible and cannot authorize
generation. No missing values were inferred. The `_all.csv` export is the source;
the other supplied export contains the same data with reordered rows and columns.

| Component | Implementation | Model |
| --- | --- | --- |
| Matrix planner | `damage_matrix.py`; general, edge-case, exclusion and incomplete-row rules | None |
| Interior loss, D2-01 | Existing elliptical interior-hole geometry | None |
| Straight edge loss, D2-02 | Existing boundary-slab geometry | None |
| Irregular edge loss, D2-03 | Existing variable-depth boundary-tear geometry | None |
| Public review previews, 14 additional types | `build_damage_review_prototype.py`; deterministic optical, surface, paired-side and deformation approximations | None |
| Layout evidence | Explicitly selected, checksum-verified existing Mergen masks | Registered `best_emanuskript_segmentation.pt`; no new inference |
| Validation/export | Pixel preservation, topology, checksums, deterministic reruns and split isolation | None |

Here “damage agents” means procedural operators. There is no LLM agent framework,
Qwen, DINO or diffusion dependency. These experiments do not train a model,
recover missing content or deploy a Fragmentarium service.

## Coverage and limits

All 17 damage types now have selectable public-review examples. The three
material-loss operators above remain the only pixel-calibrated training and
evaluation generators. Ink-following loss (D2-04), surface coating (06), tape
(07), deposits (08), staining (09), overwriting (10), fading (11), surface loss
(12), erasure (13), offset/transfer (14), corrosion haloes (16), ink bleed (17),
folds (18) and cockling/shrinkage (19) are deterministic interface prototypes.
Their affected-region masks are measurements for visual inspection, not semantic
severity calibration or validated physical simulation.

The full plan has 60 eligible general cells, 47 implemented edge-case cells
requiring opt-in, 283 cells waiting for operators, 350 exclusions and 8 cells on
incomplete rows. Original decision totals are separately preserved; incomplete
rows explain why the source exclusion count is 352.

An input supplies a source-sized binary mask for ONE content object. Calibration
uses removed area inside this mask and separately reports whole-page loss. The
shape remains continuous outside the target rather than removing only isolated
target pixels. This reuses v0.3 geometry without modifying historical results.

S1/S2/S3/S4 use explicit engineering area presets of 2.5%/12.5%/35%/65%. These
are NOT exact translations of every qualitative severity note. Every task says
`semantic_severity_validated: false`: removing 12.5% of a text region does not
establish that isolated letters were removed or that meaning is recoverable.
The supplied severity descriptions still require specialist review.

Mergen labels do not automatically map to all 15 content types. Preparing
`Main script black` as CT-01 is a caller-declared, model-derived mapping, not an
expert-verified annotation. Other content types need explicit mappings or
reviewed masks. The user has authorized use of their supplied datasets; this
workflow preserves original metadata and does not rewrite historical decisions.

## Run it

From the repository root, with Python 3.11:

```bash
python -m pip install -r requirements-synthetic.txt
python scripts/synthetic_data.py plan
python scripts/synthetic_data.py plan --content-id CT-01
python scripts/synthetic_data.py demo --output outputs/synthetic_data/my_demo
```

The demo creates nine schematic samples, not a manuscript training corpus.
Save a detailed plan with `--output outputs/synthetic_data/coverage.json`.

Build or validate the complete ten-page public review set:

```bash
python scripts/build_damage_review_prototype.py
python scripts/build_damage_review_prototype.py --validate-only
```

This writes 140 ignored previews and effect masks—14 additional types across ten
pages—to `outputs/synthetic_data/damage_review_prototype_v2/`. The manifest marks
`visual_realism_validated: false` and `historical_damage_claim: false`. The
dashboard launcher builds the set when it is absent and validates it otherwise.

Effects are applied across the union of all detected `Main script*` regions
(stored per page as `writing_area.png` and in each record's `effect_domain`),
not only the single selected region used by the calibrated loss operators;
fold and cockling operators act on the whole leaf. Validation rejects any
preview whose display-scale (500 px wide) visible change is below 2% of the page.

For the existing local corpus and stored Mergen artifacts:

```bash
python scripts/synthetic_data.py prepare-corpus \
  --split train --label 'Main script black' --content-id CT-01 --limit 10 \
  --realism-profile paper_edge_v1 \
  --output outputs/synthetic_data/my_pilot/sources.json
python scripts/synthetic_data.py generate \
  --sources outputs/synthetic_data/my_pilot/sources.json \
  --output outputs/synthetic_data/my_pilot/dataset
```

Preparation verifies images/masks, selects the largest matching region per page,
preserves model/run/source provenance, and includes the complete corpus split
registry. No database writes or new Mergen inference occur. Invalid/unavailable
pages have recorded skip reasons. `--limit` bounds the batch; test pages cannot
be selected. The original sources, masks and frozen experiments are unchanged.

Generation defaults to D2-01/02/03 and S2/S3/S4. The optional `paper_edge_v1`
profile uses seeded multi-scale correlated variation for less repetitive hole
and edge boundaries while preserving exact selected-region calibration and
connected topology. It records `visual_realism_validated: false` and
`historical_damage_claim: false`: it is an engineering approximation awaiting
specialist review, not a claim of authentic historical material damage.

Set `damage_ids`, `severities` and integer `seed` in the source JSON to change an
experiment. Use a new output directory for changed settings. An identical rerun
does not rewrite artifacts.
`--include-edge-cases` opts into edge cases, which retain a separate cohort label.
“Do not generate” has no override. Updated matrices require new versioned paths.

## Cut a page into pieces

`scripts/cut_fragments.py` splits each complete page into three non-overlapping torn
pieces (`src/evaluation/cut_pieces.py`, `cut_pieces_v1`), as a binder or dealer cutting up a
book would. It is for fragment-matching experiments, where several pieces of one page (and
pages of the same scribe) must be found among look-alikes.

```bash
python scripts/cut_fragments.py --sources data/raw/seshat_samples \
  --output outputs/cut_fragments/seshat_v1 --seed seshat-v1
```

- The leaf is isolated by colour (parchment and paper are warm; photographic surrounds,
  mounts, colour cards and library caption bands are neutral or saturated), so no piece
  carries anything that identifies the photograph.
- Every leaf is normalised to 2000 px on the long side, so resolution does not either.
- Two torn lines (the `paper_edge_v1` noise) split the leaf into three pieces; a cut is
  accepted only when each piece holds at least 18% of the leaf and 4% dark ink.
- Each piece is photographed on one neutral background with a rotation within ±6°, saved as
  JPEG with a PNG survival mask; `manifest.json` records checksums, layouts and bounding boxes.

Records state `visual_realism_validated: false` and `historical_damage_claim: false`.

## Input and output contracts

For another dataset, supply a JSON object with a `pages` array. Each page needs
`page_id`, `manuscript_id`, `split` (`train`, `validation`, `test`), `source_image`,
`content_mask`, `content_id` and `content_basis` (`model_derived`,
`expert_reviewed`, `synthetic_fixture`). Paths are relative to the JSON folder,
or absolute. Model-derived masks require `segmentation_provenance`.
Optional `source_sha256`/`mask_sha256` enforce expected bytes; use them for
registered artifacts. Test entries require registered source checksums and are
excluded without opening their files. Supply the whole dataset's `split_registry`
when generating from a subset so known held-out sources cannot be reassigned.

Masks must be source-sized mode-L images with only 0/255 pixels. Sources must
be opaque. The caller selects complete source pages and supplies manuscript
identities and content labels; the generator cannot certify their correctness.

```text
dataset/
  run.json                        immutable experiment inputs
  dataset.json                    task index and explicit skips/rejections
  matrix_<id>/
    observed/fragment.png         source pixels plus transparent synthetic loss
    observed/survival.png         255 = surviving observed material
    targets/damage.png            255 = synthetic material loss
    targets/content.png           hidden target-content mask
    targets/record.json           source reference, seed, evidence and measures
```

Load only `observed/` into inference inputs. `targets/` contains supervised or
evaluation targets, including clean-source references. Dataset indices are
preparation metadata, not model prompts. Coordinates remain in the source-page
frame, with an identity transform. Surviving decoded pixels are byte-equal.

## Validation and next step

```bash
python -m pytest -q tests/evaluation/test_damage_matrix.py
python -m pytest -q tests/evaluation/test_damage_review_prototype.py
python -m pytest -q
python -m ruff check src scripts tests
bash scripts/check_workspace.sh
```

The 2026-11-09 public-demo cohort generated 90 samples from ten existing training
pages using their stored Mergen masks. The dataset is local and ignored at
`outputs/synthetic_data/paper_profile_public_demo_v2/dataset/dataset.json`.
Generation reported no skips. Unit tests verify deterministic output, exact
selected-region loss, connected topology, provenance and explicit realism limits.
These are engineering checks, not realism approval. Review the content mapping,
shapes and severity examples with a manuscript specialist before scaling. Promote
each approved appearance/deformation prototype separately into the training-data
workflow with its own visibility contract and validation.


### Realistic profile (`--profile realistic`)

    python scripts/cut_fragments.py --sources data/raw/fragment_join_v3_sources \
        --output outputs/cut_fragments/join_v3 --seed join-v3 --profile realistic

Adds, in `src/evaluation/aged_pieces.py` (`realistic_v1`): leaf ageing (tone, grime, edge
soiling, an old fold on some leaves); per piece worn edges, a knife trim on some, two or three
surface damages from the damage matrix (D2-09, D2-11, D2-12, D2-16, D2-17, reusing the review
operators in `scripts/build_damage_review_prototype.py`, blended at partial strength and
feathered), worm or sewing holes on some, dirt along the piece's edges; photographed on one of
four archive grounds with a soft shadow and sometimes a grey-scale bar. Every piece's manifest
entry lists what was applied. Built after comparing clean pieces with the real fragments of the
FragmentJoin pilot (see FragmentJoin docs/PILOT_SET_V3.md for the measured comparison). Not
validated as a model of historical damage. The clean profile is unchanged.

### Realistic profile v2 (`--profile realistic_v2`)

    python scripts/cut_fragments.py --sources data/raw/fragment_join_v3_sources \
        --output outputs/cut_fragments/join_v4 --seed join-v4 --profile realistic_v2

Tuned on 2026-11-12 against the 18 real fragments of the FragmentJoin pilot (FragmentJoin
`scripts/compare_realism.py`; see its docs/PILOT_SET_V4.md). Same order of work as v1, with
these changes (parameters in `aged_pieces.PROFILES["realistic_v2"]`):

- cuts: each cut line is a straight knife cut (slight angle, sub-pixel waver) on 80 %, else a
  gentler tear; every piece is first asked for 85 % of the page's ink density, relaxed to 70 %
  and 50 % only if no cut qualifies;
- edges: light wear (2-6 px instead of up to 18), one to three small chips bitten out;
- leaf: warmer tone, grime that lightens as much as it darkens, a fine two-scale mottle, much
  lighter soiling towards the edge;
- surface: one or two matrix damages (D2-09, D2-11, D2-12, D2-17) at 60 % strength;
- holes: on 90 % of pieces, larger worm holes.

Medians on the 60 pieces against the real fragments (lightness L*, yellowness b*, edge
darkening, outline loss, holes, blotchiness): 67.6 / 18.6 / 0.973 / 0.0118 / 0.0037 / 7.63
against 66.2 / 19.1 / 0.959 / 0.0146 / 0.0066 / 7.25 (v1: 65.3 / 14.0 / 0.875 / 0.0741 /
0.0023 / 8.19). Pieces are still thirds of a page, so they carry fewer text lines than the
mostly near-complete real leaves. Not validated as a model of historical damage; v1 output is
unchanged (tested to the pixel against pilot v3).
