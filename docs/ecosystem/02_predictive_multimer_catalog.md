# Predictive Multimer Servers, Docking Web-Tools & Monomer-Context Databases

**Status:** Completed  
**Phase:** 1 (Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt)  
**Artifact:** `docs/ecosystem/02_predictive_multimer_catalog.md`  
**Governing Standard:** `phase_1/guideline.md`  
**Relevant Invariants:** D-05, D-06, D-08, D-10, D-11, D-12  

---

## 1. Executive Summary & Monomer vs. Multimer Architectural Boundary

A foundational failure mode in automated quaternary prediction is the conflation of monomeric tertiary structure models with true multimeric quaternary assemblies. Many public structural repositories (such as the AlphaFold Protein Structure Database) provide single-chain predictions computed in isolation, which reflect monomeric tertiary folds regardless of whether the functional biological entity is a dimer, tetramer, or higher-order multimer.

To safeguard downstream pipelines against false oligomeric inferences, this catalog codifies three core architectural invariants:

1. **The Monomer Context Boundary (D-05)**: When experimental quaternary evidence is absent or inconclusive, single-chain structure prediction databases (e.g. AlphaFold DB, ESMFold) contribute **structural context only**. They must **never** by themselves assert oligomeric state, quaternary arrangement, or stoichiometry.
2. **Caller-Opt-in Multimer Hypothesis Prerequisite (D-06)**: Automated pipelines must not execute expensive multimeric co-folding runs unprompted. Multimer prediction tools (AlphaFold-Multimer, ColabFold) may be proposed to the user after database searches, but execution is strictly **caller-opt-in** and requires an explicit partner or self-association hypothesis (e.g., self-homodimer $A_2$, or partner heterodimer $AB$ identified via IntAct).
3. **Source-Specific Confidence & Provenance Preservation (D-08)**: All source-specific confidence fields (pLDDT, pTM, ipTM, docking energy) must be preserved separately with exact origin metadata. Confidence metrics must not be synthetically aggregated or averaged during early pipeline stages.

---

## 2. Monomer-Context Structural Databases (Task 01-02-T1)

### 2.1. AlphaFold Protein Structure Database (AlphaFold DB v4)

*High-accuracy single-chain AI structural predictions covering over 200 million UniProt proteins.*

- **Provider Identifier:** `alphafold_db`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Predictive Structural Context (`predictive_structural_context`)
- **Accepted Inputs:** UniProt Primary Accession (e.g., `P0A799`).
- **Primary Endpoint / Submission Mode:** `https://alphafold.ebi.ac.uk/api/prediction/{accession}`
- **BioServices Integration & Fallback:**
  - Direct REST client using `requests.Session` / `httpx.Client` citing **Fallback Invariant 1** (Specialized prediction and coordinate asset retrieval endpoint).
- **Authentication:** None (open public API).
- **Rate Limits & Polling:** EMBL-EBI standard limits (~20-30 requests/second). Static lookup; no asynchronous job polling required for pre-computed entries.
- **Returned Fields (D-11):**
  - `uniprotAccession`: Queried primary accession
  - `uniprotId`: UniProt entry identifier
  - `gene`: Associated gene symbol
  - `uniprotDescription`: Curated protein name
  - `taxId`: Organism NCBI Taxonomy ID
  - `latestVersion`: Model version (currently v4)
  - `pdbUrl`: Download URL for 3D atomic coordinates in PDB format
  - `cifUrl`: Download URL for 3D atomic coordinates in mmCIF format
  - `bcifUrl`: Download URL for BinaryCIF format
  - `paeDocUrl`: Predicted Aligned Error (PAE) JSON matrix URL
  - `paeImageUrl`: PAE 2D plot image URL
  - `globalMetricValue`: Global average pLDDT score (0 to 100).
- **Monomer Context Boundary Protocol (D-05):**
  - *Strict Rule*: AlphaFold DB provides monomeric coordinates only.
  - An AlphaFold DB model showing a compact globular fold must **never** be cited as evidence that the protein functions as a monomer.
  - The model serves solely as structural context (domain architecture, surface residues, flexible linkers) for downstream quaternary analysis or docking.
- **Provenance & Confidence Preservation (D-08):**
  - The per-residue pLDDT array (b-factor column in PDB) and `globalMetricValue` must be stored verbatim in the target profile under `structural_context.alphafold_db.global_plddt`.
  - Never convert pLDDT to a quaternary probability score.
- **Limitations:**
  - Does not model protein-protein interfaces, oligomeric complexes, ligands, nucleic acids, or post-translational modifications.
  - Intrinsically disordered regions (pLDDT < 50) may adopt structured interfaces only upon multimerization, which is invisible in isolated monomer models.

---

### 2.2. ESMFold / ESM Metagenomic Atlas (Meta AI)

*Ultra-fast single-chain structure prediction using large protein language models (ESM-2).*

