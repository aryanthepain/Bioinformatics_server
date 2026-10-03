# Phase 2: Core Quaternary Engine & API Abstraction Module - Research

**Researched:** 2026-10-04  
**Domain:** Bioinformatics Quaternary Structure Modeling, Biological REST/BioServices API Abstraction, Pydantic v2 Schema Design, Async HTTP 303 Redirect Polling, Multi-Tier Caching  
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Module Architecture & Packaging
- **D-01:** Implement a modular subpackage layout (`quaternary/` containing `models/`, `clients/`, `session.py`, `engine.py`, `config.py`) exposed via a clean top-level facade `quaternary_pipeline.py`. Callers in notebooks can simply run `import quaternary_pipeline` or `from quaternary_pipeline import QuaternaryEngine, QuaternarySession`. — **Reversibility:** costly
- **D-02:** Structure the engine around an interactive step-wise stateful `QuaternarySession` (`session = engine.create_session(seq_or_id)`). The pipeline explicitly exposes individual stage execution (`session.run_stage_1_primary_evidence()`, `session.run_stage_2_experimental_qualification()`, `session.run_stage_3_homology_and_partners()`, `session.run_stage_4_structural_context()`, `session.run_stage_5_multimer_hypothesis()`, `session.run_stage_6_synthesis()`), rather than acting solely as an opaque black box. — **Reversibility:** costly
- **D-03:** Provide an explicit Stage 7 UI export method: `session.to_ui(format="json", ...)` defaulting to JSON, but parameterizable to export other formats (e.g. dict, dataframe) for seamless frontend handoff preview. — **Reversibility:** reversible
- **D-04:** Analysis identifiers (`analysis_id` / `session_id`) must be generated and managed strictly on the engine side. Callers provide only the target sequence or UniProt accession; the engine automatically creates unique IDs. — **Reversibility:** reversible
- **D-05:** Implement graceful non-fatal stage fallbacks. If an external service times out or errors, the session records `status: "unavailable"`, attaches error details in that stage's provenance, and allows downstream stages to continue rather than raising unhandled exceptions in notebook cells. — **Reversibility:** reversible

#### Data Modeling & Validation Framework
- **D-06:** Use Pydantic v2 (`BaseModel`) across all data entities, schemas, and stage results. Pydantic v2 is already installed and provides native serialization (`model_dump()`), validation, and automated JSON Schema generation for the Phase 4 UI data contract. — **Reversibility:** costly
- **D-07:** Model stoichiometry using a dedicated `Stoichiometry` Pydantic model with symbolic formula (e.g. `"A2B2"`), chain count mapping (`{"A": 2, "B": 2}`), total subunit count (4), and an `AssemblyType` enum (`MONOMER`, `HOMOMER`, `HETEROMER`, `UNCHARACTERIZED`). — **Reversibility:** costly
- **D-08:** Model interface interactions using a detailed `InterfaceContact` schema capturing interacting chain pairs (e.g. A-B), buried surface area (Å²), interface solvation ΔG (kcal/mol), hydrogen bonds / salt bridges count, and participating residue indices. — **Reversibility:** reversible
- **D-09:** Strictly segregate source confidence metrics into dedicated sub-models within `ConfidenceProvenance` (enforcing D-08 from Phase 1) and preserve conflicting assertions in an `ExperimentalConflict` model (enforcing D-03 from Phase 1). Zero synthetic mathematical blending of disparate scores. — **Reversibility:** one-way

#### Client Architecture & Async Polling Strategy
- **D-10:** Implement a uniform `BaseBioClient` adapter pattern. Wrap BioServices for supported services (`UniProt`, `IntAct`) and custom REST endpoints (RCSB Search DSL, PDBe PISA REST, SWISS-MODEL Repo, AlphaFold DB) behind a standardized client interface with shared session pooling, retries, and timeout settings. — **Reversibility:** costly
- **D-11:** Implement strict HTTP 303 redirect interception with `allow_redirects=False` in async polling loops (resolving Roadblock 2 from `problems.md`). Extract the target `Location` header upon receiving HTTP 303 and apply exponential backoff with a hard maximum timeout. — **Reversibility:** costly
- **D-12:** Configure session-level retries using `urllib3.util.Retry` mounted on `requests.Session` with exponential backoff on 429, 502, 503, 504 status codes, strictly honoring server `Retry-After` headers. — **Reversibility:** reversible
- **D-13:** Implement `MultimerPredictorClient` enforcing caller opt-in (`enable_multimer=True`) and explicit hypothesis specification (self-association or partner heteromer) per D-06. Include an offline simulation/dry-run mode for local notebook testing without requiring a dedicated multimer GPU. — **Reversibility:** reversible

