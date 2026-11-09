# Manuscript Fragment Demo

## Purpose

The Manuscript Fragment Demo is a read-only Next.js application for explaining
how ten real manuscript page images become controlled synthetic test fragments.
It is designed for a general audience: a compact page strip selects one fully
processed page, then the main surface shows one image, one short explanation and
one clear action at a time.

The interface keeps the evidence classes separate:

1. the observed complete page;
2. model-detected visual regions;
3. a selected writing region used only for measurement;
4. a controlled synthetic damage mask; and
5. the resulting test fragment and measured pixel loss.

The demo does not reconstruct, generate, or claim to recover missing manuscript
content.

## Run it

Node.js 20.9 or newer is recommended. From the repository root:

```bash
bash scripts/run_project_dashboard.sh
```

The launcher installs local web dependencies when necessary and serves the demo
at `http://127.0.0.1:8503/`. Use `FRAGMENT_WORKBENCH_PORT` to choose a different
port.

For the optional live storage status, start PostgreSQL/PostGIS and provide the
same `FRAGMENT_DB_*` environment variables used by the Python workflows. If the
database is unavailable, the disclosure labels its information as a validated
saved record.

## Public flow

The six main steps are:

1. **Original page** — the unchanged complete digital photograph.
2. **Find regions** — the saved layout overlay, described as visual detection
   rather than transcription or reconstruction.
3. **Select an area** — one detected block of writing chosen as the measurement
   area. This replaces the specialist phrase “content target.”
4. **Apply damage** — a controlled synthetic mask and the exact percentage of
   the selected area it removes.
5. **See the result** — the complete transparent fragment on a neutral matte, so
   removed material is visually unambiguous.
6. **Compare** — original and result shown side by side. The earlier draggable
   split control was removed because transparency made its movement appear to do
   nothing.

All ten page cards are live. Changing the page replaces the source image, layout
overlay, selected-region mask, nine damage trials, measurements and provenance;
no page is a decorative or unprocessed thumbnail. Below the main viewer, nine
page-specific variants are grouped by three plain-language damage patterns and
light, medium, or heavy measured loss. Selecting a thumbnail opens that complete
result in step five and scrolls the viewer into view.

The selected trial also has a visible classification panel derived from the
supplied taxonomy: damage code and type, matrix severity, visual class,
generation decision and measured selected-region loss. The procedural profile
is labeled synthetic and pending specialist review; it is not presented as
historically authentic damage.

## Progressive disclosure

The public surface omits personal names and keeps exact database identifiers and
hashes out of the main flow. A visible ten-row metadata table reports each page's
source identity, dimensions, detected classes, region count, selected-region
confidence, stored image/canvas/run/region bundle and source terms. Selecting a
table row opens that page in the viewer.

One collapsed disclosure retains exact depth without crowding the demonstration:

- **Exact provenance and identifiers** reports source and database identifiers,
  the Mergen/eManuSkript model identity, selected confidence and live-or-saved
  storage state.

The application reads ignored local images and generated outputs; those binaries
remain outside Git. The artifact route serves only approved local roots, and the
database route is read-only and never sends credentials to the browser.

## Architecture

```text
local metadata + real image artifacts
                    |
                    v
        Next.js server evidence adapter
          |                         |
          v                         v
whitelisted artifact API     read-only PostgreSQL API
          |                         |
          +------------+------------+
                       v
       ten-page, six-step React public demo
```

`src/frontend/project_status.py` remains the compact, tested status adapter used
by the archival PDF exporter. The interactive demo lives in `web/`. The separate
segmentation-only Streamlit viewer remains available for legacy technical
inspection; Streamlit is not used by the public demo.

## Validation

```bash
npm --prefix web run lint
npm --prefix web run build
python -m pytest -q tests/frontend/test_project_status.py
bash scripts/check_workspace.sh
```

Responsive visual inspection covers 1440 px, 768 px, and 390 px. Interaction
checks cover page selection, direct step selection, previous/next navigation,
variant selection, full fragment rendering, the side-by-side comparison, table
row selection and the optional provenance disclosure.

The 2026-11-09 validation pass completed 223 Python tests plus Ruff, Next.js
lint, a production build and the workspace validator. Automated responsive
inspection found no broken images, console errors, global horizontal overflow,
tiny text or critical visual findings. The expected page and metadata strips
scroll horizontally on narrow screens.
