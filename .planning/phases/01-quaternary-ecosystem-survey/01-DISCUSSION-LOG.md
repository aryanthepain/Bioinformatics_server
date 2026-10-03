# Phase 1: Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-10-03
**Phase:** 01-quaternary-ecosystem-survey
**Areas discussed:** Experimental-complex gate, Prediction fallback meaning, Phase 1 benchmark and catalog depth, Research and prompt handoff

---

## Experimental-complex gate

| Decision | Selected |
|---|---|
| Count every sequence-matching PDB entry as experimental evidence | |
| Require a single assembly-qualified hit | |
| Preserve all hits but count only assembly-qualified/PISA-supported evidence | ✓ |
| Accept any chain coverage | |
| Require 90%+ coverage for all candidates | |
| Use 70%+ qualifying and 90%+ high-confidence coverage tiers | ✓ |
| Let RCSB win when it conflicts with PISA | |
| Let PISA win when it conflicts with RCSB | |
| Preserve an explicit conflict state | ✓ |
| Pick one assembly and discard alternatives | |
| Collapse all assemblies to a consensus | |
| Rank candidates and retain alternatives/provenance | ✓ |

**User's choice:** Tiered evidence, tiered coverage, explicit conflicts, and ranked alternatives.
**Notes:** Experimental evidence is a proposed data-collection/reporting path, not a request to implement aggregation in this phase.

---

## Prediction fallback meaning

| Decision | Selected |
|---|---|
| Treat AlphaFold DB as a definitive quaternary result | |
| Treat AlphaFold DB as structural context only | ✓ |
| Automatically escalate to a multimer-capable predictor | ✓ |
| Escalate for every target without experimental confirmation | |
| Escalate only with a partner/self-association hypothesis | ✓ |
| Require caller opt-in before escalation | ✓ |
| Use UniProtKB only for candidate partners | |
| Use UniProtKB plus curated interaction/complex records | ✓ |
| Require caller-provided partners only | |
| Merge all evidence into one verdict | |
| Preserve source-specific tiers and returned confidence fields | ✓ |
| Let prediction replace conflicting experimental evidence | |

**User's choice:** AlphaFold DB supplies context only; an optional, partner-gated and caller-opt-in multimer prediction can follow. Preserve source provenance without aggregating it in Phase 1.
**Notes:** The current work is a proposed data-gathering path for the final project. Aggregation, runtime orchestration, and final UI schema work are deferred.

---

## Phase 1 benchmark and catalog depth

| Decision | Selected |
|---|---|
| Capability catalog plus completed research and existing measurements | ✓ |
| Live tests of public/no-auth services by default | |
| Live tests of every runnable service by default | |
| Catalog all named resources and classify them | ✓ |
| Catalog only programmable services | |
| Catalog only intended final-pipeline candidates | |
| Use a high-level summary per provider | |
| Use a data-focused profile only | |
| Use an implementation-ready provider profile | ✓ |
| Publish Markdown only | |
| Publish Markdown plus structured provider inventory | ✓ |
| Publish structured inventory only | |

**User's choice:** Use existing research by default; only run a live test when its provider, target, and test are explicitly specified. Include all named resources, use implementation-ready records, and publish Markdown plus a lightweight structured inventory.
**Notes:** The provider inventory supports later pipeline and UI work but is not the final UI JSON contract.

---

## Research and prompt handoff

| Decision | Selected |
|---|---|
| Create or refine a reusable research prompt | |
| Locate/review/track the pre-existing prompt | |
| Treat the prompt as already completed and out of new work | ✓ |

**User's choice:** Do not bother with the prompt; it has already done its job.
**Notes:** No prompt artifact or path is required for this session.

---

## the agent's Discretion

- Choose the lightweight provider-inventory serialization and field names based on Phase 2 reuse, without creating the final UI schema.

## Deferred Ideas

- Aggregation, confidence synthesis, conflict resolution, runtime orchestration, and final UI JSON are later-phase work.
- Live tests require a separately specified provider, target, and test.
