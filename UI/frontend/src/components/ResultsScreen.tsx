/*
 * The results page: a bar with the query and actions, then one tab per part.
 *   Summary     predicted function, confidence, key facts, residue map, how it was reached
 *   Primary … Quaternary   the concise analysis of each structural level
 *
 * The page opens as soon as the first level has finished, on that level's tab.
 * Levels that are still running show their progress in their own tab, and the
 * prediction appears on the Summary tab once the primary level is done; it
 * updates as levels finish ("Stop & finish now" finalises it with what is done).
 * A dot marks a tab whose content changed since it was last viewed. The Print
 * menu prints the full report or a single level in a print-friendly layout.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import type {
  AnalysisJob,
  ConfidenceRange,
  ConfidenceTier,
  LevelKey,
  LevelReport,
  SupportState,
  Verdict,
} from "../api/types";
import { isFinished } from "../hooks/useAnalysis";
import { useNow } from "../hooks/useNow";
import { downloadJson } from "../lib/download";
import { formatCount, formatDuration, parseTimestamp } from "../lib/format";
import LevelAnalysis from "./LevelAnalysis";
import LevelStatusTag from "./LevelStatusTag";
import ResidueMap from "./ResidueMap";
import type { MapRow } from "./ResidueMap";
import "./ResultsScreen.css";

interface ResultsScreenProps {
  job: AnalysisJob;
  /** "Stop & finish now" was pressed and the server is finishing. */
  stopping: boolean;
  onStop: () => void;
  onNewAnalysis: () => void;
}

type TabKey = "summary" | LevelKey;
type PrintTarget = "all" | LevelKey;

interface PrintRequest {
  target: PrintTarget;
  /** Makes every request distinct, so printing the same view twice works. */
  id: number;
}

/** A small marker after a tab's name. */
interface TabMark {
  kind: "running" | "failed" | "inactive" | "updated";
  /** Read out by screen readers. */
  label: string;
}

interface TabItem {
  key: TabKey;
  label: string;
  mark: TabMark | null;
}

/** Height of the sticky site header (Header.css). */
const HEADER_HEIGHT = 64;

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
  pending: "still running",
  placeholder: "placeholder",
  unavailable: "no result",
};

const SUPPORT_ORDER: SupportState[] = ["supports", "neutral", "contradicts", "pending", "placeholder", "unavailable"];

const LEVEL_SHORT_NAME: Record<LevelKey, string> = {
  primary: "Primary",
  secondary: "Secondary",
  tertiary: "Tertiary",
  quaternary: "Quaternary",
};

const PRINT_OPTIONS: { target: PrintTarget; label: string; hint: string }[] = [
  { target: "all", label: "Full report", hint: "Summary and all four analyses" },
  { target: "primary", label: "Primary structure", hint: "DIAMOND, Pfam, ESM-2, ProtParam" },
  { target: "secondary", label: "Secondary structure", hint: "JPred, ProtBert, PDB comparison" },
  { target: "tertiary", label: "Tertiary structure", hint: "Swiss-Model, Foldseek" },
  { target: "quaternary", label: "Quaternary structure", hint: "Assembly, complexes, interfaces" },
];

function isRunning(level: LevelReport): boolean {
  return level.status === "running" || level.status === "pending";
}

function hasResult(level: LevelReport): boolean {
  return level.status === "completed" && level.result !== null;
}

