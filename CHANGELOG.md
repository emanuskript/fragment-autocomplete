# CHANGELOG

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

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
- AGENTS guidance for future Codex sessions.
- ROADMAP_STATUS, PROJECT_BOARD, and NEXT_ACTIONS for the post-architecture next step.
