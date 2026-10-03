---
phase: "01"
plan: "01-03"
title: "Machine-Readable Provider Inventory & Evidence-Collection Route"
status: complete
completed_at: "2026-10-03"
requirements_covered:
  - QUAT-01
  - QUAT-02
decisions_enforced:
  - D-01
  - D-02
  - D-03
  - D-04
  - D-05
  - D-06
  - D-07
  - D-08
  - D-09
  - D-10
  - D-11
  - D-12
  - D-13
files_created:
  - docs/ecosystem/provider_inventory.json
  - docs/ecosystem/03_evidence_collection_route.md
---

# Plan 01-03 Summary: Machine-Readable Provider Inventory & Evidence-Collection Route

## 1. Executive Summary

Plan `01-03` has been executed to completion. We synthesized the survey findings into a machine-readable JSON inventory (`docs/ecosystem/provider_inventory.json`) covering all 13 evaluated biological web services, and authored the comprehensive evidence-collection and conflict resolution route specification (`docs/ecosystem/03_evidence_collection_route.md`).

This plan successfully establishes the architectural and operational bridge between Phase 1 ecosystem benchmarking and Phase 2 core quaternary client and adapter development.

## 2. Key Accomplishments & Deliverables

1. **Task 01-03-T1: Structured Provider Inventory (`provider_inventory.json`)**
   - Encoded complete, validated JSON specifications for all 13 providers:
     - `uniprotkb_subunit` (`pipeline-ready`)
     - `rcsb_pdb_search` (`pipeline-ready`)
     - `pdbe_pisa` (`pipeline-ready`)
     - `complex_portal` (`pipeline-ready`)
     - `intact` (`pipeline-ready`)
     - `biogrid` (`authenticated`)
     - `swissmodel_repository` (`pipeline-ready`)
     - `swissmodel_automodel` (`authenticated`)
     - `alphafold_db` (`pipeline-ready`)
     - `alphafold_multimer` (`pipeline-ready`)
     - `galaxy_heteromer` (`web-only`)
     - `cluspro` (`authenticated` / `web-only`)
     - `esmatlas` (`pipeline-ready`)
   - Each entry defines inputs, endpoint/submission mode, authentication, rate limits, BioServices wrapper status, returned fields, biological/computational limitations, and evidence tiers.

2. **Task 01-03-T2: Evidence-Collection Route & Conflict Protocol (`03_evidence_collection_route.md`)**
   - Codified the end-to-end routing flow from sequence input to normalized JSON export.
   - Enforced **D-01** (Experimental Candidate Qualification) and **D-02** (Target-chain coverage tiers: $\ge 90\%$ high confidence, $70-89\%$ qualifying, $< 70\%$ provenance-only).
   - Formulated **D-03** (Conflict Retention Protocol): explicitly logging PDB assembly vs PISA thermodynamic stability disagreements with metadata flags.
   - Formulated **D-04** (Multi-Assembly Candidate Ranking): deterministic scoring via Coverage, Experimental Resolution, and $\Delta G_{\text{diss}}$.
   - Enforced **D-05** (Monomer Context Boundary) and **D-06** (Caller Opt-In with explicit multimer hypotheses).
   - Enforced **D-08** (Strict quarantine and preservation of source-specific confidence metrics).
   - Formally documented the disposition of **QUAT-02** adhering to locked decision **D-13**.

## 3. Verification

- JSON schema validation: Verified using PowerShell and Python `json.load`, confirming all 13 providers are loaded without error.
- Evidence routing documentation: Verified pattern matching for all critical invariants (D-01 through D-13), yielding 31 verified matches.