function joinNames(names: string[]): string {
  if (names.length <= 1) {
    return names[0] ?? "";
  }
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function levelMessage(level: LevelReport): string {
  switch (level.status) {
    case "running":
      return level.message ?? "Running…";
    case "pending":
      return level.message ?? "Waiting to start…";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
    case "cancelled":
      return "Stopped before it finished";
    default:
      return "No result";
  }
}

/** The tab the page opens on: while the analysis runs, the level that finished first. */
function initialTab(job: AnalysisJob): TabKey {
  if (isFinished(job)) {
    return "summary";
  }
  let first: LevelReport | null = null;
  let firstAt = Number.POSITIVE_INFINITY;
  for (const level of job.levels) {
    if (!hasResult(level)) {
      continue;
    }
    const at = parseTimestamp(level.finished_at) ?? Number.POSITIVE_INFINITY;
    if (first === null || at < firstAt) {
      first = level;
      firstAt = at;
    }
  }
  return first?.key ?? "summary";
}

/** Changes whenever a tab gets something new to show (null: nothing to show yet). */
function tabVersion(job: AnalysisJob, key: TabKey): string | null {
  if (key === "summary") {
    const verdict = job.verdict;
    return verdict ? `${verdict.function}|${verdict.confidence_tier}|${verdict.confidence_score ?? ""}` : null;
  }
  const level = job.levels.find((candidate) => candidate.key === key);
  return level && hasResult(level) ? (level.finished_at ?? "done") : null;
}

/** What each tab showed when the page opened; the prediction counts as unseen unless Summary is open. */
function initialSeen(job: AnalysisJob, opening: TabKey): Partial<Record<TabKey, string | null>> {
  const seen: Partial<Record<TabKey, string | null>> = {};
  for (const key of ["summary", ...job.levels.map((level) => level.key)] as TabKey[]) {
    seen[key] = tabVersion(job, key);
  }
  if (opening !== "summary") {
    seen.summary = null;
  }
  return seen;
}

function levelMark(level: LevelReport): TabMark | null {
  if (isRunning(level)) {
    return { kind: "running", label: "still running" };
  }
  if (level.status === "failed") {
    return { kind: "failed", label: "failed" };
  }
  if (level.status === "skipped" || level.status === "cancelled") {
    return { kind: "inactive", label: level.status === "skipped" ? "skipped" : "stopped" };
  }
  return null;
}

function TabMarkView({ mark }: { mark: TabMark }) {
  return (
    <>
      {mark.kind === "running" ? (
        <span className="spinner results-tab__spinner" aria-hidden="true" />
      ) : (
        <span className={`results-tab__dot results-tab__dot--${mark.kind}`} aria-hidden="true" />
      )}
      <span className="visually-hidden"> ({mark.label})</span>
    </>
  );
}

function ConfidenceRangeNote({ range }: { range: ConfidenceRange }) {
  const names = joinNames(range.levels.map((key) => LEVEL_SHORT_NAME[key]));
  const lead = range.stopped
    ? `Had ${names} finished`
    : `Once ${names} ${range.levels.length > 1 ? "finish" : "finishes"}`;
  const tiers =
    range.low_tier === range.high_tier
      ? `${TIER_LABEL[range.high_tier]} either way`
      : `${TIER_LABEL[range.low_tier]} to ${TIER_LABEL[range.high_tier].toLowerCase()}`;

  return (
    <div className="confidence__range">
      <span className="confidence__range-label">{lead}</span>
      <span className="confidence__range-value">
        <span className="confidence__range-numbers">
          {range.low.toFixed(2)}–{range.high.toFixed(2)}
        </span>
        {` · ${tiers}`}
      </span>
      <span className="confidence__range-note">
        {range.stopped ? "The predicted function would have been the same." : "The predicted function will not change."}
      </span>
    </div>
  );
}

function VerdictPanel({ verdict }: { verdict: Verdict }) {
  const legend = SUPPORT_ORDER.filter((state) => verdict.level_support.some((item) => item.state === state));

  return (
    <section className="verdict" aria-label="Predicted function">
      <div className="verdict__head">
        <div className="verdict__main">
          <p className="eyebrow">Predicted function</p>
          <h1 className="verdict__function">{verdict.function}</h1>
          <p className="verdict__description">{verdict.description}</p>
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
          <ul className="support-legend" aria-hidden="true">
            {legend.map((state) => (
              <li key={state} className="support-legend__item">
                <span className={`support-legend__swatch support__bar--${state}`} />
                {SUPPORT_LABEL[state]}
              </li>
            ))}
          </ul>
          {verdict.confidence_range && <ConfidenceRangeNote range={verdict.confidence_range} />}
        </div>
      </div>

      {verdict.facts.length > 0 && (
        <dl className="verdict-facts" aria-label="Key facts behind the prediction">
          {verdict.facts.map((fact) => (
            <div key={fact.label} className="verdict-facts__item">
              <dt className="verdict-facts__label">{fact.label}</dt>
              <dd className="verdict-facts__value">{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

/** The Summary tab before the primary level has finished: the prediction is on its way. */
function PendingVerdict({ primary }: { primary: LevelReport | undefined }) {
  const status = primary && isRunning(primary) ? levelMessage(primary) : null;
  return (
    <section className="verdict-pending" aria-label="Predicted function">
      <span className="spinner verdict-pending__spinner" aria-hidden="true" />
      <div className="verdict-pending__body">
        <p className="eyebrow">Predicted function</p>
        <p className="verdict-pending__title">Appears when the primary level has finished</p>
        <p className="verdict-pending__text">
          The function is transferred from what the primary level finds (the closest characterised Swiss-Prot
          protein or a Pfam domain); the other levels then adjust its confidence. Finished levels can already be
          opened in their tabs.
        </p>
        {status && <p className="verdict-pending__status">Primary level: {status}</p>}
      </div>
    </section>
  );
}

function LevelCard({ level, onOpen }: { level: LevelReport; onOpen: () => void }) {
  const result = level.result;
  return (
    <button
      type="button"
      className={`level-card${result?.source === "placeholder" ? " level-card--placeholder" : ""}`}
      onClick={onOpen}
    >
      <span className="level-card__head">
        <span className="level-card__title">{LEVEL_SHORT_NAME[level.key]}</span>
        <LevelStatusTag level={level} />
      </span>
      {result ? (
        <>
          <span className="level-card__value">{result.headline.value}</span>
          <span className="level-card__label">{result.headline.label}</span>
        </>
      ) : (
        <span className="level-card__message">
          {isRunning(level) && <span className="spinner level-card__spinner" aria-hidden="true" />}
          {levelMessage(level)}
        </span>
      )}
      <span className="level-card__open">Open analysis →</span>
    </button>
  );
}

function SummaryView({
  job,
  onOpen,
  showCards,
}: {
  job: AnalysisJob;
  onOpen: (key: LevelKey) => void;
  showCards: boolean;
}) {
  const verdict = job.verdict;
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

  return (
    <div className="summary">
      {verdict ? (
        <VerdictPanel verdict={verdict} />
      ) : !isFinished(job) ? (
        <PendingVerdict primary={job.levels.find((level) => level.key === "primary")} />
      ) : (
        <div className="alert alert--info" role="status">
          <div className="alert__body">No prediction was produced for this analysis.</div>
        </div>
      )}

      {showCards && (
        <div className="level-cards">
          {job.levels.map((level) => (
            <LevelCard key={level.key} level={level} onOpen={() => onOpen(level.key)} />
          ))}
        </div>
      )}

      {overviewRows.length > 0 && (
        <section className="results-section" aria-label="Residue map">
          <div className="results-section__head">
            <h2 className="results-section__title">Residue map</h2>
            <p className="results-section__description">
              The structural levels aligned on residues 1–{formatCount(job.query.length)}.
            </p>
          </div>
          <div className="map-card">
            <ResidueMap rows={overviewRows} sequence={job.query.sequence} label="Residue map of all structural levels" />
          </div>
        </section>
      )}

      {verdict && verdict.rationale.length > 0 && (
        <section className="results-section" aria-label="How the prediction was reached">
          <h2 className="results-section__title">How the prediction was reached</h2>
          <ol className="rationale">
            {verdict.rationale.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function PrintMenu({ onPrint }: { onPrint: (target: PrintTarget) => void }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="print-menu" ref={menuRef}>
      <button
        type="button"
        className="btn btn--secondary"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        Print
        <svg viewBox="0 0 12 12" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 4.5L6 7.5l3-3" />
        </svg>
      </button>
      {open && (
        <ul className="print-menu__list" role="menu" aria-label="What to print">
          {PRINT_OPTIONS.map((option) => (
            <li key={option.target} role="none">
              <button
                type="button"
                role="menuitem"
                className="print-menu__item"
                onClick={() => {
                  setOpen(false);
                  onPrint(option.target);
                }}
              >
                <span className="print-menu__label">{option.label}</span>
                <span className="print-menu__hint">{option.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ReportView({ job, target, onBack }: { job: AnalysisJob; target: PrintTarget; onBack: () => void }) {
  const verdict = job.verdict;
  const levels = target === "all" ? job.levels : job.levels.filter((level) => level.key === target);
  const title = target === "all" ? "Full report" : `${LEVEL_SHORT_NAME[target]} structure`;
  const provisional = !isFinished(job);

  return (
    <div className="report">
      <div className="report__toolbar">
        <span>Print view</span>
        <button type="button" className="btn btn--secondary btn--small" onClick={onBack}>
          Back to results
        </button>
      </div>
      <header className="report__head">
        <p className="eyebrow">Protein Function Predictor · {title}</p>
        <h1 className="report__title">{job.query.name}</h1>
        <p className="report__meta">
          {formatCount(job.query.length)} residues · {new Date().toLocaleDateString()}
          {provisional ? " · provisional: some levels were still running" : ""}
        </p>
        {target !== "all" && verdict && (
          <p className="report__verdict">
            Predicted function: <strong>{verdict.function}</strong> · confidence {TIER_LABEL[verdict.confidence_tier]}
            {verdict.confidence_score !== null ? ` ${verdict.confidence_score.toFixed(2)}` : ""}
          </p>
        )}
      </header>
      {target === "all" && <SummaryView job={job} onOpen={() => undefined} showCards={false} />}
      {levels.map((level) => (
        <LevelAnalysis
          key={level.key}
          level={level}
          index={job.levels.findIndex((candidate) => candidate.key === level.key)}
          sequence={job.query.sequence}
          active={false}
          printMode
        />
      ))}
    </div>
  );
}

export default function ResultsScreen({ job, stopping, onStop, onNewAnalysis }: ResultsScreenProps) {
  const [opening] = useState<TabKey>(() => initialTab(job));
  const [tab, setTab] = useState<TabKey>(opening);
  const [seen, setSeen] = useState(() => initialSeen(job, opening));
  const [printRequest, setPrintRequest] = useState<PrintRequest | null>(null);
  const tabsRef = useRef<HTMLElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const active = !isFinished(job);
  const now = useNow(active);

  // The open tab counts as seen, including anything that arrives while it is open.
  const openVersion = tabVersion(job, tab);
  useEffect(() => {
    setSeen((current) => (current[tab] === openVersion ? current : { ...current, [tab]: openVersion }));
  }, [tab, openVersion]);

  // Print once the print view has rendered; return to the tabs afterwards.
  useEffect(() => {
    if (printRequest === null) {
      return;
    }
    const finish = () => setPrintRequest(null);
    window.addEventListener("afterprint", finish);
    const timer = window.setTimeout(() => window.print(), 80);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("afterprint", finish);
    };
  }, [printRequest]);

  const verdict = job.verdict;
  const usesPlaceholders =
    verdict?.source === "placeholder" || job.levels.some((level) => level.result?.source === "placeholder");
  const runningNames = job.levels.filter(isRunning).map((level) => LEVEL_SHORT_NAME[level.key]);
  const createdAt = parseTimestamp(job.created_at);
  const finishedAt = parseTimestamp(job.finished_at);
  const runtime =
    createdAt === null
      ? null
      : active
        ? `running for ${formatDuration(now - createdAt)}`
        : finishedAt !== null
          ? `analysed in ${formatDuration(finishedAt - createdAt)}`
          : null;

  const isUpdated = (key: TabKey): boolean => {
    const version = tabVersion(job, key);
    return key !== tab && version !== null && version !== seen[key];
  };

  const levelTab = (level: LevelReport): TabItem => ({
    key: level.key,
    label: LEVEL_SHORT_NAME[level.key],
    mark: levelMark(level) ?? (isUpdated(level.key) ? { kind: "updated", label: "new result" } : null),
  });
  const tabs: TabItem[] = [
    {
      key: "summary",
      label: "Summary",
      mark:
        active && verdict === null
          ? { kind: "running", label: "prediction not ready yet" }
          : isUpdated("summary")
            ? { kind: "updated", label: "prediction updated" }
            : null,
    },
    ...job.levels.map(levelTab),
  ];
  const currentLevel = tab === "summary" ? null : (job.levels.find((level) => level.key === tab) ?? null);

  const selectTab = (key: TabKey) => {
    // If the page is scrolled past the start of the panel, scroll back so the new
    // tab starts right below the (sticky) tab bar.
    const panel = panelRef.current;
    const bar = tabsRef.current;
    if (panel && bar) {
      const offset = panel.getBoundingClientRect().top - (HEADER_HEIGHT + bar.getBoundingClientRect().height);
      if (offset < 0) {
        window.scrollBy({ top: offset });
      }
    }
    setTab(key);
  };

  const onTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = -1;
    if (event.key === "ArrowRight") {
      next = (index + 1) % tabs.length;
    } else if (event.key === "ArrowLeft") {
      next = (index - 1 + tabs.length) % tabs.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = tabs.length - 1;
    }
    if (next < 0) {
      return;
    }
    event.preventDefault();
    selectTab(tabs[next].key);
    document.getElementById(`results-tab-${tabs[next].key}`)?.focus();
  };

  const download = () => {
    const safeName = job.query.name.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "analysis";
    downloadJson(`${safeName}-${job.id}.json`, job);
  };

  if (printRequest !== null) {
    return (
      <main className="results-screen results-screen--report container">
        <ReportView job={job} target={printRequest.target} onBack={() => setPrintRequest(null)} />
      </main>
    );
  }

  return (
    <main className="results-screen container">
      <div className="results-bar">
        <div className="results-bar__query">
          <span className="results-bar__name">{job.query.name}</span>
          <span className="results-bar__meta">
            {formatCount(job.query.length)} residues{runtime ? ` · ${runtime}` : ""}
          </span>
        </div>
        <div className="results-bar__actions">
          <PrintMenu onPrint={(target) => setPrintRequest({ target, id: Date.now() })} />
          <button type="button" className="btn btn--secondary" onClick={download}>
            Download JSON
          </button>
          <button type="button" className="btn btn--primary" onClick={onNewAnalysis}>
            New analysis
          </button>
        </div>
      </div>

      {active && runningNames.length > 0 && (
        <div className="alert alert--info results-live" role="status">
          <span className="spinner results-live__spinner" aria-hidden="true" />
          <div className="alert__body">
            <span className="alert__title">
              {verdict ? "Provisional prediction" : "First results"}: {joinNames(runningNames)} still running
            </span>
            <span>
              {verdict
                ? "The prediction uses the levels that have finished and updates by itself as the others finish. JPred and Swiss-Model can take 5–20 minutes."
                : "Finished levels can be opened in their tabs now; the prediction appears on the Summary tab once the primary level is done."}
            </span>
          </div>
          <button
            type="button"
            className="btn btn--secondary btn--small"
            onClick={onStop}
            disabled={stopping}
            title="Stop the levels that are still running and finish with the results that are in"
          >
            {stopping ? "Finishing…" : "Stop & finish now"}
          </button>
        </div>
      )}

      {usesPlaceholders && (
        <div className="alert alert--warning" role="note">
          <div className="alert__body">
            <span className="alert__title">Placeholder data</span>
            <span>Some levels show illustrative values instead of real predictions.</span>
          </div>
        </div>
      )}

      <nav ref={tabsRef} className="results-tabs" aria-label="Results sections">
        <div className="results-tabs__list" role="tablist">
          {tabs.map((item, index) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              id={`results-tab-${item.key}`}
              aria-selected={tab === item.key}
              aria-controls="results-panel"
              tabIndex={tab === item.key ? 0 : -1}
              className={`results-tab${tab === item.key ? " results-tab--active" : ""}`}
              onClick={() => selectTab(item.key)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
            >
              {item.label}
              {item.mark && <TabMarkView mark={item.mark} />}
            </button>
          ))}
        </div>
      </nav>

      <div
        ref={panelRef}
        id="results-panel"
        role="tabpanel"
        aria-labelledby={`results-tab-${tab}`}
        className="results-panel"
      >
        {currentLevel ? (
          <LevelAnalysis
            key={currentLevel.key}
            level={currentLevel}
            index={job.levels.findIndex((level) => level.key === currentLevel.key)}
            sequence={job.query.sequence}
            active={active}
          />
        ) : (
          <SummaryView job={job} onOpen={selectTab} showCards />
        )}
      </div>
    </main>
  );
}
