import fs from "node:fs";
import path from "node:path";
import type { EvidencePayload, Experiment, ProcessedPage } from "./types";

export const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const DATASET_CANDIDATES = [
  "outputs/synthetic_data/paper_profile_public_demo_v2/dataset",
  "outputs/synthetic_data/matrix_v2_public_demo/dataset",
  "outputs/synthetic_data/matrix_v1_pilot/dataset",
];

function readJson<T>(relativePath: string): T {
  return JSON.parse(fs.readFileSync(path.join(PROJECT_ROOT, relativePath), "utf8")) as T;
}

function artifactUrl(filePath: string): string {
  const normalized = path.isAbsolute(filePath) ? path.relative(PROJECT_ROOT, filePath) : filePath;
  return `/api/artifact?path=${encodeURIComponent(normalized)}`;
}

function selectedDatasetRoot(): string {
  const root = DATASET_CANDIDATES.find((candidate) =>
    fs.existsSync(path.join(PROJECT_ROOT, candidate, "dataset.json")),
  );
  if (!root) throw new Error("No generated demonstration dataset is available.");
  return root;
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

type SourceRecord = {
  canvas_identifier: string;
  canvas_label: string;
  selection_status: string;
  selection_review_status: string;
  selection_review_note: string;
  image: {
    attribution: string;
    license?: string;
    rights_statement?: string;
    rights_review_status?: string;
    training_allowed?: boolean;
  };
};

type PilotRecord = {
  task_id: string;
  page_id: string;
  manuscript_id: string;
  split: "train" | "validation" | "test";
  damage_id: string;
  severity: string;
  cohort: string;
  source_image: string;
  source_sha256: string;
  content_mask: string;
  content_basis: string;
  realism_profile?: string;
  visual_realism_validated?: boolean;
  historical_damage_claim?: boolean;
  segmentation_provenance: {
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
      status: string;
    };
  };
  matrix_entry: {
    source_row: number;
    content_id: string;
    damage_id: string;
    damage_type: string;
    visual_class?: string;
    severity: string;
    family: string;
    decision: string;
    cohort: string;
    note: string;
    status?: string;
    target_area_fraction_proxy?: number;
    semantic_severity_validated: boolean;
  };
  statistics: {
    target_pixels: number;
    removed_target_pixels: number;
    target_area_fraction_proxy: number;
    measured_target_loss: number;
    measured_page_loss: number;
    topology: { passed: boolean; removed_components: number; touched_edges: string[] };
  };
  artifacts: {
    fragment: { path: string };
    survival: { path: string };
    damage: { path: string };
    content: { path: string };
  };
  source_provenance: { source_record: SourceRecord };
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

function makeExperiment(record: PilotRecord, datasetRoot: string): Experiment {
  return {
    taskId: record.task_id,
    pageId: record.page_id,
    damageId: record.damage_id,
    severity: record.severity,
    family: record.matrix_entry.family,
    cohort: record.cohort,
    fragmentPath: artifactUrl(`${datasetRoot}/${record.artifacts.fragment.path}`),
    survivalPath: artifactUrl(`${datasetRoot}/${record.artifacts.survival.path}`),
    damagePath: artifactUrl(`${datasetRoot}/${record.artifacts.damage.path}`),
    contentPath: artifactUrl(`${datasetRoot}/${record.artifacts.content.path}`),
    realismProfile: record.realism_profile ?? "geometric_v1",
    visualRealismValidated: Boolean(record.visual_realism_validated),
    historicalDamageClaim: Boolean(record.historical_damage_claim),
    matrix: {
      sourceRow: record.matrix_entry.source_row,
      contentId: record.matrix_entry.content_id,
      damageId: record.matrix_entry.damage_id,
      damageType: record.matrix_entry.damage_type,
      visualClass: record.matrix_entry.visual_class ?? "Not recorded",
      severity: record.matrix_entry.severity,
      family: record.matrix_entry.family,
      decision: record.matrix_entry.decision,
      cohort: record.matrix_entry.cohort,
      note: record.matrix_entry.note,
      status: record.matrix_entry.status ?? "eligible",
      targetAreaFractionProxy:
        record.matrix_entry.target_area_fraction_proxy ?? record.statistics.target_area_fraction_proxy,
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
  };
}

export function loadEvidence(): EvidencePayload {
  const datasetRoot = selectedDatasetRoot();
  const audit = readJson<{
    pages: AuditPage[];
    database: { corpus_asset_count: number; total_layout_regions: number; total_segmentation_runs: number };
  }>("data/metadata/artificial_fragment_v03_corpus_audit.json");
  const dataset = readJson<{ tasks: Array<{ task_id: string; target_record: string }> }>(
    `${datasetRoot}/dataset.json`,
  );
  const records = dataset.tasks.map((task) =>
    readJson<PilotRecord>(`${datasetRoot}/${task.target_record}`),
  );
  const auditById = new Map(audit.pages.map((page) => [page.page_id, page]));
  const grouped = records.reduce<Map<string, PilotRecord[]>>((pages, record) => {
    const pageRecords = pages.get(record.page_id) ?? [];
    pageRecords.push(record);
    pages.set(record.page_id, pageRecords);
    return pages;
  }, new Map());

  const pages: ProcessedPage[] = Array.from(grouped.values()).map((pageRecords) => {
    const first = pageRecords[0];
    const stored = first.segmentation_provenance.stored_run;
    const raw = readJson<RawSegmentation>(stored.raw_output_path);
    const auditPage = auditById.get(first.page_id);
    const source = first.source_provenance.source_record;
    const rights = source.image;
    return {
      pageId: first.page_id,
      manuscriptId: first.manuscript_id,
      canvasLabel: source.canvas_label ?? auditPage?.canvas_label ?? first.page_id.slice(0, 8),
      split: first.split,
      sourcePath: first.source_image,
      sourceUrl: artifactUrl(first.source_image),
      overlayUrl: artifactUrl(stored.overlay_path),
      contentMaskUrl: artifactUrl(first.content_mask),
      dimensions: auditPage?.dimensions_px ?? [2000, 2000],
      regionCount: stored.layout_region_count,
      classCounts: auditPage?.class_counts ?? {},
      confidenceMean: auditPage?.confidence.mean ?? null,
      repository: raw.repository || "e-codices",
      canvasIdentifier: source.canvas_identifier,
      sourceSha256: first.source_sha256,
      selectionStatus: source.selection_status,
      selectionReviewStatus: source.selection_review_status,
      selectionReviewNote: source.selection_review_note,
      attribution: rights.attribution,
      license: rights.license ?? rights.rights_statement ?? "Not recorded",
      rightsReviewStatus: rights.rights_review_status ?? "Not recorded",
      trainingAllowedInSourceRecord: Boolean(rights.training_allowed),
      modelId: first.segmentation_provenance.model_id,
      modelSha256: first.segmentation_provenance.model_sha256,
      runIdentitySha256: first.segmentation_provenance.run_identity_sha256,
      dbSegmentationRunId: stored.db_segmentation_run_id,
      dbImageAssetId: stored.db_image_asset_id,
      dbCanvasId: stored.db_canvas_id,
      storageStatus: stored.status,
      detectedLabels: stored.detected_labels,
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
      experiments: pageRecords.map((record) => makeExperiment(record, datasetRoot)),
    };
  });

  return {
    generatedAt: new Date().toISOString(),
    corpus: {
      id: "ecodices_training_source_expansion_batch_01_v0_1",
      source: "Ten deterministically selected e-codices IIIF pages from the local segmented corpus.",
      attribution: pages[0]?.attribution ?? "e-codices",
      sourceCollectionPageCount: audit.database.corpus_asset_count,
      processedPageCount: pages.length,
      manuscriptCount: new Set(pages.map((page) => page.manuscriptId)).size,
      layoutRegionCount: pages.reduce((total, page) => total + page.regionCount, 0),
      segmentationRunCount: pages.length,
      pages,
    },
    boundaries: {
      source: "Observed source images and IIIF metadata from e-codices.",
      model: "Layout regions are Mergen/eManuSkript model outputs, not expert annotations.",
      synthetic: "Damage and resulting fragments are controlled synthetic artifacts; their shapes await specialist review.",
      inference: "No missing historical content is recovered or claimed here.",
    },
  };
}
