import fs from "node:fs";
import path from "node:path";
import type {
  DamageLevelDecision,
  DamageTaxonomyItem,
  EvidencePayload,
  Experiment,
  ManuscriptMetadata,
  ProcessedPage,
} from "./types";

export const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const DATASET_CANDIDATES = [
  "outputs/synthetic_data/paper_profile_public_demo_v2/dataset",
  "outputs/synthetic_data/matrix_v2_public_demo/dataset",
  "outputs/synthetic_data/matrix_v1_pilot/dataset",
];
const REVIEW_PROTOTYPE_ROOT = "outputs/synthetic_data/damage_review_prototype_v2";

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

type PrototypeRecord = {
  task_id: string;
  page_id: string;
  manuscript_id: string;
  damage_id: string;
  severity: "S3";
  preview_path: string;
  effect_mask_path: string;
  content_mask: string;
  content_basis: string;
  effect_domain: {
    basis: string;
    region_indices: number[];
    pixels: number;
    page_fraction: number;
    mask_path: string;
  };
  matrix_entry: {
    source_row: number;
    content_id: string;
    damage_id: string;
    damage_type: string;
    visual_class: string;
    severity: string;
    family: string;
    decision: string;
    cohort: string;
    note: string;
    status: string;
    semantic_severity_validated: boolean;
  };
  statistics: {
    target_pixels: number;
    affected_target_pixels: number;
    measured_effect_coverage: number;
    measured_page_coverage: number;
    effect_kind: Experiment["effectKind"];
    operator_label: string;
    visible_page_change: number;
  };
};

type MatrixLevel = {
  decision: string;
  cohort: string;
  note: string;
};

type MatrixRow = {
  content_id: string;
  content_type: string;
  damage_id: string;
  damage_type: string;
  visual_class: string;
  levels: Record<"S1" | "S2" | "S3" | "S4", MatrixLevel>;
};

const CALIBRATED_LOSS_OPERATORS = new Set(["D2-01", "D2-02", "D2-03"]);

const SIDE_RULES: Record<string, Pick<DamageTaxonomyItem, "sideScope" | "sideRule">> = {
  "D2-01": {
    sideScope: "shared-leaf",
    sideRule: "Use one registered loss shape on both sides of the same leaf.",
  },
  "D2-02": {
    sideScope: "shared-leaf",
    sideRule: "Use one registered edge loss on recto and verso.",
  },
  "D2-03": {
    sideScope: "shared-leaf",
    sideRule: "Use one registered edge tear on recto and verso.",
  },
  "D2-04": {
    sideScope: "surface-specific",
    sideRule: "Model one side unless penetration through the support is documented.",
  },
  "D2-06": {
    sideScope: "surface-specific",
    sideRule: "Record and alter only the coated surface.",
  },
  "D2-07": {
    sideScope: "surface-specific",
    sideRule: "Record the side carrying the tape or adhesive residue.",
  },
  "D2-08": {
    sideScope: "surface-specific",
    sideRule: "Place deposits on one recorded surface.",
  },
  "D2-09": {
    sideScope: "surface-specific",
    sideRule: "Treat as one-sided unless paired scans show penetration.",
  },
  "D2-10": {
    sideScope: "surface-specific",
    sideRule: "Apply overwriting only to the recorded written surface.",
  },
  "D2-11": {
    sideScope: "surface-specific",
    sideRule: "Apply fading to the affected ink or pigment on one side.",
  },
  "D2-12": {
    sideScope: "surface-specific",
    sideRule: "Model surface abrasion on the recorded side only.",
  },
  "D2-13": {
    sideScope: "surface-specific",
    sideRule: "Model erasure on the altered writing surface only.",
  },
  "D2-14": {
    sideScope: "paired-surfaces",
    sideRule: "Link a donor and receiving surface; do not assume they are recto and verso.",
  },
  "D2-16": {
    sideScope: "paired-surfaces",
    sideRule: "Start from one side; add a registered reverse effect only with evidence of penetration.",
  },
  "D2-17": {
    sideScope: "paired-surfaces",
    sideRule: "Register recto and verso and model ink showing through the support.",
  },
  "D2-18": {
    sideScope: "shared-leaf",
    sideRule: "Share the same fold geometry across recto and verso.",
  },
  "D2-19": {
    sideScope: "shared-leaf",
    sideRule: "Share the same leaf deformation across recto and verso.",
  },
};

