# Training Corpus Validation Decision Audit

## Outcome

The frozen five-manuscript validation manifest remains unchanged. Its 45 recorded rejections are all explicit label-based exclusions: 20 covers, 10 paste-downs, and 15 binding/calibration views.

Applying the versioned expansion rules in audit mode identifies 35 additional obvious auxiliary views that the historical rules retained as candidates. It also identifies 12 accompanying-material canvases; these remain candidates with a manual-review requirement and are not silently rejected.

## Visual engineering triage

All 15 downloaded validation selections were inspected at review scale. Fourteen are page-like manuscript content. One (`ubb-F-IX-0068`, `V2v`) is a blank-like damaged flyleaf and is explicitly flagged for manual review. This is engineering triage, not scholarly or rights approval.

## Rule correction

Expansion rule version `obvious_non_training_canvas_rules_v0_2` adds explicit matches for digital color checkers/color profiles, rulers/QP cards, fore-edge/head/tail views, and open views. `Accompanying materials` stays a candidate but is excluded from automatic seeded selection pending review.

The historical validation artifacts keep rule version v0.1 and are not regenerated. The corrected rules apply only to new batch specifications.
