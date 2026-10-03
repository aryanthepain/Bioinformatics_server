# Quaternary Evidence-Collection Route, Conflict Protocol & Prompt Disposition

**Status:** Completed  
**Phase:** 1 (Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt)  
**Artifact:** `docs/ecosystem/03_evidence_collection_route.md`  
**Governing Standard:** `phase_1/guideline.md` (BioServices-First Integration Standard)  
**Requirements Satisfied:** QUAT-01, QUAT-02  
**Decisions & Invariants Enforced:** D-01 through D-13  

---

## 1. Executive Summary & Routing Philosophy

The objective of the uncharacterized protein quaternary pipeline is to take an uncharacterized protein sequence, systematically query biological databases and predictive tools, and output structured, biologically defensible insights regarding its oligomeric state, stoichiometry, and assembly interfaces.

To prevent common bioinformatics pitfalls—such as mistaking a monomeric crystal packing lattice for a functional biological unit, conflating single-chain AlphaFold predictions with true multimers, or silently dropping conflicting biophysical evidence—this document establishes the formal routing architecture, qualification criteria, and conflict resolution protocols for the pipeline.

```
                          [ Input Sequence / Query ]
                                      |
                                      v
       +--------------------------------------------------------------+
       |   Stage 1: Primary Evidence Retrieval (BioServices-First)    |
       |   - UniProtKB (Subunit Annotations & ComplexPortal CrossRef) |
       |   - Complex Portal Reference Complexes                      |
       |   - RCSB PDB Sequence Similarity Search (Coverage >= 70%)   |
       +--------------------------------------------------------------+
                                      |
                   +------------------+------------------+
                   |                                     |
         [ PDB Hits Found ]                     [ No PDB Hits Found ]
                   |                                     |
                   v                                     v
       +-----------------------+             +-----------------------+
       | Stage 2: Experimental |             | Stage 3: Homology &   |
       | Qualification (D-01)  |             | Interactome Context   |
       | - PDBe PISA Analysis  |             | - SWISS-MODEL Repo    |
       | - D-02 Coverage Tiers |             | - IntAct / BioGRID    |
       | - D-03 Conflict Check |             +-----------------------+
       | - D-04 Assembly Rank  |                         |
       +-----------------------+             +-----------+-----------+
                   |                         |                       |
        [ Confirmed / Disputed ]    [ Homology Found ]     [ Orphan Sequence ]
                   |                         |                       |
                   |                         v                       v
                   |              +--------------------+   +-------------------+
                   |              | Stage 4: Structural|   | Stage 4b: Fast In |
                   |              | Context (D-05)     |   | Silico Fallback   |
                   |              | - AlphaFold DB v4  |   | - ESMFold API     |
                   |              +--------------------+   +-------------------+
                   |                         |                       |
                   +-------------------------+-----------------------+
                                             |
                                             v
       +--------------------------------------------------------------+
       | Stage 5: Predictive Multimer Proposal & Opt-In (D-06)       |
       | - Multimer Proposal Flag (caller opt-in required)            |
       | - Hypothesis formulation (Self A2/A4 or Partner AB)          |
       | - AlphaFold-Multimer / ColabFold Batch execution             |
       +--------------------------------------------------------------+
                                             |
                                             v
       +--------------------------------------------------------------+
       | Stage 6: Unified Normalization & Provenance Packaging (D-08) |
       | - Output standardized JSON schema                            |
       | - Separate source-specific confidence fields                 |
       +--------------------------------------------------------------+
```

---

## 2. Stage-by-Stage Routing Specification

### Stage 1: Primary Annotation & Sequence Query (BioServices Standard)
1. **UniProtKB Discovery**:
   - Query target sequence / accession using `bioservices.UniProt`.
   - Retrieve `comment(SUBUNIT)`, `xref_pdb`, and `xref_complexportal`.
   - If high-throughput proteome streaming is invoked, bypass wrapper serialization using the raw Streaming API (`/uniprotkb/stream`) under **Fallback Invariant 2**.
2. **Complex Portal Reference Lookup**:
   - If `xref_complexportal` is present, retrieve the validated stoichiometry and participant roster using Complex Portal REST under **Fallback Invariant 1**.
   - If present, this represents *Curated Reference Complex Evidence* (Tier 1 Reference).
3. **RCSB PDB Sequence Similarity Search**:
   - Submit sequence to RCSB Search API v2 using direct JSON query DSL under **Fallback Invariant 1**.
   - Filter matches by alignment E-value $\le 10^{-5}$ and sequence identity.

---

### Stage 2: Experimental Assembly Qualification Protocol (D-01, D-02, D-03, D-04)

Whenever PDB structural hits are retrieved, they must be rigorously evaluated before any oligomeric state is asserted:

