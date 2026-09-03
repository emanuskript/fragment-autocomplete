# Training Corpus Expansion — Batch 01 Deterministic Gate

## Outcome

The decision-aware deterministic gate passes for all 15 assigned official e-codices manifests without overlapping or rewriting the frozen five-manuscript validation corpus. Assigned Batch splits remain 11/2/2 train/validation/test; aggregate assigned splits remain 14/3/3.

The original dry run selected 75 pages. After explicit decisions, the final manifest selects 70 pages from 14 active manuscripts. All 70 pages are now downloaded, checksum-verified, registered, and segmented through the existing eManuSkript workflow. None is marked training-allowed.

## Review gate

All eight review decisions are explicit Mo rejections: one audit-only disposition in the frozen validation corpus and seven Batch selection rejections. Every rejected page remains in the audit trail with its reason and provenance.

The unchanged seeded order promoted three same-manuscript replacements: `bc-b-0103/40r`, `bcul-Ms0403/86r`, and `bcj-A2437/102`. The CEA album manuscript is explicitly unsuitable after only two suitable pages and seven unsuitable pages among its first nine reviewed seeded candidates; it contributes zero pages rather than forcing five.

## Final gate statistics

- Assigned manuscripts: 15
- Active selected-page manuscripts: 14
- Final selected pages: 70
- Candidate canvases: 4129
- Explicitly rejected canvases: 188
- Batch splits: 11 train / 2 validation / 2 test manuscripts
- Selected-page splits: 50 train / 10 validation / 10 test pages
- Manual Batch rejects: 7; deterministic replacements: 3; unresolved decisions: 0
- Cross-batch overlaps: 0 manuscripts, 0 manifests, 0 canvases
- Rights: `pending_review`; `training_allowed: false`

## Storage planning estimate

The 15-page validation set contains 20984367 source-image bytes, or approximately 1398958 bytes/page. At that observed mean, this 70-page selection would use about 97927046 bytes and 500 pages about 699478900 bytes before raw manifests, safety margin, optional segmentation, and database overhead.

## Reproduce

```bash
PYTHON_BIN=/usr/bin/python3 bash scripts/validate_training_corpus_expansion_batch.sh
```

This command runs the dry build twice and requires byte-identical manifests/statistics before executing the structural, provenance, split, rights, overlap, and review-gate validator.

## Acquisition and segmentation follow-through

Acquisition and registration passed with 70/70 assets and an unchanged 70-asset reuse run. The expanded eManuSkript segmentation milestone subsequently passed with 70/70 successful page outcomes, 3,358 source-sized binary instance masks, idempotent local artifacts, 70 stable database runs, and unchanged rights/split/source invariants. See `data/metadata/training_corpus_expansion_batch_01_acquisition_validation.yaml` and `docs/18_training_corpus_expansion_batch_01_segmentation.md`.
