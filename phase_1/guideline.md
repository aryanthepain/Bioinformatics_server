# Phase 1 Architectural Guideline: BioServices-First Integration Standard

**Status:** Active  
**Scope:** Phase 1 (Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt) and Downstream Quaternary Pipelines  
**Author:** AI Orchestrator  
**Enforcement:** Mandatory for all Phase 1 research recommendations, server discovery prompts, and pipeline design  

---

## 1. Core Mandate

When researching, querying, benchmarking, or integrating biological databases and web services across this project, **developers and AI agents MUST prioritize the [`bioservices`](https://bioservices.readthedocs.io/) Python library as the primary interface**.

Direct, ad-hoc HTTP/REST requests (e.g., via `requests`, `httpx`, or `urllib`) must **not** be authored from scratch for any biological service where a tested `bioservices` module already exists.

---

## 2. Background & Rationale

This guideline is established to address critical lessons learned during prior pipeline iterations, specifically documented in [`problems.md`](file:///d:/projects/bioinformatics_project/problems.md) and [`docs/uniprot_server_overview.md`](file:///d:/projects/bioinformatics_project/docs/uniprot_server_overview.md):

1. **Eliminating the "BioServices Refactoring Trap" ([`problems.md:L3-7`](file:///d:/projects/bioinformatics_project/problems.md#L3-L7))**:
   - In earlier explorations, pipelines were initially authored with fragmented, raw REST calls. When refactoring to `bioservices`, substantial engineering overhead was incurred resolving divergent parameter names (`fields` vs `columns`, `format` vs `frmt`) and return type mismatches.
   - Adopting `bioservices` from Day 1 eliminates redundant refactoring and ensures immediate consistency.

2. **Outsourced Upstream Maintenance**:
   - European Bioinformatics Institute (EMBL-EBI), UniProt, and PDB APIs continuously evolve endpoints and schemas. `bioservices` is actively maintained by the bioinformatics open-source community, meaning upstream deprecations and changes are resolved without requiring in-house re-engineering.

3. **Surgical Fault Localization**:
   - Wrapping high-level `bioservices` methods inside isolated adapter tests allows instant detection of failing upstream methods if an external schema shifts.

---

## 3. Primary BioServices Modules for Quaternary Analysis

All Phase 1 ecosystem evaluations, research prompts, and pipeline abstractions should target the following `bioservices` classes:

| Service / Module | Target Information for Quaternary Characterization | Key Methods / Usage |
|:---|:---|:---|
| **`bioservices.UniProt`** | Curated subunit composition (`comment(SUBUNIT)`), stoichiometry (e.g. *Homotetramer*, *Heterodimer*), cross-references (`xref_pdb`, `xref_complexportal`). | `UniProt().search(query, columns="id,entry_name,comment(SUBUNIT),xref_pdb,xref_complexportal")` |
| **`bioservices.IntAct`** | Curated molecular interactions, multimer complex participants, and experimental stoichiometry. | `IntAct().get_interaction(...)` / `get_interactors(...)` |
| **`bioservices.PDB`** | Biological assembly definitions, biological unit descriptions, symmetry, and coordinate downloads. | `PDB().getFile(...)` / `PDB().describePDB(...)` |
| **`bioservices.QuickGO`** | Quaternary-related Gene Ontology annotations (e.g., `GO:0043234` protein complex, `GO:0042802` identical protein binding). | `QuickGO().get_go_terms(...)` |
| **`bioservices.BioGrid`** | Physical interaction partners and complex evidence for multi-subunit assemblies. | `BioGrid().get_interactions(...)` |
| **`bioservices.KEGG`** | Pathway-level multi-protein complexes and enzymatic quaternary assemblies. | `KEGG().get(...)` |

---

## 4. Implementation Pattern: BioServices-First Adapter Architecture

To handle the known caveat of BioServices—dynamic return types ranging from raw TSV strings to Python dictionaries—all `bioservices` calls in downstream modules (e.g., `quaternary_pipeline.py`) must follow the **BioServices-First Adapter Pattern**:

```
+-----------------------------------------------------------------+
|               Caller / Quaternary Interactive Notebook          |
|                      (High-level Python API)                    |
+-----------------------------------------------------------------+
                                |
                                v
+-----------------------------------------------------------------+
|            Quaternary Pipeline Engine (Adapter Layer)           |
+-----------------------------------------------------------------+
           |                                             |
           v                                             v
  [Primary Standard Path]                       [Documented Fallback Path]
+---------------------------+                 +---------------------------+
|    BioServices Adapter    |                 |     Direct REST Client    |
| - bioservices.UniProt     |                 |   (httpx / requests)      |
| - bioservices.IntAct      |                 | - PDBe PISA REST API      |
| - bioservices.PDB         |                 | - SWISS-MODEL Repo API    |
| - bioservices.QuickGO     |                 | - AlphaFold-Multimer      |
+---------------------------+                 +---------------------------+
           \                                             /
            \                                           /
             v                                         v
+-----------------------------------------------------------------+
|               Unified Output Normalizer (Pydantic)              |
|        Ensures clean, strongly-typed JSON/Dict outputs          |
+-----------------------------------------------------------------+
```

- **Output Sanitization**: The adapter layer must ingest the raw string/TSV/dict from `bioservices` and convert it into strongly-typed Pydantic models (e.g., `QuaternaryAssemblyResult`).
- **Defensive Parsing**: Use helper functions (e.g., `io.StringIO` with `pandas.read_csv(sep='\t')` for TSV returns) to ensure deterministic outputs.

---

## 5. Strict Preference with Documented Fallback Rules

Per project consensus, developers and AI agents must follow a **strict preference with documented fallback**:

### Fallback Criteria (When Direct REST is Permitted)
Direct HTTP client requests (`httpx` / `requests`) are permitted **only** when at least one of the following criteria is met:

1. **Unsupported Specialized Endpoints**:
   - The tool or server does not have an official or functional `bioservices` wrapper.
   - *Examples*: PDBe PISA REST API (quaternary interface analysis), SWISS-MODEL Repository API (oligomeric homology templates), ColabFold / AlphaFold-Multimer runners, GalaxyHeteromer, ClusPro.
2. **High-Throughput Batch Streaming**:
   - High-volume proteome streaming tasks where empirical benchmarks prove `bioservices` internal serialization causes prohibitive latency (e.g., as benchmarked in [`docs/uniprot_server_overview.md`](file:///d:/projects/bioinformatics_project/docs/uniprot_server_overview.md) where raw Stream API was >15x faster than BioServices).
3. **Non-Standard Asynchronous Redirect Protocols**:
   - Workflows where API servers employ non-standard redirect patterns requiring custom low-level HTTP interceptors (e.g., the UniProtKB `/idmapping` HTTP 303 redirect quirk requiring `allow_redirects=False` documented in [`problems.md:L10-15`](file:///d:/projects/bioinformatics_project/problems.md#L10-L15)).

### Documentation Requirement for Fallbacks
Any fallback to direct REST must include an inline code comment citing:
1. The missing BioServices capability or benchmark rationale.
2. Link to this guideline document.

---

## 6. Phase 1 Deliverables Checklist

When executing Phase 1 plans (`01-01`, `01-02`, `01-03`):
- [ ] Catalog all quaternary tools and explicitly categorize which ones are natively supported by `bioservices`.
- [ ] Ensure the reusable Phase 1 research prompt instructs external agents to evaluate `bioservices` wrappers first.
- [ ] Structure the proposed Phase 2 architecture around the BioServices Adapter Pattern.