- **Provider Identifier:** `esmfold`
- **Classification (D-10):** `pipeline-ready`
- **Evidence Tier (D-07):** Predictive Structural Context (`predictive_structural_context`)
- **Accepted Inputs:** Amino acid sequence string in FASTA format (up to ~400 residues for public API; up to 1000+ locally).
- **Primary Endpoint / Submission Mode:** `https://api.esmatlas.com/foldSequence/v1/pdb/` (HTTP POST with raw sequence string).
- **BioServices Integration & Fallback:**
  - Direct REST client citing **Fallback Invariant 1** (ESM Metagenomic Atlas REST endpoint).
- **Authentication:** None for public API; self-hosted GPU containers require local PyTorch/FairScale runtime.
- **Rate Limits & Polling:** Public API enforces concurrency limits (recommend <= 5 concurrent calls, rate-limited at ~60 requests/minute). Immediate synchronous response (inference takes ~1-3 seconds on NVIDIA A100).
- **Returned Fields (D-11):**
  - Atomic coordinates in PDB format (text stream).
  - Per-residue pLDDT scores embedded directly in the B-factor column.
  - Mean predicted pLDDT across all residues.
- **Architectural Boundary:**
  - Serves as the primary fast fallback when a sequence lacks a pre-computed AlphaFold DB entry (e.g., novel synthetic constructs, newly sequenced clinical isolates, or modified expression constructs).
  - Restricted strictly to single-chain structural context; does not resolve quaternary assemblies.
- **Limitations:**
  - Sequence length restricted on public web endpoints.
  - Lower structural accuracy on unaligned orphan sequences compared to MSA-based AlphaFold2 for complex folds.

---

## 3. Predictive Multimer Servers & Docking Tools (Task 01-02-T2)

### 3.1. AlphaFold-Multimer & ColabFold

*State-of-the-art end-to-end co-folding of multimeric protein complexes trained on the Protein Data Bank.*

- **Provider Identifier:** `alphafold_multimer`
- **Classification (D-10):** `pipeline-ready` (Batch/Local container runner); `web-only` (Google Colab / public web notebooks)
- **Evidence Tier (D-07):** Predictive Multimer Hypothesis (`predictive_multimer_hypothesis`)
- **Accepted Inputs:**
  - Multiple FASTA sequences representing unique chains (e.g., Chain A and Chain B for heteromers).
  - Stoichiometric multiplier notation (e.g. `ChainA:ChainA` for $A_2$ homodimers; `ChainA:ChainB` for $AB$ heterodimers; `ChainA:2:ChainB:2` for $A_2B_2$ heterotetramers).
- **Submission Mode / Implementation Architecture:**
  - Local GPU Pipeline: `colabfold_batch` CLI runner executing MMseqs2 fast MSA search against UniRef30/ColabFoldDB, followed by AlphaFold-Multimer v3 inference.
  - BioServices Integration: Direct command-line / container invocation citing **Fallback Invariant 1** (No BioServices wrapper exists for local deep-learning inference engines).
- **Authentication:** None for local container / self-hosted GPU runner.
- **Rate Limits & Polling:** Computationally bounded by local GPU hardware availability. Typical run duration: 3 to 20 minutes per complex depending on total combined amino acid length and ensemble iterations.
- **Returned Fields (D-11):**
  - `predicted_complex_pdb`: Multi-chain 3D atomic coordinates (Chains A, B, C...)
  - `plddt`: Per-residue local confidence array
  - `ptm`: Predicted TM-score (overall complex topological accuracy)
  - `iptm`: Interface predicted TM-score (reliability of inter-chain interaction interface)
  - `model_confidence`: Weighted composite ranking score ($0.8 \times \text{ipTM} + 0.2 \times \text{pTM}$). Values $\ge 0.75$ denote high-confidence predicted complexes; $0.50 - 0.74$ represent plausible hypotheses; $< 0.50$ indicate unreliable interface predictions.
  - `pae_matrix`: Pairwise inter-residue predicted aligned error matrix.
- **Caller-Opt-in and Hypothesis Prerequisite Protocol (D-06):**
  - *Hard Architectural Constraint*: AlphaFold-Multimer must **never** be triggered automatically or blindly across uncharacterized proteome batches.
  - Execution requires:
    1. **Explicit Caller Opt-in**: The user or calling script must explicitly pass an execution flag (`--enable-multimer-prediction`).
    2. **Hypothesis Formulation**: The caller must specify an explicit stoichiometry hypothesis:
       - *Self-Association Hypothesis*: Testing homodimer ($A_2$), homotrimer ($A_3$), or homotetramer ($A_4$).
       - *Partner Hypothesis*: Testing heterodimer ($AB$) with a candidate partner identified through IntAct, BioGRID, or co-expression data.
- **Confidence Preservation (D-08):**
  - `iptm`, `ptm`, and composite `model_confidence` are recorded with explicit labels in the prediction block. They are never merged or averaged with experimental PISA $\Delta G_{\text{diss}}$ values.
