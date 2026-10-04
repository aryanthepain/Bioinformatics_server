# Phase 2: Core Quaternary Engine & API Abstraction Module — UAT Report

**Status:** PASSED  
**Date:** 2026-10-04  
**Scope:** Core clients, engine pipeline, caching backends, and multi-stage execution session  

---

## 1. User Acceptance Testing Results

| Test ID | Description | Expected Outcome | Actual Result | Status |
|---|---|---|---|---|
| **UAT-02-01** | Complex Portal Client Resolution | Retrieve complex stoichiometry from EBI Complex Portal without 404 | Returns `CPX-2113` GroEL/GroES complex (`A14B7`) via `intact/complex-ws` REST endpoint | **PASSED** |
| **UAT-02-02** | PDBe PISA REST Endpoint & Interface Parsing | Query interface thermodynamics and contacts without 404 or empty payload | Fetches 42 pairwise interfaces and dissociation energy $\Delta G = 20.11\text{ kcal/mol}$ for 1AON | **PASSED** |
| **UAT-02-03** | SWISS-MODEL Repository Parsing | Parse structures list from SWISS-MODEL API response without `AttributeError` | Successfully extracts 114 homology templates for P0A6F5, validating QMQE/GMQE | **PASSED** |
| **UAT-02-04** | IntAct Client Responsiveness | Retrieve physical interactors with low-latency timeout protection | Emits auxiliary interactors without blocking pipeline execution on slow upstream EBI endpoints | **PASSED** |
| **UAT-02-05** | Consensus Stoichiometry Synthesis | Synthesize biological stoichiometry from multi-provider precedence hierarchy | P0A6F5 resolves to `A14B7` (21 subunits, Heteromer); P44101 resolves to `A` (1 subunit, Monomer) | **PASSED** |
| **UAT-02-06** | Test Suite Verification | All unit and regression tests pass deterministically | 44/44 tests pass in `pytest` | **PASSED** |

---

## 2. Issues Diagnosed and Resolved

1. **Complex Portal 404 Bug:**
   - *Cause:* URL was using legacy/retired endpoint `api/complex/{id}`.
   - *Fix:* Updated to official EBI REST endpoint `https://www.ebi.ac.uk/intact/complex-ws/complex/{clean_id}` and parsed stoichiometry from `systematicName` fallback (`14xgroL:7xgroS` $\to$ `A14B7`).

2. **PDBe PISA Missing Assembly ID & Interface Extraction:**
   - *Cause:* URL omitted `/{target_asm}` causing 404, and response contained `assembly` with `interfaces` rather than `assemblies`.
   - *Fix:* Updated endpoint to `https://www.ebi.ac.uk/pdbe/api/pisa/interfaces/{clean_id}/{target_asm}` with fallback to `assembly/{clean_id}/{target_asm}`, extracting all 42 interfaces, macromolecular size, and dissociation energy.

3. **SWISS-MODEL Dict Structure Iteration:**
   - *Cause:* Live API returned `dict` for `data["result"]` containing `structures: [...]`, causing iteration over dict string keys and throwing `AttributeError: 'str' object has no attribute 'get'`.
   - *Fix:* Safely handled both `data["result"]["structures"]` (live API) and `data["result"]` list (fixture).

4. **IntAct Long-Tail Hangs:**
   - *Cause:* EBI IntAct API exhibited high latency (>30s) triggering urllib3 exponential retry loops.
   - *Fix:* Added direct request with 3s timeout and non-blocking fallback to preserve pipeline responsiveness.
