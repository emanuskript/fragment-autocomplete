# CHANGELOG

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Responsive Next.js/React Fragment Evidence Workbench using the actual local
  corpus images, saved Mergen artifacts, Jeremy matrix records, nine generated
  fragments, measurements, and an optional read-only live PostgreSQL view.
- Reproducible archival status-PDF exporter for meeting handoff.
- Whole-project Fragment Autocomplete Evidence Observatory with seven focused
  views covering the pipeline, Jeremy's matrix, Mergen segmentation, storage and
  provenance, controlled experiments, the implementation ledger, and ordered
  next steps.
- Metadata-first dashboard adapter and regression tests deriving the 85-page /
  4,230-mask corpus state, matrix coverage, SQL schema status, experiment totals,
  and implemented-versus-future boundaries from committed records.
- Dashboard run script, responsive framed-sheet visual system, JSON status export,
  and project-dashboard documentation.
- Canonical Mergen repository and GWDG OwnCloud weight-directory metadata, expected checkpoint filenames, and regression tests for the model registry.
- October 2026 implementation-status comparison between the historical May 2026 Architecture Draft v0.2 and the current repository.
- Temporary external-review notice clarifying that no software licence has been selected and that reuse or redistribution permission must not be assumed.
- External collaborator quickstart, current-state architecture, and integration-boundary documentation.
- Environment-only database credential configuration, `.env.example`, correctness-focused Ruff configuration, and database configuration tests.
- Reproducible PDF metadata normalization for future local architecture rebuilds.
- Development dependency file with the validated test/lint tool versions and pinned validated ML inference stack.
- Batch 01 eManuSkript segmentation specification, prepared 70-page input manifest, compact results/storage/statistics/snapshots/validation artifacts, expanded-scale report, orchestration, and validation tests.
- Expanded segmentation validation for exact corpus/frozen-set coverage, source and rights snapshots, binary source-sized mask integrity, bbox clipping, database relationships, artifact/storage idempotency, performance, distributions, and review outliers.
- Batch 01 acquisition/idempotency validator covering exact file membership, checksums, dimensions, IIIF/database relationships, split isolation, manual decisions, rights state, and Git ignore safety.
- Machine-readable Batch 01 acquisition validation for 15 assigned manifests, 14 page-bearing manuscripts, and 70 registered source pages.
- Explicit versioned page decisions, annotation-only replacement reviews, and a manuscript-suitability disposition for Training Corpus Expansion Batch 01.
- Artificial fragment generator for the five registered full-page samples, with rectangular and irregular mask families, ground-truth placement metadata, validation, tests, and a generation report.
- HSP/German metadata standards alignment migration, controlled vocabulary import, validation script, generated normdata YAML, field-mapping YAML, and alignment report.
- Full pilot segmentation input preparation, runner, storage script, validators, and report.
- Minimal local segmentation viewer scripts and viewer documentation.
- Segmentation output storage script, validator, storage results manifest, and storage report.
- Segmentation smoke-test runner, validator, results manifest, and report.
- Controlled segmentation smoke-test input manifest, preparation script, validation script, and readiness report.
- Model weights compatibility inspection script, YAML manifest, and report.
- Initial sample dataset configuration for 5 full pages and 5 fragments from `autocomplete-test-dataset/`.
- Local sample dataset registration script and validation script.
- Initial sample dataset resolved metadata and human-readable report.
- Tests for initial sample dataset configuration.
- Local dataset and model-weight inventory for `autocomplete-test-dataset/` and `model weights/`.
- Machine-readable local asset manifest and human-readable local asset inventory report.
- Inventory-only model registry metadata for local model weight files.
- IIIF Presentation v2/v3 manifest normalization proof of concept.
- Local and remote IIIF manifest ingestion CLI with dry-run mode.
- Fixture manifests and normalizer tests for IIIF v2 and v3.
- IIIF ingestion validation script with database row checks.
- IIIF ingestion proof-of-concept documentation.
- PostgreSQL/PostGIS Docker database foundation.
- Initial SQL migration with UUID primary keys, PostGIS geometry columns, constraints, triggers, and indexes.
- Seed lookup values for known repository/resource placeholders.
- Database start, migrate, reset, and validation scripts.
- Database schema and storage plan documentation.
- Full technical architecture draft for Fragment Autocomplete.
- Ten Mermaid architecture figure sources and rendered SVG targets.
- Architecture PDF/HTML build script.
- Architecture figure rendering script.
- Workspace validation coverage for architecture figures and document outputs.

### Updated

- Replaced the generic project-level Streamlit dashboard and launcher with the
  evidence-first workbench; retained the separate segmentation-only viewer.
- Current README, architecture, collaborator, status, and model-compatibility guidance to name Mergen as the eManuSkript layout-analysis component while preserving historical checkpoint provenance.
- Removed machine-specific eManuSkript release-staging instructions from the active Fragment Autocomplete next-actions and roadmap summaries.
- Preserved and relabeled the 2026-05-06 architecture PDF as historical Architecture Draft v0.2; local rebuilds no longer overwrite that artifact.
- Rewrote the root README for external researchers, separating implemented capabilities from planned work, data from metadata, and software licensing from source-data rights.
- Removed hard-coded local paths and the committed development database password; external HSP inputs now use configurable paths and portable checksum provenance.
- Expanded ignore rules for credentials, private data, experiment trackers, checkpoints, virtual-environment metadata, and machine-specific files.
- Removed unused imports identified by the new correctness lint gate; preserved the historical architecture PDF bytes and kept metadata normalization available only for future rebuilds.
- Existing eManuSkript runner now resolves unchanged checksum-verified page artifacts before model loading, records richer source/performance/failure provenance, clips source-coordinate boxes, and preserves unchanged result manifests.
- Existing segmentation storage now preserves matching run/region rows and timestamps, while retaining deterministic replacement only when stored logical content differs.
- Training Corpus Builder selection now consumes explicit review decisions, records deterministic same-manuscript replacements without changing heuristics, and preserves review-artifact provenance.
- IIIF image-asset upserts now refresh harvested source rights while preserving human-reviewed training authorization and its versioned provenance without a schema migration.
- Storage, corpus, roadmap, and next-action documentation for the completed Batch 01 acquisition and the next expanded-scale eManuSkript segmentation milestone.
- Documented Python ingestion/scripts/tests modules with module-level docstrings, added core ingestion API docstrings, and removed dead imports plus generated `__pycache__` artifacts.
- Removed boilerplate source-directory README files and kept empty source boundaries with `.gitkeep` files.
- Cleaned stale duplicate status files and clarified the full-pilot segmentation runner/viewer handling for large-image retries and failed-run visibility.
- Local viewer to browse both smoke-test and full-pilot segmentation runs from PostgreSQL/PostGIS.
- README, roadmap, project board, next actions, and requirements for the local segmentation viewer step.
- README, roadmap, project board, and next actions for the minimal local UI viewer step after segmentation storage.
- README, roadmap, project board, and next actions for the post-smoke-test database storage step.
- README, roadmap, project board, and next actions for the first controlled segmentation smoke-test preparation step.
- Model registry entries for `best_catmus.pt`, `best_emanuskript_segmentation.pt`, and `best_zone_detection.pt` after compatibility inspection.
- README, roadmap, project board, and next actions for the post-inspection next step.
- Git ignore rules to protect local datasets, model weights, large image formats, archives, caches, and local database files.
- README with architecture build instructions and current project status.
- AGENTS guidance for project automation and contributor sessions.
- ROADMAP_STATUS, PROJECT_BOARD, and NEXT_ACTIONS for the post-architecture next step.
