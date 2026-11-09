import fs from "node:fs";
import path from "node:path";
import type { CorpusPage, EvidencePayload, Experiment } from "./types";

export const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const PILOT_ROOT = "outputs/synthetic_data/matrix_v1_pilot/dataset";
const FOCUS_PAGE_ID = "07b71712497e5e020af5";

function readJson<T>(relativePath: string): T {
  return JSON.parse(fs.readFileSync(path.join(PROJECT_ROOT, relativePath), "utf8")) as T;
}

function artifactUrl(relativePath: string): string {
  const normalized = path.isAbsolute(relativePath)
    ? path.relative(PROJECT_ROOT, relativePath)
    : relativePath;
  return `/api/artifact?path=${encodeURIComponent(normalized)}`;
}

type AuditPage = {
  page_id: string;
  manuscript_id: string;
  canvas_label: string;
  split: "train" | "validation" | "test";
  source_path: string;
  dimensions_px: [number, number];
  valid_mask_count: number;
  class_counts: Record<string, number>;
  confidence: { mean?: number };
};

type PilotRecord = Record<string, unknown> & {
  task_id: string;
  damage_id: string;
  severity: string;
  cohort: string;
  source_image: string;
  content_mask: string;
  segmentation_provenance: Record<string, unknown> & {
    model_id: string;
    model_sha256: string;
    run_identity_sha256: string;
    region_index: number;
    label: string;
    confidence: number;
    mapping_basis: string;
    stored_run: {
      db_image_asset_id: string;
      db_canvas_id: string;
      db_segmentation_run_id: string;
      detected_labels: string[];
      raw_output_path: string;
      overlay_path: string;
      layout_region_count: number;
    };
  };
  content_basis: string;
  matrix_entry: {
    source_row: number;
    content_id: string;
    damage_id: string;
    damage_type: string;
    severity: string;
    family: string;
    decision: string;
    cohort: string;
    note: string;
    example_url: string;
    semantic_severity_validated: boolean;
  };
  statistics: {
    target_pixels: number;
    removed_target_pixels: number;
    measured_target_loss: number;
    measured_page_loss: number;
    topology: {
      passed: boolean;
      removed_components: number;
      touched_edges: string[];
    };
  };
  artifacts: {
    fragment: { path: string };
    survival: { path: string };
    damage: { path: string };
    content: { path: string };
  };
  source_provenance: {
    source_record: {
      canvas_identifier: string;
      selection_status: string;
      selection_review_status: string;
      selection_review_note: string;
      image: { attribution: string };
    };
  };
};

type RawSegmentation = {
  repository: string;
  detections: Array<{
    index: number;
    label: string;
    confidence: number;
    bbox_xyxy: number[];
    mask_path: string;
    mask_pixel_area: number;
  }>;
};

