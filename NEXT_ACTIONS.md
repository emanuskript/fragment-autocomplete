# NEXT_ACTIONS

## Next recommended task

Build the IIIF ingestion proof of concept.

## Acceptance criteria

- Parse IIIF Presentation manifests.
- Register `repository`, `manuscript`, `canvas`, and `image_asset` records.
- Cache raw manifest JSON in `iiif_manifest_cache`.
- Extract IIIF Image API service URLs.
- Store rights and attribution metadata where available.
- Validate ingestion on 3-5 sample manifests.
- Do not download huge image sets by default.
- Add tests or a validation command.
- Do not implement eManuSkript integration, reconstruction, retrieval, ML, frontend UI, or deployment as part of this proof of concept unless explicitly requested.
