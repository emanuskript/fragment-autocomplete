export type Detection = {
  index: number;
  label: string;
  confidence: number;
  bbox: number[];
  maskPath: string;
  pixelArea: number;
};

export type MatrixEntry = {
  sourceRow: number;
  contentId: string;
  damageId: string;
  damageType: string;
  visualClass: string;
  severity: string;
  family: string;
  decision: string;
  cohort: string;
  note: string;
  status: string;
  targetAreaFractionProxy: number;
  semanticSeverityValidated: boolean;
};

export type Experiment = {
  taskId: string;
  pageId: string;
  damageId: string;
  severity: string;
  family: string;
  cohort: string;
  fragmentPath: string;
  survivalPath: string;
  damagePath: string;
  contentPath: string;
  realismProfile: string;
  visualRealismValidated: boolean;
  historicalDamageClaim: boolean;
  matrix: MatrixEntry;
  statistics: {
    targetPixels: number;
    removedTargetPixels: number;
    measuredTargetLoss: number;
    measuredPageLoss: number;
    topologyPassed: boolean;
    removedComponents: number;
    touchedEdges: string[];
  };
};

export type DamageLevelDecision = {
  severity: "S1" | "S2" | "S3" | "S4";
  decision: string;
  cohort: string;
  note: string;
};

export type DamageTaxonomyItem = {
  damageId: string;
  name: string;
  visualClasses: string[];
  sourceRowCount: number;
  activeOperator: boolean;
  currentPageArtifactCount: number;
  decisions: DamageLevelDecision[];
  sideScope: "shared-leaf" | "surface-specific" | "paired-surfaces";
  sideRule: string;
};

export type ProcessedPage = {
  pageId: string;
  manuscriptId: string;
  canvasLabel: string;
  split: "train" | "validation" | "test";
  sourcePath: string;
  sourceUrl: string;
  overlayUrl: string;
  contentMaskUrl: string;
  dimensions: [number, number];
  regionCount: number;
  classCounts: Record<string, number>;
  confidenceMean: number | null;
  repository: string;
  canvasIdentifier: string;
  sourceSha256: string;
  selectionStatus: string;
  selectionReviewStatus: string;
  selectionReviewNote: string;
  attribution: string;
  license: string;
  rightsReviewStatus: string;
  trainingAllowedInSourceRecord: boolean;
  modelId: string;
  modelSha256: string;
  runIdentitySha256: string;
  dbSegmentationRunId: string;
  dbImageAssetId: string;
  dbCanvasId: string;
  storageStatus: string;
  detectedLabels: string[];
  detections: Detection[];
  mappingBasis: string;
  contentBasis: string;
  selectedRegionIndex: number;
  selectedRegionLabel: string;
  selectedRegionConfidence: number;
  experiments: Experiment[];
};

export type EvidencePayload = {
  generatedAt: string;
  corpus: {
    id: string;
    source: string;
    attribution: string;
    sourceCollectionPageCount: number;
    processedPageCount: number;
    manuscriptCount: number;
    layoutRegionCount: number;
    segmentationRunCount: number;
    pages: ProcessedPage[];
  };
  boundaries: {
    source: string;
    model: string;
    synthetic: string;
    inference: string;
  };
  damageTaxonomy: {
    sourceNamedTypeCount: number;
    displayedTypeCount: number;
    activeOperatorCount: number;
    contentId: string;
    contentLabel: string;
    items: DamageTaxonomyItem[];
  };
};
