# Fragment evidence workbench

## Purpose

The Fragment Evidence Workbench is a read-only Next.js application for following
one real manuscript page through the implemented project pipeline. It uses the
locally available e-codices corpus images, saved Mergen/eManuSkript segmentation
artifacts, Jeremy's matrix decisions, generated synthetic fragments, measurement
records, and PostgreSQL rows. It is not a mock dashboard and it does not generate
new research evidence in the browser.

The interface keeps four evidence classes distinct:

1. observed source pixels and IIIF provenance;
2. model-derived layout regions and confidence values;
3. synthetic damage masks, fragments, and measurements; and
4. future candidate inference, which is not implemented.

No displayed synthetic fragment is presented as recovered historical content.

## Run it

Node.js 20.9 or newer is recommended. From the repository root:

```bash
bash scripts/run_project_dashboard.sh
```

The launcher installs the local web dependencies when necessary and serves the
application at `http://127.0.0.1:8503/`. Use `FRAGMENT_WORKBENCH_PORT` to select a
different port.

For a live database view, start PostgreSQL/PostGIS and provide the same
`FRAGMENT_DB_*` environment variables used by the Python workflows. If the
database is unavailable, the application labels its stored run information as a
validated artifact snapshot instead of implying a live connection.

## What the application shows

- **Corpus filmstrip:** 84 locally present page images from the 85-page audited
  corpus, grouped by recorded train/validation/test split. The missing local
  raster is reported explicitly.
- **Source and layout:** the observed page, the saved Mergen overlay, individual
  masks, model identifier, confidence values, and recorded run identity.
- **Matrix decision:** the exact Jeremy matrix row, damage ID, severity, cohort,
  note, and the fact that qualitative severity still needs expert validation.
- **Synthetic experiment:** nine generated outputs for D2-01, D2-02, and D2-03
  at S2-S4, with the source, target content mask, damage mask, fragment, and a
  draggable source/fragment comparison.
- **Database:** a read-only query of the selected `segmentation_run` and its 21
  `layout_region` rows when PostgreSQL is live; otherwise an honest snapshot of
  the saved identifiers.
- **Measurements:** target-pixel loss, whole-page loss, topology checks, removed
  component count, and touched edges from the generated record.
- **Provenance:** source selection status, repository and canvas identifiers,
  model hash, source hash, and explicit evidence boundaries.

The application deliberately reads ignored local images and experiment outputs;
those binaries remain outside Git. The `/api/artifact` route only serves paths
under the approved local artifact roots. The database route is read-only and
does not expose database credentials to the browser.

## Architecture

```text
local JSON/YAML + ignored image artifacts
                    |
                    v
        Next.js server evidence adapter
          |                         |
          v                         v
whitelisted artifact API     read-only PostgreSQL API
          |                         |
          +------------+------------+
                       v
          React evidence workbench
```

`src/frontend/project_status.py` remains the compact, tested status adapter used
by the archival PDF exporter. The interactive browser application lives in
`web/` and is the current project interface. The older project-level Streamlit
dashboard was removed; the separate segmentation-only Streamlit viewer remains
available for legacy technical inspection.

## Validation

```bash
npm --prefix web run lint
npm --prefix web run build
python -m pytest -q tests/frontend/test_project_status.py
bash scripts/check_workspace.sh
python scripts/export_project_status_pdf.py
```

The generated meeting snapshot is written to the ignored
`output/pdf/Fragment_Autocomplete_Status_Dashboard_2026-11-09.pdf` path. It is an
archival report, not a substitute for the evidence workbench.
