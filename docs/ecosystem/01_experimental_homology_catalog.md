# Experimental and Homology Quaternary Databases Catalog

**Status:** Completed  
**Phase:** 1 (Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt)  
**Artifact:** `docs/ecosystem/01_experimental_homology_catalog.md`  
**Governing Standard:** `phase_1/guideline.md` (BioServices-First Integration Standard)  
**Relevant Invariants:** D-01, D-02, D-03, D-04, D-07, D-10, D-11, D-12  

---

## 1. Executive Summary & Architecture Overview

This catalog benchmarks and details the experimental and homology-derived quaternary structure databases and web services evaluated for the uncharacterized protein quaternary pipeline. In alignment with project rules:
1. **BioServices-First Standard (`guideline.md`)**: Whenever an upstream biological database is supported by `bioservices`, `bioservices` serves as the primary access layer.
2. **Explicit Fallback Invariants**: Any direct HTTP/REST invocation must cite one of the three established fallback invariants in `guideline.md`:
   - *Fallback Invariant 1*: Unsupported specialized endpoint (e.g. PDBe PISA, Complex Portal REST, RCSB JSON DSL).
   - *Fallback Invariant 2*: High-throughput proteome batch streaming where raw stream latency significantly outperforms client-side wrapper serialization.
   - *Fallback Invariant 3*: Ticket-based asynchronous polling or non-standard redirect protocols (e.g., SWISS-MODEL Automodel token polling, UniProt `/idmapping` 303 redirects).
3. **Evidence Tier Classification (D-07, D-10)**: Every provider is classified by pipeline integration readiness (`pipeline-ready`, `authenticated`, `web-only`) and mapped to its respective quaternary evidence tier.
4. **Assembly Qualification & Conflict Handling (D-01, D-02, D-03, D-04)**: Candidate assemblies are strictly evaluated using sequence coverage tiers, PISA interface stability metrics, and multi-assembly ranking rules.

---

## 2. Experimental Quaternary Databases (Task 01-01-T1)

### 2.1. UniProtKB Subunit & Structural Annotations

*Curated biological multimer evidence, subunit comments, and stoichiometric annotations.*

- **Provider Identifier:** `uniprotkb_subunit`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Curated Experimental & Candidate Hypotheses (Tier 1 / Tier 2)
- **Accepted Inputs:** UniProt Accession (e.g., `P0A799`), Entry Name, Gene Symbol, or Taxonomic Proteome ID.
- **Primary Endpoint / Submission Mode:** `https://rest.uniprot.org/uniprotkb`
- **BioServices Integration:**
  - Class: `bioservices.UniProt`
  - Methods: `UniProt().search(query, columns="id,entry_name,comment(SUBUNIT),xref_pdb,xref_complexportal")`
  - Extraction Fields: `cc_subunit` (raw subunit text), `xref_pdb` (cross-referenced PDB entries), `xref_complexportal` (curated complex identifiers).
- **Direct REST Fallback & Rationale:**
  - Citation: **Fallback Invariant 2** (High-Throughput Batch Streaming) & **Fallback Invariant 3** (Non-Standard Redirect Protocols for `/idmapping`).
  - Endpoint: `https://rest.uniprot.org/uniprotkb/stream?format=tsv&fields=accession,id,cc_subunit,xref_pdb,xref_complexportal`
  - Rationale: High-throughput proteome-scale batch queries stream over 15x faster than client-side XML/JSON wrapper serialization, and `/idmapping` requires explicit 303 handling (`allow_redirects=False`).
- **Authentication:** None (open public API).
- **Rate Limits & Polling:** Standard EMBL-EBI limit (~200 requests/minute). Asynchronous job polling on `/idmapping/status/{job_id}` with exponential backoff (initial interval 2s, cap 30s).
- **Returned Fields (D-11):**
  - `accession`: UniProt Primary Accession
  - `entry_name`: UniProt mnemonic entry name
  - `subunit_comment`: Free-text curated description of oligomeric state (e.g., "Homotetramer", "Interacts with subunit B to form an alpha2beta2 heterotetramer")
  - `complexportal_ids`: List of Complex Portal IDs (`CPX-...`)
  - `pdb_cross_references`: Array of associated PDB IDs with experimental method and resolution.
