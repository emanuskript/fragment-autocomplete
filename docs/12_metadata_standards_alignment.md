# Fragment Autocomplete - Metadata Standards Alignment

## Purpose

This report records the HSP/German cataloguing normdata alignment inputs used by the local pipeline. It preserves the existing UUID/PostGIS schema while adding controlled-vocabulary support and selected normalized catalogue fields.

## Source Inputs

- Workbook: `/Users/mobasuony/Downloads/hsp_normdaten_thesauri (1).xlsx`
- Field mapping: `/Users/mobasuony/Downloads/Sources_and_Metadata_data_fields.md`

## Controlled Vocabularies

| Vocabulary | Sheet | Expected terms | Extracted terms |
| --- | --- | ---: | ---: |
| `SCRP` | SCRP – Script Types | 116 | 116 |
| `FORM` | FORM – Fragment & Object Types | 92 | 92 |
| `CODC` | CODC – Codicology | 73 | 73 |
| `BNDG` | BNDG – Binding | 240 | 240 |
| `HSP_SIMPLIFIED` | HSP simplified vocabs | 18 | 18 |

## Field Mapping Summary

- Parsed mapping tables: `18`
- Parsed mapping fields: `132`
- The mapping is treated as a standards reference, not as a direct replacement for the implemented database schema.
- Existing source metadata remains in `raw_metadata`; normalized fields are populated only when values are detectable or explicitly reviewed.

## Pipeline Implications

- IIIF ingestion and local sample registration should populate HSP-aligned fields opportunistically.
- Rights and access flags remain conservative until explicit review.
- Controlled notation assignments should reference imported `controlled_term` rows rather than free text alone.
- Segmentation, artificial-fragment generation, retrieval, and reconstruction can use normalized metadata as context, not as proof of historical reconstruction.

## Next Step

Import these vocabularies into PostgreSQL/PostGIS and validate the metadata alignment layer before expanding dataset registration.
