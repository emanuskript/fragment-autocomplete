# CHANGELOG

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

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
