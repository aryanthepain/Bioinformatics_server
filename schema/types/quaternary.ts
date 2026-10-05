/**
 * TypeScript Type Definitions for Quaternary Structure Analysis.
 *
 * Generated from Pydantic v2 domain schemas (QuaternaryStructureOutput)
 * and UI backend LevelResult contract.
 *
 * Conforms to JSON Schema Draft 2020-12 in schema/quaternary_structure_output.schema.json.
 */

// ============================================================================
// Core Vocabulary & Enums
// ============================================================================

export type AssemblyType =
  | "MONOMER"
  | "HOMOMER"
  | "HETEROMER"
  | "DYNAMIC_COMPLEX"
  | "UNCHARACTERIZED";

export type EvidenceStatus =
  | "CONFIRMED"
  | "SUPPORTED"
  | "CONFLICTING"
  | "INSUFFICIENT EVIDENCE"
  | "UNAVAILABLE"
  | "PREDICTED"
  | "UNCHARACTERIZED";

export type QueryState =
  | "QUERY_SUCCESS_WITH_HIT"
  | "QUERY_SUCCESS_NO_HIT"
  | "QUERY_FAILED"
  | "SKIPPED"
  | "UNAVAILABLE"
  | "PREDICTION_NOT_EXECUTED";

export type ProvenanceSource =
  | "EXPERIMENTAL"
  | "HOMOLOGY"
  | "PREDICTIVE"
  | "DATABASE"
  | "CONSENSUS";

export type StageStatus =
  | "not_started"
  | "running"
  | "success"
  | "failed"
  | "unavailable"
  | "skipped";

// ============================================================================
// Domain Sub-Models
// ============================================================================

export interface Stoichiometry {
  formula?: string | null;
  chains: Record<string, number>;
  total_subunits: number;
  assembly_type: AssemblyType;
  symmetry?: string | null;
  confidence_status?: EvidenceStatus;
}

export interface TargetSelfAssembly {
  formula: string;
  assembly_type: AssemblyType;
  subunit_count: number;
  symmetry?: string | null;
  confidence_status: EvidenceStatus;
}

export interface FunctionalComplex {
  name: string;
  stoichiometry: string;
  partner_uniprot_accessions: string[];
  partner_names: string[];
  complex_portal_id?: string | null;
  evidence?: string | null;
}

export interface ObservedAssembly {
  pdb_id: string;
  assembly_id: string;
  stoichiometry: string;
  biological_assembly_type: string;
  conditions?: string | null;
  delta_g_dissociation?: number | null;
  resolution?: number | null;
  source?: string | null;
}

export interface InterfaceContact {
  chain_1: string;
  chain_2: string;
  buried_surface_area_angstrom2?: number | null;
  solvation_free_energy_kcal_mol?: number | null;
  hydrogen_bonds_count?: number;
  salt_bridges_count?: number;
  interface_residues_chain_1?: number[];
  interface_residues_chain_2?: number[];
}

export interface ConflictRecord {
  source_a: string;
  source_b: string;
  assertion_a: string;
  assertion_b: string;
  rationale: string;
}

export interface ExperimentalConflict {
  has_conflict: boolean;
  author_assembly?: string | null;
  software_assembly?: string | null;
  pisa_assembly?: string | null;
  rationale?: string | null;
}

export interface PisaConfidence {
  delta_g_dissociation?: number | null;
  buried_surface_area?: number | null;
  status: string;
}

export interface SwissModelConfidence {
  qmqe?: number | null;
  gmqe?: number | null;
  template_id?: string | null;
}

export interface AlphaFoldConfidence {
  global_plddt?: number | null;
  ptm?: number | null;
  iptm?: number | null;
  status: string;
}

export interface MultimerConfidence {
  iptm?: number | null;
  ptm?: number | null;
  model_confidence?: number | null;
  status: string;
}

export interface ConfidenceProvenance {
  pdbe_pisa: PisaConfidence;
  swissmodel: SwissModelConfidence;
  alphafold_db: AlphaFoldConfidence;
  alphafold_multimer: MultimerConfidence;
}

export interface InferredFunction {
  molecular_function: string;
  biological_process?: string | null;
  quaternary_mechanism_hypothesis: string;
  status: EvidenceStatus;
  confidence_score: number;
}

export interface DatabaseAuditRecord {
  database_name: string;
  query_state: QueryState;
  details?: string | null;
}

export interface EvidenceCoverage {
  databases_queried: DatabaseAuditRecord[];
  residual_gaps: string[];
}

// ============================================================================
// Root Quaternary Output Contract
// ============================================================================

export interface QuaternaryStructureOutput {
  analysis_id: string;
  target_accession_or_sequence: string;
  quaternary_status: string;
  stoichiometry: Stoichiometry;
  target_self_assembly?: TargetSelfAssembly | null;
  functional_complexes: FunctionalComplex[];
  observed_assemblies: ObservedAssembly[];
  interfaces: InterfaceContact[];
  conflicts: ConflictRecord[];
  experimental_conflict?: ExperimentalConflict | null;
  confidence_provenance: ConfidenceProvenance;
  inferred_function?: InferredFunction | null;
  evidence_coverage?: EvidenceCoverage | null;
  status: EvidenceStatus;
  experimental_oligomeric_state?: string | null;
  predicted_oligomeric_state?: string | null;
  fallback_representation?: string | null;
  stages_completed: number[];
  metadata: Record<string, unknown>;
}

// ============================================================================
// UI Backend LevelResult Presentation Contract
// ============================================================================

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
export type NoteKind = "recommendation" | "observation" | "caution";
export type ColumnAlign = "left" | "right";

export interface Headline {
  value: string;
  label: string;
}

export interface Metric {
  label: string;
  value: string;
  hint?: string | null;
  group?: string | null;
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
  label?: string | null;
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
  overview?: boolean;
}

export interface TableColumn {
  key: string;
  label: string;
  align?: ColumnAlign;
  mono?: boolean;
}

export interface Table {
  key: string;
  title: string;
  caption?: string | null;
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
  raw?: QuaternaryStructureOutput | null;
}
