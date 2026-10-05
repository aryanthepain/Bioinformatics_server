/*
 * The detailed analysis of one structural level.
 *
 * Every level uses this same template, filled from its LevelResult:
 *   key figures · residue tracks (+ sequence view) · tables
 *   recommendations / observations · evidence · grouped properties · links
 * Sections that have no data are simply left out.
 */
import { useState } from "react";
import type {
  EvidenceItem,
  LevelReport,
  LevelResult,
  Link,
  Metric,
  Note,
  NoteKind,
  Polarity,
  Table,
} from "../api/types";
import { analysisId } from "../lib/anchors";
import { formatDuration, parseTimestamp } from "../lib/format";
import LevelStatusTag from "./LevelStatusTag";
import ResidueMap from "./ResidueMap";
import type { MapRow } from "./ResidueMap";
import SequenceView from "./SequenceView";
import "./LevelAnalysis.css";

interface LevelAnalysisProps {
  level: LevelReport;
  index: number;
  sequence: string;
}

const NOTE_ORDER: NoteKind[] = ["recommendation", "observation", "caution"];

const NOTE_HEADING: Record<NoteKind, string> = {
  recommendation: "Recommendations",
  observation: "Observations",
  caution: "Cautions",
};

const POLARITY_LABEL: Record<Polarity, string> = {
  positive: "Supporting evidence",
  negative: "Evidence against",
  neutral: "Note",
};

interface MetricGroup {
  title: string;
  metrics: Metric[];
}

function groupMetrics(metrics: Metric[]): MetricGroup[] {
  const groups: MetricGroup[] = [];
  for (const metric of metrics) {
    const title = metric.group;
    if (title === null) {
      continue;
    }
    let group = groups.find((candidate) => candidate.title === title);
    if (!group) {
      group = { title, metrics: [] };
      groups.push(group);
    }
    group.metrics.push(metric);
  }
  return groups;
}