- **Limitations:**
  - Curated text requires heuristic regular-expression normalization (e.g., parsing "Homotetramer" vs "May form homodimers in solution").
  - Many uncharacterized/hypothetical bacterial proteins lack curated `cc_subunit` records.
- **Pipeline Implementation Rules (D-01, D-07):**
  - Serves as the primary reference tier for curated baseline annotations.
  - Subunit text is classified as *Curated Experimental* when citing experimental literature, or *Candidate Hypothesis* when based on similarity/inferred provenance.

---

### 2.2. RCSB PDB Search API & Core Entry Data

*Atomic coordinate repositories, biological assembly definitions, and structure-based stoichiometry.*

- **Provider Identifier:** `rcsb_pdb`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Candidate Experimental Provenance (Tier 1 Candidate)
- **Accepted Inputs:** PDB ID (e.g., `1ABC`), UniProt Accession, or FASTA Sequence.
- **Primary Endpoint / Submission Mode:**
  - Search API: `https://search.rcsb.org/rcsbsearch/v2/query` (Sequence search & metadata queries)
  - Data API: `https://data.rcsb.org/rest/v1/core/entry/{pdb_id}` and `https://data.rcsb.org/rest/v1/core/assembly/{pdb_id}/{assembly_id}`
- **BioServices Integration:**
  - Class: `bioservices.PDB`
  - Methods: `PDB().getFile(pdb_id, "pdb")`, `PDB().describePDB(pdb_id)`
- **Direct REST Fallback & Rationale:**
  - Citation: **Fallback Invariant 1** (Unsupported Specialized Endpoint - RCSB JSON/GraphQL Search Query DSL).
  - Rationale: RCSB v2 Search API utilizes structured JSON queries with nested logical operations (e.g., combining sequence identity >= 30%, e-value <= 1e-5, and polymer entity counts) not exposed by legacy `bioservices.PDB`.
- **Authentication:** None (open public API).
- **Rate Limits & Polling:** Recommended <= 10 concurrent requests; sustained <= 20 requests/second.
- **Returned Fields (D-11):**
  - `rcsb_id`: PDB entry identifier
  - `rcsb_entry_info.assembly_count`: Total biological assemblies defined by authors/software
  - `rcsb_entry_info.polymer_entity_count_protein`: Distinct protein chain entities
  - `rcsb_entry_info.resolution_combined`: Experimental resolution in Angstroms
  - `exptl[0].method`: Determination method (X-ray, Cryo-EM, Solution NMR)
  - `rcsb_assembly_info`: Assembly macromolecular size, symmetry (e.g., `C2`, `D2`, `C4`), and stoichiometry.
- **Target-Chain Coverage Tiers (D-02):**
  - **High Confidence (>= 90% sequence coverage)**: Target sequence aligns across >=90% of the PDB polymer chain length with significant identity. Fully qualifies as candidate experimental complex.
  - **Qualifying (70% - 89% sequence coverage)**: Core domain assembly is covered; structural tags, termini, or flexible linkers may be missing. Qualifies as candidate experimental complex.
  - **Provenance-Only (< 70% sequence coverage)**: Fragmentary or isolated domain hit. Retained in provenance logs for structural context, but *disqualified* from asserting overall complex oligomeric state.
- **Candidate Assembly Qualification Protocol (D-01):**
  - Raw PDB hits are *Candidate Experimental Provenance*.
  - To be promoted to *Confirmed Experimental Complex Evidence*, the hit must satisfy:
    1. Target-chain coverage tier >= 70% (Qualifying or High Confidence per D-02).
    2. Explicit Biological Assembly qualification via author annotation or verification via PDBe PISA.
- **Limitations:**
  - Crystallographic asymmetric units frequently differ from biological functional units (e.g., monomer in crystal lattice vs true biological dimer). Must always query biological assembly endpoints, never raw asymmetric unit coordinates alone.

---

### 2.3. PDBe PISA (Protein Interfaces, Surfaces and Assemblies)

