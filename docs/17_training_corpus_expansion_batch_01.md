# Training Corpus Expansion — Batch 01 Dry-Run Readiness

## Outcome

A separate immutable dry-run batch now contains 15 newly verified official e-codices manuscript manifests. It does not overlap or rewrite the frozen five-manuscript validation corpus. Together they represent 20 manuscripts with aggregate 14/3/3 train/validation/test manuscript splits.

The dry run selected 75 pages (five per new manuscript) across 11 repositories. No page was downloaded, registered, segmented, or marked training-allowed.

## Review gate

All 75 selected IIIF thumbnails were visually triaged. 68 appear page-like at review scale; 7 are explicitly flagged as blank-like, photographic/non-text, or low-contrast and need a manual keep/reject decision.

Acquisition is intentionally blocked. No uncertain page has been silently discarded or replaced. Any rejection must preserve its evidence and a replacement must come from the unchanged seeded order.

## Dry-run statistics

- New manuscripts: 15
- Selected pages: 75
- Candidate canvases: 4131
- Explicitly rejected canvases: 181
- Batch splits: 11 train / 2 validation / 2 test manuscripts
- Cross-batch overlaps: 0 manuscripts, 0 manifests, 0 canvases
- Rights: `pending_review`; `training_allowed: false`

## Storage planning estimate

The 15-page validation set contains 20984367 source-image bytes, or approximately 1398958 bytes/page. At that observed mean, this 75-page batch would use about 104921835 bytes and 500 pages about 699478900 bytes before raw manifests, safety margin, optional segmentation, and database overhead.

## Reproduce

```bash
PYTHON_BIN=/usr/bin/python3 bash scripts/validate_training_corpus_expansion_batch.sh
```

This command runs the dry build twice and requires byte-identical manifests/statistics before executing the structural, provenance, split, rights, overlap, and review-gate validator.

## Next gate

Resolve all eight recorded page exceptions, then rerun the unchanged dry-run validator before acquisition.
