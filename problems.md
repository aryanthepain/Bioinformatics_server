# Project Roadblocks & Challenges

### Roadblock 1: BioServices Refactoring Trap

- **Issue**: The pipeline was initially built using multiple independent, raw REST API calls for querying UniProt. Later, after discovering the high-level `bioservices` Python library, the codebase had to be completely rewritten to switch over.
- **Impact**: Inconsistent return types (e.g., TSV text strings vs. parsed JSON dictionaries) and parameter divergences required rewriting data parsing logic from scratch, causing significant delays and implementation overhead.

---

### Roadblock 2: Asynchronous ID Mapping API Quirk (UniProtKB)

- **Issue**: UniProt's asynchronous batch/ID mapping workflow (`/idmapping/run` and `/idmapping/status`) deviates from standard async API behavior. When a job finishes, the API does not return a terminal status flag like `{"jobStatus": "FINISHED"}`. Instead, it responds with an HTTP 303 (See Other) redirect directly to the results URL.
- **Impact**: Standard HTTP clients (such as Python `requests`) automatically follow redirects by default. The polling loop then receives the actual results payload—which lacks a `jobStatus` field—causing naive polling code to crash with a `KeyError` or get trapped in an infinite loop.
- **Resolution**: Disable automatic redirect following during status polling (`allow_redirects=False`) to intercept the HTTP 303 status and retrieve the target results location header directly.
