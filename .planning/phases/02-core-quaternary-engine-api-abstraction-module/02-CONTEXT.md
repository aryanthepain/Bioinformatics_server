# Phase 2: Core Quaternary Engine & API Abstraction Module - Context

**Gathered:** 2026-10-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a robust, standalone Python module (`quaternary_pipeline.py` and `quaternary/` subpackage) that provides clean abstractions for querying biological quaternary databases (UniProtKB SUBUNIT, Complex Portal, RCSB PDB, PDBe PISA, SWISS-MODEL, IntAct, AlphaFold DB, ESMFold, AlphaFold-Multimer), robust async polling with HTTP 303 redirect interception, and normalized Pydantic data models. It exposes a step-wise stateful analysis session (`QuaternarySession`) designed specifically for cell-by-cell notebook execution and inspection, ending with a dedicated `to_ui(format="json")` export preview method.

This phase does NOT build the final interactive notebook (Phase 3), perform end-to-end benchmark validation on *H. influenzae* (Phase 4), or develop the frontend UI application.

</domain>

<decisions>
## Implementation Decisions

### Module Architecture & Packaging

- **D-01:** Implement a modular subpackage layout (`quaternary/` containing `models/`, `clients/`, `session.py`, `engine.py`, `config.py`) exposed via a clean top-level facade `quaternary_pipeline.py`. Callers in notebooks can simply run `import quaternary_pipeline` or `from quaternary_pipeline import QuaternaryEngine, QuaternarySession`. — **Reversibility:** costly — changing the import structure touches all downstream notebooks and scripts.
- **D-02:** Structure the engine around an interactive step-wise stateful `QuaternarySession` (`session = engine.create_session(seq_or_id)`). The pipeline explicitly exposes individual stage execution (`session.run_stage_1_primary_evidence()`, `session.run_stage_2_experimental_qualification()`, `session.run_stage_3_homology_and_partners()`, `session.run_stage_4_structural_context()`, `session.run_stage_5_multimer_hypothesis()`, `session.run_stage_6_synthesis()`), rather than acting solely as an opaque black box. — **Reversibility:** costly — downstream Phase 3 notebook structure directly mirrors these stages.
- **D-03:** Provide an explicit Stage 7 UI export method: `session.to_ui(format="json", ...)` defaulting to JSON, but parameterizable to export other formats (e.g. dict, dataframe) for seamless frontend handoff preview. — **Reversibility:** reversible
- **D-04:** Analysis identifiers (`analysis_id` / `session_id`) must be generated and managed strictly on the engine side. Callers provide only the target sequence or UniProt accession; the engine automatically creates unique IDs. — **Reversibility:** reversible
- **D-05:** Implement graceful non-fatal stage fallbacks. If an external service times out or errors, the session records `status: "unavailable"`, attaches error details in that stage's provenance, and allows downstream stages to continue rather than raising unhandled exceptions in notebook cells. — **Reversibility:** reversible

### Data Modeling & Validation Framework

- **D-06:** Use Pydantic v2 (`BaseModel`) across all data entities, schemas, and stage results. Pydantic v2 is already installed and provides native serialization (`model_dump()`), validation, and automated JSON Schema generation for the Phase 4 UI data contract. — **Reversibility:** costly — switching modeling frameworks would require rewriting serialization and schema validators.
- **D-07:** Model stoichiometry using a dedicated `Stoichiometry` Pydantic model with symbolic formula (e.g. `"A2B2"`), chain count mapping (`{"A": 2, "B": 2}`), total subunit count (4), and an `AssemblyType` enum (`MONOMER`, `HOMOMER`, `HETEROMER`, `UNCHARACTERIZED`). — **Reversibility:** costly — affects data structures throughout stages and UI exports.
- **D-08:** Model interface interactions using a detailed `InterfaceContact` schema capturing interacting chain pairs (e.g. A-B), buried surface area (Å²), interface solvation ΔG (kcal/mol), hydrogen bonds / salt bridges count, and participating residue indices. — **Reversibility:** reversible
- **D-09:** Strictly segregate source confidence metrics into dedicated sub-models within `ConfidenceProvenance` (enforcing D-08 from Phase 1) and preserve conflicting assertions in an `ExperimentalConflict` model (enforcing D-03 from Phase 1). Zero synthetic mathematical blending of disparate scores. — **Reversibility:** one-way — changing this breaks core scientific integrity and conflict transparency guarantees.

### Client Architecture & Async Polling Strategy

- **D-10:** Implement a uniform `BaseBioClient` adapter pattern. Wrap BioServices for supported services (`UniProt`, `IntAct`) and custom REST endpoints (RCSB Search DSL, PDBe PISA REST, SWISS-MODEL Repo, AlphaFold DB) behind a standardized client interface with shared session pooling, retries, and timeout settings. — **Reversibility:** costly — touches all client implementations.
- **D-11:** Implement strict HTTP 303 redirect interception with `allow_redirects=False` in async polling loops (resolving Roadblock 2 from `problems.md`). Extract the target `Location` header upon receiving HTTP 303 and apply exponential backoff with a hard maximum timeout. — **Reversibility:** costly — critical for preventing infinite polling loops and crashes on UniProt/EBI async jobs.
- **D-12:** Configure session-level retries using `urllib3.util.Retry` mounted on `requests.Session` with exponential backoff on 429, 502, 503, 504 status codes, strictly honoring server `Retry-After` headers. — **Reversibility:** reversible
- **D-13:** Implement `MultimerPredictorClient` enforcing caller opt-in (`enable_multimer=True`) and explicit hypothesis specification (self-association or partner heteromer) per D-06. Include an offline simulation/dry-run mode for local notebook testing without requiring a dedicated multimer GPU. — **Reversibility:** reversible