function loadDamageTaxonomy(currentPageArtifactCount: Map<string, number>): EvidencePayload["damageTaxonomy"] {
  const matrix = readJson<{
    rows: MatrixRow[];
    summary: { named_damage_types: number };
  }>("data/metadata/jeremy_damage_matrix_v3.json");
  const namedRows = matrix.rows.filter((row) => row.damage_id && row.damage_type);
  const names = new Map<string, string>();
  for (const row of namedRows) names.set(row.damage_id, row.damage_type);

  const contentId = "CT-01";
  const contentRows = namedRows.filter((row) => row.content_id === contentId);
  const items = Array.from(names.entries())
    .sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true }))
    .map(([damageId, name]): DamageTaxonomyItem => {
      const allRows = namedRows.filter((row) => row.damage_id === damageId);
      const current = contentRows.find((row) => row.damage_id === damageId);
      const side = SIDE_RULES[damageId];
      if (!current || !side) {
        throw new Error(`Damage taxonomy is incomplete for ${damageId}.`);
      }
      const severities: Array<DamageLevelDecision["severity"]> = ["S1", "S2", "S3", "S4"];
      return {
        damageId,
        name,
        visualClasses: Array.from(new Set(allRows.map((row) => row.visual_class).filter(Boolean))).sort(),
        sourceRowCount: allRows.length,
        activeOperator: (currentPageArtifactCount.get(damageId) ?? 0) > 0,
        calibratedLossOperator: CALIBRATED_LOSS_OPERATORS.has(damageId),
        currentPageArtifactCount: currentPageArtifactCount.get(damageId) ?? 0,
        decisions: severities.map((severity) => ({ severity, ...current.levels[severity] })),
        ...side,
      };
    });

  if (items.length !== matrix.summary.named_damage_types) {
    throw new Error(
      `Damage taxonomy count mismatch: matrix reports ${matrix.summary.named_damage_types}, loaded ${items.length}.`,
    );
  }

  return {
    sourceNamedTypeCount: matrix.summary.named_damage_types,
    displayedTypeCount: items.length,
    activeOperatorCount: items.filter((item) => item.activeOperator).length,
    contentId,
    contentLabel: contentRows[0]?.content_type ?? "Main text",
    items,
  };
}

function pageSide(canvasLabel: string): ProcessedPage["pageSide"] {
  if (/r$/i.test(canvasLabel)) return "recto";
  if (/v$/i.test(canvasLabel)) return "verso";
  return "not recorded";
}

function makeExperiment(record: PilotRecord, datasetRoot: string, pagePixels: number): Experiment {
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
    effectKind: "material-loss",
    measurementLabel: "Material removed",
    operatorLabel: "Content-calibrated material-loss operator",
    reviewPrototype: false,
    areaMaskPath: artifactUrl(`${datasetRoot}/${record.artifacts.content.path}`),
    measurementBasis: "selected writing region",
    areaRegionCount: 1,
    areaPageFraction: record.statistics.target_pixels / Math.max(pagePixels, 1),
    visiblePageChange: null,
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
      measuredEffectCoverage: record.statistics.measured_target_loss,
      topologyPassed: record.statistics.topology.passed,
      removedComponents: record.statistics.topology.removed_components,
      touchedEdges: record.statistics.topology.touched_edges,
    },
  };
}

