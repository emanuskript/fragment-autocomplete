# AGENTS.md

## Working principles for future Codex sessions

- Do not jump into generative reconstruction first. The project strategy is layout-first.
- Treat eManuSkript as the central technical backbone for early reconstruction work.
- Preserve uncertainty, provenance, and comparator language in all reconstruction-related outputs. Candidate reconstructions must be framed as scholarly hypotheses, not facts.
- Keep [ROADMAP_STATUS.md](/Users/mobasuony/Desktop/Fragments/ROADMAP_STATUS.md) updated after every meaningful task.
- Update [NEXT_ACTIONS.md](/Users/mobasuony/Desktop/Fragments/NEXT_ACTIONS.md) with the next recommended task before ending a substantial work session.
- Do not store large images, large datasets, or model binaries in git.
- Prefer clear documentation, explicit assumptions, and reproducible scripts over ad hoc notes.
- CoMMA is a text, transcription, and metadata resource. Do not treat it as the core visual reconstruction dataset.
- If adding code later, include tests or at least runnable validation commands.
- If adding data-processing steps later, document inputs, outputs, provenance, and failure modes.

## Scope guardrails

- Do not claim backend, database, IIIF, ML, or eManuSkript integration is complete unless implemented and verified.
- Keep early design aligned with segmentation, pseudo-labeling, layout priors, retrieval support, UI overlays, evaluation, and conditioning.
- Favor incremental, reviewable milestones over large speculative implementations.