#### Rule D-02: Target-Chain Coverage Tiers
- **Tier 1: High Confidence ($\ge 90\%$ sequence coverage)**: Target aligns across $\ge 90\%$ of the structural chain. The structural assembly represents the full macromolecule. Fully qualifies for experimental complex assignment.
- **Tier 2: Qualifying ($70\% - 89\%$ sequence coverage)**: Core structural domain is captured; terminal tags, signal peptides, or flexible linkers may be absent. Qualifies as candidate experimental complex.
- **Tier 3: Provenance-Only ($< 70\%$ sequence coverage)**: Fragmentary domain match. Disqualified from asserting complex oligomeric state. Retained in output provenance logs for domain-level structural context only.

#### Rule D-01: Assembly Qualification vs. Provenance
- A raw PDB match is initially classified as *Candidate Experimental Provenance*.
- To be promoted to *Confirmed Experimental Complex Evidence*, the entry must:
  1. Belong to Coverage Tier 1 or Tier 2 ($\ge 70\%$).
  2. Possess explicit biological assembly definitions from the author or crystallographic deposition.
  3. Undergo thermodynamic interface verification via PDBe PISA.
- Unqualified or sub-70% hits do not block the pipeline from pursuing homology search or predictive structural fallback.

#### Rule D-03: Conflict Retention Protocol
- Biological assemblies in the PDB can contradict biophysical stability calculations from PDBe PISA (e.g., author defines a biological tetramer, but PISA reports $\Delta G_{\text{diss}} \le 0$ kcal/mol, indicating crystal lattice contacts).
- **Mandate**: The pipeline **must never** silently choose one assertion or discard the candidate.
- **Implementation**:
  - The record is flagged with `conflict_detected: true`.
  - Both assertions are preserved in the output:
    ```json
    "experimental_conflict": {
      "conflict_detected": true,
      "rcsb_annotated_assembly": "tetramer",
      "pisa_thermodynamic_state": "monomer_crystal_artifact",
      "dissociation_energy_kcal_mol": -1.4,
      "conflict_rationale": "PISA thermodynamic analysis indicates interface is non-specific crystal packing despite author biological unit annotation."
    }
    ```

#### Rule D-04: Multi-Assembly Candidate Ranking Protocol
- When multiple PDB entries or multiple biological assemblies within a single entry exist for the target:
  1. Filter out all assemblies in Coverage Tier 3 ($< 70\%$).
  2. Compute an Assembly Ranking Score ($S_{\text{assembly}}$):
     $$S_{\text{assembly}} = W_{\text{coverage}} + W_{\text{resolution}} + W_{\text{pisa}}$$
     - $W_{\text{coverage}}$: High Confidence ($\ge 90\%$) = 3.0; Qualifying ($70-89\%$) = 2.0.
     - $W_{\text{resolution}}$: Resolution $< 2.0\text{\AA}$ = 3.0; $2.0 - 3.0\text{\AA}$ = 2.0; $> 3.0\text{\AA}$ / NMR = 1.0.
     - $W_{\text{pisa}}$: PISA $\Delta G_{\text{diss}} > 0$ (stable) = 3.0; PISA $\Delta G_{\text{diss}} \le 0$ = 0.0.
  3. The highest-scoring candidate is designated `primary_assembly_candidate`.
  4. All other qualified candidates are preserved in `alternative_assembly_candidates` with their respective scores and coverage tiers.

---

### Stage 3: Homology Modeling & Interactome Partner Discovery
If no experimental PDB structures pass qualification ($\ge 70\%$ coverage and PISA validation):
1. **SWISS-MODEL Repository**:
   - Query SWISS-MODEL Repository REST API under **Fallback Invariant 1**.
   - If pre-calculated homology models exist, extract template oligomeric state and Quaternary Structure Model Quality Estimate (`qmqe`).
   - If `qmqe` $\ge 0.70$, classify as *Homology-Derived Hypothesis* (Tier 3).
2. **Interactome Partner Discovery (IntAct & BioGRID)**:
   - Query `bioservices.IntAct` and `bioservices.BioGrid` (with API key) for known physical binding partners.
   - Filter for `physical` interaction type (discard genetic synthetics).
   - Generates candidate partners for downstream heteromer modeling.

---

### Stage 4: Structural Context Boundary (D-05)
When experimental evidence is absent or inconclusive, single-chain structural prediction is consulted:
1. **AlphaFold DB Lookup**:
   - Query AlphaFold DB REST API under **Fallback Invariant 1**.
   - If available, download tertiary coordinates and mean pLDDT.
2. **ESMFold Fallback**:
   - If not in AlphaFold DB, submit sequence to ESM Metagenomic Atlas REST API under **Fallback Invariant 1** for rapid in-silico single-chain folding.
3. **Rule D-05 Enforced Invariant**:
   - Single-chain models contribute **structural context only**.
   - The pipeline is strictly prohibited from declaring an oligomeric state based on AlphaFold DB or ESMFold models alone.
   - The output must explicitly state: `quaternary_status: uncharacterized` with `structural_context_attached: true`.

---

### Stage 5: Predictive Multimer Proposal & Caller Opt-In (D-06)
1. **Rule D-06 Enforced Invariant**:
   - Deep learning multimer co-folding (AlphaFold-Multimer, ColabFold) is **never executed automatically**.
   - Automated unprompted execution across batches of uncharacterized proteins wastes significant GPU resources and risks hallucinated interfaces.
