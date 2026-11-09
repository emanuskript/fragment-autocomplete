"use client";

import {
  Braces,
  Check,
  CircleDot,
  Database,
  ExternalLink,
  FileCheck2,
  FlaskConical,
  Focus,
  Image as ImageIcon,
  Layers3,
  LibraryBig,
  Menu,
  PanelRightClose,
  RefreshCw,
  ScanLine,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CorpusPage, EvidencePayload, Experiment } from "../lib/types";

type ViewMode = "source" | "segmentation" | "content" | "damage" | "fragment" | "compare";
type InspectorTab = "decision" | "database" | "measurement" | "provenance";

const pipeline = [
  { id: "source", label: "Corpus", icon: LibraryBig, note: "Observed" },
  { id: "source", label: "Decision", icon: FileCheck2, note: "Recorded" },
  { id: "segmentation", label: "Segmentation", icon: ScanLine, note: "Model-derived" },
  { id: "segmentation", label: "Stored", icon: Database, note: "PostgreSQL" },
  { id: "damage", label: "Damage", icon: FlaskConical, note: "Synthetic" },
  { id: "fragment", label: "Fragment", icon: Focus, note: "Output" },
  { id: "compare", label: "Measurement", icon: ShieldCheck, note: "Computed" },
] as const;

const viewModes: Array<{ id: ViewMode; label: string }> = [
  { id: "source", label: "Source" },
  { id: "segmentation", label: "Layout" },
  { id: "content", label: "Content target" },
  { id: "damage", label: "Damage mask" },
  { id: "fragment", label: "Fragment" },
  { id: "compare", label: "Compare" },
];

const pct = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;
const shortHash = (value: string) => `${value.slice(0, 10)}…${value.slice(-8)}`;

function EvidenceImage({
  page,
  mode,
  experiment,
  focus,
  comparison,
  onComparison,
}: {
  page: CorpusPage;
  mode: ViewMode;
  experiment: Experiment;
  focus: EvidencePayload["focus"];
  comparison: number;
  onComparison: (value: number) => void;
}) {
  const hasExperiment = page.pageId === focus.pageId;
  if (!hasExperiment && mode !== "source" && mode !== "segmentation") {
    return (
      <div className="empty-state">
        <ImageIcon aria-hidden="true" />
        <strong>No synthetic experiment for this page</strong>
        <span>Choose the page marked “experiment” to follow the complete evidence chain.</span>
      </div>
    );
  }

  if (mode === "source") {
    return <img className="evidence-image" src={page.sourceUrl} alt={`Source manuscript page ${page.canvasLabel}`} />;
  }
  if (mode === "segmentation") {
    return <img className="evidence-image" src={page.overlayUrl} alt={`Mergen layout overlay for ${page.canvasLabel}`} />;
  }
  if (mode === "content") {
    return (
      <div className="layered-image">
        <img src={page.sourceUrl} alt={`Source manuscript page ${page.canvasLabel}`} />
        <img className="mask-layer content-layer" src={focus.contentMaskPath} alt="Selected model-derived content mask" />
      </div>
    );
  }
  if (mode === "damage") {
    return (
      <div className="layered-image">
        <img src={page.sourceUrl} alt={`Source manuscript page ${page.canvasLabel}`} />
        <img className="mask-layer damage-layer" src={experiment.damagePath} alt="Generated damage mask" />
      </div>
    );
  }
  if (mode === "fragment") {
    return <img className="evidence-image checker" src={experiment.fragmentPath} alt="Synthetic fragment produced from the source page" />;
  }
  return (
    <div className="compare-stage">
      <img src={page.sourceUrl} alt={`Undamaged source page ${page.canvasLabel}`} />
      <div className="compare-clip" style={{ width: `${comparison}%` }}>
        <img src={experiment.fragmentPath} alt="Synthetic fragment comparison" />
      </div>
      <div className="compare-handle" style={{ left: `${comparison}%` }} aria-hidden="true" />
      <input
        aria-label="Move comparison boundary"
        type="range"
        min="0"
        max="100"
        value={comparison}
        onChange={(event) => onComparison(Number(event.target.value))}
      />
      <span className="compare-label compare-label-left">Fragment</span>
      <span className="compare-label compare-label-right">Source</span>
    </div>
  );
}

function StatusMark({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "good" | "warn" | "neutral" }) {
  return <span className={`status-mark status-${tone}`}>{children}</span>;
}