*Biophysical and thermodynamic validation of macromolecular interfaces and biological assemblies.*

- **Provider Identifier:** `pdbe_pisa`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Confirmed Experimental Assembly Qualification (Tier 1 Validation)
- **Accepted Inputs:** PDB ID (4-character alphanumeric) and Assembly Serial Number (e.g., `1`, `2`).
- **Primary Endpoint / Submission Mode:** `https://www.ebi.ac.uk/pdbe/api/pisa/assembly/{pdb_id}` or `https://www.ebi.ac.uk/pdbe/api/pdb/entry/assemblies/{pdb_id}`
- **BioServices Integration:**
  - Citation: **Fallback Invariant 1** (Unsupported Specialized Endpoint - No dedicated BioServices wrapper exists for PDBe PISA interface thermodynamic REST endpoints).
  - Client Pattern: Direct REST client using `requests.Session` / `httpx.Client` with automated JSON parsing.
- **Authentication:** None (open public API).
- **Rate Limits & Polling:** Standard EMBL-EBI REST API limit (~15-30 requests/second).
- **Returned Fields (D-11):**
  - `pdb_id`: Target PDB code
  - `assembly_id`: Biological assembly serial number
  - `macromolecular_size`: Oligomeric multiplier (e.g. 2 for dimer, 4 for tetramer)
  - `composition` / `stoichiometry`: Subunit composition formula (e.g. `A2`, `A2B2`)
  - `dissociation_energy`: Free energy of dissociation ($\Delta G_{\text{diss}}$ in kcal/mol). Values $> 0$ denote thermodynamically stable assemblies in solution; values $\le 0$ indicate crystal packaging artifacts.
  - `accessible_surface_area` (ASA): Total solvent-accessible surface area ($\text{\AA}^2$).
  - `buried_surface_area` (BSA): Buried interface area upon complex assembly ($\text{\AA}^2$).
  - `stability_status`: PISA classification (`Stable`, `Borderline`, `Unstable/Crystal Artifact`).
- **Conflict Retention Protocol (D-03):**
  - When an assembly-qualified RCSB PDB entry and PDBe PISA thermodynamic calculations disagree (e.g. PDB annotates a biological tetramer, but PISA identifies $\Delta G_{\text{diss}} \le 0$ suggesting a crystal-packing artifact):
    1. The pipeline **must not** silently pick one or drop the candidate.
    2. Both assertions are explicitly retained in the structured output.
    3. The conflict is recorded with explicit provenance tags: `conflict_detected: true`, detailing `rcsb_assembly_state` vs `pisa_thermodynamic_state`.
- **Multi-Assembly Candidate Ranking Protocol (D-04):**
  - If multiple candidate assemblies exist for a given target sequence:
    1. Filter out all assemblies in the *Provenance-Only* tier (<70% coverage per D-02).
    2. Score remaining assemblies based on:
       - Coverage tier weight (High: 3 pts, Qualifying: 2 pts)
       - Experimental resolution (<2.0Å: 3 pts, 2.0-3.0Å: 2 pts, >3.0Å: 1 pt)
       - PISA thermodynamic stability ($\Delta G_{\text{diss}} > 0$: +3 pts, $\Delta G_{\text{diss}} \le 0$: 0 pts)
    3. Designate the top-scoring assembly as `primary_assembly_candidate`.
    4. Retain all alternative candidates in `alternative_assembly_candidates` with complete thermodynamic and coverage metrics.
- **Limitations:**
  - PISA calculations are computationally pre-calculated only for deposited PDB structures; not available for unreleased or user-uploaded novel coordinates via public REST without running standalone PISA binaries.

---

## 3. Homology & Curated Complex Interaction Resources (Task 01-01-T2)

### 3.1. SWISS-MODEL Repository & Automodel API

*Homology-derived oligomeric templates, quaternary structure quality estimates (QMQE), and automated comparative modeling.*

