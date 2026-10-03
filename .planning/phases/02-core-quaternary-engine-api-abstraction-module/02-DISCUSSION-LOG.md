# Phase 2: Core Quaternary Engine & API Abstraction Module - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-04
**Phase:** 02-core-quaternary-engine-api-abstraction-module
**Areas discussed:** Module Architecture & Packaging, Data Modeling & Validation Framework, Client Architecture & Async Polling Strategy, API Caching & Network Strategy

---

## Module Architecture & Packaging

| Option | Description | Selected |
|--------|-------------|----------|
| Modular subpackage (`quaternary/`) + `quaternary_pipeline.py` facade | Clean modular structure for models/clients/engine with root facade import | ✓ |
| Single monolithic script (`quaternary_pipeline.py`) | All models, clients, and pipeline code in one flat script | |
| You decide | Agent discretion | |

**User's choice:** Modular subpackage (`quaternary/`) with top-level `quaternary_pipeline.py` facade.
**Notes:** Separates concerns while keeping notebook imports simple.

| Option | Description | Selected |
|--------|-------------|----------|
| Unified `QuaternaryEngine` class + functional shortcut | Class orchestrator + fast function | |
| Pure functional API only | Loose functions without session | |
| Step-wise things shown in notebook | Intermediate stages visible and executable in separate cells | ✓ |

**User's choice:** Step-wise things should be shown in the notebook, not e2e.
**Notes:** User explicitly instructed that the analysis must not be an opaque black box. Biologists and reviewers need to step through intermediate stages (Stage 1 to 6) cell-by-cell in the notebook.

| Option | Description | Selected |
|--------|-------------|----------|
| Stateful Analysis Session (`QuaternarySession`) | Accumulates findings across stages with cell variable access | ✓ |
| Pure Modular Stage Functions | Pure data pipes | |
| You decide | Agent discretion | |

**User's choice:** Stateful Analysis Session (`QuaternarySession`) + dedicated Stage 7 UI export (`to_ui(format="json")`).
**Notes:** User requested an explicit UI export stage at the end with a configurable `format` parameter defaulting to `"json"`.

| Option | Description | Selected |
|--------|-------------|----------|
| Graceful stage fallback with status flags | Non-fatal status flags ('unavailable') and error provenance | ✓ |
| Strict exception raising | Halts notebook execution on network/API failure | |
| You decide | Agent discretion | |

**User's choice:** Graceful stage fallback with status flags.
**Notes:** Allows remaining stages to continue cleanly if an external service experiences intermittent downtime.

| Option | Description | Selected |
|--------|-------------|----------|
| Engine-side ID generation | Engine generates unique session/analysis tracking IDs | ✓ |
| Caller-provided ID | User/caller must generate and manage IDs | |

**User's choice:** Also have the id creation on the engine side only.
**Notes:** Callers pass target sequence or accession, engine manages internal identifiers.

---

## Data Modeling & Validation Framework

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic v2 (`BaseModel`) | Native validation, serialization, and automated JSON schema export | ✓ |
| Standard library `@dataclass` | Zero external dependencies, manual serialization | |
| You decide | Agent discretion | |

**User's choice:** Pydantic v2 (`BaseModel`).
**Notes:** Pydantic 2.11 is already installed; provides direct schema export required for Phase 4 UI contract.

| Option | Description | Selected |
|--------|-------------|----------|
| Structured Stoichiometry model | Formula ("A2B2"), chain count dict, total count, AssemblyType enum | ✓ |
| Flat string & integer fields | Simple string and count | |
| You decide | Agent discretion | |

**User's choice:** Structured Stoichiometry model.
**Notes:** Explicit modeling of homomer, heteromer, monomer, and uncharacterized states.

| Option | Description | Selected |
|--------|-------------|----------|
| Detailed `InterfaceContact` model | Chain pairs, buried surface area (Å²), ΔG, H-bonds, residue indices | ✓ |
| Summary metrics only | Aggregate area and count only | |
| You decide | Agent discretion | |

**User's choice:** Detailed `InterfaceContact` model.
**Notes:** Preserves biophysical and residue-level interaction details from PISA.

| Option | Description | Selected |
|--------|-------------|----------|
| Strict `ConfidenceProvenance` & `ExperimentalConflict` schemas | Segregated source confidence (D-08) & explicit conflict tracking (D-03) | ✓ |
| Loose dictionary (`extra_metrics: Dict[str, Any]`) | Unstructured metadata | |
| You decide | Agent discretion | |