- **Limitations:**
  - High computational resource footprint (requires high-memory CUDA GPU, >= 16GB VRAM).
  - Accuracy decreases for very large complexes (> 2,000 total residues) or transient low-affinity assemblies.

---

### 3.2. GalaxyHeteromer (Seok Lab)

*Template-based and ab-initio modeling server for protein-protein heteromer complexes.*

- **Provider Identifier:** `galaxy_heteromer`
- **Classification (D-10):** `web-only`
- **Evidence Tier (D-07):** Predictive Multimer Hypothesis (`predictive_multimer_hypothesis`)
- **Accepted Inputs:** Two or more protein sequences in FASTA format.
- **Primary Endpoint / Submission Mode:** `http://galaxy.seoklab.org/cgi-bin/submit.cgi?type=HETEROMER` (Web form submission via POST).
- **BioServices Integration & Fallback:**
  - Citation: **Fallback Invariant 1** (Web-only server with no programmatic API).
- **Authentication:** Optional web account; anonymous submissions allowed with web tracking URL.
- **Rate Limits & Polling:** Web queue-based scheduling. Processing times range from 30 minutes to multiple hours depending on server queue depth.
- **Returned Fields (D-11):**
  - Downloadable multi-chain PDB models (Top 5 models).
  - Template identification (PDB template ID and alignment coverage).
  - Cluster energy scores.
- **Limitations & Pipeline Recommendation:**
  - **Classified as `web-only`**: Lack of a stable, documented REST API and variable public queue latencies make GalaxyHeteromer unsuitable for headless automated batch pipelines.
  - Recommended for manual validation and interactive user exploration only.

---

### 3.3. ClusPro 2.0 (Boston University / Vajda Lab)

*Premier rigid-body macromolecular docking server utilizing Fast Fourier Transform (FFT) correlation.*

- **Provider Identifier:** `cluspro`
- **Classification (D-10):** `authenticated` / `web-only`
- **Evidence Tier (D-07):** Docking Assembly Hypothesis (`docking_assembly_hypothesis`)
- **Accepted Inputs:** Two 3D coordinate structures in PDB format: Receptor PDB and Ligand PDB (can be derived from AlphaFold DB monomer structural context).
- **Primary Endpoint / Submission Mode:** `https://cluspro.bu.edu/api/` (API queue submission and status endpoints).
- **BioServices Integration & Fallback:**
  - Citation: **Fallback Invariant 1** (ClusPro REST API queue).
- **Authentication:** Required academic/institutional user credentials (`username` and `api_token`).
- **Rate Limits & Polling:** Polling required on job status URL (`/api/queue/status/{job_id}`); queue times vary from 5 minutes to 1 hour based on cluster load.
- **Returned Fields (D-11):**
  - Docked complex coordinates in PDB format (Top 10 cluster centers across 4 scoring schemes: Balanced, Electrostatic-favored, Hydrophobic-favored, Van der Waals + Electrostatics).
  - Cluster size (number of docked poses in the dominant cluster; larger clusters correlate with physiological relevance).
  - Lowest energy score per cluster (arbitrary FFT correlation energy units).
- **Architectural Role in Quaternary Pipeline:**
  - Acts as a bridge between monomeric tertiary models (from AlphaFold DB) and potential quaternary assemblies when deep-learning multimer co-folding is unavailable.
  - Tests whether two folded monomers exhibit complementary surface shape and charge to form a stable binary interface.
- **Limitations:**
  - Assumes rigid-body docking: cannot accommodate major conformational changes or flexible loop rearrangements upon binding.
  - Requires user account registration and API authentication.

---

## 4. Synthesis of Predictive Invariants & Decision Matrix

| Invariant / Decision | Rule Statement | Concrete Pipeline Implementation Guard |
|:---|:---|:---|
| **D-05** | AlphaFold DB is structural context only | If only AlphaFold DB data is found for a target, the pipeline marks `quaternary_status: uncharacterized` and attaches the PDB URL under `structural_context.monomer_model_url`. Oligomeric state is **never** assigned. |
| **D-06** | Caller-opt-in for predictive multimer modeling | Multimer co-folding (AlphaFold-Multimer/ColabFold) is never run by default. The pipeline returns a proposal (`multimer_hypothesis_eligible: true`) requiring the user to explicitly supply `--opt-in-multimer` and a hypothesis (e.g. `--stoichiometry A2`). |
| **D-08** | Preservation of source-specific confidence fields | All scores are quarantined under provider-specific keys: `alphafold_db.mean_plddt`, `alphafold_multimer.iptm`, `cluspro.cluster_size`. Never merged or averaged into a single synthetic score. |
| **D-10** | Provider classification | Clear separation into `pipeline-ready` (automated integration), `authenticated` (credentials required), and `web-only` (manual/fallback). |
| **D-11** | Full implementation readiness profile | Inputs, endpoints, auth, limits, fields, and limitations fully defined for every service. |
| **D-12** | Human-readable catalog format | Clear Markdown documentation with structured tables and explicit protocols. |