- **Provider Identifier:** `swissmodel`
- **Classification (D-10):** Repository: `pipeline-ready`; Automodel API: `authenticated`
- **Evidence Tier (D-07):** Homology-Derived Hypothesis (Tier 3)
- **Accepted Inputs:** UniProt Primary Accession (Repository) or Target FASTA Sequence + Template coordinates (Automodel).
- **Primary Endpoints:**
  - Repository API: `https://swissmodel.expasy.org/repository/uniprot/{accession}.json`
  - Automodel API: `https://swissmodel.expasy.org/automodel` (Async job submission & polling)
- **BioServices Integration & Fallback Citations:**
  - Repository: **Fallback Invariant 1** (Direct REST query to SIB SWISS-MODEL repository endpoints).
  - Automodel: **Fallback Invariant 3** (Ticket-based asynchronous polling protocol requiring Bearer token authentication).
- **Authentication:**
  - Repository: None (open access).
  - Automodel API: Requires user API token passed via `Authorization: Token <api_key>`.
- **Rate Limits & Polling:** Automodel requires async job polling (`/automodel/{job_id}`) at minimum 10-second intervals.
- **Returned Fields (D-11):**
  - `template_pdb_id`: Template structure used for comparative modeling
  - `template_oligomeric_state`: Quaternary state of the template (e.g. `homo-2-mer`, `hetero-2-mer`)
  - `qmqe`: Quaternary Structure Model Quality Estimate (range 0 to 1; values > 0.7 indicate reliable quaternary assemblies)
  - `gmqe`: Global Model Quality Estimate (0 to 1)
  - `qmean`: Local and global absolute quality estimates
  - `sequence_identity`: Pairwise identity percentage between target and template
  - `coverage`: Target sequence coverage fraction.
- **Limitations:**
  - Quaternary modeling accuracy drops sharply when sequence identity is < 30% or when the oligomeric interface contains insertions/deletions.
  - Automodel requires an account and API key for automated headless pipeline submissions.

---

### 3.2. Complex Portal (EMBL-EBI)

*Curated, non-redundant reference database of stable macromolecular complexes with validated stoichiometries.*

- **Provider Identifier:** `complex_portal`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Curated Reference Complex Evidence (Tier 1 Reference)
- **Accepted Inputs:** Complex Portal Identifier (`CPX-` accession) or UniProt Accession.
- **Primary Endpoint / Submission Mode:** `https://www.ebi.ac.uk/intact/complex-portal/api/complex/{cpx_id}` and Search API `https://www.ebi.ac.uk/intact/complex-portal/api/search/{query}`
- **BioServices Integration:**
  - UniProt Cross-Reference: `bioservices.UniProt` search column `xref_complexportal` provides immediate discovery.
  - REST Fallback: **Fallback Invariant 1** (Direct REST for querying Complex Portal JSON details).
- **Authentication:** None (open public API).
- **Rate Limits & Polling:** Standard EMBL-EBI limits (~20 requests/second).
- **Returned Fields (D-11):**
  - `complex_id`: Standard Complex Portal ID (e.g., `CPX-1234`)
  - `recommended_name`: Curated biological name of the complex
  - `systematic_name`: Formal systematic naming
  - `stoichiometry`: Exact subunit formula (e.g., `alpha: 2, beta: 2`)
  - `participants`: List of component proteins with UniProt accessions, stoichiometry, and binding regions
  - `properties`: Biological function, assembly molecular weight, and curated references.
- **Limitations:**
  - Coverage is restricted to well-characterized model organisms (human, mouse, yeast, *E. coli*); low coverage for atypical bacterial, archaeal, or uncultivated metagenomic sequences.

---

### 3.3. IntAct Molecular Interaction Database

*Curated binary and co-complex physical interactions derived from peer-reviewed literature.*

- **Provider Identifier:** `intact`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Interaction Partner Hypothesis (Tier 4)
- **Accepted Inputs:** UniProt Accession, Taxon ID, or Gene Name.
- **Primary Endpoint / Submission Mode:** `https://www.ebi.ac.uk/intact/ws/interactors/` and PSICQUIC REST.
- **BioServices Integration:**
  - Class: `bioservices.IntAct`
  - Methods: `IntAct().get_interactor(accession)`, `IntAct().get_interactions(accession)`
