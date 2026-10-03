---
phase: "02"
plan: "02-01"
title: "Core Domain Models and Pluggable Caching Architecture"
status: complete
completed_at: "2026-10-04"
requirements_covered:
  - QUAT-03
decisions_enforced:
  - D-03
  - D-06
  - D-07
  - D-08
  - D-09
  - D-14
  - D-15
  - D-16
files_created:
  - quaternary/__init__.py
  - quaternary/config.py
  - quaternary/models/__init__.py
  - quaternary/models/stoichiometry.py
  - quaternary/models/interface.py
  - quaternary/models/conflict.py
  - quaternary/models/provenance.py
  - quaternary/models/session_state.py
  - quaternary/cache/__init__.py
  - quaternary/cache/base.py
  - quaternary/cache/json_cache.py
  - quaternary/cache/sqlite_cache.py
  - tests/test_models_and_cache.py
---

# Plan 02-01 Summary: Core Domain Models and Pluggable Caching Architecture

## 1. Executive Summary

Plan `02-01` has been executed to completion. We constructed the fundamental domain data models using Pydantic v2 and implemented a pluggable dual caching architecture supporting both JSON directory caching and SQLite database storage.

All locked architectural decisions (D-03 conflict retention, D-06 Pydantic v2 domain schemas, D-07 symbolic stoichiometry with automated parsing, D-08 segregated confidence provenance without mathematical blending, D-14 dual cache backend, D-15 permanent caching with manual clear, and D-16 hierarchical configuration) have been codified and verified with deterministic unit tests.

## 2. Key Accomplishments & Deliverables

1. **Hierarchical QuaternaryConfig (`quaternary/config.py`)**:
   - Implemented `QuaternaryConfig` supporting resolution precedence:
     1. Constructor kwargs
     2. Working directory `quaternary_config.json`
     3. Environment variables (`QUATERNARY_CACHE_BACKEND`, `QUATERNARY_OFFLINE_MODE`, etc.)
     4. Default values
   - Manages timeouts, retries, backoff factors, cache directory paths, and offline mode.

2. **Pydantic v2 Domain Models (`quaternary/models/`)**:
   - `Stoichiometry` & `AssemblyType`: Parses complex stoichiometry formulas (e.g. `A`, `A2`, `A2B2`, `A4B4C2`) into subunit mappings and oligomeric classification (`MONOMER`, `HOMOMER`, `HETEROMER`, `UNCHARACTERIZED`).
   - `InterfaceContact` & `ResidueRange`: Captures pairwise chain buried surface area (Å²), solvation ΔG, hydrogen bonds, salt bridges, and participating residue lists.
   - `ExperimentalConflict`: Preserves crystallographic assembly vs PISA biophysical conflict details and rationale (D-03).
   - `ConfidenceProvenance`: Strictly segregates source confidence metrics (`pdbe_pisa`, `swissmodel`, `alphafold_db`, `alphafold_multimer`) without synthetic blending (D-08).
   - `StageResult` & `QuaternaryStructureOutput`: Tracks stage-wise execution status (`SUCCESS`, `UNAVAILABLE`, `FAILED`, `PENDING`, `SKIPPED`) and provides the final validated data contract.

3. **Pluggable Dual Cache Backend (`quaternary/cache/`)**:
   - `CacheBackend`: Abstract base class with SHA-256 endpoint/query hashing.
   - `JsonDirectoryCache`: Human-readable JSON filesystem cache at `.cache/quaternary/<endpoint>/<hash>.json`.
   - `SqliteCache`: High-performance relational cache at `.cache/quaternary.db`.
   - `get_cache_backend`: Factory resolving the active backend from `QuaternaryConfig`.

4. **Deterministic Unit Tests (`tests/test_models_and_cache.py`)**:
   - 11 unit tests covering config resolution, stoichiometry parsing, interface validation, conflict retention, confidence segregation, cache operations (set, get, overwrite, clear), and factory dispatch.

## 3. Verification

- `python -m pytest tests/test_models_and_cache.py -v`: 11 passed in 0.60s.
- `python -c "import quaternary; from quaternary.models import QuaternaryStructureOutput; from quaternary.config import QuaternaryConfig; from quaternary.cache import get_cache_backend"`: executed with exit code 0.
