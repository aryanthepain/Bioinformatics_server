# Phase 4: Standardized UI JSON Data Contract & Benchmark Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-05
**Phase:** 4-standardized-ui-json-data-contract-benchmark-validation
**Areas discussed:** JSON Schema Export & Contract Validation, UI Examples Benchmarking, Synthetic & Novel Sequence Validation, Frontend UI Developer Integration Guide

---

## JSON Schema Export & Contract Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic model_json_schema() | Generate standard JSON Schema (Draft 2020-12) via Pydantic model_json_schema() into schema/quaternary_structure_output.schema.json | ✓ |
| Manual handcrafting | Maintain a hand-authored JSON schema file independently from Pydantic models | |
| You decide | Follow backend-driven automated generation | |

**User's choice:** Generate standard JSON Schema (Draft 2020-12) via Pydantic model_json_schema() into schema/quaternary_structure_output.schema.json (Guarantees 100% sync with Python backend engine)
**Notes:** Ensures schema is generated from source models with zero manual drift.

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-archetype fixture pack | Export 4 representative payloads under schema/fixtures/ plus a canonical quaternary_structure_output.json at root | ✓ |
| Single root JSON only | Single root quaternary_structure_output.json only | |
| You decide | Open to agent discretion | |

**User's choice:** Multi-archetype fixture pack, with user note: "1 but also the ui might need to run on some other thing as well"
**Notes:** User emphasized that while fixtures provide canonical reference examples, the contract and schema must be generic and flexible enough for arbitrary input sequences and accessions.

| Option | Description | Selected |
|--------|-------------|----------|
| Automated jsonschema test gate | Automated JSON Schema test suite (tests/test_ui_contract.py) using jsonschema validator against exported schema for all archetypes and dynamic targets | ✓ |
| Pydantic-only unit tests | Pydantic-only Python validation in backend tests without external jsonschema validator | |
| You decide | Agent discretion | |

**User's choice:** Automated JSON Schema test suite (tests/test_ui_contract.py) using jsonschema validator against the exported schema for all archetypes and dynamic targets (Ensures schema validity for any arbitrary protein)
**Notes:** Guarantees strict JSON schema compliance at the serialized JSON layer.

| Option | Description | Selected |
|--------|-------------|----------|
| Dual export exposure | Dedicated CLI script (scripts/export_ui_contract.py) for CI/batch regeneration + interactive export cell in Quaternary_Structure.ipynb | ✓ |
| CLI script only | scripts/export_ui_contract.py only | |
| Notebook export cell only | Interactive cell only | |

**User's choice:** Dual exposure: Dedicated CLI script (scripts/export_ui_contract.py) for CI/batch regeneration + interactive export cell in Quaternary_Structure.ipynb allowing one-click export for any analyzed target
**Notes:** Facilitates both automated CI artifact builds and interactive exploratory exports.

---

## Haemophilus influenzae / UI Examples Benchmarking

| Option | Description | Selected |
|--------|-------------|----------|
| UP000000579 cohort | Multi-target cohort (3-5 targets) from UP000000579 | |
| Single canonical target | Benchmark P44101 deeply without extra targets | |
| UI branch default examples | Inspect UI branch and benchmark its default example targets | ✓ |

**User's choice:** "look into the ui branch. tey have used some default examples, try to use those examples only and get the outputs for those"
**Notes:** Pivotal user directive aligning quaternary benchmark work directly with the 5 canonical example proteins in `origin/UI:UI/backend/app/examples.py`.

| Option | Description | Selected |
|--------|-------------|----------|
| Full alignment | Run all 5 UI examples + H. influenzae + Novel | |
| UI branch 5 default examples only | Ubiquitin, Hemoglobin-alpha, Bacteriorhodopsin, p53, AKT1 | ✓ |
| You decide | Agent discretion | |

**User's choice:** UI branch 5 default examples only (Ubiquitin, Hemoglobin-alpha, Bacteriorhodopsin, p53, AKT1)
**Notes:** Targets selected: Ubiquitin (PDB 1UBQ, Monomer), Hemoglobin-α (UniProt P69905, α2β2 heterotetramer), Bacteriorhodopsin (UniProt P02945, homotrimer), p53 (UniProt P04637, homotetramer), AKT1 (UniProt P31749, monomer).

| Option | Description | Selected |
|--------|-------------|----------|
| Retain H. influenzae test | Include H. influenzae in automated tests to satisfy QUAT-09 | |
| Replace H. influenzae scope | Replace H. influenzae entirely with the 5 UI examples across both fixtures and benchmarks (amending QUAT-09 scope) | ✓ |
| You decide | Agent discretion | |