function makePrototypeExperiment(record: PrototypeRecord): Experiment {
  return {
    taskId: record.task_id,
    pageId: record.page_id,
    damageId: record.damage_id,
    severity: record.severity,
    family: record.matrix_entry.family,
    cohort: record.matrix_entry.cohort,
    fragmentPath: artifactUrl(`${REVIEW_PROTOTYPE_ROOT}/${record.preview_path}`),
    survivalPath: artifactUrl(`${REVIEW_PROTOTYPE_ROOT}/${record.preview_path}`),
    damagePath: artifactUrl(`${REVIEW_PROTOTYPE_ROOT}/${record.effect_mask_path}`),
    contentPath: artifactUrl(record.content_mask),
    realismProfile: "damage_review_prototype_v2",
    visualRealismValidated: false,
    historicalDamageClaim: false,
    effectKind: record.statistics.effect_kind,
    measurementLabel: "Affected writing area",
    operatorLabel: record.statistics.operator_label,
    reviewPrototype: true,
    areaMaskPath: artifactUrl(`${REVIEW_PROTOTYPE_ROOT}/${record.effect_domain.mask_path}`),
    measurementBasis: "detected main-writing area",
    areaRegionCount: record.effect_domain.region_indices.length,
    areaPageFraction: record.effect_domain.page_fraction,
    visiblePageChange: record.statistics.visible_page_change,
    matrix: {
      sourceRow: record.matrix_entry.source_row,
      contentId: record.matrix_entry.content_id,
      damageId: record.matrix_entry.damage_id,
      damageType: record.matrix_entry.damage_type,
      visualClass: record.matrix_entry.visual_class,
      severity: record.matrix_entry.severity,
      family: record.matrix_entry.family,
      decision: record.matrix_entry.decision,
      cohort: record.matrix_entry.cohort,
      note: record.matrix_entry.note,
      status: record.matrix_entry.status,
      targetAreaFractionProxy: record.statistics.measured_effect_coverage,
      semanticSeverityValidated: false,
    },
    statistics: {
      targetPixels: record.statistics.target_pixels,
      removedTargetPixels: record.statistics.affected_target_pixels,
      measuredTargetLoss: record.statistics.measured_effect_coverage,
      measuredPageLoss: record.statistics.measured_page_coverage,
      measuredEffectCoverage: record.statistics.measured_effect_coverage,
      topologyPassed: true,
      removedComponents: 0,
      touchedEdges: [],
    },
  };
}

export function loadEvidence(): EvidencePayload {
  const datasetRoot = selectedDatasetRoot();
  const audit = readJson<{
    pages: AuditPage[];
    database: { corpus_asset_count: number; total_layout_regions: number; total_segmentation_runs: number };
  }>("data/metadata/artificial_fragment_v03_corpus_audit.json");
  const catalogue = readJson<{ records: ManuscriptMetadata[] }>(
    "data/metadata/public_demo_manuscript_metadata_v1.json",
  );
  const catalogueById = new Map(
    catalogue.records.map((record) => [record.manuscriptId, record]),
  );
  const dataset = readJson<{ tasks: Array<{ task_id: string; target_record: string }> }>(
    `${datasetRoot}/dataset.json`,
  );
  const records = dataset.tasks.map((task) =>
    readJson<PilotRecord>(`${datasetRoot}/${task.target_record}`),
  );
  const prototype = readJson<{ records: PrototypeRecord[] }>(
    `${REVIEW_PROTOTYPE_ROOT}/prototype.json`,
  );
  const prototypeByPage = prototype.records.reduce<Map<string, Experiment[]>>((pages, record) => {
    const experiments = pages.get(record.page_id) ?? [];
    experiments.push(makePrototypeExperiment(record));
    pages.set(record.page_id, experiments);
    return pages;
  }, new Map());
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
    const manuscript = catalogueById.get(first.manuscript_id);
    if (!manuscript) {
      throw new Error(`No catalogue metadata is available for ${first.manuscript_id}.`);
    }
    const canvasLabel = source.canvas_label ?? auditPage?.canvas_label ?? first.page_id.slice(0, 8);
    return {
      pageId: first.page_id,
      manuscriptId: first.manuscript_id,
      canvasLabel,
      pageSide: pageSide(canvasLabel),
      catalogue: manuscript,
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
      experiments: [
        ...pageRecords.map((record) => makeExperiment(
          record,
          datasetRoot,
          (auditPage?.dimensions_px ?? [2000, 2000]).reduce((product, side) => product * side, 1),
        )),
        ...(prototypeByPage.get(first.page_id) ?? []),
      ],
    };
  });
  const firstPageArtifactCount = new Map<string, number>();
  for (const experiment of pages[0]?.experiments ?? []) {
    firstPageArtifactCount.set(
      experiment.damageId,
      (firstPageArtifactCount.get(experiment.damageId) ?? 0) + 1,
    );
  }

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
    damageTaxonomy: loadDamageTaxonomy(firstPageArtifactCount),
  };
}
