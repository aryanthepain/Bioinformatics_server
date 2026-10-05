---
phase: "04"
slug: "standardized-ui-json-data-contract-benchmark-validation"
status: verified
threats_open: 0
asvs_level: 1
created: "2026-10-05"
---

# Phase 4 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail for UI JSON Data Contract and Benchmarks.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| User Input -> UI Adapter | External protein sequence or accession submitted to `analyze()` | Plaintext FASTA sequence or UniProt ID |
| External Bioinformatics APIs -> Client Parser | Upstream REST endpoints (UniProt, RCSB, PDBe PISA, SWISS-MODEL, IntAct) | Unauthenticated external JSON/XML data |
| CLI / Notebook Exporters -> Filesystem | Exporter scripts writing schemas and fixtures (`export_ui_contract.py`) | JSON payloads to disk |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering / Input Injection | `quaternary/ui_adapter.py` | medium | mitigate | Strict input validation enforcing 25-1000 aa bounds, canonical IUPAC amino acids, and explicit error raising verified by `tests/test_ui_adapter.py` | closed |
| T-04-02 | Information Disclosure | `quaternary/models/provenance.py` | low | mitigate | Strict sanitization of API URLs, offline mode isolation, and absence of credential/token leaks in exported JSON payloads | closed |
| T-04-03 | Denial of Service | `quaternary/session.py` | medium | mitigate | Cancellation check support (`StageContext.is_cancelled`) and timeout guards on all network requests | closed |
| T-04-04 | Schema Tampering / Type Confusion | `schema/quaternary_structure_output.schema.json` | high | mitigate | Automated JSON Schema Draft 2020-12 validation via `Draft202012Validator.check_schema` and strict model adherence via Pydantic v2 | closed |

---

## Accepted Risks Log

No accepted risks. All identified threats are mitigated and verified.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-05 | 4 | 4 | 0 | Antigravity Autonomous Orchestrator |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-05
