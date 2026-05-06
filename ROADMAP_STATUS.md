# ROADMAP_STATUS

| Area | Expected status after 1.5 months | Concrete definition of done | Current status | Evidence / files | Next action |
| --- | --- | --- | --- | --- | --- |
| Repository / workspace | Done | Git repo, folder structure, docs skeleton, project board, basic setup instructions. | Done | README.md, AGENTS.md, docs/, src/, data/, scripts/ | Maintain as project evolves. |
| Architecture draft | Done | Complete technical architecture document with figures and PDF/HTML export. | Done | docs/01_architecture_overview.md, docs/figures/architecture/, outputs/Fragment_Autocomplete_Architecture_Draft.pdf | Review with Anna, Jeremy, SUB Göttingen, and Fragmentarium collaborators. |
| Database schema draft | Done | PostgreSQL/PostGIS Docker setup, SQL migration, seed values, validation script, and schema documentation. | Done | infra/db/docker-compose.yml, infra/db/migrations/001_init.sql, infra/db/seed/001_seed_lookup_values.sql, scripts/db_validate.sh, docs/02_database_plan.md | Build the IIIF ingestion proof of concept. |
| Storage decision | Done or In progress | DB vs object storage strategy described; final institutional path policy still needs confirmation. | In progress | docs/02_database_plan.md, docs/01_architecture_overview.md storage section | Confirm GWDG/object-storage/filesystem path policy. |
| IIIF ingestion proof of concept | Done | IIIF parser and image asset cache demonstrated on selected manifests. | Not started | None | Build IIIF parser and image cache prototype. |
| Initial sample dataset registration | Done | Sample complete pages/fragments registered with provenance, rights, and identifiers. | Not started | None | Register sample complete pages/fragments after IIIF proof of concept. |
| eManuSkript segmentation test | Done | eManuSkript run on selected sample pages/fragments with outputs reviewed. | Not started | None | Run model on selected sample pages after sample registration. |
| Segmentation storage | Done or In progress | Labels, masks, polygons, confidence values, and provenance can be stored in schema. | Schema ready, implementation not tested | infra/db/migrations/001_init.sql, docs/02_database_plan.md | Test storage with real eManuSkript outputs after segmentation run. |
| 20-30 use-case selection | In progress | Representative fragments/use cases selected for first evaluation cycle. | Not started | None | Coordinate with Anna/Jeremy to select representative fragments. |
| Evaluation criteria draft | In progress | Metrics and expert-review dimensions initially described. | In progress | docs/01_architecture_overview.md evaluation section, docs/02_database_plan.md | Create detailed evaluation rubric and metrics document. |
| Artificial fragment generator | Next | Prototype creates controlled synthetic fragment tasks from complete pages. | Not started | docs/02_database_plan.md artificial-fragment schema section | Implement artificial fragment prototype after IIIF/sample data foundation. |
