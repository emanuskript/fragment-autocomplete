# ROADMAP_STATUS

| Area | Expected status after 1.5 months | Concrete definition of done | Current status | Evidence / files | Next action |
| --- | --- | --- | --- | --- | --- |
| Repository / workspace | Done | Git repo, folder structure, docs skeleton, project board, basic setup instructions. | Done | README.md, AGENTS.md, docs/, src/, data/, scripts/ | Maintain as project evolves. |
| Architecture draft | Done | Complete technical architecture document with figures and PDF/HTML export. | Done | docs/01_architecture_overview.md, docs/figures/architecture/, outputs/Fragment_Autocomplete_Architecture_Draft.pdf | Review with Anna, Jeremy, SUB Göttingen, and Fragmentarium collaborators. |
| Database schema draft | In progress / Next | Initial entities and storage plan described; concrete migrations still required. | In progress / Next | Architecture document database section | Create concrete PostgreSQL/PostGIS schema and migrations. |
| Storage decision | Done or In progress | DB vs object storage strategy described. | In progress | Architecture document storage section | Confirm GWDG/object-storage/filesystem path policy. |
| IIIF ingestion proof of concept | Done | IIIF parser and image asset cache demonstrated on selected manifests. | Not started | None | Build IIIF parser and image cache prototype. |
| Initial sample dataset registration | Done | Sample complete pages/fragments registered with provenance, rights, and identifiers. | Not started | None | Register sample complete pages/fragments. |
| eManuSkript segmentation test | Done | eManuSkript run on selected sample pages/fragments with outputs reviewed. | Not started | None | Run model on selected sample pages. |
| Segmentation storage | Done or In progress | Labels, masks, polygons, confidence values, and provenance stored. | Not started | Architecture document database section | Store labels, masks, polygons, confidence values. |
| 20-30 use-case selection | In progress | Representative fragments/use cases selected for first evaluation cycle. | Not started | None | Coordinate with Anna/Jeremy to select representative fragments. |
| Evaluation criteria draft | In progress | Metrics and expert-review dimensions initially described. | In progress | docs/01_architecture_overview.md evaluation section | Create detailed evaluation rubric and metrics document. |
| Artificial fragment generator | Next | Prototype creates controlled synthetic fragment tasks from complete pages. | Not started | Architecture document artificial-fragment section | Implement artificial fragment prototype after schema. |
