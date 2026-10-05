# Phase 4: Standardized UI JSON Data Contract & Benchmark Validation - Context

**Gathered:** 2026-10-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 formalizes and exports the standardized UI JSON data contract (`quaternary_structure_output.schema.json` and `quaternary_structure_output.json`) derived directly from the backend Pydantic models. It benchmarks and validates the complete quaternary pipeline on the 5 canonical example proteins established in the `UI` branch (`ubiquitin`, `hemoglobin-alpha`, `bacteriorhodopsin`, `p53`, and `akt1`), authoring a comprehensive benchmark report (`BENCHMARK_REPORT.md`) and deterministic validation tests. It delivers a direct drop-in UI backend adapter (`quaternary/ui_adapter.py`) conforming to `UI/backend/app/schemas.py:LevelResult`, complete TypeScript interface definitions (`schema/types/quaternary.ts`), and an exhaustive UI developer integration guide (`docs/UI_INTEGRATION_GUIDE.md`) to enable seamless frontend ingestion.

Novel/synthetic unannotated sequence validation and edge-case testing are deferred to a dedicated future milestone issue to prioritize happy-path delivery for the UI team.

</domain>

<decisions>
## Implementation Decisions

### 1. JSON Schema Formalization & Contract Verification
- **D-01: Pydantic-Driven JSON Schema Export**: Generate standard JSON Schema (Draft 2020-12) directly from `QuaternaryStructureOutput.model_json_schema()` into `schema/quaternary_structure_output.schema.json`. This guarantees 100% synchronization between the Python backend engine and the published contract without manual schema duplication.
- **D-02: Multi-Archetype Fixture Pack & Generic Target Extensibility**: Deliver sample JSON payloads under `schema/fixtures/` alongside a canonical `quaternary_structure_output.json` at the root. The schema and contract must remain strictly generic and flexible so the UI backend and frontend can process and display arbitrary user-supplied protein sequences and accessions beyond the default presets.
- **D-03: Automated JSON Schema Test Gate**: Implement `tests/test_ui_contract.py` utilizing the `jsonschema` library validator to deterministically verify that all exported fixtures and dynamic session results conform strictly to `quaternary_structure_output.schema.json`.
- **D-04: Dual Export Exposure**: Provide a dedicated CLI script (`scripts/export_ui_contract.py`) for CI/batch artifact generation, and add an interactive export cell in `Quaternary_Structure.ipynb` allowing notebook users to export the contract for any analyzed protein in one click.

### 2. UI Examples Proteome Benchmarking (Amending QUAT-09 Scope)
- **D-05: Strict Alignment with UI Branch Default Examples**: Align benchmark targets directly with the UI branch (`origin/UI:UI/backend/app/examples.py`). Benchmark the 5 canonical UI examples across biological oligomeric spectrum:
  1. `ubiquitin` (PDB: `1UBQ`, Monomer)
  2. `hemoglobin-alpha` (UniProt: `P69905`, Heterotetramer $\alpha_2\beta_2$)
  3. `bacteriorhodopsin` (UniProt: `P02945`, Homotrimer)
  4. `p53` (UniProt: `P04637`, Homotetramer)
  5. `akt1` (UniProt: `P31749`, Monomer)
- **D-06: Replace H. influenzae with UI Examples**: Per explicit user directive, replace *Haemophilus influenzae* UP000000579 entirely with the 5 UI examples across both benchmark execution and sample fixtures, amending the target scope of QUAT-09 to directly serve the active UI application.
- **D-07: Comprehensive Benchmark Deliverables**: Produce `BENCHMARK_REPORT.md` documenting oligomeric state prediction accuracy, stoichiometry, PISA interface contacts, and runtime performance across all 5 UI examples. Save their exported JSON outputs in `schema/fixtures/ui_examples/` and assert determinism via `tests/test_benchmarks.py`.

### 3. Novel Sequence Validation Scope
- **D-08: Defer Novel Sequence Validation to Future Issue**: Fully skip novel/synthetic unannotated sequence validation for Phase 4. Track this work as a future scope GitHub issue to thoroughly test edge cases and boundary conditions later, focusing Phase 4 strictly on the happy-path delivery for the UI team.

### 4. UI Developer Integration Guide & LevelResult Adapter
- **D-09: Direct UI Backend Adapter (`quaternary/ui_adapter.py`)**: Implement a modular adapter function `analyze(sequence: str, ctx: StageContext) -> LevelResult` conforming exactly to `UI/docs/LEVEL_CONTRACT.md` and `UI/backend/app/schemas.py`. This provides an immediate drop-in replacement for the placeholder in `UI/backend/app/levels/placeholders.py:quaternary`. Embed the complete `QuaternaryStructureOutput.model_dump()` in the `raw` dictionary.
- **D-10: Visual Field Mappings in LevelResult**:
  - `headline`: Predicted oligomeric assembly state (e.g. `Homotetramer`, `Heterotetramer (α2β2)`, `Monomer`).
  - `tracks`: A residue-map track with `style="marks"` and `tone="ink"`, marking interface contact positions (1-based, inclusive).
  - `metrics`: Key figures including Subunit Count, Stoichiometry Formula, PISA Interface Area ($\text{Å}^2$), and Evidence Status.
  - `tables`: Macromolecular component table and PISA interface contact chemistry table.
  - `notes`: Highlight bio-mechanistic functional inference hypothesis as a note (`kind="observation"`).
