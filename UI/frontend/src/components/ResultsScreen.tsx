/*
 * The results page, top to bottom:
 *   1. verdict      predicted function, GO terms, confidence and per-level support
 *   2. residue map  every level's main track on one residue axis
 *   3. overview     one card per level, linking to its full analysis
 *   4. analyses     the detailed section for each level
 *   5. rationale    how the verdict was reached
 */
import { useMemo } from "react";
import type { AnalysisJob, ConfidenceTier, LevelReport, SupportState } from "../api/types";
import { analysisId } from "../lib/anchors";
import { downloadJson } from "../lib/download";
import { formatCount, formatDuration, parseTimestamp } from "../lib/format";
import LevelAnalysis from "./LevelAnalysis";
import LevelStatusTag from "./LevelStatusTag";
import ResidueMap from "./ResidueMap";
import type { MapRow } from "./ResidueMap";
import "./ResultsScreen.css";

interface ResultsScreenProps {
  job: AnalysisJob;
  onNewAnalysis: () => void;
}

const TIER_LABEL: Record<ConfidenceTier, string> = {
  high: "High",
  moderate: "Moderate",
  low: "Low",
  undetermined: "Not determined",
};

const SUPPORT_LABEL: Record<SupportState, string> = {
  supports: "supports",
  neutral: "neutral",
  contradicts: "contradicts",
  placeholder: "placeholder",
  unavailable: "no result",
};

const LEVEL_SHORT_NAME: Record<LevelReport["key"], string> = {
  primary: "Primary",
  secondary: "Secondary",
  tertiary: "Tertiary",
  quaternary: "Quaternary",
};

function scrollToAnalysis(levelKey: string): void {
  const section = document.getElementById(analysisId(levelKey));
  if (!section) {
    return;
  }
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  section.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  section.querySelector<HTMLElement>("h3")?.focus({ preventScroll: true });
}

function LevelCard({ level }: { level: LevelReport }) {
  const result = level.result;
  const tools = level.tools.length > 0 ? level.tools.join(" · ") : "Module in progress";

  return (
    <article className={`level-card${result?.source === "placeholder" ? " level-card--placeholder" : ""}`}>
      <div className="level-card__head">
        <h3 className="level-card__title">{LEVEL_SHORT_NAME[level.key]}</h3>
        <LevelStatusTag level={level} />
      </div>
      {result ? (
        <>
          <div className="level-card__stat">
            <span className="level-card__value">{result.headline.value}</span>
            <span className="level-card__label">{result.headline.label}</span>
          </div>
          <p className="level-card__summary">{result.summary}</p>
        </>
      ) : (
        <p className="level-card__message">{level.message ?? "No result."}</p>
      )}
      <div className="level-card__foot">
        <p className="level-card__tools">{tools}</p>
        <button type="button" className="level-card__jump" onClick={() => scrollToAnalysis(level.key)}>
          View analysis
          <svg viewBox="0 0 12 12" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 2v8M2.5 6.5L6 10l3.5-3.5" />
          </svg>
        </button>
      </div>
    </article>
  );
}

