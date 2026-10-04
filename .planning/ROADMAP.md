# Roadmap: Bioinformatics Server - Quaternary Protein Structure

## Overview

This roadmap drives the development of the Quaternary Structure module for the bioinformatics server. Starting with an exhaustive survey of quaternary bioinformatics servers and a reusable research prompt, the workflow advances through authoring a clean Python API abstraction module (`quaternary_pipeline.py`), building an interactive abstracted Jupyter notebook (`Quaternary_Structure.ipynb`), and culminating in a standardized frontend JSON data contract validated against uncharacterized bacterial pathogen targets and novel synthetic sequences.

## Phases

- [x] **Phase 1: Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt** - Survey quaternary servers/APIs and author reusable discovery prompt. (Completed 2026-10-03)
- [x] **Phase 2: Core Quaternary Engine & API Abstraction Module** - Implement `quaternary_pipeline.py` abstracting API calls, async polling, and data normalization. (Completed 2026-10-04)
- [ ] **Phase 3: Abstracted Interactive Jupyter Notebook** - Create `Quaternary_Structure.ipynb` providing high-level analysis with minimal boilerplate.
- [ ] **Phase 4: Standardized UI JSON Data Contract & Benchmark Validation** - Export standard schema for frontend UI and validate against *H. influenzae* and synthetic sequences.

## Phase Details

### Phase 1: Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt

**Goal**: Identify, catalog, and evaluate all available quaternary structure databases and predictive servers; author a structured reusable prompt for server research.
**Depends on**: Nothing (first phase)
**Requirements**: QUAT-01, QUAT-02
**Success Criteria** (what must be TRUE):
  1. A comprehensive catalog of quaternary databases (UniProtKB SUBUNIT, PDBe PISA, SWISS-MODEL) and predictive servers (AlphaFold-Multimer, GalaxyHeteromer, ClusPro, ESM-complex) is documented with inputs, endpoints, and limitations.
  2. A proven, copy-pasteable reusable research prompt is produced for discovering and evaluating additional quaternary servers.
  3. API authentication, rate limits, and async polling characteristics are cataloged for pipeline design.

**Plans**: 3 plans

Plans:
- [x] 01-01: Research and catalog experimental and homology quaternary databases (UniProtKB SUBUNIT, PDBe PISA, SWISS-MODEL oligomers)
- [x] 01-02: Research predictive multimer servers and docking APIs (AlphaFold-Multimer, ColabFold, GalaxyHeteromer, ClusPro, ESM-complex)
- [x] 01-03: Synthesize findings and formulate the reusable quaternary server research prompt

### Phase 2: Core Quaternary Engine & API Abstraction Module

**Goal**: Build a robust, standalone Python module (`quaternary_pipeline.py`) that handles all quaternary queries, async polling, redirect handling, and data normalization outside of notebook cells.
**Depends on**: Phase 1
**Requirements**: QUAT-03, QUAT-04, QUAT-05
**Success Criteria** (what must be TRUE):
  1. `quaternary_pipeline.py` exists and can be imported cleanly into notebooks or server scripts.
  2. Experimental and homology quaternary annotations are queried and parsed with zero raw boilerplate in caller code.
  3. Asynchronous job polling safely handles UniProt/EBI HTTP 303 redirects and rate limits without crashes or infinite loops.
  4. Unified data structures represent oligomeric state, subunit count, stoichiometry, and interface residues.

**Plans**: 4 plans

Plans:
**Wave 1**
- [x] 02-01: Design core data models (dataclasses/Pydantic) for quaternary structure results in `quaternary_pipeline.py`

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02: Implement experimental and homology-based retrieval clients (UniProtKB SUBUNIT, PDB PISA, SWISS-MODEL)
- [x] 02-03: Implement predictive multimer client wrappers with robust async polling and HTTP 303 redirect handling

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-04: Implement unified aggregation, error fallback, and interface contact extraction logic

### Phase 3: Abstracted Interactive Jupyter Notebook

**Goal**: Deliver a clean, highly readable Jupyter notebook (`Quaternary_Structure.ipynb`) that demonstrates complete quaternary characterization using high-level module calls.
**Depends on**: Phase 2
**Requirements**: QUAT-06, QUAT-07
**Success Criteria** (what must be TRUE):
  1. `Quaternary_Structure.ipynb` executes cleanly from start to finish without exposing raw HTTP or parser internals.
  2. Clear visual summary tables and plots display predicted oligomeric states, stoichiometry, and confidence scores.
  3. Interactive cells allow users to input a sequence or accession ID and inspect quaternary assembly predictions.

