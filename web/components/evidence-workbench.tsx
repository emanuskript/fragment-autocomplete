"use client";

import Image from "next/image";
import { Check, ChevronLeft, ChevronRight, Database, Layers3 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { EvidencePayload, Experiment } from "../lib/types";

type DemoStep = "source" | "layout" | "area" | "damage" | "result" | "compare";

const steps: Array<{ id: DemoStep; label: string; title: string }> = [
  { id: "source", label: "Original page", title: "Start with the complete page" },
  { id: "layout", label: "Find regions", title: "Find the page’s visual regions" },
  { id: "area", label: "Select an area", title: "Choose one area to test" },
  { id: "damage", label: "Apply damage", title: "Apply a controlled damage shape" },
  { id: "result", label: "See the result", title: "Create the test fragment" },
  { id: "compare", label: "Compare", title: "Compare before and after" },
];

const severityLabels: Record<string, string> = {
  S2: "Light",
  S3: "Medium",
  S4: "Heavy",
};

const familyLabels: Record<string, string> = {
  internal_hole: "Interior hole",
  edge_loss: "Straight edge loss",
  edge_tear: "Irregular edge loss",
};

const percentage = (value: number, digits = 0) => `${(value * 100).toFixed(digits)}%`;

function stepDescription(step: DemoStep, experiment: Experiment): string {
  const loss = percentage(experiment.statistics.measuredTargetLoss);
  const family = familyLabels[experiment.family] ?? experiment.matrix.damageType;

  const descriptions: Record<DemoStep, string> = {
    source: "This complete digital photograph is the unchanged reference for the experiment.",
    layout: "A layout model marks visual regions such as writing and page numbers. It detects shapes; it does not read or reconstruct the text.",
    area: "One detected block of writing is chosen as the measurement area. Selecting one area lets us measure damage consistently.",
    damage: `A ${family.toLowerCase()} mask removes ${loss} of the selected writing area. The shape and amount are controlled so the test can be repeated.`,
    result: "The selected pixels are removed to create a synthetic fragment. The pale gaps are transparent: the system has not painted or guessed any replacement text.",
    compare: "The original page and the generated fragment are shown side by side. This makes the exact effect of the selected damage easy to inspect.",
  };
  return descriptions[step];
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

function DemoVisual({ step, evidence, experiment }: { step: DemoStep; evidence: EvidencePayload; experiment: Experiment }) {
  const page = evidence.corpus.pages.find((item) => item.pageId === evidence.focus.pageId) ?? evidence.corpus.pages[0];

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
        <ManuscriptImage src={evidence.focus.contentMaskPath} alt="Selected writing area" className="area-overlay" />
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
        <ManuscriptImage src={experiment.fragmentPath} alt="Full generated test fragment with transparent missing areas" />
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
          <ManuscriptImage src={experiment.fragmentPath} alt="Generated test fragment" />
        </div>
        <figcaption>Test fragment</figcaption>
      </figure>
    </div>
  );
}

export function EvidenceWorkbench({ evidence }: { evidence: EvidencePayload }) {
  const initialExperiment = evidence.experiments.find(
    (item) => item.damageId === "D2-01" && item.severity === "S3",
  ) ?? evidence.experiments[0];
  const [step, setStep] = useState<DemoStep>("source");
  const [selectedTaskId, setSelectedTaskId] = useState(initialExperiment.taskId);
  const [database, setDatabase] = useState<{ loading: boolean; live: boolean; regionCount?: number }>({
    loading: true,
    live: false,
  });
  const demoRef = useRef<HTMLElement>(null);
  const selectedExperiment = evidence.experiments.find((item) => item.taskId === selectedTaskId) ?? initialExperiment;
  const activeStepIndex = steps.findIndex((item) => item.id === step);
  const page = evidence.corpus.pages.find((item) => item.pageId === evidence.focus.pageId) ?? evidence.corpus.pages[0];

  useEffect(() => {
    const controller = new AbortController();
    const loadDatabaseState = async () => {
      try {
        const response = await fetch(`/api/database/${evidence.focus.dbSegmentationRunId}`, {
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
  }, [evidence.focus.dbSegmentationRunId]);

  const changeStep = (nextStep: DemoStep) => {
    setStep(nextStep);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    demoRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  };

  const chooseExperiment = (experiment: Experiment) => {
    setSelectedTaskId(experiment.taskId);
    setStep("result");
    requestAnimationFrame(() => {
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      demoRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    });
  };

  const previousStep = () => changeStep(steps[Math.max(0, activeStepIndex - 1)].id);
  const nextStep = () => changeStep(steps[Math.min(steps.length - 1, activeStepIndex + 1)].id);

  return (
    <main className="public-demo">
      <header className="demo-intro">
        <div className="demo-mark" aria-hidden="true"><Layers3 /></div>
        <div>
          <h1>From complete page to test fragment</h1>
          <p>Follow one real page through six simple, repeatable steps.</p>
        </div>
      </header>

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
            <span>Page {page.canvasLabel}</span>
            <span>{page.dimensions[0]} × {page.dimensions[1]} pixels</span>
          </div>
        </div>

        <div className={step === "result" ? "main-visual result-view" : "main-visual"}>
          <DemoVisual step={step} evidence={evidence} experiment={selectedExperiment} />
        </div>

        <div className="stage-controls">
          <button type="button" className="secondary-action" onClick={previousStep} disabled={activeStepIndex === 0}>
            <ChevronLeft aria-hidden="true" /> Previous
          </button>
          <span className="step-progress" aria-label={`Step ${activeStepIndex + 1} of ${steps.length}`}>
            {steps.map((item) => <i key={item.id} className={item.id === step ? "active" : ""} />)}
          </span>
          <button type="button" className="primary-action" onClick={nextStep} disabled={activeStepIndex === steps.length - 1}>
            Next <ChevronRight aria-hidden="true" />
          </button>
        </div>
      </section>

      <section className="damage-chooser" aria-labelledby="damage-heading">
        <div className="section-heading">
          <h2 id="damage-heading">Choose a damage pattern</h2>
          <p>Selecting a thumbnail opens the complete result in the main viewer above.</p>
        </div>
        <div className="damage-groups">
          {["D2-01", "D2-02", "D2-03"].map((damageId) => {
            const experiments = evidence.experiments.filter((item) => item.damageId === damageId);
            const family = experiments[0]?.family;
            return (
              <article className="damage-group" key={damageId}>
                <h3>{familyLabels[family] ?? experiments[0]?.matrix.damageType}</h3>
                <div className="variant-row">
                  {experiments.map((experiment) => {
                    const selected = experiment.taskId === selectedExperiment.taskId;
                    return (
                      <button
                        type="button"
                        key={experiment.taskId}
                        className={selected ? "variant selected" : "variant"}
                        onClick={() => chooseExperiment(experiment)}
                        aria-pressed={selected}
                        aria-label={`${severityLabels[experiment.severity]} ${familyLabels[experiment.family]}; ${percentage(experiment.statistics.measuredTargetLoss)} of selected area removed`}
                      >
                        <span className="variant-image">
                          <Image
                            unoptimized
                            src={experiment.fragmentPath}
                            alt=""
                            width={240}
                            height={297}
                            loading="lazy"
                          />
                        </span>
                        <strong>{severityLabels[experiment.severity]}</strong>
                        <small>{percentage(experiment.statistics.measuredTargetLoss)} removed</small>
                        {selected && <Check aria-hidden="true" />}
                      </button>
                    );
                  })}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <details className="optional-panel">
        <summary>
          <span>Technical details</span>
          <small>Optional</small>
        </summary>
        <div className="technical-grid">
          <section>
            <h3>Source</h3>
            <p>{evidence.focus.repository}, page {page.canvasLabel}</p>
            <dl>
              <div><dt>Local pages</dt><dd>{evidence.corpus.localPageCount} of {evidence.corpus.pageCount}</dd></div>
              <div><dt>Manuscripts</dt><dd>{evidence.corpus.manuscriptCount}</dd></div>
            </dl>
          </section>
          <section>
            <h3>Layout analysis</h3>
            <p>The regions are model detections, not human transcription.</p>
            <dl>
              <div><dt>Regions on this page</dt><dd>{evidence.focus.detections.length}</dd></div>
              <div><dt>Selected region confidence</dt><dd>{percentage(evidence.focus.selectedRegionConfidence, 1)}</dd></div>
            </dl>
          </section>
          <section>
            <h3>Stored evidence</h3>
            <p><Database aria-hidden="true" /> {database.loading ? "Checking local storage…" : database.live ? "Connected to live local records" : "Showing the validated saved record"}</p>
            <dl>
              <div><dt>Stored layout rows</dt><dd>{database.live ? database.regionCount : evidence.focus.detections.length}</dd></div>
              <div><dt>Damage result</dt><dd>{percentage(selectedExperiment.statistics.measuredTargetLoss, 1)} removed</dd></div>
            </dl>
          </section>
        </div>
        <p className="evidence-note">Observed pixels, model detections, and synthetic damage are kept separate. No missing manuscript text is reconstructed.</p>
      </details>

      <details className="optional-panel collection-panel">
        <summary>
          <span>Browse the source-page collection</span>
          <small>{evidence.corpus.localPageCount} local images</small>
        </summary>
        <p className="collection-intro">These are the complete page images available in this local demonstration.</p>
        <div className="collection-grid">
          {evidence.corpus.pages.map((item) => (
            <figure key={item.pageId}>
              <Image
                unoptimized
                src={item.sourceUrl}
                alt={`Manuscript ${item.manuscriptId}, page ${item.canvasLabel}`}
                width={160}
                height={198}
                loading="lazy"
              />
              <figcaption>{item.manuscriptId}<span>page {item.canvasLabel}</span></figcaption>
            </figure>
          ))}
        </div>
      </details>

      <footer className="demo-footer">
        <span>Synthetic test data for visual comparison</span>
        <span>No generated replacement content</span>
      </footer>
    </main>
  );
}