- **D-11: Exhaustive UI Developer Guide (`docs/UI_INTEGRATION_GUIDE.md`)**: Deliver comprehensive handoff documentation containing the full data dictionary, enum descriptions, nullability rules, visual tone mappings, and step-by-step instructions for integrating the adapter into the UI server.
- **D-12: Curated TypeScript Types (`schema/types/quaternary.ts`)**: Export clean, strict TypeScript definitions corresponding to `QuaternaryStructureOutput` for frontend engineers building custom quaternary visualization components.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UI Branch Contracts & Schemas
- `origin/UI:UI/backend/app/schemas.py` — The canonical shared data contract (`LevelResult`, `Headline`, `Metric`, `Track`, `Segment`, `Table`, `Note`, `Link`).
- `origin/UI:UI/docs/LEVEL_CONTRACT.md` — Structural level integration specification, residue map track styles, tone definitions, and error handling rules (`LevelSkipped`).
- `origin/UI:UI/backend/app/examples.py` — The 5 canonical example protein definitions and sequences (`ubiquitin`, `hemoglobin-alpha`, `bacteriorhodopsin`, `p53`, `akt1`).
- `origin/UI:UI/backend/app/levels/placeholders.py` — Placeholder quaternary implementation to be superseded by `quaternary/ui_adapter.py`.

### Backend Engine & Models
- `quaternary/models/session_state.py` — Root definition of `QuaternaryStructureOutput` and stage tracking models.
- `quaternary/session.py` — `QuaternarySession` multi-stage pipeline and `to_ui()` serialization.
- `quaternary/models/stoichiometry.py` — `Stoichiometry`, `EvidenceCoverage`, `FunctionalComplex`, `InferredFunction`.
- `quaternary/models/interface.py` — `InterfaceContact` schema.
- `quaternary/models/conflict.py` — `ExperimentalConflict` schema.

### Project Planning
- `.planning/REQUIREMENTS.md` — QUAT-08, QUAT-09 (amended to UI examples), QUAT-10 (deferred).
- `.planning/ROADMAP.md` — Phase 4 scope and plan definitions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `quaternary.session.QuaternarySession`: Executes Stages 1–6 and produces `QuaternaryStructureOutput`.
- `quaternary.session.to_ui()`: Native JSON and dict exporter already attached to session.
- `quaternary.presentation`: Rich visual component library developed in Phase 03.2.
- `quaternary.models`: Complete Pydantic v2 schemas ready for JSON schema export.

### Established Patterns
- Pydantic v2 `model_json_schema()` for automated schema generation.
- Pure function adapters returning dataclass/BaseModel instances without side effects.
- Segregated confidence provenance and standardized six-tier consensus status vocabulary (`CONFIRMED`, `SUPPORTED`, `CONFLICTING`, `INSUFFICIENT EVIDENCE`, `UNAVAILABLE`, `PREDICTED`).
- Non-zero PISA interface extraction with transparent `N/A` fallbacks.

### Integration Points
- `quaternary/ui_adapter.py`: New module bridging `QuaternarySession` to `UI.backend.app.schemas.LevelResult`.
- `scripts/export_ui_contract.py`: New CLI tool generating `schema/quaternary_structure_output.schema.json`, `schema/fixtures/`, and `schema/types/quaternary.ts`.
- `Quaternary_Structure.ipynb`: Add an export cell invoking `to_ui()`.
- `tests/test_ui_contract.py`: New test suite validating JSON schema conformance with `jsonschema`.
- `tests/test_benchmarks.py`: New benchmark test suite asserting results for the 5 UI examples.

</code_context>

<specifics>
## Specific Ideas

- User guidance: "look into the ui branch. tey have used some default examples, try to use those examples only and get the outputs for those" — directly adopt the 5 sequences from `UI/backend/app/examples.py`.
- User guidance: "the ui might need to run on some other thing as well" — ensure the data contract, JSON schema, and UI adapter remain completely generic and uncoupled from hardcoded sequences.
- User guidance: "just skip the novel sequence fully for now. add as future scope(issue) to test things out properly and add them in later. ignore the above decisions regarding the novel seq as well please. let us just do the happy path coding for now" — defer QUAT-10 to a GitHub issue and focus Phase 4 on happy-path contract and UI integration.

</specifics>

<deferred>
## Deferred Ideas

- Novel and synthetic sequence validation (QUAT-10): Defer comprehensive boundary testing, scrambled negative-control sequence validation, and de novo fallback assertions to a dedicated future milestone/issue.
- Live external AlphaFold-Multimer cloud execution: Maintained as deferred per Phase 03.2 decisions (cleanly tagged as `PREDICTION_NOT_EXECUTED`).

</deferred>

---

*Phase: 4-standardized-ui-json-data-contract-benchmark-validation*
*Context gathered: 2026-10-05*
