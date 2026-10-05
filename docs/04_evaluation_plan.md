# 04 Evaluation Plan

Status: controlled synthetic evaluation is implemented; reconstruction-candidate evaluation remains planned.

Implemented evaluation infrastructure covers deterministic artificial damage on complete pages, requested versus measured severity, source-pixel survival, eManuSkript region-mask overlap, grouped corpus/experiment statistics, task/database idempotency, source and rights invariants, and full artifact determinism checks. The v0.2 and v0.3 records are in `data/metadata/artificial_fragment_v02_*` and `data/metadata/artificial_fragment_v03_*`.

These measures are technical comparators. They do not measure semantic recoverability, historical likelihood, or scholarly acceptance.

Future reconstruction evaluation should include:

- layout and placement fidelity where controlled ground truth exists;
- provenance and evidence completeness;
- calibrated confidence and visible uncertainty;
- comparison of multiple plausible candidates rather than a forced single answer;
- expert usefulness and documented accept/reject/revise rationale;
- failure and insufficient-evidence reporting;
- strict confirmation that observed pixels were preserved and distinguishable from inference.

A detailed expert-review rubric and representative 20-30 use-case set remain open work.