**User's choice:** Replace H. influenzae entirely with the 5 UI examples across both fixtures and benchmarks (amending QUAT-09 scope)
**Notes:** Roadmap requirement QUAT-09 scope formally redirected to the 5 UI benchmark examples.

| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive benchmark deliverables | Detailed BENCHMARK_REPORT.md + JSON payloads in schema/fixtures/ui_examples/ + automated tests in tests/test_benchmarks.py | ✓ |
| Markdown report only | BENCHMARK_REPORT.md only | |
| Fixtures only | schema/fixtures/ only | |

**User's choice:** Comprehensive benchmark artifacts: Detailed BENCHMARK_REPORT.md documenting assembly results & timing for the 5 UI examples, exported JSON payloads in schema/fixtures/ui_examples/, and automated verification in tests/test_benchmarks.py
**Notes:** Provides complete auditability and reproducibility.

---

## Synthetic & Novel Sequence Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Full novel validation suite | Dual validation: notebook novel sequence + scrambled control | |
| Skip and defer to future issue | Skip novel sequence fully for now, add as future scope GitHub issue, focus on happy-path coding | ✓ |

**User's choice:** "just skip the novel sequence fully for now. add as future scope(issue) to test things out properly and add them in later. ignore the above decisions regarding the novel seq as well please. let us just do the happy path coding for now"
**Notes:** User explicitly instructed to defer novel/synthetic sequence benchmarking to a future GitHub issue, keeping Phase 4 focused strictly on happy-path contract and UI integration.

---

## Frontend UI Developer Integration Guide

| Option | Description | Selected |
|--------|-------------|----------|
| Direct UI LevelResult adapter | Implement direct UI adapter (quaternary/ui_adapter.py) implementing analyze(sequence, ctx) -> LevelResult matching UI LEVEL_CONTRACT.md | ✓ |
| Markdown docs only | Provide documentation without code | |
| You decide | Agent discretion | |

**User's choice:** Direct UI adapter (quaternary/ui_adapter.py) implementing analyze(sequence, ctx) -> LevelResult matching UI LEVEL_CONTRACT.md (Ready for immediate drop-in replacement into UI/backend/app/levels/)
**Notes:** Enables seamless zero-glue drop-in replacement into the UI server.

| Option | Description | Selected |
|--------|-------------|----------|
| Assembly headline + interface marks track | Headline = oligomeric state, Track = interface residues (marks), Tables = components & interfaces, Notes = functional mechanism | ✓ |
| Minimal LevelResult | Headline and summary only | |
| You decide | Agent discretion | |

**User's choice:** Assembly Headline + Interface Marks Track: Headline displays the oligomeric state (e.g. 'Homotetramer (A4)'), Track displays interface contact residues ('marks' style), Tables list subunits and PISA interfaces, and Notes highlight the functional mechanism hypothesis
**Notes:** Rich visual mapping conforming to `LEVEL_CONTRACT.md`.

| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive handoff guide | docs/UI_INTEGRATION_GUIDE.md with data dictionary, enum mappings, drop-in replacement instructions, and fixture walkthroughs | ✓ |
| Data dictionary only | Markdown reference only | |
| You decide | Agent discretion | |

**User's choice:** Comprehensive handoff guide (docs/UI_INTEGRATION_GUIDE.md): Data dictionary, enum values, drop-in replacement instructions for UI/backend/app/levels/, and sample fixture walkthroughs
**Notes:** Clear handoff documentation for the frontend/fullstack team.

| Option | Description | Selected |
|--------|-------------|----------|
| Curated TypeScript types | Export schema/types/quaternary.ts + include in docs/UI_INTEGRATION_GUIDE.md | ✓ |
| Snippets in docs only | Snippets only | |
| You decide | Agent discretion | |

**User's choice:** Export curated TypeScript type definitions (schema/types/quaternary.ts) and include them in docs/UI_INTEGRATION_GUIDE.md (Enables full type safety for frontend TypeScript components)
**Notes:** Enables compile-time type safety for frontend developers.

---

## Deferred Ideas

- Novel and synthetic sequence edge-case benchmarking: Defer full boundary testing, scrambled negative-control assertions, and uncharacterized sequence fallbacks to a dedicated future milestone GitHub issue.
- AlphaFold-Multimer live cloud runner execution: Maintained as deferred per Phase 03.2 decisions (cleanly tagged as `PREDICTION_NOT_EXECUTED`).
