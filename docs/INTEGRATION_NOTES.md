# Integration Notes

## Purpose

These notes identify boundaries that could support future collaboration with IIIF-based manuscript research systems. They do not claim current compatibility with CODICUM, the Swedish National Archives, MPO data, or the Manuscript Workbench.

## Capability matrix

| Boundary | Exists now | Proposed extension |
| --- | --- | --- |
| IIIF manifest ingestion | common Presentation API v2/v3 manifests, canvases, image/service URLs, rights, attribution, raw metadata | broader IIIF coverage, collections, authentication profiles, annotations, change/refresh policy |
| Stable source identifiers | manifest URL/ID, canvas ID, source image URL, image-service URL, repository/manuscript IDs | partner namespace mapping and identifier reconciliation |
| Layout evidence | stored segmentation runs/regions, confidence, polygons/bounds, source-sized mask paths/checksums | exchangeable Web Annotation or partner-defined evidence package |
| Candidate generation/ranking | schema fields only; no engine or API | service accepting fragment/layout evidence and returning multiple ranked hypotheses |
| Proposal exchange | not implemented | versioned payload containing candidates, placement transforms, confidence/uncertainty, comparators, provenance, and rights |
| Accept/reject/review | not implemented | append-only scholarly review events, reviewer authority, rationale, and supersession links |
| External export | schema groundwork only | JSON/JSON-LD, IIIF annotations, PAGE-XML/ALTO, or tool-specific adapter after joint specification |
| MPO ingestion | not implemented | mapping study based on an approved public/schema sample; no assumptions about private data |

## Suggested inbound contract

A future ingestion adapter should accept, at minimum:

- provider/repository identifier;
- stable manuscript/object identifier;
- IIIF manifest and canvas identifiers where available;
- image or Image API service identifier;
- source rights statement, licence, attribution, and access state;
- fragment/page relationship supplied by the source, without inferring physical joins from filenames;
- optional physical dimensions and source-provided coordinates;
- raw source metadata retained unchanged for audit.

Partner-specific fields should be mapped into normalized fields only when their semantics are documented. Unknown fields should remain in a namespaced raw payload rather than being discarded or guessed.

## Suggested proposal payload

No proposal API exists yet. A future exchange object should separate evidence from inference and support multiple candidates. A minimal design could contain:

```text
proposal_id, proposal_version, status
source:
  provider_id, manuscript_id, manifest_id, canvas_id, image_service_id
observed_evidence:
  image_checksum, fragment_mask, segmentation_run_id, layout_regions
candidate:
  rank, canvas_estimate, placement_transform, layout_zones
  score, confidence, uncertainty, insufficiency_reasons
comparators:
  source_ids, retrieval/model reasons
provenance:
  software/model/data versions, parameters, timestamps, actor/process
rights:
  source rights, access, publication/demo/training state
review:
  decision, reviewer authority, rationale, supersedes
```

Confidence and uncertainty must be defined per field or method; a single unexplained score is insufficient. "Insufficient evidence" and several low-confidence candidates must be valid outcomes.

## Accept/reject semantics

Acceptance should mean that a scholar selected a candidate for a stated workflow, not that the candidate became historical truth. Review records should be append-only or versioned, preserve the original automated proposal, identify the reviewer/authority according to partner policy, and allow rejection, revision, deferral, or comparison without collapsing uncertainty.

## Export considerations

Before implementing an adapter, collaborators should agree on:

1. the authoritative source and canvas identifiers;
2. coordinate frames and transforms;
3. evidence/proposal/review versioning;
4. confidence and uncertainty semantics;
5. rights fields and permitted downstream actions;
6. whether IIIF Web Annotations, JSON-LD, PAGE-XML/ALTO, or another partner contract is the primary interchange form;
7. how missing or restricted source binaries are referenced without redistribution.

Exports must never imply that generated content overwrites or recovers missing manuscript evidence.

## Recommended first collaboration spike

Use public, rights-cleared fixture data to compare identifier, canvas, coordinate, provenance, and proposal-review models. Produce a written field mapping and round-trip test before connecting private services or moving restricted data. Do not hard-code partner endpoints, credentials, or institutional assumptions in the core modules.