export function EvidenceWorkbench({ evidence }: { evidence: EvidencePayload }) {
  const [selectedPageId, setSelectedPageId] = useState(evidence.focus.pageId);
  const [selectedTaskId, setSelectedTaskId] = useState(
    evidence.experiments.find((item) => item.damageId === "D2-01" && item.severity === "S3")?.taskId ?? evidence.experiments[0].taskId,
  );
  const [viewMode, setViewMode] = useState<ViewMode>("compare");
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("decision");
  const [comparison, setComparison] = useState(48);
  const [search, setSearch] = useState("");
  const [split, setSplit] = useState("all");
  const [mobileCorpus, setMobileCorpus] = useState(false);
  const [mobileInspector, setMobileInspector] = useState(false);
  const [dbState, setDbState] = useState<{
    loading: boolean;
    live: boolean;
    error?: string;
    run?: Record<string, unknown> | null;
    regions?: Array<Record<string, unknown>>;
    regionCount?: number;
    checkedAt?: string;
  }>({ loading: true, live: false });

  const selectedPage = evidence.corpus.pages.find((page) => page.pageId === selectedPageId) ?? evidence.corpus.pages[0];
  const selectedExperiment = evidence.experiments.find((item) => item.taskId === selectedTaskId) ?? evidence.experiments[0];
  const filteredPages = useMemo(() => {
    const term = search.trim().toLowerCase();
    return evidence.corpus.pages.filter((page) => {
      const matchesSplit = split === "all" || page.split === split;
      const matchesSearch = !term || `${page.manuscriptId} ${page.canvasLabel} ${page.pageId}`.toLowerCase().includes(term);
      return matchesSplit && matchesSearch;
    });
  }, [evidence.corpus.pages, search, split]);

  async function refreshDatabase() {
    setDbState((current) => ({ ...current, loading: true }));
    try {
      const response = await fetch(`/api/database/${evidence.focus.dbSegmentationRunId}`, { cache: "no-store" });
      const data = await response.json();
      setDbState({ loading: false, ...data });
    } catch (error) {
      setDbState({ loading: false, live: false, error: error instanceof Error ? error.message : "Database request failed." });
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/database/${evidence.focus.dbSegmentationRunId}`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => response.json())
      .then((data) => setDbState({ loading: false, ...data }))
      .catch((error) => {
        if (error instanceof Error && error.name === "AbortError") return;
        setDbState({
          loading: false,
          live: false,
          error: error instanceof Error ? error.message : "Database request failed.",
        });
      });
    return () => controller.abort();
  }, [evidence.focus.dbSegmentationRunId]);

  function choosePage(page: CorpusPage) {
    setSelectedPageId(page.pageId);
    setViewMode(page.hasExperiment ? "compare" : "source");
    setMobileCorpus(false);
  }

  function choosePipeline(mode: ViewMode, label: string) {
    setViewMode(mode);
    if (label === "Stored") setInspectorTab("database");
    if (label === "Decision") setInspectorTab("provenance");
    if (label === "Damage") setInspectorTab("decision");
    if (label === "Measurement") setInspectorTab("measurement");
  }

  const storageSnapshot = {
    segmentation_run: {
      id: evidence.focus.dbSegmentationRunId,
      image_asset_id: evidence.focus.dbImageAssetId,
      model_name: evidence.focus.modelId,
      status: "matched_and_reused",
    },
    layout_region_count: evidence.focus.detections.length,
    canvas_id: evidence.focus.dbCanvasId,
  };

  return (
    <main className="workbench">
      <header className="topbar">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true"><Layers3 /></span>
          <div>
            <strong>Fragment Evidence Workbench</strong>
            <span>Real page → real artifacts → explicit uncertainty</span>
          </div>
        </div>
        <div className="topbar-meta">
          <StatusMark tone="good"><CircleDot aria-hidden="true" /> Local evidence loaded</StatusMark>
          <StatusMark tone={dbState.live ? "good" : "warn"}>
            <Database aria-hidden="true" /> {dbState.loading ? "Checking PostgreSQL" : dbState.live ? "PostgreSQL live" : "Storage snapshot"}
          </StatusMark>
          <button className="icon-button mobile-only" onClick={() => setMobileCorpus(true)} aria-label="Open corpus browser"><Menu /></button>
          <button className="icon-button mobile-only" onClick={() => setMobileInspector(true)} aria-label="Open evidence inspector"><Braces /></button>
        </div>
      </header>

      <nav className="pipeline" aria-label="Evidence pipeline">
        {pipeline.map((step, index) => {
          const Icon = step.icon;
          const active = step.id === viewMode;
          return (
            <button key={`${step.label}-${index}`} aria-label={`${step.label}: ${step.note}`} className={active ? "pipeline-step active" : "pipeline-step"} onClick={() => choosePipeline(step.id, step.label)}>
              <span className="step-number">Step {index + 1}</span>
              <Icon aria-hidden="true" />
              <span><strong>{step.label}</strong><small>{step.note}</small></span>
            </button>
          );
        })}
      </nav>

      <div className="evidence-boundary" role="note">
        <span><i className="dot observed" /><span className="full-label">Observed source</span><span className="short-label">Observed</span></span>
        <span><i className="dot model" /><span className="full-label">Model-derived layout</span><span className="short-label">Layout</span></span>
        <span><i className="dot synthetic" /><span className="full-label">Synthetic damage</span><span className="short-label">Synthetic</span></span>
        <span className="boundary-note">No missing historical content is claimed or recovered.</span>
      </div>

      <div className="workspace-grid">
        <aside className={mobileCorpus ? "corpus-panel mobile-open" : "corpus-panel"}>
          <div className="panel-heading">
            <div>
              <span className="meta-label">Corpus browser</span>
              <h2>{evidence.corpus.localPageCount} local page images</h2>
            </div>
            <button className="icon-button mobile-only" onClick={() => setMobileCorpus(false)} aria-label="Close corpus browser"><X /></button>
          </div>
          <p className="corpus-origin">{evidence.corpus.source} {evidence.corpus.pageCount - evidence.corpus.localPageCount} audited raster is not present locally.</p>
          <div className="search-field">
            <Search aria-hidden="true" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find manuscript or folio" aria-label="Search corpus" />
          </div>
          <div className="split-tabs" role="group" aria-label="Filter corpus by split">
            {["all", "train", "validation", "test"].map((value) => (
              <button key={value} className={split === value ? "active" : ""} onClick={() => setSplit(value)}>{value}</button>
            ))}
          </div>
          <div className="corpus-list">
            {filteredPages.map((page) => (
              <button key={page.pageId} className={page.pageId === selectedPage.pageId ? "corpus-item selected" : "corpus-item"} onClick={() => choosePage(page)}>
                <img src={page.sourceUrl} alt="" loading="lazy" />
                <span className="corpus-item-copy">
                  <strong>{page.manuscriptId}</strong>
                  <span>folio {page.canvasLabel} · {page.regionCount} regions</span>
                  <span className="corpus-flags"><i>{page.split}</i>{page.hasExperiment && <i className="experiment-flag">experiment</i>}</span>
                </span>
              </button>
            ))}
          </div>
          <footer className="panel-footer">
            {evidence.corpus.localPageCount}/{evidence.corpus.pageCount} images · {evidence.corpus.manuscriptCount} manuscripts · {evidence.corpus.layoutRegionCount.toLocaleString()} regions
          </footer>
        </aside>

        <section className="visual-stage">
          <header className="stage-header">
            <div>
              <span className="breadcrumb">Corpus / {selectedPage.manuscriptId} / <strong>{selectedPage.canvasLabel}</strong></span>
              <h1>{selectedPage.manuscriptId} · folio {selectedPage.canvasLabel}</h1>
            </div>
            <div className="stage-header-meta">
              <StatusMark>{selectedPage.split}</StatusMark>
              <span className="mono">{selectedPage.dimensions[0]} × {selectedPage.dimensions[1]} px</span>
            </div>
          </header>

          <div className="view-tabs" role="tablist" aria-label="Visual evidence layers">
            {viewModes.map((item) => {
              const unavailable = !selectedPage.hasExperiment && !["source", "segmentation"].includes(item.id);
              return (
                <button key={item.id} role="tab" aria-selected={viewMode === item.id} className={viewMode === item.id ? "active" : ""} onClick={() => setViewMode(item.id)} disabled={unavailable}>
                  {item.label}
                </button>
              );
            })}
          </div>

          <div className="image-well">
            <EvidenceImage page={selectedPage} mode={viewMode} experiment={selectedExperiment} focus={evidence.focus} comparison={comparison} onComparison={setComparison} />
            <div className="image-caption">
              <span><ImageIcon aria-hidden="true" /> {viewMode === "segmentation" ? "Saved Mergen/eManuSkript overlay" : viewMode === "source" ? "Acquired e-codices raster" : `Experiment ${selectedExperiment.taskId}`}</span>
              <span className="mono">page {selectedPage.pageId}</span>
            </div>
          </div>

          {selectedPage.hasExperiment && (
            <div className="experiment-strip">
              <div className="experiment-strip-heading">
                <div><span className="meta-label">Jeremy matrix pilot</span><strong>9 generated fragments · choose a cell</strong></div>
                <span>D2-01 / D2-02 / D2-03 × S2 / S3 / S4</span>
              </div>
              <div className="experiment-grid">
                {evidence.experiments.map((experiment) => (
                  <button key={experiment.taskId} className={experiment.taskId === selectedExperiment.taskId ? "experiment-cell selected" : "experiment-cell"} onClick={() => { setSelectedTaskId(experiment.taskId); setViewMode("compare"); }}>
                    <img src={experiment.fragmentPath} alt="" loading="lazy" />
                    <span><strong>{experiment.damageId}</strong><small>{experiment.severity}</small></span>
                    <i>{pct(experiment.statistics.measuredTargetLoss, 0)} target loss</i>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        <aside className={mobileInspector ? "inspector-panel mobile-open" : "inspector-panel"}>
          <div className="panel-heading inspector-heading">
            <div><span className="meta-label">Evidence inspector</span><h2>{selectedPage.hasExperiment ? selectedExperiment.damageId + " · " + selectedExperiment.severity : "Page record"}</h2></div>
            <button className="icon-button mobile-only" onClick={() => setMobileInspector(false)} aria-label="Close evidence inspector"><PanelRightClose /></button>
          </div>
          <div className="inspector-tabs" role="tablist">
            {(["decision", "database", "measurement", "provenance"] as InspectorTab[]).map((tab) => (
              <button key={tab} className={inspectorTab === tab ? "active" : ""} onClick={() => setInspectorTab(tab)}>{tab}</button>
            ))}
          </div>

          {inspectorTab === "decision" && selectedPage.hasExperiment && (
            <div className="inspector-content">
              <section className="decision-lead">
                <span className="meta-label">Jeremy’s matrix decision</span>
                <h3>{selectedExperiment.matrix.decision}</h3>
                <p>{selectedExperiment.matrix.note}</p>
                <div className="decision-codes"><span>{selectedExperiment.matrix.contentId}</span><span>×</span><span>{selectedExperiment.matrix.damageId}</span><span>×</span><span>{selectedExperiment.matrix.severity}</span></div>
              </section>
              <dl className="evidence-list">
                <div><dt>Content target</dt><dd>Main text · prose / verse</dd></div>
                <div><dt>Damage family</dt><dd>{selectedExperiment.matrix.damageType} / {selectedExperiment.family}</dd></div>
                <div><dt>Cohort</dt><dd>{selectedExperiment.matrix.cohort}</dd></div>
                <div><dt>Matrix row</dt><dd className="mono">{selectedExperiment.matrix.sourceRow}</dd></div>
                <div><dt>Semantic severity</dt><dd><StatusMark tone="warn">not yet expert-validated</StatusMark></dd></div>
              </dl>
              {selectedExperiment.matrix.exampleUrl && <a className="external-link" href={selectedExperiment.matrix.exampleUrl} target="_blank" rel="noreferrer">Open Jeremy’s comparator <ExternalLink aria-hidden="true" /></a>}
              <div className="scope-warning"><ShieldCheck aria-hidden="true" /><p><strong>Synthetic experiment, not historical recovery.</strong> This record tests how layout evidence survives controlled loss.</p></div>
            </div>
          )}

          {inspectorTab === "database" && (
            <div className="inspector-content">
              <section className="db-status">
                <div>
                  <span className="meta-label">PostgreSQL evidence</span>
                  <h3>{dbState.live ? "Live rows connected" : "Committed storage snapshot"}</h3>
                </div>
                <button className="icon-button" onClick={() => void refreshDatabase()} aria-label="Refresh database status" disabled={dbState.loading}><RefreshCw className={dbState.loading ? "spin" : ""} /></button>
              </section>
              {!dbState.live && <p className="db-fallback">The local database is unavailable. The values below come from the validated storage result written by the ingestion pipeline, not a fabricated mock.</p>}
              <dl className="evidence-list">
                <div><dt>segmentation_run.id</dt><dd className="mono copyable">{evidence.focus.dbSegmentationRunId}</dd></div>
                <div><dt>image_asset_id</dt><dd className="mono copyable">{evidence.focus.dbImageAssetId}</dd></div>
                <div><dt>layout_region rows</dt><dd className="mono">{dbState.live ? dbState.regionCount : evidence.focus.detections.length}</dd></div>
                <div><dt>model_name</dt><dd>{String(dbState.run?.model_name ?? evidence.focus.modelId)}</dd></div>
              </dl>
              {dbState.live && dbState.regions ? (
                <div className="db-region-list">
                  {dbState.regions.slice(0, 8).map((region, index) => <div key={String(region.id ?? index)}><span>{String(region.label ?? "region")}</span><span className="mono">{Number(region.confidence ?? 0).toFixed(3)}</span></div>)}
                </div>
              ) : <pre className="json-block">{JSON.stringify(storageSnapshot, null, 2)}</pre>}
              {dbState.error && <p className="database-error">Connection note: {dbState.error}</p>}
            </div>
          )}

          {inspectorTab === "measurement" && selectedPage.hasExperiment && (
            <div className="inspector-content">
              <section className="measurement-lead">
                <span className="meta-label">Computed from saved masks</span>
                <strong>{pct(selectedExperiment.statistics.measuredTargetLoss)}</strong>
                <p>of the selected content target removed</p>
              </section>
              <div className="measure-bars">
                <div><span>Target loss <b>{pct(selectedExperiment.statistics.measuredTargetLoss)}</b></span><i><em style={{ width: pct(selectedExperiment.statistics.measuredTargetLoss) }} /></i></div>
                <div><span>Whole-page loss <b>{pct(selectedExperiment.statistics.measuredPageLoss, 2)}</b></span><i><em className="page-loss" style={{ width: pct(selectedExperiment.statistics.measuredPageLoss) }} /></i></div>
              </div>
              <dl className="evidence-list">
                <div><dt>Target pixels</dt><dd className="mono">{selectedExperiment.statistics.targetPixels.toLocaleString()}</dd></div>
                <div><dt>Removed target pixels</dt><dd className="mono">{selectedExperiment.statistics.removedTargetPixels.toLocaleString()}</dd></div>
                <div><dt>Removed components</dt><dd className="mono">{selectedExperiment.statistics.removedComponents}</dd></div>
                <div><dt>Topology checks</dt><dd>{selectedExperiment.statistics.topologyPassed ? <StatusMark tone="good"><Check /> passed</StatusMark> : <StatusMark tone="warn">review</StatusMark>}</dd></div>
                <div><dt>Touched edges</dt><dd>{selectedExperiment.statistics.touchedEdges.length ? selectedExperiment.statistics.touchedEdges.join(", ") : "none"}</dd></div>
              </dl>
            </div>
          )}

          {inspectorTab === "provenance" && (
            <div className="inspector-content">
              <section className="provenance-stack">
                <article><span className="provenance-index">source</span><div><strong>Observed page</strong><p>{evidence.focus.repository}; e-codices IIIF canvas.</p></div></article>
                <article><span className="provenance-index">select</span><div><strong>Selection</strong><p>{evidence.focus.selectionReviewNote}</p></div></article>
                <article><span className="provenance-index">model</span><div><strong>Layout model</strong><p>Mergen/eManuSkript model output, confidence threshold 0.25.</p></div></article>
                <article><span className="provenance-index">map</span><div><strong>Content mapping</strong><p>{evidence.focus.mappingBasis.replaceAll("_", " ")}.</p></div></article>
                <article><span className="provenance-index">damage</span><div><strong>Controlled damage</strong><p>Jeremy matrix adapter + deterministic generator seed.</p></div></article>
              </section>
              <dl className="evidence-list provenance-hashes">
                <div><dt>Source SHA-256</dt><dd className="mono">{shortHash(evidence.focus.sourceSha256)}</dd></div>
                <div><dt>Model SHA-256</dt><dd className="mono">{shortHash(evidence.focus.modelSha256)}</dd></div>
                <div><dt>Run identity</dt><dd className="mono">{shortHash(evidence.focus.runIdentitySha256)}</dd></div>
                <div><dt>Selected region</dt><dd>#{evidence.focus.selectedRegionIndex} · {evidence.focus.selectedRegionLabel} · {evidence.focus.selectedRegionConfidence.toFixed(3)}</dd></div>
              </dl>
              <a className="external-link" href={evidence.focus.canvasIdentifier} target="_blank" rel="noreferrer">Open source IIIF canvas <ExternalLink aria-hidden="true" /></a>
            </div>
          )}
        </aside>
      </div>
      {(mobileCorpus || mobileInspector) && <button className="mobile-scrim" onClick={() => { setMobileCorpus(false); setMobileInspector(false); }} aria-label="Close open panel" />}
    </main>
  );
}
