# 03 Data Sources

Status: current source summary; detailed evidence is in the committed metadata manifests.

| Source/resource | Implemented use | Repository content | Constraint |
| --- | --- | --- | --- |
| e-codices | IIIF manifest ingestion and deterministic complete-page corpus acquisition | specifications, URLs, checksums, decisions, and compact results | downloaded images are ignored; training remains unapproved |
| Fragmentarium | five local pilot-fragment references | metadata only | local images are ignored; source rights remain authoritative |
| Mergen / eManuSkript | primary layout-analysis checkpoints and label system | canonical repository/weight-directory references, model registry, and compact derived metadata | checkpoints excluded; masks are model evidence, not manual ground truth |
| HSP/German normdata | controlled terms and field-alignment reference | extracted terms/mapping and source checksums | original workbook/Markdown are external |
| CoMMA | possible future text/transcription/metadata support | no ingestion | not the visual training dataset |
| MPO / Swedish National Archives | possible future interoperability source | no data or private endpoint | no compatibility, access, or rights claim |

Stable upstream manifest, canvas, image-service, and source identifiers are preserved where supplied. Acquisition, publication, demonstration, and training authorization remain separate. See `README.md`, `data/README.md`, and `docs/INTEGRATION_NOTES.md`.
