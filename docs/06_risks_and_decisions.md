# 06 Risks and Decisions

Status: current high-level register; milestone-specific risks remain in the numbered reports.

## Decisions

- Use a layout/morphology-first path with eManuSkript as the technical backbone.
- Keep observed evidence, model-derived layout evidence, synthetic ground truth, and inference separate.
- Store large binaries outside Git and PostgreSQL; retain paths, checksums, identifiers, provenance, and geometry.
- Assign corpus splits by manuscript and keep validated experiment versions immutable.
- Default new source assets to pending rights review and not training-allowed.
- Treat reconstructions as multiple candidate hypotheses, never recovered historical fact.

## Open risks

- The current corpus is provider- and class-imbalanced, and some segmentation outputs require human review.
- Local ignored artifacts need durable institutional storage, backup, retention, and quota policy.
- External source, image, metadata, and checkpoint rights require separate review from software licensing.
- Checkpoint loading may require trusted deserialization; only checksum-verified, trusted weights should be used.
- Database schema groundwork can be mistaken for implemented reconstruction/retrieval features; documentation must preserve the distinction.
- Future integration needs agreed identifier, coordinate, provenance, confidence, review, and export semantics.

## Deferred choices

- Targeted Corpus Expansion Batch 02 scope and rights-approved training subset.
- Retrieval/candidate architecture and detailed evaluation rubric.
- CODICUM, Manuscript Workbench, MPO, CoMMA, MSI, and production deployment integrations.
