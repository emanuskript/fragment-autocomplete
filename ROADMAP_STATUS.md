# ROADMAP_STATUS

| Area | Expected status after 1.5 months | Concrete definition of done | Current status | Evidence / files | Next action |
| --- | --- | --- | --- | --- | --- |
| Repository / workspace | Done | Git repo created, folder structure, docs skeleton, project board, basic setup instructions | Done | README.md, AGENTS.md, PROJECT_BOARD.md, docs/, src/, data/ | Draft architecture + database schema |
| Architecture draft | In progress | System boundaries, data flow, interfaces, and key dependencies documented | Not started | docs/01_architecture_overview.md | Draft architecture overview |
| Database schema draft | In progress | Core entities, relations, spatial needs, and candidate reconstruction records outlined | Not started | docs/02_database_plan.md | Draft entity model and storage notes |
| Storage decision | In progress | Filesystem or object storage approach compared and documented with rationale | Not started | docs/02_database_plan.md, docs/06_risks_and_decisions.md | Draft storage decision |
| IIIF ingestion proof of concept | In progress | One narrow path for IIIF manifest acquisition and asset registration demonstrated | Not started | src/ingestion/, docs/03_data_sources.md | Define proof-of-concept scope |
| Initial sample dataset registration | In progress | First sample sources registered with provenance, rights, and identifiers | Not started | docs/03_data_sources.md, data/metadata/ | Register candidate sample sources |
| eManuSkript segmentation test | In progress | First segmentation trial planned against a narrow sample set | Not started | src/ml/, docs/01_architecture_overview.md | Define segmentation test setup |
| Segmentation storage | In progress | Representation for segmentation outputs and annotations documented | Not started | docs/02_database_plan.md | Design segmentation storage model |
| 20–30 use-case selection | In progress | Priority use cases selected and bounded for the first evaluation cycle | Not started | docs/05_use_cases_20_30.md | Draft shortlist criteria |
| Evaluation criteria draft | In progress | Reconstruction quality, provenance, and uncertainty criteria documented | Not started | docs/04_evaluation_plan.md | Draft evaluation dimensions |
| Artificial fragment generator | In progress | Generator goal, inputs, outputs, and evaluation role defined | Not started | docs/04_evaluation_plan.md, src/evaluation/ | Define generator purpose and limits |