#### API Caching & Network Strategy
- **D-14:** Support a dual/pluggable caching architecture (`CacheBackend`) with both transparent JSON directory caching (`.cache/quaternary/`) as default and SQLite database storage (`.cache/quaternary.db`). — **Reversibility:** reversible
- **D-15:** Use permanent caching until manually cleared (`engine.clear_cache()`) or bypassed (`force_refresh=True`) for Phase 2. Automated TTL expiration and background pruning is deferred to a future milestone (tracked in GitHub Issue #3). — **Reversibility:** reversible
- **D-16:** Implement hierarchical `QuaternaryConfig` supporting configuration via constructor kwargs, environment variables (`QUATERNARY_CACHE_DIR`, `QUATERNARY_CACHE_BACKEND`), or an optional local JSON configuration file (`quaternary_config.json`). — **Reversibility:** reversible
- **D-17:** Implement an offline fixture fallback mode (`offline_mode=True`) allowing the engine and test suite to run against bundled JSON response fixtures without requiring live network calls. — **Reversibility:** reversible

### the agent's Discretion
- Internal directory file layout within `quaternary/` subpackage.
- Helper class names, logging formatters, and utility functions.

### Deferred Ideas (OUT OF SCOPE)
- Automated Time-To-Live (TTL) cache invalidation and background pruning (logged to GitHub Issue #3 for future milestone).
- Interactive Jupyter notebook visualizations (`Quaternary_Structure.ipynb`) — Phase 3.
- *Haemophilus influenzae* proteome benchmarking and final JSON schema validation — Phase 4.
</user_constraints>

---

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| External API Clients & Adapters (`quaternary/clients/`) | Integration / Network | API / Backend | Connects to UniProt, RCSB PDB, PDBe PISA, SWISS-MODEL, IntAct, AlphaFold DB, and ColabFold Multimer runner |
| Domain Models & Schemas (`quaternary/models/`) | Domain / Schema | Validation | Defines Pydantic v2 data models, stoichiometry enums, and JSON serializable entities |
| Persistence & Caching (`quaternary/cache/`) | Storage / Cache | Local Filesystem / DB | Manages JSON directory store and SQLite relational cache for offline fast repeats and rate-limit preservation |
| Stateful Analysis Session (`quaternary/session.py`) | Workflow / State | Orchestration | Manages stage progression (Stages 1 through 7), intermediate state accumulation, and `to_ui()` formatting |
| Engine Orchestrator (`quaternary/engine.py`) | Application Facade | Core Pipeline | Coordinates client configurations, cache instances, session creation, and engine-side ID generation |
| Top-Level Facade (`quaternary_pipeline.py`) | Public API | Client Facade | Exposes public imports (`QuaternaryEngine`, `QuaternarySession`, `QuaternaryConfig`) for notebook cleanliness |
</architectural_responsibility_map>

---

<research_summary>
## Summary

Phase 2 builds the core computational engine and API abstraction module for quaternary protein structure analysis. In Phase 1, an exhaustive ecosystem survey cataloged 13 biological databases and predictive tools into `provider_inventory.json` and established a 6-stage evidence collection route (`03_evidence_collection_route.md`) alongside critical invariants (D-01 through D-13). Phase 2 codifies these rules into a clean, modular Python architecture that isolates networking, retries, and schema parsing outside of notebook cells.

The design centers on an interactive, step-wise execution model (`QuaternarySession`). Rather than burying complex biophysical retrieval behind an opaque, single black-box function, the engine exposes explicit stage runners so biologists and downstream notebooks (Phase 3) can step through each scientific milestone independently:
1. Primary Evidence Retrieval (UniProtKB SUBUNIT, Complex Portal, RCSB PDB sequence search)
2. Experimental Qualification & PISA Thermodynamics (Target coverage tiers D-02, PISA $\Delta G_{\text{diss}}$, conflict retention D-03, assembly ranking D-04)
3. Homology & Interactome (SWISS-MODEL repository, IntAct/BioGRID physical partners)
4. Structural Context (AlphaFold DB v4 coordinates & pLDDT, strictly enforcing monomer boundary D-05)
5. Predictive Multimer Hypothesis Formulation (Caller opt-in requirement D-06, dry-run simulation mode)
6. Unified Synthesis & Provenance Normalization (Segregated source confidence metrics D-08, assembly classification)
7. UI Export & Preview (`session.to_ui(format="json")`, with parameterizable format support)

Network robustness directly incorporates solutions for historical roadblocks documented in `problems.md`. A uniform `BaseBioClient` wraps BioServices where supported (`UniProt`, `IntAct`) and manages direct `requests.Session` instances for specialized REST endpoints (RCSB Search DSL, PDBe PISA REST, SWISS-MODEL Repo, AlphaFold DB). Crucially, asynchronous polling loops strictly employ `allow_redirects=False` to intercept UniProt/EBI HTTP 303 redirects, extract the terminal `Location` header, and poll with exponential backoff and hard timeouts, eliminating infinite loops and unexpected crashes.

**Primary recommendation:** Build a modular `quaternary/` subpackage with clean Pydantic v2 models, robust `BaseBioClient` adapters with explicit HTTP 303 handling, a pluggable JSON/SQLite `CacheBackend`, and an interactive `QuaternarySession` exposed via `quaternary_pipeline.py`.
</research_summary>

---

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python` | 3.12 | Execution Runtime | Base Python environment installed on system |
| `pydantic` | 2.11.5 | Data validation & JSON schemas | Native JSON Schema generation for Phase 4 UI contract, strict validation, high speed |
| `requests` | 2.34.1 | HTTP Client | Ubiquitous Python HTTP library, supports custom adapters and connection pooling |
| `urllib3` | 2.x (bundled) | Session retry & connection pooling | Standard `urllib3.util.Retry` handles 429/502/503/504 backoff and `Retry-After` headers |
| `bioservices` | latest installed | Bio-informatics client wrapper | Project standard for UniProt and IntAct; avoids custom HTTP boilerplate for EBI services |
| `sqlite3` | stdlib | Relational Cache Backend | Zero-dependency ACID relational cache for fast indexed query lookups |
| `pathlib` | stdlib | Path management | Robust cross-platform path resolution for cache and fixtures |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pandas` | 3.0.3 | Tabular inspection | Format intermediate stage findings into DataFrames for clean notebook rendering |
| `json` | stdlib | Serialization | Read/write raw JSON cache files and fixture datasets |
| `hashlib` | stdlib | Query Hashing | Generate SHA-256 cache keys from endpoint + payload parameters |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic v2 | Standard `@dataclass` | Dataclasses lack automated JSON schema export required for Phase 4 UI data contract |
| Dual JSON/SQLite Cache | In-Memory `lru_cache` only | In-memory cache is wiped on kernel restart; persistent cache saves API rate limits during dev |
| Step-Wise Session | Monolithic e2e function | Monolithic calls hide intermediate biophysical evidence, violating user inspection requirements |
</standard_stack>

---

<architecture_patterns>
## Architecture Patterns

### System Architecture Diagram

```
                        [ Target Query: Sequence or UniProt ID ]
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │  quaternary_pipeline   │
                               │   (Top-Level Facade)   │
                               └───────────┬────────────┘
                                           │ creates
                                           ▼
                               ┌────────────────────────┐
                               │    QuaternaryEngine    │
                               │  (Config & ID Manager) │
                               └───────────┬────────────┘
                                           │ instantiates
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        QuaternarySession (Stateful Coordinator)                        │
│                                                                                        │
│  Stage 1: Primary Evidence ──► UniProtClient / ComplexPortalClient / RCSBSearchClient  │
│  Stage 2: Experimental     ──► PISAClient (Coverage Tiers, Conflict Retention D-03)    │
│  Stage 3: Homology         ──► SwissModelClient / IntActClient (Physical Partners)     │
│  Stage 4: Structural       ──► AlphaFoldClient / ESMFold (Monomer Boundary D-05)       │
│  Stage 5: Multimer Hypoth  ──► MultimerPredictorClient (Opt-in D-06, Dry-run sim)      │
│  Stage 6: Synthesis        ──► Normalizer (Confidence Provenance D-08, Ranking D-04)   │
│  Stage 7: UI Export        ──► session.to_ui(format="json" | "dict" | "dataframe")     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ queries / updates
                                           ▼
                               ┌────────────────────────┐
                               │  Pluggable Cache Layer │
                               │  (JSON & SQLite DB)    │
                               └────────────────────────┘
```

### Recommended Project Structure

```
d:/projects/bioinformatics_project/
├── quaternary/
│   ├── __init__.py                # Package exports
│   ├── config.py                  # QuaternaryConfig (hierarchical configuration)
│   ├── engine.py                  # QuaternaryEngine orchestrator
│   ├── session.py                 # QuaternarySession (7-stage stateful execution)
│   ├── models/
│   │   ├── __init__.py            # Model re-exports
│   │   ├── stoichiometry.py       # Stoichiometry, AssemblyType enum
│   │   ├── interface.py           # InterfaceContact, ResidueRange
│   │   ├── conflict.py            # ExperimentalConflict (D-03)
│   │   ├── provenance.py          # ConfidenceProvenance (D-08), SourceConfidence
│   │   └── session_state.py       # StageResult, QuaternaryStructureOutput
│   ├── clients/
│   │   ├── __init__.py            # Client registry
│   │   ├── base.py                # BaseBioClient with retry & HTTP 303 poller
│   │   ├── uniprot.py             # UniProtKB SUBUNIT client (BioServices + stream fallback)
│   │   ├── rcsb.py                # RCSB Search API v2 DSL client
│   │   ├── pisa.py                # PDBe PISA interface & assembly client
│   │   ├── complex_portal.py      # Complex Portal REST client
│   │   ├── swissmodel.py          # SWISS-MODEL Repository client
│   │   ├── alphafold.py           # AlphaFold DB v4 client (monomer boundary)
│   │   ├── intact.py              # IntAct / BioGRID physical interactome client
│   │   └── multimer.py            # MultimerRunner (opt-in validation + dry-run)
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── base.py                # CacheBackend abstract base class
│   │   ├── json_cache.py          # File-system JSON directory cache (.cache/quaternary/)
│   │   └── sqlite_cache.py        # Relational SQLite database cache (.cache/quaternary.db)
│   └── fixtures/                  # Bundled offline responses for offline_mode=True
│       ├── uniprot_p12345.json
│       ├── rcsb_search_hit.json
│       └── pisa_assembly_sample.json
├── quaternary_pipeline.py         # Top-level clean facade module for notebook imports
└── tests/
    └── test_quaternary_pipeline.py # Deterministic pytest suite for all stages
```

### Pattern 1: Step-Wise Stateful Analysis Session (`QuaternarySession`)

```python
class QuaternarySession:
    """Manages the progressive state of a protein quaternary characterization."""
    
    def __init__(self, target_input: str, engine: "QuaternaryEngine"):
        self.session_id: str = engine._generate_session_id(target_input)
        self.target_input: str = target_input
        self.engine = engine
        self.stages: Dict[int, StageResult] = {}
        self.output: Optional[QuaternaryStructureOutput] = None

    def run_stage_1_primary_evidence(self) -> StageResult:
        # Queries UniProtKB, Complex Portal, and RCSB PDB sequence search
        ...

    def run_stage_2_experimental_qualification(self) -> StageResult:
        # Runs PDBe PISA, evaluates D-02 coverage tiers, detects D-03 conflicts, ranks assemblies D-04
        ...

    def run_stage_3_homology_and_partners(self) -> StageResult:
        # Queries SWISS-MODEL Repo and physical interactors (IntAct)
        ...

    def run_stage_4_structural_context(self) -> StageResult:
        # Queries AlphaFold DB coordinates & pLDDT, enforces monomer boundary D-05
        ...

    def run_stage_5_multimer_hypothesis(self, enable: bool = False, hypothesis: Optional[str] = None) -> StageResult:
        # Validates caller opt-in D-06; executes runner or returns simulation/eligible proposal
        ...

    def run_stage_6_synthesis(self) -> QuaternaryStructureOutput:
        # Synthesizes final assembly, segregates confidence D-08, builds final object
        ...

    def to_ui(self, format: str = "json", **kwargs) -> Any:
        """Stage 7: Formats and exports the final normalized output for the frontend UI."""
        if self.output is None:
            self.run_stage_6_synthesis()
        
        if format == "json":
            return self.output.model_dump_json(indent=2)
        elif format == "dict":
            return self.output.model_dump()
        elif format == "dataframe":
            return self._to_dataframe()
        else:
            raise ValueError(f"Unsupported export format: {format}")
```

### Pattern 2: `BaseBioClient` with HTTP 303 Redirect Interception

```python
class BaseBioClient:
    """Unified HTTP client adapter handling retries, pooling, and async 303 polling."""

    def __init__(self, config: QuaternaryConfig, cache_backend: Optional[CacheBackend] = None):
        self.config = config
        self.cache = cache_backend
        self.session = self._create_retrying_session()

    def _create_retrying_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 502, 503, 504],
            raise_on_status=False,
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def poll_async_job(self, status_url: str, timeout_sec: int = 120) -> Dict[str, Any]:
        """Polls async status URL strictly with allow_redirects=False to catch HTTP 303."""
        start_time = time.time()
        backoff = 1.0

        while (time.time() - start_time) < timeout_sec:
            resp = self.session.get(status_url, allow_redirects=False, timeout=self.config.timeout)
            
            # Roadblock 2 resolution: HTTP 303 See Other indicates job finished
            if resp.status_code == 303:
                result_url = resp.headers.get("Location")
                if not result_url:
                    raise RuntimeError("HTTP 303 redirect missing Location header.")
                res_resp = self.session.get(result_url, timeout=self.config.timeout)
                res_resp.raise_for_status()
                return res_resp.json()
            
            elif resp.status_code == 200:
                data = resp.json()
                if data.get("jobStatus") == "FINISHED":
                    return data
                # Job still running
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 10.0)
            else:
                resp.raise_for_status()

        raise TimeoutError(f"Async job timed out after {timeout_sec} seconds.")
```

### Pattern 3: Strict Confidence Segregation & Conflict Schema

```python
class ConfidenceProvenance(BaseModel):
    """Preserves distinct source confidence metrics without mathematical blending (D-08)."""
    pdbe_pisa: Optional[PisaConfidence] = None
    swissmodel: Optional[SwissModelConfidence] = None
    alphafold_db: Optional[AlphaFoldConfidence] = None
    alphafold_multimer: Optional[MultimerConfidence] = None

class ExperimentalConflict(BaseModel):
    """Preserves biophysical vs deposition conflicts without discarding candidates (D-03)."""
    conflict_detected: bool = False
    rcsb_annotated_assembly: Optional[str] = None
    pisa_thermodynamic_state: Optional[str] = None
    dissociation_energy_kcal_mol: Optional[float] = None
    conflict_rationale: Optional[str] = None
```
</architecture_patterns>

---

<pitfalls_and_landmines>
## Pitfalls & Landmines

| Pitfall | Consequence | Prevention Mechanism |
|---------|-------------|----------------------|
| **UniProt 303 Redirect Trapping** | Naive `requests.get` follows 303 to results; poller crashes with `KeyError: 'jobStatus'` | Enforce `allow_redirects=False` in `BaseBioClient.poll_async_job()` |
| **BioServices Return Inconsistency** | Some endpoints return TSV strings while others return parsed dicts | Abstract raw responses inside `quaternary/clients/` and normalize to Pydantic models |
| **Silent Discard of PISA Disagreements** | Discarding PDB structures when PISA reports crystal packing obscures biological nuance | Enforce D-03: set `conflict_detected: true` and preserve both assertions in `ExperimentalConflict` |
| **Monomer Over-Interpretation** | Declaring a protein monomeric based solely on AlphaFold DB single-chain structure | Enforce D-05: AlphaFold DB contributes structural context only; status remains `uncharacterized` |
| **Unprompted GPU Multimer Execution** | Wasteful execution of ColabFold on batch uncharacterized targets | Enforce D-06: require explicit `enable_multimer=True` and concrete hypothesis ($A_2$ or $AB$) |
| **Synthetic Score Hallucination** | Merging $\Delta G_{\text{diss}}$ (kcal/mol), QMQE ($0-1$), and ipTM ($0-1$) into one fake metric | Enforce D-08: segregate metrics into distinct fields in `ConfidenceProvenance` |
| **Rate-Limit Lockout** | Rapid repeated notebook reruns exhaust EBI/RCSB limits (HTTP 429) | Use `CacheBackend` (JSON / SQLite) and `urllib3.util.Retry` with `Retry-After` honoring |
</pitfalls_and_landmines>

---

<code_references>
## Code References & Integration Touchpoints

- `problems.md`: Documents Roadblock 1 (BioServices refactoring trap) and Roadblock 2 (UniProt async HTTP 303 redirect quirk).
- `docs/ecosystem/provider_inventory.json`: Machine-readable specification of endpoints, parameters, and evidence tiers for all 13 biological providers.
- `docs/ecosystem/03_evidence_collection_route.md`: 6-stage evidence collection route, Assembly Ranking Score formula ($S_{\text{assembly}} = W_{\text{coverage}} + W_{\text{resolution}} + W_{\text{pisa}}$), and conflict resolution protocol.
- `UniProtKB.ipynb`: Working implementation of retrying `requests.Session` and streaming REST query handling.
- `UniProt.ipynb`: BioServices `UniProt` instance usage and cross-referencing PDB structures.
</code_references>

---

*Phase: 02-core-quaternary-engine-api-abstraction-module*  
*Research complete: 2026-10-04*
