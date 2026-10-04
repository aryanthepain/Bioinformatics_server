import type { AnalysisJob, LevelResult, StepStatus } from "../api/types";
import { isFinished } from "../hooks/useAnalysis";
import { useNow } from "../hooks/useNow";
import { formatClock, formatCount, formatDuration, parseTimestamp } from "../lib/format";
import StepIcon from "./StepIcon";
import "./RunScreen.css";

interface RunScreenProps {
  job: AnalysisJob;
  cancelling: boolean;
  connectionError: string | null;
  onCancel: () => void;
  onNewAnalysis: () => void;
  onEditAndRerun: () => void;
}

interface StepView {
  key: string;
  title: string;
  caption: string;
  status: StepStatus;
  message: string | null;
  startedAt: number | null;
  finishedAt: number | null;
  result: LevelResult | null;
}

function toSteps(job: AnalysisJob): StepView[] {
  const levelSteps: StepView[] = job.levels.map((level) => ({
    key: level.key,
    title: level.title,
    caption: level.tools.length > 0 ? level.tools.join(" · ") : "Module in progress",
    status: level.status,
    message: level.message,
    startedAt: parseTimestamp(level.started_at),
    finishedAt: parseTimestamp(level.finished_at),
    result: level.result,
  }));
  return [
    ...levelSteps,
    {
      key: "integration",
      title: "Evidence integration",
      caption: "Combines the levels into one prediction",
      status: job.verdict_status,
      message: null,
      startedAt: null,
      finishedAt: null,
      result: null,
    },
  ];
}

function stepMessage(step: StepView): string {
  switch (step.status) {
    case "pending":
      return "Waiting";
    case "running":
      return step.message ?? "Working…";
    case "completed":
      return step.result ? `${step.result.headline.value} · ${step.result.headline.label}` : "Done";
    case "failed":
      return step.message ?? "Failed";
    case "skipped":
      return step.message ?? "Skipped";
    case "cancelled":
      return "Cancelled";
  }
}

function stepTime(step: StepView, now: number): string {
  if (step.startedAt === null) {
    return "";
  }
  const end = step.finishedAt ?? (step.status === "running" ? now : null);
  return end === null ? "" : formatDuration(end - step.startedAt);
}

const HEADINGS: Record<AnalysisJob["status"], string> = {
  queued: "Queued",
  running: "Analysing",
  completed: "Complete",
  failed: "Analysis failed",
  cancelled: "Cancelled",
};

export default function RunScreen({
  job,
  cancelling,
  connectionError,
  onCancel,
  onNewAnalysis,
  onEditAndRerun,
}: RunScreenProps) {
  const active = !isFinished(job);
  const now = useNow(active);
  const steps = toSteps(job);

  const createdAt = parseTimestamp(job.created_at) ?? now;
  const endedAt = parseTimestamp(job.finished_at);
  const elapsed = (endedAt ?? now) - createdAt;

  const doneCount = steps.filter((step) => step.status !== "pending" && step.status !== "running").length;
  const progress = Math.round((doneCount / steps.length) * 100);
  const runningStep = steps.find((step) => step.status === "running");
  const announcement = runningStep ? `${runningStep.title}: running` : HEADINGS[job.status];
  const sequenceBlocks = job.query.sequence.match(/.{1,10}/g)?.join(" ") ?? job.query.sequence;

  return (
    <main className="run-screen container">
      <div className="run-head">
        <div className="run-head__text">
          <p className={`eyebrow eyebrow--${job.status}`}>{HEADINGS[job.status]}</p>
          <h1 className="run-head__title">{job.query.name}</h1>
          <p className="run-head__meta">
            <span>{formatCount(job.query.length)} residues</span>
            <span>Started {formatClock(createdAt)}</span>
            <span className="run-head__elapsed">
              {active ? "Elapsed" : "Ran for"} {formatDuration(elapsed)}
            </span>
          </p>
        </div>
        <div className="run-head__actions">
          {active ? (
            <button type="button" className="btn btn--secondary" onClick={onCancel} disabled={cancelling}>
              {cancelling ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  Cancelling…
                </>
              ) : (
                "Cancel analysis"
              )}
            </button>
          ) : (
            <>
              <button type="button" className="btn btn--secondary" onClick={onNewAnalysis}>
                New analysis
              </button>
              <button type="button" className="btn btn--primary" onClick={onEditAndRerun}>
                Edit and run again
              </button>
            </>
          )}
        </div>
      </div>

      <div
        className={`run-progress run-progress--${job.status}`}
        role="progressbar"
        aria-label="Analysis progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
      >
        <div className="run-progress__bar" style={{ width: `${progress}%` }} />
      </div>
      <p className="visually-hidden" aria-live="polite">
        {announcement}
      </p>

      <div className="run-layout">
        <div className="run-main">
          {active && connectionError && (
            <div className="alert alert--warning" role="status">
              <div className="alert__body">
                <span className="alert__title">Connection interrupted — retrying…</span>
                <span>{connectionError}</span>
              </div>
            </div>
          )}
          {job.status === "queued" && (
            <div className="alert alert--info" role="status">
              <div className="alert__body">
                Another analysis is running. This one starts automatically when it finishes.
              </div>
            </div>
          )}
          {job.status === "failed" && (
            <div className="alert alert--error" role="alert">
              <div className="alert__body">
                <span className="alert__title">The analysis stopped because of an error.</span>
                <span>{job.error ?? "No details were provided."}</span>
              </div>
            </div>
          )}
          {job.status === "cancelled" && (
            <div className="alert alert--info" role="status">
              <div className="alert__body">
                This analysis was cancelled. Steps that finished before cancelling are listed below.
              </div>
            </div>
          )}

          <ol className="steps">
            {steps.map((step) => (
              <li key={step.key} className={`step step--${step.status}`}>
                <StepIcon status={step.status} />
                <div className="step__body">
                  <div className="step__title-row">
                    <span className="step__title">{step.title}</span>
                    {step.result?.source === "placeholder" && <span className="tag tag--placeholder">placeholder</span>}
                  </div>
                  <span className="step__caption">{step.caption}</span>
                  <span className="step__message">{stepMessage(step)}</span>
                </div>
                <span className="step__time">{stepTime(step, now)}</span>
              </li>
            ))}
          </ol>
        </div>

        <aside className="run-aside">
          <section className="query-card" aria-labelledby="query-card-title">
            <h2 id="query-card-title" className="query-card__title">
              Query
            </h2>
            <pre className="query-card__sequence">{sequenceBlocks}</pre>
            <dl className="facts">
              <dt>Length</dt>
              <dd>{formatCount(job.query.length)} aa</dd>
              <dt>Submitted</dt>
              <dd>{formatClock(createdAt)}</dd>
              <dt>Analysis ID</dt>
              <dd className="mono">{job.id}</dd>
            </dl>
          </section>
          {active && (
            <p className="run-note">
              Some levels use public web servers (Swiss-Model, JPred) and can take 5–15 minutes. You can
              safely refresh this page — the analysis keeps running on the server.
            </p>
          )}
        </aside>
      </div>
    </main>
  );
}
