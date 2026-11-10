"use client";

import Image from "next/image";
import { Check, ChevronLeft, ChevronRight, Database, Layers3 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type {
  DamageLevelDecision,
  DamageTaxonomyItem,
  EvidencePayload,
  Experiment,
  ProcessedPage,
} from "../lib/types";

type DemoStep = "source" | "layout" | "area" | "damage" | "result" | "compare";

const steps: Array<{ id: DemoStep; label: string; title: string }> = [
  { id: "source", label: "Original page", title: "Start with the complete page" },
  { id: "layout", label: "Find regions", title: "Find the page’s visual regions" },
  { id: "area", label: "Select an area", title: "Choose one writing region to measure" },
  { id: "damage", label: "Apply damage", title: "Apply a controlled damage shape" },
  { id: "result", label: "See the result", title: "Create the test fragment" },
  { id: "compare", label: "Compare", title: "Compare before and after" },
];

const severityLabels: Record<string, string> = { S2: "Light", S3: "Medium", S4: "Heavy" };
const percentage = (value: number, digits = 0) => `${(value * 100).toFixed(digits)}%`;
const shortLicense = (value: string) => {
  if (value.includes("by-nc/4.0")) return "CC BY-NC 4.0";
  if (value.includes("publicdomain/zero/1.0")) return "CC0 1.0";
  return value;
};
const plainMatrixNote = (value: string) => value
  .replaceAll("content target", "selected writing region")
  .replaceAll("content object", "selected writing region");

function stepDescription(step: DemoStep, experiment: Experiment): string {
  const amount = percentage(experiment.statistics.measuredEffectCoverage);
  const family = experiment.matrix.damageType;
  const materialLoss = experiment.effectKind === "material-loss";
  return {
    source: "This unchanged digital photograph is the reference for every later step.",
    layout: "The layout model marks writing, page numbers, decoration, and other visual regions. It detects shapes; it does not read or reconstruct the text.",
    area: "One detected writing region is selected. All loss percentages are measured against this exact region, not against the whole page.",
    damage: materialLoss
      ? `A ${family.toLowerCase()} mask removes ${amount} of the selected writing region. The seeded shape and measured amount can be reproduced.`
      : `A deterministic ${family.toLowerCase()} field affects ${amount} of the selected writing region. Its mask and settings can be reproduced.`,
    result: materialLoss
      ? "The masked pixels become transparent. No text, decoration, or missing historical material is painted into the gap."
      : "The controlled visual transformation is applied to the observed page. It is a review prototype, not a claim about historical damage.",
    compare: "The unchanged source and generated review image are shown together so the synthetic intervention stays visible.",
  }[step];
}

function ManuscriptImage({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  return (
    <Image
      unoptimized
      src={src}
      alt={alt}
      width={2000}
      height={2471}
      className={className}
      sizes="(max-width: 760px) 92vw, 760px"
      loading="eager"
    />
  );
}

function DemoVisual({ step, page, experiment }: { step: DemoStep; page: ProcessedPage; experiment: Experiment }) {
  if (step === "source") {
    return <ManuscriptImage src={page.sourceUrl} alt="Complete manuscript page before synthetic damage" />;
  }
  if (step === "layout") {
    return <ManuscriptImage src={page.overlayUrl} alt="Page with model-detected visual regions outlined" />;
  }
  if (step === "area") {
    return (
      <div className="layered-visual">
        <ManuscriptImage src={page.sourceUrl} alt="Complete manuscript page" />
        <ManuscriptImage src={page.contentMaskUrl} alt="Selected writing region" className="area-overlay" />
      </div>
    );
  }
  if (step === "damage") {
    return (
      <div className="layered-visual">
        <ManuscriptImage src={page.sourceUrl} alt="Complete manuscript page" />
        <ManuscriptImage src={experiment.damagePath} alt="Controlled synthetic damage shape" className="damage-overlay" />
      </div>
    );
  }
  if (step === "result") {
    return (
      <div className="fragment-matte">
        <ManuscriptImage src={experiment.fragmentPath} alt="Generated synthetic damage review image" />
      </div>
    );
  }
  return (
    <div className="comparison-pair">
      <figure>
        <div className="comparison-image source-matte">
          <ManuscriptImage src={page.sourceUrl} alt="Original complete manuscript page" />
        </div>
        <figcaption>Original page</figcaption>
      </figure>
      <figure>
        <div className="comparison-image fragment-matte">
          <ManuscriptImage src={experiment.fragmentPath} alt="Generated synthetic damage review image" />
        </div>
        <figcaption>Synthetic review image</figcaption>
      </figure>
    </div>
  );
}

function PageBrowser({ pages, selectedPageId, onSelect }: {
  pages: ProcessedPage[];
  selectedPageId: string;
  onSelect: (page: ProcessedPage) => void;
}) {
  return (
    <section className="page-browser" aria-labelledby="pages-heading">
      <div className="compact-heading">
        <div>
          <h2 id="pages-heading">{pages.length} processed pages</h2>
          <p>Every page has layout regions, a selected writing area, all 17 damage types, and stored metadata.</p>
        </div>
        <span>Choose a page</span>
      </div>
      <div className="page-strip">
        {pages.map((page, index) => {
          const selected = page.pageId === selectedPageId;
          return (
            <button
              type="button"
              key={page.pageId}
              className={selected ? "page-choice selected" : "page-choice"}
              onClick={() => onSelect(page)}
              aria-pressed={selected}
            >
              <span className="page-thumb">
                <Image unoptimized src={page.sourceUrl} alt="" width={150} height={185} loading={index < 5 ? "eager" : "lazy"} />
              </span>
              <strong>Page {page.canvasLabel}</strong>
              <small>{page.catalogue.shelfmark ?? page.manuscriptId}</small>
              <i>{page.regionCount} regions</i>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function DamageClassification({ experiment }: { experiment: Experiment }) {
  return (
    <section className="classification" aria-labelledby="classification-heading">
      <div className="classification-title">
        <span>Defined damage classification</span>
        <h2 id="classification-heading">{experiment.damageId} · {experiment.matrix.damageType}</h2>
      </div>
      <dl>
        <div><dt>Matrix severity</dt><dd>{severityLabels[experiment.severity]} · {experiment.severity}</dd></div>
        <div><dt>Visual class</dt><dd>{experiment.matrix.visualClass}</dd></div>
        <div><dt>{experiment.measurementLabel}</dt><dd>{percentage(experiment.statistics.measuredEffectCoverage, 1)} of selected region</dd></div>
        <div><dt>Generation decision</dt><dd>{experiment.matrix.decision}</dd></div>
      </dl>
      <p>{plainMatrixNote(experiment.matrix.note)}</p>
      <small>{experiment.operatorLabel}. Visual realism awaits specialist review; this is not evidence of historical damage.</small>
    </section>
  );
}

const decisionLabel = (decision: string) => ({
  "do not generate": "Exclude",
  "generate for general training": "General",
  "generate as edge case": "Edge case",
}[decision] ?? "Review");

function compactDecisions(decisions: DamageLevelDecision[]): string {
  return decisions.map((item) => `${item.severity} ${decisionLabel(item.decision)}`).join(" · ");
}

function DamageTaxonomy({
  taxonomy,
  onChoose,
}: {
  taxonomy: EvidencePayload["damageTaxonomy"];
  onChoose: (damageId: string) => void;
}) {
  return (
    <section className="taxonomy-section" aria-labelledby="taxonomy-heading">
      <div className="section-heading taxonomy-heading">
        <div>
          <h2 id="taxonomy-heading">Complete damage taxonomy</h2>
          <p>
            The supplied source contains {taxonomy.sourceNamedTypeCount} named types—not 16.
            All {taxonomy.displayedTypeCount} are shown here; D2-05 and D2-15 are absent from its numbering.
          </p>
        </div>
        <dl className="taxonomy-totals" aria-label="Damage taxonomy coverage">
          <div><dt>Ready to review</dt><dd>{taxonomy.activeOperatorCount}</dd></div>
          <div><dt>Calibrated loss operators</dt><dd>{taxonomy.items.filter((item) => item.calibratedLossOperator).length}</dd></div>
        </dl>
      </div>
      <div className="taxonomy-table-wrap">
        <table className="taxonomy-table">
          <thead>
            <tr>
              <th>Damage type</th>
              <th>{taxonomy.contentId} decisions</th>
              <th>Recto / verso handling</th>
              <th>Current output</th>
            </tr>
          </thead>
          <tbody>
            {taxonomy.items.map((item: DamageTaxonomyItem) => (
              <tr key={item.damageId}>
                <td>
                  <strong>{item.damageId} · {item.name}</strong>
                  <span>{item.visualClasses.join(" · ") || "No visual class recorded"}</span>
                </td>
                <td>{compactDecisions(item.decisions)}</td>
                <td>
                  <strong>{item.sideScope.replaceAll("-", " ")}</strong>
                  <span>{item.sideRule}</span>
                </td>
                <td>
                  <button type="button" className="taxonomy-action" onClick={() => onChoose(item.damageId)}>
                    View generated example
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="table-note">
        Severity decisions shown here are for {taxonomy.contentLabel}. Every type has a deterministic S3 review image. The three material-loss operators are pixel-calibrated; the other visual operators are prototypes awaiting specialist realism review.
      </p>
    </section>
  );
}

function MetadataTable({ pages, selectedPageId, onSelect }: {
  pages: ProcessedPage[];
  selectedPageId: string;
  onSelect: (page: ProcessedPage) => void;
}) {
  const selected = pages.find((page) => page.pageId === selectedPageId) ?? pages[0];
  const record = selected.catalogue;
  const value = (item: string | number | null) => item ?? "Not supplied by source";
  return (
    <section className="metadata-section" aria-labelledby="metadata-heading">
      <div className="section-heading">
        <h2 id="metadata-heading">Digested page metadata</h2>
        <p>One row per processed page, combining catalogue identity with layout analysis and storage results.</p>
      </div>
      <div className="metadata-table-wrap">
        <table className="metadata-table">
          <thead>
            <tr>
              <th>Page and side</th>
              <th>Repository and shelfmark</th>
              <th>Date</th>
              <th>Work and language</th>
              <th>Material and writing</th>
              <th>Layout digestion</th>
              <th>Database storage</th>
              <th>Source terms</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((page) => (
              <tr key={page.pageId} className={page.pageId === selectedPageId ? "active" : ""}>
                <td>
                  <button type="button" className="table-page-link" onClick={() => onSelect(page)}>
                    <strong>{page.manuscriptId}</strong>
                    <span>page {page.canvasLabel} · {page.pageSide}</span>
                  </button>
                </td>
                <td><strong>{page.catalogue.shelfmark ?? "Shelfmark not supplied"}</strong><span>{page.catalogue.repository ?? "Repository not supplied"}</span></td>
                <td>
                  {page.catalogue.dateDisplay ?? "Not supplied"}
                  <span>{page.catalogue.century === page.catalogue.dateDisplay ? "Century supplied as catalogue date" : page.catalogue.century ?? "Century not supplied"}</span>
                </td>
                <td><strong>{page.catalogue.title ?? "Title not supplied"}</strong><span>{page.catalogue.languages.join(" · ") || "Language not supplied"} · {page.catalogue.documentType ?? "type not supplied"}</span></td>
                <td>{page.catalogue.material ?? "Not supplied"}<span>Script / hand: {page.catalogue.scriptOrHand ?? "not supplied"} · Font: {page.catalogue.typefaceOrFont ?? "not catalogued"}</span></td>
                <td><strong>{page.regionCount} region rows</strong><span>{page.detectedLabels.join(" · ")}</span></td>
                <td><strong>Stored</strong><span>image + canvas + run + {page.regionCount} regions</span></td>
                <td>{shortLicense(page.license)}<span>{page.rightsReviewStatus.replaceAll("_", " ")}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="table-note">Selecting a row opens that page in the viewer and updates the complete catalogue record below. “Stored” reflects the saved ingestion record; the interface checks the live local database when available.</p>
      <article className="catalogue-record" aria-labelledby="catalogue-record-heading">
        <div className="catalogue-record-title">
          <h3 id="catalogue-record-heading">Selected manuscript record</h3>
          <span>{record.metadataSource}</span>
        </div>
        <dl className="catalogue-grid">
          <div><dt>Repository</dt><dd>{value(record.repository)}</dd></div>
          <div><dt>Shelfmark</dt><dd>{value(record.shelfmark)}</dd></div>
          <div><dt>Page / side</dt><dd>{selected.canvasLabel} · {selected.pageSide}</dd></div>
          <div><dt>Title</dt><dd>{value(record.title)}</dd></div>
          <div><dt>Date</dt><dd>{value(record.dateDisplay)}</dd></div>
          <div><dt>Century</dt><dd>{value(record.century)}</dd></div>
          <div><dt>Language</dt><dd>{record.languages.join(" · ") || "Not supplied by source"}</dd></div>
          <div><dt>Document type</dt><dd>{value(record.documentType)}</dd></div>
          <div><dt>Material</dt><dd>{value(record.material)}</dd></div>
          <div><dt>Script / hand</dt><dd>{value(record.scriptOrHand)}</dd></div>
          <div><dt>Typeface / font</dt><dd>{record.typefaceOrFont ?? "Not catalogued for this manuscript"}</dd></div>
          <div><dt>Physical dimensions</dt><dd>{value(record.dimensions)}</dd></div>
          <div><dt>Catalogue page count</dt><dd>{value(record.pageCount)}</dd></div>
          <div><dt>Place of origin</dt><dd>{value(record.placeOfOrigin)}</dd></div>
          <div><dt>DOI</dt><dd>{value(record.doi)}</dd></div>
          <div><dt>Online since</dt><dd>{value(record.onlineSince)}</dd></div>
          <div><dt>Digitized by</dt><dd>{value(record.digitizedBy)}</dd></div>
          <div><dt>People named</dt><dd>{value(record.persons)}</dd></div>
          <div className="catalogue-summary"><dt>Catalogue summary</dt><dd>{value(record.summary)}</dd></div>
        </dl>
        <p className="catalogue-caveat">“Main script black” is a layout class produced by Mergen; it is not a palaeographic identification of script, hand, or font. Missing catalogue fields remain explicitly missing.</p>
      </article>
    </section>
  );
}

export function EvidenceWorkbench({ evidence }: { evidence: EvidencePayload }) {
  const firstPage = evidence.corpus.pages[0];
  const firstExperiment = firstPage.experiments.find(
    (item) => item.damageId === "D2-03" && item.severity === "S3",
  ) ?? firstPage.experiments[0];
  const [step, setStep] = useState<DemoStep>("source");
  const [selectedPageId, setSelectedPageId] = useState(firstPage.pageId);
  const [selectedTaskId, setSelectedTaskId] = useState(firstExperiment.taskId);
  const [database, setDatabase] = useState<{ loading: boolean; live: boolean; regionCount?: number }>({
    loading: true,
    live: false,
  });
  const demoRef = useRef<HTMLElement>(null);
  const page = evidence.corpus.pages.find((item) => item.pageId === selectedPageId) ?? firstPage;
  const selectedExperiment = page.experiments.find((item) => item.taskId === selectedTaskId)
    ?? page.experiments.find((item) => item.damageId === "D2-03" && item.severity === "S3")
    ?? page.experiments[0];
  const activeStepIndex = steps.findIndex((item) => item.id === step);

  useEffect(() => {
    const controller = new AbortController();
    const loadDatabaseState = async () => {
      try {
        const response = await fetch(`/api/database/${page.dbSegmentationRunId}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = await response.json();
        setDatabase({ loading: false, live: Boolean(data.live), regionCount: data.regionCount });
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
        setDatabase({ loading: false, live: false });
      }
    };
    void loadDatabaseState();
    return () => controller.abort();
  }, [page.dbSegmentationRunId]);

  const scrollToViewer = () => {
    requestAnimationFrame(() => {
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      demoRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    });
  };

  const selectPage = (nextPage: ProcessedPage, shouldScroll = false) => {
    const defaultExperiment = nextPage.experiments.find(
      (item) => item.damageId === "D2-03" && item.severity === "S3",
    ) ?? nextPage.experiments[0];
    setSelectedPageId(nextPage.pageId);
    setSelectedTaskId(defaultExperiment.taskId);
    setDatabase({ loading: true, live: false });
    setStep("source");
    if (shouldScroll) scrollToViewer();
  };

  const changeStep = (nextStep: DemoStep) => {
    setStep(nextStep);
    scrollToViewer();
  };

  const chooseExperiment = (experiment: Experiment) => {
    setSelectedTaskId(experiment.taskId);
    setStep("result");
    scrollToViewer();
  };

  const chooseDamageType = (damageId: string) => {
    const experiment = page.experiments.find(
      (item) => item.damageId === damageId && item.severity === "S3",
    ) ?? page.experiments.find((item) => item.damageId === damageId);
    if (experiment) chooseExperiment(experiment);
  };

  return (
    <main className="public-demo">
      <header className="demo-intro">
        <div className="demo-mark" aria-hidden="true"><Layers3 /></div>
        <div>
          <h1>From complete pages to test fragments</h1>
          <p>Browse {evidence.corpus.processedPageCount} real page images and inspect every recorded step applied to each one.</p>
        </div>
      </header>

      <PageBrowser pages={evidence.corpus.pages} selectedPageId={page.pageId} onSelect={(item) => selectPage(item)} />

      <nav className="step-navigation" aria-label="Demo steps">
        {steps.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={item.id === step ? "step-button active" : "step-button"}
            onClick={() => changeStep(item.id)}
            aria-current={item.id === step ? "step" : undefined}
          >
            <span>{index + 1}</span>
            <strong>{item.label}</strong>
          </button>
        ))}
      </nav>

      <section className="demo-stage" ref={demoRef}>
        <div className="step-explanation">
          <span className="step-count">Step {activeStepIndex + 1} of {steps.length}</span>
          <h2>{steps[activeStepIndex].title}</h2>
          <p>{stepDescription(step, selectedExperiment)}</p>
          <div className="page-context">
            <span>{page.catalogue.shelfmark ?? page.manuscriptId} · page {page.canvasLabel} · {page.pageSide}</span>
            <span>{page.dimensions[0]} × {page.dimensions[1]} pixels</span>
          </div>
        </div>
        <div className={step === "result" ? "main-visual result-view" : "main-visual"}>
          <DemoVisual step={step} page={page} experiment={selectedExperiment} />
        </div>
        <div className="stage-controls">
          <button type="button" className="secondary-action" onClick={() => changeStep(steps[Math.max(0, activeStepIndex - 1)].id)} disabled={activeStepIndex === 0}>
            <ChevronLeft aria-hidden="true" /> Previous
          </button>
          <span className="step-progress" aria-label={`Step ${activeStepIndex + 1} of ${steps.length}`}>
            {steps.map((item) => <i key={item.id} className={item.id === step ? "active" : ""} />)}
          </span>
          <button type="button" className="primary-action" onClick={() => changeStep(steps[Math.min(steps.length - 1, activeStepIndex + 1)].id)} disabled={activeStepIndex === steps.length - 1}>
            Next <ChevronRight aria-hidden="true" />
          </button>
        </div>
      </section>

      <DamageClassification experiment={selectedExperiment} />

      <DamageTaxonomy taxonomy={evidence.damageTaxonomy} onChoose={chooseDamageType} />

      <section className="damage-chooser" aria-labelledby="damage-heading">
        <div className="section-heading">
          <h2 id="damage-heading">Review all damage types</h2>
          <p>Select any type to show its generated example in the main viewer.</p>
        </div>
        <div className="damage-review-list">
          {evidence.damageTaxonomy.items.map((item) => {
            const experiment = page.experiments.find(
              (candidate) => candidate.damageId === item.damageId && candidate.severity === "S3",
            ) ?? page.experiments.find((candidate) => candidate.damageId === item.damageId);
            if (!experiment) return null;
            const selected = experiment.taskId === selectedExperiment.taskId;
            return (
              <button
                type="button"
                key={item.damageId}
                className={selected ? "damage-review-item selected" : "damage-review-item"}
                onClick={() => chooseExperiment(experiment)}
                aria-pressed={selected}
              >
                <span className="damage-review-thumb">
                  <Image unoptimized src={experiment.fragmentPath} alt="" width={160} height={198} loading="lazy" />
                </span>
                <span className="damage-review-copy">
                  <strong>{item.damageId} · {item.name}</strong>
                  <small>{experiment.reviewPrototype ? "S3 synthetic review prototype" : "S3 calibrated material loss"}</small>
                  <i>{percentage(experiment.statistics.measuredEffectCoverage, 1)} of selected region affected</i>
                </span>
                {selected && <Check aria-hidden="true" />}
              </button>
            );
          })}
        </div>
      </section>

      <MetadataTable pages={evidence.corpus.pages} selectedPageId={page.pageId} onSelect={(item) => selectPage(item, true)} />

      <details className="optional-panel">
        <summary><span>Exact provenance and identifiers</span><small>Optional</small></summary>
        <div className="technical-grid">
          <section>
            <h3>Source</h3>
            <p>{page.repository}, {page.manuscriptId}, page {page.canvasLabel}</p>
            <dl>
              <div><dt>Canvas</dt><dd>{page.dbCanvasId.slice(0, 8)}…</dd></div>
              <div><dt>Image asset</dt><dd>{page.dbImageAssetId.slice(0, 8)}…</dd></div>
            </dl>
          </section>
          <section>
            <h3>Layout analysis</h3>
            <p>Mergen/eManuSkript model detections, not human transcription.</p>
            <dl>
              <div><dt>Model</dt><dd>{page.modelId}</dd></div>
              <div><dt>Selected confidence</dt><dd>{percentage(page.selectedRegionConfidence, 1)}</dd></div>
            </dl>
          </section>
          <section>
            <h3>Stored evidence</h3>
            <p><Database aria-hidden="true" /> {database.loading ? "Checking local database…" : database.live ? "Connected to live local records" : "Showing the validated saved record"}</p>
            <dl>
              <div><dt>Segmentation run</dt><dd>{page.dbSegmentationRunId.slice(0, 8)}…</dd></div>
              <div><dt>Layout rows</dt><dd>{database.live ? database.regionCount : page.regionCount}</dd></div>
            </dl>
          </section>
        </div>
        <p className="evidence-note">Observed pixels, model detections, and synthetic damage remain separate. No missing manuscript content is reconstructed.</p>
      </details>

      <footer className="demo-footer">
        <span>{evidence.corpus.processedPageCount} processed pages · {evidence.corpus.layoutRegionCount} stored layout regions · {evidence.damageTaxonomy.displayedTypeCount} damage types per page</span>
        <span>No generated replacement content</span>
      </footer>
    </main>
  );
}