**Plans**: 3 plans

Plans:
**Wave 1**
- [x] 03-01: Scaffold `Quaternary_Structure.ipynb` importing `quaternary_pipeline` with configuration and input handling cells

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02: Implement interactive tabular displays, confidence metric visuals, and assembly status summaries

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-03: Add interactive export triggers and complete end-to-end biological interpretation markdown documentation

### Phase 03.1: Quaternary Engine Rigor, Complex Disambiguation & Functional Inference (INSERTED)

**Goal:** Resolve biological modeling ambiguities (GroEL A14 self-assembly vs GroEL-GroES A14B7 partner complex), recover the core mission of Quaternary-to-Function biological inference, establish canonical 1–6 stage sequencing, ensure absence of evidence yields UNCHARACTERIZED (not MONOMER), and enforce truthful multimer simulation reporting and auditability.
**Requirements**: QUAT-03, QUAT-04, QUAT-05, QUAT-06, QUAT-07, QUAT-09
**Depends on:** Phase 3
**Success Criteria** (what must be TRUE):
  1. GroEL target self-assembly reports `A14 / HOMOMER` while GroES partner complex reports `A14B7` separately.
  2. Novel sequences without experimental/homology evidence report `UNCHARACTERIZED` (not `MONOMER`).
  3. Quaternary-to-Function Inference Engine links oligomeric geometry and homologous complexes to molecular function and biological process.
  4. Stage 1 to 6 canonical sequence is established on `QuaternarySession` and misleading aliases are removed.
  5. Stage 5 multimer execution is transparently labeled as `SIMULATED` / `HEURISTIC_PREDICTED` (default `enable_multimer=True`), with prediction disagreements retained in `conflicts[]`.
  6. `Quaternary_Structure.ipynb` dynamically renders Component Identity, Interface Contact, Evidence Coverage, and Functional Inference tables without hardcoded markdown metrics.

**Plans:** 3 plans

Plans:
**Wave 1**
- [x] 03.1-01: Core Domain Models, Canonical 6-Stage Session & Biological Evidence Schemas

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03.1-02: Biological Disambiguation, Engineering Hardening & Functional Inference Engine

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03.1-03: Jupyter Notebook Overhaul, Dynamic Rendering & Benchmark Showcase


### Phase 4: Standardized UI JSON Data Contract & Benchmark Validation

**Goal**: Formalize the UI JSON export schema and validate the pipeline against *Haemophilus influenzae* uncharacterized proteins and synthetic novel sequences.
**Depends on**: Phase 3
**Requirements**: QUAT-08, QUAT-09, QUAT-10
**Success Criteria** (what must be TRUE):
  1. Standardized JSON payload (`quaternary_structure_output.json`) is exported with complete metadata, ready for frontend UI ingestion.
  2. Pipeline successfully processes and benchmarks uncharacterized targets from *H. influenzae* (UP000000579).
  3. Pipeline successfully runs on synthetic/novel unannotated primary sequences, providing meaningful fallback/predictions.
  4. Frontend UI integration guide and data dictionary are delivered to support the UI team member.

**Plans**: 3 plans

Plans:
- [ ] 04-01: Formalize JSON schema contract (`quaternary_structure_output.json`) and write schema validation checks
- [ ] 04-02: Run benchmarking suite on *Haemophilus influenzae* uncharacterized proteome entries (UP000000579)
- [ ] 04-03: Run validation on novel/synthetic unannotated sequences and deliver the UI developer handoff guide

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Quaternary Ecosystem Survey & Reusable Prompt | 3/3 | Complete | 2026-10-03 |
| 2. Core Quaternary Engine & API Abstraction Module | 4/4 | Complete | 2026-10-04 |
| 3. Abstracted Interactive Jupyter Notebook | 3/3 | Complete | 2026-10-04 |
| 03.1. Quaternary Engine Rigor & Functional Inference | 0/3 | In progress | - |
| 4. UI JSON Data Contract & Benchmark Validation | 0/3 | Not started | - |

---
*Roadmap defined: 2026-10-03*
*Last updated: 2026-10-04 after Phase 3 execution*
