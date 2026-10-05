# Implementation Status — October 2026

## Purpose and source of truth

This document compares the planned system in the historical [Fragment Autocomplete Architecture Draft v0.2, dated 2026-05-06](../outputs/Fragment_Autocomplete_Architecture_Draft_v0.2_2026-05-06.pdf), with the repository as inspected on 2026-10-05. The draft is retained unchanged as a record of the original design. It is not an implementation report.

The current code, tests, migrations, scripts, committed compact metadata, [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP_STATUS.md](../ROADMAP_STATUS.md), and [NEXT_ACTIONS.md](../NEXT_ACTIONS.md) are the source of truth for what exists now. Database tables alone are not counted as implemented workflows.

Status meanings:

- **Implemented:** a runnable, repository-backed workflow exists and has validation or test coverage.
- **Partially implemented:** a useful subset or foundation exists, but the May 2026 subsystem is not complete.
- **Planned:** the repository contains design or schema groundwork but no runnable end-to-end workflow.
- **Superseded:** the original framing is retained historically but a newer document or narrower direction now governs the work.

## Subsystem comparison

| Subsystem | Status | Current repository evidence | Difference from the May 2026 draft |
| --- | --- | --- | --- |
| Database / PostGIS foundation | **Implemented** | Docker Compose, PostgreSQL/PostGIS migrations, seed data, environment-only connection settings, and start/migrate/validate scripts exist under `infra/db/` and `scripts/db_*.sh`. | The local foundation exists. Institutional deployment, managed storage, access control, and production operations remain outside the prototype. |
| IIIF ingestion | **Implemented** | `src/ingestion/` normalizes common IIIF Presentation API v2/v3 manifests and registers repository, manuscript, manifest cache, canvas, image-service/source identifiers, rights, and raw metadata. Fixtures and tests cover both versions. | This is not complete IIIF coverage: nested collections, authentication profiles, annotation exchange, a viewer, and a refresh policy are not implemented. |
| Corpus registration | **Implemented** | `src/ingestion/training_corpus.py` plus corpus CLIs support deterministic selection, manifest/page registration, checksum-aware resumable acquisition, rejected/replacement decisions, and manuscript-isolated splits. | Current validated sources are bounded research corpora, not a general public corpus service. Large source files remain external to Git. |
| Rights and provenance handling | **Implemented** | Source identifiers, checksums, harvested rights, attribution, raw metadata, `rights_review_status`, `training_allowed`, model/run identity, parameters, and parent relationships are retained in schema and compact records. Ordinary refreshes preserve human review state. | Governance is not complete: current acquired corpus assets remain `pending_review` and `training_allowed: false`; publication/demo decisions still require human authorization. |
| eManuSkript segmentation integration | **Implemented** | Existing runners execute the eManuSkript/Ultralytics model, restore source-coordinate instance masks, record confidence/model/configuration provenance, and store segmentation runs and regions. Validation and Batch 01 workflows reuse the same inference path. | It is a local research pipeline, not a network service. The checkpoint and source images are intentionally not distributed. Model-derived labels remain provisional evidence. |
| Artificial fragment generator | **Implemented** | Deterministic rectangular, irregular, and structured-damage families preserve source pixels, explicit survival/damage masks, transforms, seeds, and source-space evidence. v0.1.1, v0.2, and v0.3 records are present. | Synthetic damage supports controlled comparison only; it is not evidence of actual manuscript loss and does not reconstruct missing content. |
| Task registration | **Implemented** | `artificial_fragment_task` registration has deterministic identities, idempotent matching, provenance payloads, and tests. | Registration currently covers artificial-fragment experiments, not future reconstruction jobs or external scholarly review tasks. |
| Evaluation infrastructure | **Partially implemented** | Corpus audits, frozen-invariant checks, determinism checks, storage/idempotency validation, topology/severity checks, and layout-survival measurements exist. | Candidate-ranking metrics, placement/reconstruction evaluation, expert-review rubrics, retrieval evaluation, and production dashboards described in the draft do not yet exist. |
| Reconstruction / candidate generation | **Planned** | The schema and architecture describe reconstruction jobs/candidates and evidence boundaries, but there is no generator, ranking implementation, or runnable reconstruction workflow. | No missing manuscript content is generated or claimed as recovered. Multiple candidate hypotheses, uncertainty, and evidence links remain design requirements. |
| Retrieval | **Planned** | Schema groundwork and design notes mention embeddings and explainable analogue retrieval. | No index, embedding pipeline, similarity service, ranking evaluation, or retrieval API is implemented. |
| Web / API interface | **Partially implemented** | A local, read-only Streamlit viewer can inspect stored segmentation outputs. | The draft's backend API, authenticated scholarly UI, IIIF viewer, asynchronous jobs, candidate comparison/review, and deployment are not implemented. Empty `src/backend/` and `src/frontend/` boundaries are placeholders, not applications. |
| Exports | **Planned** | The database contains export-oriented schema groundwork and the architecture defines evidence/provenance requirements. | No reconstruction proposal bundle, IIIF annotation export, PAGE-XML/ALTO export, TEI export, or external-tool adapter exists. Architecture/document rendering is not the scholarly export subsystem described in the draft. |
| MSI | **Planned** | An `msi_asset` schema concept and design notes exist. | No MSI data, alignment, processing, viewer support, model input, or export workflow is implemented or included. |
| CoMMA integration | **Planned** | Schema/design groundwork allows future text-witness links. | There is no CoMMA ingestion, search, mapping, or dataset in the repository. CoMMA remains possible text/metadata support and is not visual training ground truth. |
| External interoperability | **Partially implemented** | IIIF source/canvas/image-service identifiers are preserved, and [INTEGRATION_NOTES.md](INTEGRATION_NOTES.md) documents proposed evidence, proposal, review, confidence, rights, and export boundaries. | No MPO adapter, partner endpoint, proposal exchange API, accept/reject workflow, or CODICUM/Manuscript Workbench compatibility has been implemented or claimed. |
| Large-object storage and deployment | **Partially implemented** | A consistent local split keeps metadata/geometry in PostgreSQL, compact records in Git, and large binaries in ignored `data/raw/` and `outputs/` paths. | Institutional object storage, backup/retention policy, queue/workers, monitoring, authentication, and hosted deployment remain planned. |
| Model training / conditioned completion | **Planned** | Versioned model registry metadata and inference compatibility checks exist. | No training or fine-tuning workflow is implemented. Current rights state does not authorize the acquired corpus for training. |
| May 2026 draft as a live status document | **Superseded** | The draft is preserved as Architecture Draft v0.2; this file and `docs/ARCHITECTURE.md` describe the October 2026 implementation state. | Planned diagrams and narrative must not be read as evidence that future subsystems are complete. |

## Current implemented data flow

```text
IIIF/local references
    -> normalization and rights/provenance-aware registration
    -> ignored source files + PostgreSQL/PostGIS records
    -> eManuSkript segmentation and source-coordinate masks
    -> stored layout evidence + ignored binary artifacts
    -> deterministic synthetic damage and registered experiment tasks
    -> audit, determinism, and layout-survival measurements

[planned] retrieval -> multiple reconstruction candidates -> expert review -> export
```

Observed source pixels, model-derived layout evidence, synthetic ground truth, and future inference are separate layers. Current generated fragment artifacts are controlled experimental transformations, not recovered historical pages.

## Preflight boundary

The Python test/lint/compilation/workspace, secret, link, and documented bare-clone quickstart checks are release-gated separately. PostgreSQL/PostGIS runtime validation requires an active Docker daemon. On 2026-10-05 the Docker CLI and Compose configuration were present, but the local Docker daemon was not running; the database runtime validation is therefore the only unverified infrastructure check in this preflight.