export function loadEvidence(): EvidencePayload {
  const audit = readJson<{
    pages: AuditPage[];
    database: { corpus_asset_count: number; total_layout_regions: number; total_segmentation_runs: number };
  }>("data/metadata/artificial_fragment_v03_corpus_audit.json");
  const dataset = readJson<{ tasks: Array<{ task_id: string; target_record: string }> }>(
    `${PILOT_ROOT}/dataset.json`,
  );
  const records = dataset.tasks.map((task) =>
    readJson<PilotRecord>(`${PILOT_ROOT}/${task.target_record}`),
  );
  const first = records[0];
  const raw = readJson<RawSegmentation>(first.segmentation_provenance.stored_run.raw_output_path);
  const experimentIds = new Set(records.map((record) => record.task_id));
  const manuscriptCount = new Set(audit.pages.map((page) => page.manuscript_id)).size;
  const splitCounts = audit.pages.reduce<Record<string, number>>((counts, page) => {
    counts[page.split] = (counts[page.split] ?? 0) + 1;
    return counts;
  }, {});

  const pages: CorpusPage[] = audit.pages
    .filter((page) => fs.existsSync(path.join(PROJECT_ROOT, page.source_path)))
    .map((page) => ({
      pageId: page.page_id,
      manuscriptId: page.manuscript_id,
      canvasLabel: page.canvas_label,
      split: page.split,
      sourcePath: page.source_path,
      sourceUrl: artifactUrl(page.source_path),
      overlayUrl: artifactUrl(
        `outputs/training_corpus_segmentation/batch_01/overlays/${page.page_id}_overlay.jpg`,
      ),
      dimensions: page.dimensions_px,
      regionCount: page.valid_mask_count,
      classCounts: page.class_counts,
      confidenceMean: page.confidence.mean ?? null,
      hasExperiment: page.page_id === FOCUS_PAGE_ID && experimentIds.size > 0,
    }))
    .sort((a, b) => Number(b.hasExperiment) - Number(a.hasExperiment) || a.manuscriptId.localeCompare(b.manuscriptId));

  const experiments: Experiment[] = records.map((record) => ({
    taskId: record.task_id,
    damageId: record.damage_id,
    severity: record.severity,
    family: record.matrix_entry.family,
    cohort: record.cohort,
    fragmentPath: artifactUrl(`${PILOT_ROOT}/${record.artifacts.fragment.path}`),
    survivalPath: artifactUrl(`${PILOT_ROOT}/${record.artifacts.survival.path}`),
    damagePath: artifactUrl(`${PILOT_ROOT}/${record.artifacts.damage.path}`),
    contentPath: artifactUrl(`${PILOT_ROOT}/${record.artifacts.content.path}`),
    matrix: {
      sourceRow: record.matrix_entry.source_row,
      contentId: record.matrix_entry.content_id,
      damageId: record.matrix_entry.damage_id,
      damageType: record.matrix_entry.damage_type,
      severity: record.matrix_entry.severity,
      family: record.matrix_entry.family,
      decision: record.matrix_entry.decision,
      cohort: record.matrix_entry.cohort,
      note: record.matrix_entry.note,
      exampleUrl: record.matrix_entry.example_url,
      semanticSeverityValidated: record.matrix_entry.semantic_severity_validated,
    },
    statistics: {
      targetPixels: record.statistics.target_pixels,
      removedTargetPixels: record.statistics.removed_target_pixels,
      measuredTargetLoss: record.statistics.measured_target_loss,
      measuredPageLoss: record.statistics.measured_page_loss,
      topologyPassed: record.statistics.topology.passed,
      removedComponents: record.statistics.topology.removed_components,
      touchedEdges: record.statistics.topology.touched_edges,
    },
  }));

  return {
    generatedAt: new Date().toISOString(),
    corpus: {
      id: "ecodices_training_source_expansion_batch_01_v0_1",
      source: "Selected IIIF pages from e-codices; not a random scrape and not CoMMA.",
      attribution: first.source_provenance.source_record.image.attribution,
      pageCount: audit.database.corpus_asset_count,
      localPageCount: pages.length,
      manuscriptCount,
      layoutRegionCount: audit.database.total_layout_regions,
      segmentationRunCount: audit.database.total_segmentation_runs,
      pageSplitCounts: splitCounts,
      pages,
    },
    focus: {
      pageId: FOCUS_PAGE_ID,
      sourcePath: artifactUrl(first.source_image),
      overlayPath: artifactUrl(first.segmentation_provenance.stored_run.overlay_path),
      contentMaskPath: artifactUrl(first.content_mask),
      rawOutputPath: first.segmentation_provenance.stored_run.raw_output_path,
      repository: raw.repository,
      canvasIdentifier: first.source_provenance.source_record.canvas_identifier,
      sourceSha256: String(first.source_sha256),
      selectionStatus: first.source_provenance.source_record.selection_status,
      selectionReviewStatus: first.source_provenance.source_record.selection_review_status,
      selectionReviewNote: first.source_provenance.source_record.selection_review_note,
      modelId: first.segmentation_provenance.model_id,
      modelSha256: first.segmentation_provenance.model_sha256,
      runIdentitySha256: first.segmentation_provenance.run_identity_sha256,
      dbSegmentationRunId: first.segmentation_provenance.stored_run.db_segmentation_run_id,
      dbImageAssetId: first.segmentation_provenance.stored_run.db_image_asset_id,
      dbCanvasId: first.segmentation_provenance.stored_run.db_canvas_id,
      detectedLabels: first.segmentation_provenance.stored_run.detected_labels,
      detections: raw.detections.map((detection) => ({
        index: detection.index,
        label: detection.label,
        confidence: detection.confidence,
        bbox: detection.bbox_xyxy,
        maskPath: artifactUrl(detection.mask_path),
        pixelArea: detection.mask_pixel_area,
      })),
      mappingBasis: first.segmentation_provenance.mapping_basis,
      contentBasis: first.content_basis,
      selectedRegionIndex: first.segmentation_provenance.region_index,
      selectedRegionLabel: first.segmentation_provenance.label,
      selectedRegionConfidence: first.segmentation_provenance.confidence,
    },
    experiments,
    boundaries: {
      source: "Observed source image and IIIF metadata from e-codices.",
      model: "Layout regions are Mergen/eManuSkript model outputs, not expert annotations.",
      synthetic: "Damage and resulting fragments are generated experimental artifacts.",
      inference: "No missing historical content is recovered or claimed here.",
    },
  };
}
