# Phase 1: Quaternary Ecosystem Survey, Server Benchmarking & Reusable Research Prompt - Context

**Gathered:** 2026-10-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce a research-backed catalog of quaternary-structure resources, a lightweight structured provider inventory, and a proposed evidence-collection route for the final project. The route must explain how data can be gathered and reported for later UI use; it does **not** implement the runtime pipeline, aggregate evidence, orchestrate prediction jobs, or define the final frontend JSON contract.

The reusable research prompt is already complete and outside this phase's new work. Do not create, review, track, or plan further work for it.

</domain>

<decisions>
## Implementation Decisions

### Experimental evidence route

- **D-01:** Preserve every RCSB PDB sequence-search hit as provenance, but count only assembly-qualified and PISA-supported candidates as confirmed experimental complex evidence. Unqualified hits do not prevent the prediction fallback. — **Reversibility:** costly — changing this later would alter evidence-status semantics across the catalog, pipeline, and UI handoff.
- **D-02:** Use tiered target-chain coverage: at least 70% can qualify, 90%+ is high confidence, and lower coverage remains provenance-only.
- **D-03:** If an assembly-qualified RCSB candidate and PISA disagree, retain an explicit experimental-evidence conflict rather than silently choosing a winner. It is not a confirmed complex; prediction can be collected as corroborating evidence.
- **D-04:** When multiple PDB assemblies suggest different oligomeric states, rank candidates by coverage, experimental quality, and PISA support; report the top candidate while retaining alternatives and provenance.

### Proposed prediction fallback

- **D-05:** When experimental evidence is absent or inconclusive, AlphaFold DB contributes structural context only. It must not by itself assert oligomeric state or stoichiometry.
- **D-06:** A multimer-capable prediction source may be proposed after the AlphaFold DB lookup, but execution is caller-opt-in and requires a partner or self-association hypothesis.
- **D-07:** UniProtKB plus curated interaction/complex records may propose candidate partners. Those hints remain distinct from confirmed complex evidence.
- **D-08:** Preserve returned source-specific confidence fields and provenance separately. Phase 1 does not define aggregation, conflict-resolution logic, runtime job orchestration, or the final UI JSON schema.

### Catalog and reporting deliverables

- **D-09:** Treat the Phase 1 benchmark as a capability catalog backed by completed research, official provider information, and existing UniProt measurements. Run live tests only when the provider, target, and test are explicitly specified.
- **D-10:** Include every named database, API, web server, and predictor, clearly classified as `pipeline-ready`, `authenticated`, `web-only`, `deprecated`, or `not suitable`.
- **D-11:** Every provider record must be implementation-ready: accepted inputs; endpoint or submission mode; authentication, rate limits, and polling; returned fields; limitations; evidence tier; and provenance.
- **D-12:** Publish a readable Markdown catalog plus a lightweight structured provider inventory for downstream work. This inventory is not the final frontend JSON contract.

### Scope boundary

- **D-13:** The pre-existing reusable research prompt has already served its purpose. Do not spend Phase 1 effort creating, refining, reviewing, tracking, or locating it.

### the agent's Discretion

- Select the inventory's concrete serialization and field names based on the existing project patterns and downstream Phase 2 reuse, without treating it as the final UI JSON schema.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract and scope

- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, and planned survey slices (`01-01` through `01-03`).
- `.planning/REQUIREMENTS.md` — Phase 1 requirements `QUAT-01` and `QUAT-02`, plus later-phase boundaries.
- `.planning/PROJECT.md` — quaternary-only scope, clean module/notebook architecture, and frontend handoff intent.

### Integration policy and known failure modes

- `.planning/phases/01-quaternary-ecosystem-survey/guideline.md` — BioServices-first mandate, documented direct-REST fallback criteria, and required provider-evaluation fields.
- `problems.md` — BioServices refactor risk and the UniProt HTTP 303 redirect requirement for asynchronous polling.
- `docs/uniprot_server_overview.md` — existing UniProt access-method benchmark, rate-limit/async guidance, and when to use direct streaming versus a wrapper.

### Reusable implementation evidence

- `UniProtKB.ipynb` — existing retry/session, streaming-query, wrapper, and benchmark patterns. Its historical async mapping logic must not override the HTTP 303 rule in `problems.md`.
- `UniProt.ipynb` — existing BioServices examples and UniProt-to-PDB mapping reference.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `UniProtKB.ipynb`: retrying `requests.Session`, stream-query-to-DataFrame, and timing/result-count benchmark patterns that can inform provider records and later adapters.
- `UniProt.ipynb`: BioServices `UniProt` lookup and PDB mapping examples.
- `docs/uniprot_server_overview.md`: an existing comparison table and observed performance data that should be reused rather than re-benchmarked by default.

### Established Patterns

- BioServices is the primary integration path when it supports the needed biological service; direct REST is permitted only for an unsupported specialized endpoint, proven high-throughput need, or a non-standard asynchronous protocol, with the rationale documented.
- UniProt async polling must explicitly handle the terminal HTTP 303 redirect; do not treat a redirected results payload as a normal status response.
- No quaternary-specific implementation currently exists, so this phase establishes conventions and data requirements rather than extending an existing engine.

### Integration Points

- The Phase 1 provider inventory supplies Phase 2 with source selection, client constraints, and normalized-field requirements.
- The proposed evidence route supplies Phase 4 with provenance and evidence-status concepts, while leaving the published UI schema to that phase.

</code_context>

<specifics>
## Specific Ideas

The user wants the proposed final-project route to follow this shape:

```text
Sequence / UniProt ID
        ↓
   UniProtKB
        ↓
RCSB PDB sequence search
        ↓
Experimental complex found?
   ├─ Yes → PISA
   └─ No or inconclusive → AlphaFold DB structural context
                                  ↓
               optional, caller-opt-in multimer prediction
               (only with a partner/self-association hypothesis)
                                  ↓
                 provenance-rich quaternary evidence
                                  ↓
                    later-phase UI JSON handoff
```

Phase 1 should propose and document this route, gather/report provider capabilities and returned data fields, and leave aggregation and implementation to later phases.

</specifics>

<deferred>
## Deferred Ideas

- Evidence aggregation, confidence synthesis, and automatic conflict resolution — later pipeline and data-contract work.
- Runtime client implementation, async job orchestration, and multimer-prediction execution — Phase 2.
- Final frontend-ready JSON schema and UI handoff contract — Phase 4.
- Live provider tests — only perform if the user later specifies the provider, target, and exact test.

</deferred>

---

*Phase: 01-quaternary-ecosystem-survey*
*Context gathered: 2026-10-03*