function EvidenceIcon({ polarity }: { polarity: Polarity }) {
  if (polarity === "positive") {
    return (
      <svg className="evidence__icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="9" cy="9" r="8" className="evidence__icon-fill" />
        <path d="M5.6 9.2l2.2 2.2 4.4-4.8" stroke="#ffffff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (polarity === "negative") {
    return (
      <svg className="evidence__icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="9" cy="9" r="8" className="evidence__icon-fill" />
        <path d="M5.5 9h7" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className="evidence__icon" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="3.2" className="evidence__icon-fill" />
    </svg>
  );
}

function NoteIcon({ kind }: { kind: NoteKind }) {
  if (kind === "recommendation") {
    // laboratory flask
    return (
      <svg className="note__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M7.5 2.5h5M8.5 2.5v5L3.8 15.2A1.5 1.5 0 0 0 5.1 17.5h9.8a1.5 1.5 0 0 0 1.3-2.3L11.5 7.5v-5" />
        <path d="M6.2 12.5h7.6" />
      </svg>
    );
  }
  if (kind === "caution") {
    return (
      <svg className="note__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M10 3l7.5 13.5h-15L10 3z" />
        <path d="M10 8.5v3.5M10 14.4v.1" />
      </svg>
    );
  }
  // observation: magnifying glass
  return (
    <svg className="note__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5" />
      <path d="M12.3 12.3L17 17" />
    </svg>
  );
}

function DataTable({ table }: { table: Table }) {
  return (
    <div className="analysis__block">
      <div className="analysis__block-head">
        <h4 className="analysis__block-title">{table.title}</h4>
        {table.caption && <p className="analysis__block-caption">{table.caption}</p>}
      </div>
      {table.rows.length === 0 ? (
        <p className="analysis__empty">No entries.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={column.align === "right" ? "data-table__cell--right" : undefined}
                  >
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {table.columns.map((column) => (
                    <td
                      key={column.key}
                      className={[
                        column.align === "right" ? "data-table__cell--right" : "",
                        column.mono ? "data-table__cell--mono" : "",
                      ]
                        .filter((name) => name !== "")
                        .join(" ") || undefined}
                    >
                      {row[column.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function NotesBlock({ kind, notes }: { kind: NoteKind; notes: Note[] }) {
  return (
    <div className="analysis__block">
      <h4 className="analysis__block-title">{NOTE_HEADING[kind]}</h4>
      <ul className="notes">
        {notes.map((note, index) => (
          <li key={index} className={`note note--${note.kind}`}>
            <NoteIcon kind={note.kind} />
            <div className="note__body">
              <p className="note__title">{note.title}</p>
              <p className="note__text">{note.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceBlock({ items }: { items: EvidenceItem[] }) {
  return (
    <div className="analysis__block">
      <h4 className="analysis__block-title">Evidence</h4>
      <ul className="evidence">
        {items.map((item, index) => (
          <li key={index} className={`evidence__item evidence__item--${item.polarity}`}>
            <EvidenceIcon polarity={item.polarity} />
            <span>
              <span className="visually-hidden">{POLARITY_LABEL[item.polarity]}: </span>
              {item.text}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PropertiesBlock({ group }: { group: MetricGroup }) {
  return (
    <div className="analysis__block">
      <h4 className="analysis__block-title">{group.title}</h4>
      <dl className="props">
        {group.metrics.map((metric, index) => (
          <div key={index} className="props__row">
            <dt className={metric.hint ? "props__term props__term--hint" : "props__term"} title={metric.hint ?? undefined}>
              {metric.label}
            </dt>
            <dd className="props__value">{metric.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function LinksBlock({ links }: { links: Link[] }) {
  return (
    <div className="analysis__block">
      <h4 className="analysis__block-title">References</h4>
      <ul className="links">
        {links.map((link) => (
          <li key={link.url}>
            <a href={link.url} target="_blank" rel="noreferrer" className="links__item">
              {link.label}
              <svg viewBox="0 0 12 12" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" aria-hidden="true">
                <path d="M4.5 2.5h5v5M9.5 2.5L3 9" />
              </svg>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalysisBody({ result, sequence, title }: { result: LevelResult; sequence: string; title: string }) {
  const [showSequence, setShowSequence] = useState(false);
  const figures = result.metrics.filter((metric) => metric.group === null);
  const groups = groupMetrics(result.metrics);
  const noteGroups = NOTE_ORDER.map((kind) => ({
    kind,
    notes: result.notes.filter((note) => note.kind === kind),
  })).filter((group) => group.notes.length > 0);
  const mapRows: MapRow[] = result.tracks.map((track) => ({
    key: track.key,
    label: track.label,
    caption: track.caption,
    track,
  }));
  const hasSide =
    noteGroups.length > 0 || result.evidence.length > 0 || groups.length > 0 || result.links.length > 0;
  const hasMain = mapRows.length > 0 || result.tables.length > 0;

  return (
    <>
      <p className="analysis__summary">{result.summary}</p>

      <div className="figures">
        <div className="figure figure--headline">
          <span className="figure__value">{result.headline.value}</span>
          <span className="figure__label">{result.headline.label}</span>
        </div>
        {figures.map((metric, index) => (
          <div key={index} className="figure" title={metric.hint ?? undefined}>
            <span className="figure__value">{metric.value}</span>
            <span className="figure__label">{metric.label}</span>
          </div>
        ))}
      </div>

      {(hasMain || hasSide) && (
        <div className={`analysis__body${hasMain && hasSide ? "" : " analysis__body--single"}`}>
          {hasMain && (
            <div className="analysis__main">
              {mapRows.length > 0 && (
                <div className="analysis__block">
                  <div className="analysis__block-head analysis__block-head--row">
                    <h4 className="analysis__block-title">Along the sequence</h4>
                    <button
                      type="button"
                      className="btn btn--secondary btn--small analysis__toggle"
                      aria-expanded={showSequence}
                      onClick={() => setShowSequence((current) => !current)}
                    >
                      {showSequence ? "Hide residues" : "Show residues"}
                    </button>
                  </div>
                  <ResidueMap rows={mapRows} sequence={sequence} label={`${title}: residue map`} />
                  {showSequence && <SequenceView sequence={sequence} tracks={result.tracks} />}
                </div>
              )}
              {result.tables.map((table) => (
                <DataTable key={table.key} table={table} />
              ))}
            </div>
          )}

          {hasSide && (
            <div className="analysis__side">
              {noteGroups.map((group) => (
                <NotesBlock key={group.kind} kind={group.kind} notes={group.notes} />
              ))}
              {result.evidence.length > 0 && <EvidenceBlock items={result.evidence} />}
              {groups.map((group) => (
                <PropertiesBlock key={group.title} group={group} />
              ))}
              {result.links.length > 0 && <LinksBlock links={result.links} />}
            </div>
          )}
        </div>
      )}

      {result.raw && (
        <details className="raw-output">
          <summary>Raw module output</summary>
          <pre>{JSON.stringify(result.raw, null, 2)}</pre>
        </details>
      )}
    </>
  );
}

export default function LevelAnalysis({ level, index, sequence }: LevelAnalysisProps) {
  const startedAt = parseTimestamp(level.started_at);
  const finishedAt = parseTimestamp(level.finished_at);
  const duration = startedAt !== null && finishedAt !== null ? formatDuration(finishedAt - startedAt) : null;
  const tools = level.tools.length > 0 ? level.tools.join(" · ") : "Module in progress";
  const sectionId = analysisId(level.key);

  return (
    <section id={sectionId} className="analysis" aria-labelledby={`${sectionId}-title`}>
      <header className="analysis__head">
        <span className="analysis__number" aria-hidden="true">
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="analysis__titles">
          <h3 id={`${sectionId}-title`} className="analysis__title" tabIndex={-1}>
            {level.title}
          </h3>
          <p className="analysis__tools">{tools}</p>
        </div>
        <div className="analysis__meta">
          <LevelStatusTag level={level} />
          {duration && <span className="analysis__duration">{duration}</span>}
        </div>
      </header>

      {level.result ? (
        <AnalysisBody result={level.result} sequence={sequence} title={level.title} />
      ) : level.status === "failed" ? (
        <div className="alert alert--error">
          <div className="alert__body">
            <span className="alert__title">This level failed.</span>
            <span>{level.message ?? "No details were provided."}</span>
          </div>
        </div>
      ) : (
        <div className="alert alert--info">
          <div className="alert__body">
            {level.status === "skipped" ? `Skipped: ${level.message ?? "no reason given."}` : "No result."}
          </div>
        </div>
      )}
    </section>
  );
}