export default function ResultsScreen({ job, onNewAnalysis }: ResultsScreenProps) {
  const verdict = job.verdict;
  const usesPlaceholders =
    verdict?.source === "placeholder" || job.levels.some((level) => level.result?.source === "placeholder");
  const createdAt = parseTimestamp(job.created_at);
  const finishedAt = parseTimestamp(job.finished_at);
  const runtime = createdAt !== null && finishedAt !== null ? formatDuration(finishedAt - createdAt) : null;

  const overviewRows = useMemo<MapRow[]>(
    () =>
      job.levels.flatMap((level) =>
        (level.result?.tracks ?? [])
          .filter((track) => track.overview)
          .map((track) => ({
            key: `${level.key}-${track.key}`,
            label: track.label,
            caption: track.caption,
            track,
          })),
      ),
    [job],
  );

  const download = () => {
    const safeName = job.query.name.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "analysis";
    downloadJson(`${safeName}-${job.id}.json`, job);
  };

  return (
    <main className="results-screen container">
      <div className="results-bar">
        <div className="results-bar__query">
          <span className="results-bar__name">{job.query.name}</span>
          <span className="results-bar__meta">
            {formatCount(job.query.length)} residues{runtime ? ` · analysed in ${runtime}` : ""}
          </span>
        </div>
        <div className="results-bar__actions">
          <button type="button" className="btn btn--secondary" onClick={() => window.print()}>
            Print report
          </button>
          <button type="button" className="btn btn--secondary" onClick={download}>
            Download JSON
          </button>
          <button type="button" className="btn btn--primary" onClick={onNewAnalysis}>
            New analysis
          </button>
        </div>
      </div>

      {usesPlaceholders && (
        <div className="alert alert--warning" role="note">
          <div className="alert__body">
            <span className="alert__title">Placeholder results</span>
            <span>
              Some analysis modules are not connected yet, so parts of this page show illustrative values
              rather than real predictions.
            </span>
          </div>
        </div>
      )}

      {verdict ? (
        <section className="verdict" aria-label="Predicted function">
          <div className="verdict__main">
            <p className="eyebrow">Predicted function</p>
            <h1 className="verdict__function">{verdict.function}</h1>
            <p className="verdict__description">{verdict.description}</p>
            {verdict.go_terms.length > 0 && (
              <ul className="go-terms" aria-label="Gene Ontology terms">
                {verdict.go_terms.map((term) => (
                  <li key={term.id} className="go-term">
                    <span className="go-term__id">{term.id}</span>
                    {term.term}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="confidence">
            <div className="confidence__row">
              <span className="confidence__label">Confidence</span>
              <span className="confidence__tier">
                {TIER_LABEL[verdict.confidence_tier]}
                {verdict.confidence_score !== null && (
                  <span className="confidence__score">{verdict.confidence_score.toFixed(2)}</span>
                )}
              </span>
            </div>
            <ul className="support" aria-label="Evidence from each structural level">
              {verdict.level_support.map((item) => (
                <li key={item.key} className="support__item">
                  <span className={`support__bar support__bar--${item.state}`} aria-hidden="true" />
                  <span className="support__name">{LEVEL_SHORT_NAME[item.key]}</span>
                  <span className="visually-hidden">: {SUPPORT_LABEL[item.state]}</span>
                </li>
              ))}
            </ul>
            <p className="confidence__note">Solid: supports · striped: placeholder · grey: no result</p>
          </div>
        </section>
      ) : (
        <div className="alert alert--info" role="status">
          <div className="alert__body">No verdict was produced for this analysis.</div>
        </div>
      )}

      {overviewRows.length > 0 && (
        <section className="results-section" aria-labelledby="residue-map-title">
          <div className="results-section__head">
            <h2 id="residue-map-title" className="results-section__title">
              Residue map
            </h2>
            <p className="results-section__description">
              Every structural level aligned on residues 1–{formatCount(job.query.length)}.
            </p>
          </div>
          <div className="map-card">
            <ResidueMap rows={overviewRows} sequence={job.query.sequence} label="Residue map of all structural levels" />
          </div>
        </section>
      )}

      <section className="results-section" aria-labelledby="levels-title">
        <div className="results-section__head">
          <h2 id="levels-title" className="results-section__title">
            Evidence by structural level
          </h2>
        </div>
        <div className="level-cards">
          {job.levels.map((level) => (
            <LevelCard key={level.key} level={level} />
          ))}
        </div>
      </section>

      <section className="results-section" aria-labelledby="analyses-title">
        <div className="results-section__head">
          <h2 id="analyses-title" className="results-section__title">
            Detailed analysis
          </h2>
          <p className="results-section__description">
            Each level in full: key figures, residue-level data, tables, evidence and recommendations.
          </p>
        </div>
        <div className="analyses">
          {job.levels.map((level, index) => (
            <LevelAnalysis key={level.key} level={level} index={index} sequence={job.query.sequence} />
          ))}
        </div>
      </section>

      {verdict && verdict.rationale.length > 0 && (
        <section className="results-section" aria-labelledby="rationale-title">
          <div className="results-section__head">
            <h2 id="rationale-title" className="results-section__title">
              How this verdict was reached
            </h2>
          </div>
          <ul className="rationale">
            {verdict.rationale.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
