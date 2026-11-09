export type CorpusPage = {
  pageId: string;
  manuscriptId: string;
  canvasLabel: string;
  split: "train" | "validation" | "test";
  sourcePath: string;
  sourceUrl: string;
  overlayUrl: string;
  dimensions: [number, number];
  regionCount: number;
  classCounts: Record<string, number>;
  confidenceMean: number | null;
  hasExperiment: boolean;
};

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
  severity: string;
  family: string;
  decision: string;
  cohort: string;
  note: string;
  exampleUrl: string;
  semanticSeverityValidated: boolean;
};

export type Experiment = {
  taskId: string;
  damageId: string;
  severity: string;
  family: string;
  cohort: string;
  fragmentPath: string;
  survivalPath: string;
  damagePath: string;
  contentPath: string;
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

export type EvidencePayload = {
  generatedAt: string;
  corpus: {
    id: string;
    source: string;
    attribution: string;
    pageCount: number;
    localPageCount: number;
    manuscriptCount: number;
    layoutRegionCount: number;
    segmentationRunCount: number;
    pageSplitCounts: Record<string, number>;
    pages: CorpusPage[];
  };
  focus: {
    pageId: string;
    sourcePath: string;
    overlayPath: string;
    contentMaskPath: string;
    rawOutputPath: string;
    repository: string;
    canvasIdentifier: string;
    sourceSha256: string;
    selectionStatus: string;
    selectionReviewStatus: string;
    selectionReviewNote: string;
    modelId: string;
    modelSha256: string;
    runIdentitySha256: string;
    dbSegmentationRunId: string;
    dbImageAssetId: string;
    dbCanvasId: string;
    detectedLabels: string[];
    detections: Detection[];
    mappingBasis: string;
    contentBasis: string;
    selectedRegionIndex: number;
    selectedRegionLabel: string;
    selectedRegionConfidence: number;
  };
  experiments: Experiment[];
  boundaries: {
    source: string;
    model: string;
    synthetic: string;
    inference: string;
  };
};
