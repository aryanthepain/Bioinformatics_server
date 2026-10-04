/*
 * TypeScript mirror of backend/app/schemas.py.
 * If a field changes there, change it here too — the compiler then points
 * at every part of the interface that needs updating.
 */

export type LevelKey = "primary" | "secondary" | "tertiary" | "quaternary";
export type StepStatus = "pending" | "running" | "completed" | "failed" | "skipped" | "cancelled";
export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type DataSource = "live" | "placeholder";
export type TrackStyle = "blocks" | "states" | "marks";
export type Tone =
  | "accent"
  | "ink"
  | "neutral"
  | "helix"
  | "strand"
  | "coil"
  | "uncertain"
  | "confidence-very-high"
  | "confidence-high"
  | "confidence-low"
  | "confidence-very-low";
export type Polarity = "positive" | "negative" | "neutral";
export type SupportState = "supports" | "neutral" | "contradicts" | "placeholder" | "unavailable";
export type ConfidenceTier = "high" | "moderate" | "low" | "undetermined";
export type GoAspect = "molecular_function" | "biological_process" | "cellular_component";
export type NoteKind = "recommendation" | "observation" | "caution";
export type ColumnAlign = "left" | "right";

export interface Headline {
  value: string;
  label: string;
}

export interface Metric {
  label: string;
  value: string;
  hint: string | null;
  /** null = shown as a key-figure tile; otherwise listed under this heading. */
  group: string | null;
}

export interface EvidenceItem {
  polarity: Polarity;
  text: string;
}

export interface Link {
  label: string;
  url: string;
}

export interface Segment {
  start: number;
  end: number;
  tone: Tone;
  label: string | null;
}

export interface LegendItem {
  label: string;
  tone: Tone;
}

export interface Track {
  key: string;
  label: string;
  caption: string;
  style: TrackStyle;
  segments: Segment[];
  legend: LegendItem[];
  /** false = only shown in the level's own section, not on the combined map. */
  overview: boolean;
}

export interface TableColumn {
  key: string;
  label: string;
  align: ColumnAlign;
  mono: boolean;
}

export interface Table {
  key: string;
  title: string;
  caption: string | null;
  columns: TableColumn[];
  rows: Record<string, string>[];
}

export interface Note {
  kind: NoteKind;
  title: string;
  text: string;
}

export interface LevelResult {
  source: DataSource;
  headline: Headline;
  summary: string;
  metrics: Metric[];
  evidence: EvidenceItem[];
  tracks: Track[];
  tables: Table[];
  notes: Note[];
  links: Link[];
  raw: Record<string, unknown> | null;
}

export interface LevelReport {
  key: LevelKey;
  title: string;
  tools: string[];
  status: StepStatus;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
  result: LevelResult | null;
}

export interface GoTerm {
  id: string;
  term: string;
  aspect: GoAspect;
}

export interface LevelSupport {
  key: LevelKey;
  state: SupportState;
}

export interface Verdict {
  source: DataSource;
  function: string;
  description: string;
  confidence_tier: ConfidenceTier;
  confidence_score: number | null;
  go_terms: GoTerm[];
  level_support: LevelSupport[];
  rationale: string[];
}

export interface QueryInfo {
  name: string;
  sequence: string;
  length: number;
}

export interface AnalysisJob {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  query: QueryInfo;
  levels: LevelReport[];
  verdict_status: StepStatus;
  verdict: Verdict | null;
  error: string | null;
}

export interface ExampleSequence {
  key: string;
  name: string;
  organism: string;
  reference: string;
  sequence: string;
  length: number;
}

export interface HealthResponse {
  status: string;
  version: string;
}
