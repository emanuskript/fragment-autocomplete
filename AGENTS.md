# AGENTS.md

## Project Rules for Future Codex Sessions

- This project is layout-first, not full-image hallucination-first.
- Treat eManuSkript / "Manuskripte digital lesen lernen" as the central technical backbone for layout analysis.
- Always preserve uncertainty, provenance, and comparator language in reconstruction-related documentation, code, UI text, exports, and status updates.
- Do not claim missing manuscript content is recovered unless external scholarly evidence supports that specific claim.
- Present reconstructions as candidate scholarly hypotheses, not historical truth.
- CoMMA is text and metadata support, not the visual training dataset.
- Keep [ROADMAP_STATUS.md](/Users/mobasuony/Desktop/Fragments/ROADMAP_STATUS.md) updated after every meaningful task.
- Keep [NEXT_ACTIONS.md](/Users/mobasuony/Desktop/Fragments/NEXT_ACTIONS.md) updated with the next recommended task.
- Do not commit large images, downloaded IIIF assets, MSI files, generated datasets, trained models, or bulk outputs.
- Prefer reproducible scripts, documented assumptions, and explicit validation commands.
- Do not mark work as Done unless files or code actually exist and validation passes.
- If adding code later, include validation commands or tests.

## Scope Boundaries

- Do not implement the backend, frontend, database, IIIF ingestion pipeline, eManuSkript integration, ML model, retrieval service, MSI viewer, or deployment unless explicitly requested.
- Do not treat CoMMA as ground truth for visual reconstruction.
- Do not collapse multiple plausible reconstruction candidates into one final answer when uncertainty exists.
- Keep evidence separate from inference in data models, documentation, UI concepts, and exports.