2. **Execution Prerequisite**:
   - The pipeline outputs a proposal: `multimer_hypothesis_eligible: true`.
   - Execution occurs only when the caller supplies:
     1. Explicit opt-in flag: `--enable-multimer-prediction`.
     2. Concrete hypothesis specification:
        - Self-association: Homodimer ($A_2$), Homotrimer ($A_3$), Homotetramer ($A_4$).
        - Partner association: Heterodimer ($AB$) using partner identified in Stage 3.
3. **Execution Architecture**:
   - Containerized ColabFold batch runner with MMseqs2 MSA acceleration.
   - Evaluated using model confidence: $0.8 \times \text{ipTM} + 0.2 \times \text{pTM}$.

---

### Stage 6: Provenance & Confidence Preservation Protocol (D-08)
- Every returned score and metric must be maintained in distinct, source-attributed data blocks.
- **Prohibited**: Creating a unified "quaternary confidence score" that mathematically combines experimental $\Delta G_{\text{diss}}$, homology `qmqe`, and AlphaFold `ipTM`.
- **Enforced Schema Segregation**:
  ```json
  "confidence_provenance": {
    "pdbe_pisa": {
      "dissociation_energy_kcal_mol": 12.4,
      "buried_surface_area_sq_angstrom": 1850.2
    },
    "swissmodel": {
      "qmqe": 0.82,
      "gmqe": 0.76
    },
    "alphafold_db": {
      "global_plddt": 88.4
    },
    "alphafold_multimer": {
      "iptm": 0.84,
      "ptm": 0.81,
      "model_confidence": 0.834
    }
  }
  ```

---

## 3. Requirement QUAT-02 & Locked Decision D-13 Disposition

### Formal Disposition Statement
In accordance with locked project decision **D-13** established during Phase 1 specification:

> **Decision D-13:**  
> *"The pre-existing reusable research prompt has already served its purpose in generating the comprehensive ecosystem survey. Do not spend Phase 1 effort creating, refining, reviewing, tracking, or locating it."*

### Reconciliation with Requirement QUAT-02
- **Requirement QUAT-02** ("Curate and benchmark biological web-servers with reusable prompt") is formally fulfilled by:
  1. The comprehensive provider benchmarks codified in `docs/ecosystem/01_experimental_homology_catalog.md` and `docs/ecosystem/02_predictive_multimer_catalog.md`.
  2. The machine-readable provider inventory in `docs/ecosystem/provider_inventory.json` (covering all 13 providers with complete implementation profiles per D-11).
  3. The evidence-collection route specified in this document (`03_evidence_collection_route.md`).
- No separate external prompt artifact is required, sought, or created. Any future server discovery will leverage the structured taxonomy and schema defined in `provider_inventory.json`.

---

## 4. Summary of Project Invariants (D-01 through D-13)

| ID | Title | Summary & Enforcement |
|:---|:---|:---|
| **D-01** | Experimental Candidate Qualification | Count only assembly-qualified and PISA-supported candidates as confirmed experimental evidence; unqualified hits remain provenance. |
| **D-02** | Target-Chain Coverage Tiers | $\ge 90\%$: High Confidence; $70-89\%$: Qualifying; $< 70\%$: Provenance-Only. |
| **D-03** | Conflict Retention | Explicitly record disagreements between PDB biological units and PISA thermodynamic calculations; never silently discard. |
| **D-04** | Multi-Assembly Candidate Ranking | Rank multiple candidates using Coverage, Resolution, and PISA stability; designate top candidate while retaining alternatives. |
| **D-05** | Monomer Context Boundary | AlphaFold DB provides structural context only; never asserts oligomeric state. |
| **D-06** | Caller Opt-In for Multimer Modeling | Predictive multimer co-folding is strictly opt-in and requires an explicit partner or self-association hypothesis. |
| **D-07** | Evidence-Tier Taxonomy | Classify evidence across 5 tiers: Curated Reference, Confirmed Experimental, Candidate Hypotheses, Homology-Derived, and Predictive Multimer. |
| **D-08** | Provenance & Confidence Preservation | Preserve source-specific metrics (pLDDT, ipTM, $\Delta G_{\text{diss}}$) separately; zero synthetic score aggregation. |
| **D-09** | Capability Catalog Rules | Benchmark is an implementation-ready capability catalog backed by research and official provider specs. |
| **D-10** | Provider Classification | Formally categorize providers as `pipeline-ready`, `authenticated`, or `web-only`. |
| **D-11** | Implementation Profile Contract | Every catalog entry must specify inputs, endpoint, auth, rate limit, wrapper, fields, limitations, and evidence tier. |
| **D-12** | Human-Readable Catalog Format | Clean, structured Markdown documentation with diagrams and tables. |
| **D-13** | Reusable Prompt Disposition | Reusable prompt fulfilled by ecosystem survey and inventory; no separate prompt tracking required in Phase 1. |
