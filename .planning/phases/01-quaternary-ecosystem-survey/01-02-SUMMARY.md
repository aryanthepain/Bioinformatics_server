---
phase: "01"
plan: "01-02"
title: "Predictive Multimer Servers, Docking Web-Tools & Monomer-Context Databases"
status: complete
completed_at: "2026-10-03"
requirements_covered:
  - QUAT-01
decisions_enforced:
  - D-05
  - D-06
  - D-08
  - D-10
  - D-11
  - D-12
files_created:
  - docs/ecosystem/02_predictive_multimer_catalog.md
---

# Plan 01-02 Summary: Predictive Multimer Servers & Monomer-Context Databases

## 1. Executive Summary

Plan `01-02` has been executed to completion. We authored `docs/ecosystem/02_predictive_multimer_catalog.md`, delivering an authoritative benchmark catalog of single-chain structural context databases (AlphaFold DB, ESMFold) and predictive multimer modeling and docking servers (AlphaFold-Multimer, ColabFold, GalaxyHeteromer, ClusPro).

Crucially, this artifact codifies the architectural distinction between monomeric tertiary fold context and true multimeric quaternary assemblies, establishing strict pipeline gates for predictive execution.

## 2. Key Accomplishments & Deliverables

1. **Task 01-02-T1: Monomer-Context Databases & Boundaries**
   - **AlphaFold DB v4**: Detailed REST API, coordinate retrieval endpoints (PDB, mmCIF, BinaryCIF), PAE matrices, and per-residue pLDDT scores.
   - **ESMFold / ESM Metagenomic Atlas**: Detailed rapid in-silico single-chain folding API for uncharacterized or novel sequences.
   - **Monomer Context Invariant (D-05)**: Codified the hard constraint that AlphaFold DB models contribute single-chain structural context *only* and must never by themselves assert oligomeric state.
   - **Provenance & Confidence Preservation (D-08)**: Codified the requirement that raw pLDDT scores and model URLs are preserved under provider-specific keys without synthetic aggregation.

2. **Task 01-02-T2: Predictive Multimer Servers & Docking Tools**
   - **AlphaFold-Multimer & ColabFold**: Specified local/batch container deployment with MMseqs2 fast MSA searching, returning multi-chain coordinates, pTM, ipTM, and model confidence ($0.8 \times \text{ipTM} + 0.2 \times \text{pTM}$).
   - **Caller-Opt-In & Hypothesis Prerequisite (D-06)**: Codified that multimer co-folding runs are never triggered automatically; execution requires caller opt-in and an explicit partner or self-association hypothesis.
   - **GalaxyHeteromer**: Cataloged as `web-only` (lacks stable public REST API; manual queue polling required).
   - **ClusPro 2.0**: Cataloged as `authenticated` / `web-only` rigid-body docking server for evaluating quaternary interfaces using tertiary monomer coordinates.

3. **Classification & Readiness Profiles (D-10, D-11, D-12)**
   - Every server profile includes accepted inputs, submission mode, authentication, rate limits, returned fields, biological/computational limitations, and evidence tiers.

## 3. Verification

- Automated path test: `Test-Path 'docs/ecosystem/02_predictive_multimer_catalog.md'` returned `True`.
- Automated content verification: Pattern match for AlphaFold-Multimer, ColabFold, GalaxyHeteromer, and ClusPro yielded 12 matches across all sections.
