---
phase: "01"
plan: "01-01"
title: "Experimental and Homology Quaternary Databases Catalog"
status: complete
completed_at: "2026-10-03"
requirements_covered:
  - QUAT-01
decisions_enforced:
  - D-01
  - D-02
  - D-03
  - D-04
  - D-07
  - D-10
  - D-11
  - D-12
files_created:
  - docs/ecosystem/01_experimental_homology_catalog.md
---

# Plan 01-01 Summary: Experimental and Homology Quaternary Databases Catalog

## 1. Executive Summary

Plan `01-01` has been executed to completion. We constructed `docs/ecosystem/01_experimental_homology_catalog.md`, delivering an authoritative, implementation-ready benchmark catalog of experimental quaternary structure repositories and homology/interaction databases.

The catalog strictly adheres to the BioServices-First Integration Mandate (`phase_1/guideline.md`), standardizing on `bioservices.UniProt`, `bioservices.PDB`, `bioservices.IntAct`, and `bioservices.BioGrid` while explicitly documenting and citing the three approved Fallback Invariants for unsupported specialized REST endpoints.

## 2. Key Accomplishments & Deliverables

1. **Task 01-01-T1: Experimental Quaternary Databases**
   - **UniProtKB Subunit & Structural Annotations**: Mapped to `bioservices.UniProt` (`search`, `retrieve`), columns (`cc_subunit`, `xref_pdb`, `xref_complexportal`), with streaming API cited under Fallback Invariant 2.
   - **RCSB PDB Search API & Core Entry Data**: Mapped to `bioservices.PDB` (`getFile`, `describePDB`) with custom JSON search DSL queries cited under Fallback Invariant 1.
   - **PDBe PISA**: Documented REST interface thermodynamics (`macromolecular_size`, `composition`, $\Delta G_{\text{diss}}$, ASA, BSA) citing Fallback Invariant 1.

2. **Task 01-01-T2: Homology & Curated Interaction Resources**
   - **SWISS-MODEL Repository & Automodel API**: Detailed Repository API (Fallback Invariant 1) and ticket-based async Automodel API (Fallback Invariant 3).
   - **Complex Portal (EBI)**: Mapped to UniProt cross-references and direct EBI Complex Portal REST (Fallback Invariant 1).
   - **IntAct**: Standardized on `bioservices.IntAct`.
   - **BioGRID**: Standardized on `bioservices.BioGrid` with API key requirement.

3. **Invariants & Decision Rules Formulated**
   - **D-01 (Candidate Qualification)**: Assembly-qualified & PISA-verified structures are designated *Confirmed Experimental Complex Evidence*; raw or unverified hits remain *Candidate Experimental Provenance*.
   - **D-02 (Coverage Tiers)**: High Confidence ($\ge 90\%$), Qualifying ($70-89\%$), Provenance-Only ($< 70\%$).
   - **D-03 (Conflict Retention)**: PDB biological assembly vs PISA stability conflicts are explicitly preserved with metadata flags, never dropped.
   - **D-04 (Multi-Assembly Ranking)**: Assemblies are ranked by coverage, experimental resolution, and $\Delta G_{\text{diss}}$ while retaining alternative candidates.
   - **D-07, D-10, D-11, D-12**: Explicit taxonomy, pipeline readiness classification, implementation profiles, and human-readable documentation format.

## 3. Verification

- Automated path test: `Test-Path 'docs/ecosystem/01_experimental_homology_catalog.md'` returned `True`.
- Automated content verification: Pattern match for SWISS-MODEL, Complex Portal, IntAct, and BioGRID yielded 25 matches across all required sections.