### API Caching & Network Strategy

- **D-14:** Support a dual/pluggable caching architecture (`CacheBackend`) with both transparent JSON directory caching (`.cache/quaternary/`) as default and SQLite database storage (`.cache/quaternary.db`). — **Reversibility:** reversible
- **D-15:** Use permanent caching until manually cleared (`engine.clear_cache()`) or bypassed (`force_refresh=True`) for Phase 2. Automated TTL expiration and background pruning is deferred to a future milestone (tracked in GitHub Issue #3). — **Reversibility:** reversible
- **D-16:** Implement hierarchical `QuaternaryConfig` supporting configuration via constructor kwargs, environment variables (`QUATERNARY_CACHE_DIR`, `QUATERNARY_CACHE_BACKEND`), or an optional local JSON configuration file (`quaternary_config.json`). — **Reversibility:** reversible
- **D-17:** Implement an offline fixture fallback mode (`offline_mode=True`) allowing the engine and test suite to run against bundled JSON response fixtures without requiring live network calls. — **Reversibility:** reversible

### the agent's Discretion

- Selection of specific internal helper class names, directory structure within `quaternary/`, and internal logging formatter details.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract and scope
- `.planning/ROADMAP.md` — Phase 2 goal, requirements (QUAT-03, QUAT-04, QUAT-05), and success criteria.
- `.planning/REQUIREMENTS.md` — Requirement definitions for QUAT-03 (Engine module), QUAT-04 (Experimental & homology retrieval), and QUAT-05 (Predictive multimer & async polling).
- `.planning/PROJECT.md` — Project context, constraints, and key decisions.

### Prior Phase Decisions & Ecosystem Evidence
- `.planning/phases/01-quaternary-ecosystem-survey/01-CONTEXT.md` — Prior decisions D-01 through D-13 (Coverage tiers, PISA validation, conflict retention, monomer boundary, multimer opt-in, confidence segregation).
- `docs/ecosystem/03_evidence_collection_route.md` — The 6-stage evidence collection routing specification, conflict retention protocol, and assembly ranking scoring formula ($S_{\text{assembly}}$).
- `docs/ecosystem/provider_inventory.json` — Machine-readable inventory of all 13 biological providers, accepted inputs, endpoints, rate limits, and evidence tiers.

### Technical Roadblocks & Guidelines
- `problems.md` — Roadblock 1 (BioServices refactoring trap) and Roadblock 2 (UniProt async HTTP 303 redirect quirk requiring `allow_redirects=False`).
- `phase_1/guideline.md` — BioServices-first integration standard and documented direct-REST fallback criteria.
- `docs/uniprot_server_overview.md` — UniProt access methods, streaming API, and session retry patterns.
- `UniProtKB.ipynb` — Existing retrying session and benchmark implementations.
- `UniProt.ipynb` — BioServices UniProt client patterns and PDB cross-reference queries.

### Issue Tracker Linkage
- `https://github.com/aryanthepain/Bioinformatics_server/issues/3` — feat(cache): add configurable TTL expiration and automatic cache invalidation (deferred to future milestone).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `UniProtKB.ipynb`: retrying `requests.Session` configuration, streaming-query handlers, and benchmark patterns.
- `UniProt.ipynb`: BioServices `UniProt` client patterns and PDB cross-reference queries.
- `docs/ecosystem/provider_inventory.json`: complete JSON specifications for UniProt, RCSB PDB, PDBe PISA, SWISS-MODEL, IntAct, AlphaFold DB, and ESMFold endpoints.

### Established Patterns
- BioServices is the preferred client for supported databases (`UniProt`, `IntAct`); direct `requests.Session` adapters are used for specialized endpoints (RCSB Search API v2 DSL, PDBe PISA REST, SWISS-MODEL Repo, AlphaFold DB v4).
- Polling for asynchronous jobs must strictly use `allow_redirects=False` to intercept HTTP 303 status codes.
- Pydantic v2 (`BaseModel`) is the standard schema framework for data models and JSON serialization.

### Integration Points
- `quaternary_pipeline.py` serves as the public entrypoint for the Phase 3 Jupyter notebook (`Quaternary_Structure.ipynb`).
- `QuaternarySession.to_ui(format="json")` produces the data contract consumed in Phase 4 (`quaternary_structure_output.json`).

</code_context>

<specifics>
## Specific Ideas

- The user emphasized: **"step wise things should be shown in the notebook, not e2e."** The pipeline must expose individual stages clearly so notebook cells can step through each part of the analysis.
- The user specified: **"ui export stage - make it to_ui with default param json but the ability to change this param to export in some other format."**
- The user specified: **"also have the id creation on the engine side only."**
- The user requested: **"also mention that this thing should be configurable depending on the user"** (hierarchical `QuaternaryConfig`).

</specifics>

<deferred>
## Deferred Ideas

- **Automated Cache TTL & Expiration**: Automated Time-To-Live (TTL) cache invalidation and background pruning deferred to a future milestone (tracked in GitHub Issue #3).
- **Interactive Jupyter Notebook**: Creating and formatting `Quaternary_Structure.ipynb` with interactive tables and plots — Phase 3.
- **Comprehensive Benchmarking & Final UI Schema Export**: Validation on *Haemophilus influenzae* and synthetic sequences — Phase 4.

</deferred>

---

*Phase: 02-core-quaternary-engine-api-abstraction-module*
*Context gathered: 2026-10-04*
