# Bioinformatics Server: Quaternary Protein Structure & Complex Annotation

## What This Is

A specialized bioinformatics exploration and pipeline module focusing on quaternary protein structure characterization (oligomeric states, subunit stoichiometry, multimer complexes, and interface interactions) for unknown, unlabelled, or newly discovered protein sequences. It forms the quaternary research pillar of a larger multi-tier protein prediction system (Primary, Secondary, Tertiary, Quaternary) and provides an abstracted notebook, reusable Python pipeline, and clean JSON data contract for frontend UI consumption.

## Core Value

Accurately identify, benchmark, and predict the quaternary arrangement, oligomeric state, and assembly interfaces of unknown or uncharacterized protein sequences, exporting structured, frontend-ready biological insights.

## Requirements

### Validated

- ✓ [UniProtKB Programmatic Ingestion & Benchmarking] — existing in UniProtKB.ipynb and docs/uniprot_server_overview.md
- ✓ [Primary, Secondary & Tertiary Baseline Explorations] — existing in Mapping_Protein_Function_from_Primary_Structure.ipynb, Foldseek_Swiss_model.ipynb, Structure_Prediction.ipynb, InterPro_Cath.ipynb

### Active

- [ ] [Phase 1: Quaternary Ecosystem Survey & Research Prompt] — Explore available quaternary servers/APIs (PDB PISA, SWISS-MODEL oligomers, AlphaFold-Multimer/ColabFold, GalaxyHeteromer, ClusPro, UniProt SUBUNIT) and generate a reusable prompt for ongoing server discovery
- [ ] [Phase 2: Quaternary Prediction & Ingestion Engine] — Core Python module (`quaternary_pipeline.py`) abstracting queries, polling, and multimer data extraction
- [ ] [Phase 3: Interactive Abstracted Notebook] — Clean Jupyter notebook demonstrating the quaternary analysis on target sequences with minimal boilerplate
- [ ] [Phase 4: Standardized UI JSON Data Contract] — Define and export `quaternary_structure_output.json` with oligomeric state, stoichiometry, confidence, interface contacts, and assembly metadata for UI developers
- [ ] [Phase 5: Benchmark Validation] — Validate against *Haemophilus influenzae* uncharacterized proteome targets and synthetic/novel primary sequences

### Out of Scope

- [Primary, Secondary, Tertiary model development] — Handled by other team members in parallel
- [Frontend UI application implementation] — A dedicated team member is building the UI; our deliverable is the structured JSON contract and documented outputs
- [End-to-end heavy local multimer training] — Leverage cloud APIs, external bioinformatics web servers, and lightweight inference/retrieval

## Context

- Part of a BTP/Bioinformatics Server project predicting comprehensive protein function from primary sequence.
- Project division: Primary, Secondary, Tertiary, and Quaternary structure tiers.
- High-level Python abstraction is desired: the Jupyter notebook should import heavy lifting from a clean Python script (`quaternary_pipeline.py`) so biologists and reviewers see clean, high-level code.
- Known pitfalls identified in `problems.md` (e.g., UniProt async HTTP 303 redirect handling, BioServices vs direct REST trade-offs) must inform all external API integration.

## Constraints

- **Scope Focus**: Quaternary structure analysis only; do not duplicate primary/secondary/tertiary tasks.
- **Abstraction**: Internal API querying/parsing logic abstracted into a reusable Python module; notebook remains lean.
- **UI Handover**: Deliverable must include a standard JSON export schema for seamless UI consumption.
- **Async Robustness**: Adhere to redirect and rate-limit lessons learned in prior UniProt pipelines.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus strictly on Quaternary Structure | Other teammates are handling Primary, Secondary, and Tertiary workflows | — Pending |
| Abstract pipeline into Python module (`quaternary_pipeline.py`) | Keeps Jupyter notebook clean, readable, and reusable by server backend | — Pending |
| Standardized JSON UI data contract | Enables frontend team member to build UI independently of bioinformatics backend | — Pending |
| Benchmarking on *H. influenzae* and novel unannotated sequences | Tests both real-world uncharacterized pathogen sequences and synthetic edge cases | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-03 after initialization*