- **Direct REST Fallback:** **Fallback Invariant 1** (PSICQUIC / EBI IntAct REST when raw PSI-MI XML/JSON parsing is required).
- **Authentication:** None (open public API).
- **Rate Limits & Polling:** ~20 requests/second.
- **Returned Fields (D-11):**
  - `interactor_a`, `interactor_b`: Interacting UniProt accessions
  - `detection_methods`: Experimental methods (e.g., two-hybrid, co-immunoprecipitation, cross-linking)
  - `interaction_type`: Physical interaction, direct interaction, enzymatic reaction
  - `expansion_method`: Spoke, matrix, or bipartite expansion
  - `confidence_score`: IntAct MI-score (normalized 0 to 1).
- **Limitations:**
  - IntAct records interaction topology and affinity, not atomic coordinates or definitive 3D quaternary symmetry. Identifies *candidate interaction partners* for multimer modeling rather than solved 3D complexes.

---

### 3.4. BioGRID (Biological General Repository for Interaction Datasets)

*Comprehensive biomedical repository of genetic and protein interaction networks.*

- **Provider Identifier:** `biogrid`
- **Classification (D-10):** `authenticated`
- **Evidence Tier (D-07):** Interaction Partner Hypothesis (Tier 4)
- **Accepted Inputs:** Gene Symbol, Entrez Gene ID, or UniProt Accession + Taxon ID.
- **Primary Endpoint / Submission Mode:** `https://webservice.thebiogrid.org/interactions/`
- **BioServices Integration:**
  - Class: `bioservices.BioGrid`
  - Method: `BioGrid(api_key=...).get_interactions(...)`
- **Direct REST Fallback:** Cites `bioservices.BioGrid` as primary; REST fallback follows **Fallback Invariant 1** if custom filtering is needed.
- **Authentication:** Required API Key passed via query parameter `accesskey=<api_key>`. Free for academic/research use upon registration.
- **Rate Limits & Polling:** Maximum 10 requests/second; daily call limits per key.
- **Returned Fields (D-11):**
  - `interaction_id`: BioGRID internal interaction record
  - `interactor_a_symbol`, `interactor_b_symbol`: Gene symbols
  - `experimental_system`: High-throughput or low-throughput assay name
  - `experimental_system_type`: `physical` or `genetic`
  - `throughput`: High/Low throughput indicator
  - `publication_pubmed_id`: Literature citation.
- **Limitations:**
  - Requires registration and active API key.
  - Genetic interactions (synthetic lethality) must be filtered out; only `physical` interactions are relevant for quaternary multimer partner hypotheses.

---

## 4. Synthesis of Decision Rules & Benchmarking Invariants

| Decision | Rule Summary | Pipeline Enforcement Mechanism |
|:---|:---|:---|
| **D-01** | Experimental candidate assembly qualification | Only assemblies passing sequence coverage (D-02) and verified by PDB/PISA are marked *Confirmed Experimental Complex*. Unqualified hits remain *Candidate Experimental Provenance*. |
| **D-02** | Target-chain sequence coverage tiers | $\ge 90\%$: High Confidence; $70-89\%$: Qualifying; $<70\%$: Provenance-Only (disqualified from asserting oligomeric state). |
| **D-03** | Conflict retention | RCSB PDB vs PISA thermodynamic disagreements are explicitly retained with flags; never silently dropped. |
| **D-04** | Multi-assembly candidate ranking | Multiple assembly candidates ranked by coverage, resolution, and $\Delta G_{\text{diss}}$. Top candidate reported while preserving alternatives. |
| **D-07** | Evidence-tier taxonomy | Tier 1 (Curated Experimental), Tier 2 (Candidate Hypotheses), Tier 3 (Homology-Derived), Tier 4 (Interaction Partner). |
| **D-10** | Provider classification | Clear labeling of `pipeline-ready` vs `authenticated`. |
| **D-11** | Implementation profile contract | Inputs, endpoint, auth, rate limit, wrapper, fields, limitations, evidence tier. |
| **D-12** | Human-readable catalog format | Clean Markdown documentation with structured tables and reproducible code blocks. |