**User's choice:** Strict `ConfidenceProvenance` & `ExperimentalConflict` schemas.
**Notes:** Enforces Phase 1 invariants D-03 and D-08.

---

## Client Architecture & Async Polling Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform `BaseBioClient` adapter pattern | Consistent interface wrapping BioServices & custom REST | ✓ |
| Decentralized independent client functions | Standalone query scripts | |
| You decide | Agent discretion | |

**User's choice:** Uniform `BaseBioClient` adapter pattern.
**Notes:** Adheres to BioServices-first guideline while supporting specialized REST endpoints (RCSB, PISA, SWISS-MODEL, AlphaFold DB).

| Option | Description | Selected |
|--------|-------------|----------|
| Strict HTTP 303 intercept (`allow_redirects=False`) + backoff | Directly catches 303, extracts Location header, hard timeout | ✓ |
| Permissive redirect following with body sniffing | Follows redirects and checks body | |
| You decide | Agent discretion | |

**User's choice:** Strict HTTP 303 intercept (`allow_redirects=False`) + backoff poller.
**Notes:** Directly resolves Roadblock 2 from `problems.md` for UniProt/EBI async endpoints.

| Option | Description | Selected |
|--------|-------------|----------|
| Session-level `urllib3.util.Retry` with `Retry-After` support | Retries on 429/502/503/504 with exponential backoff and server respect | ✓ |
| Caller-level manual retry loops | Ad-hoc sleeps | |
| You decide | Agent discretion | |

**User's choice:** Session-level `urllib3.util.Retry` with `Retry-After` support.
**Notes:** Robust rate-limit and transient error management across all clients.

| Option | Description | Selected |
|--------|-------------|----------|
| MultimerRunner with Opt-In validation & Dry-Run simulation | Enforces D-06 opt-in + hypothesis, provides mock mode for local testing | ✓ |
| Strict GPU CLI execution only | Fails if local GPU is missing | |
| You decide | Agent discretion | |

**User's choice:** MultimerRunner with Opt-In validation & Dry-Run simulation.
**Notes:** Allows running and testing the pipeline locally without requiring a dedicated multimer GPU.

---

## API Caching & Network Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Transparent file-system directory cache (`.cache/quaternary/`) | JSON files hashed by query | ✓ (Hybrid) |
| SQLite database file (`.cache/quaternary.db`) | Relational SQLite database with timestamps | ✓ (Hybrid) |
| In-memory cache only | Ephemeral dictionary cache | |
| You decide | Agent discretion | |

**User's choice:** 1 and 2 (both supported via pluggable `CacheBackend` architecture).
**Notes:** Supports both human-inspectable JSON files and SQLite backend.

| Option | Description | Selected |
|--------|-------------|----------|
| Default 7-day TTL with force_refresh toggle | Automatic TTL expiration | Deferred |
| Permanent Cache until manually cleared | Permanent cache + manual clear / force_refresh | ✓ |
| You decide | Agent discretion | |

**User's choice:** Permanent Cache until manually cleared for now, but automated TTL in future milestone.
**Notes:** Logged to GitHub Issue #3 (`https://github.com/aryanthepain/Bioinformatics_server/issues/3`).

| Option | Description | Selected |
|--------|-------------|----------|
| Hierarchical `QuaternaryConfig` | Kwargs, env vars (`QUATERNARY_*`), and JSON config file | ✓ |
| Constructor kwargs only | Code-only configuration | |
| You decide | Agent discretion | |

**User's choice:** Hierarchical `QuaternaryConfig`.
**Notes:** User emphasized that settings should be fully configurable per user.

| Option | Description | Selected |
|--------|-------------|----------|
| Offline fixture fallback (`offline_mode=True`) | Bundled test fixtures for offline dev and tests | ✓ |
| Strict network requirement | Connection errors on cache miss | |
| You decide | Agent discretion | |

**User's choice:** Offline fixture fallback (`offline_mode=True`).
**Notes:** Ensures local tests and demonstrations can execute deterministically without external network dependency.

---

## the agent's Discretion

- Concrete internal utility helpers, logging message formats, and subpackage file division within `quaternary/`.

## Deferred Ideas

- Automated Time-To-Live (TTL) cache expiration and background pruning (logged to GitHub Issue #3).
- Interactive Jupyter notebook visualizations (`Quaternary_Structure.ipynb`) — Phase 3.
- *Haemophilus influenzae* proteome benchmarking and final JSON schema validation — Phase 4.
