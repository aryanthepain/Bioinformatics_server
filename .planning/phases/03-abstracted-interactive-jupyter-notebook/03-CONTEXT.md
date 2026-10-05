# Phase 3: Abstracted Interactive Jupyter Notebook - Context

**Gathered:** 2026-10-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers `Quaternary_Structure.ipynb`: a clean, end-user-friendly, interactive Jupyter notebook demonstrating full quaternary structure characterization using exclusively the high-level API provided by `quaternary_pipeline.py`.

The notebook accepts a target protein (UniProt accession or FASTA sequence), executes quaternary analysis across experimental, homology, and predictive stages without exposing raw HTTP or parser internals, renders collapsible JSON and tabular biological summaries, and exports a standardized data contract (`quaternary_structure_output.json`).

Per user direction, heavy UI/frontend styling is deferred to the dedicated UI application team; the notebook remains lightweight, robust, and focused on clear demonstration and scientific explanation.
</domain>

<decisions>
## Implementation Decisions

### Input Handling & Execution Experience
- **D-01:** Dual-mode input mechanism — Provide interactive `ipywidgets` (accession text box, preset example dropdown, multimer checkbox, run button) with an automatic, graceful fallback to declarative Python variable assignments (`TARGET_PROTEIN = "P0A6F5"`) in headless or non-interactive notebook environments. — **Reversibility:** reversible — [standard notebook input fallback pattern]
- **D-02:** Pre-flight validation with clean inline warning banners — Validate accession regex and FASTA sequence integrity before dispatching pipeline calls, rendering clear HTML/markdown alerts for malformed inputs rather than uncaught stack traces. — **Reversibility:** reversible — [isolated to input verification cell]
- **D-03:** Lightweight console stage logging — As the dedicated UI team is building the final frontend web interface, avoid heavy UI/widget redraws. Display clean, readable stage prints and progress milestones (`[STAGE 1/6: UNIPROT SUBUNIT] ...`) to provide clear execution status without widget bloat. — **Reversibility:** reversible — [print/logging convention]

### Visual Summaries & Inspection Style
- **D-04:** Collapsible VS Code-style dark tree viewer + HTML biological metric summary — Adopt the `show_json(data, max_depth=1)` helper from `UniProtKB.ipynb` (using `renderjson@1.4.0` via `IPython.display.HTML`) for interactive inspection of intermediate stage payloads and the final `QuaternaryStructureOutput`. Supplement with a clean HTML summary table displaying top-level biological metrics (Assembly Type, Stoichiometry Formula, Subunit Count, Interface Confidence). — **Reversibility:** costly — [determines notebook rendering cell output structures]
- **D-05:** No 3D molecular rendering in `Quaternary_Structure.ipynb` — 3D rendering is already handled in `Structure_Prediction.ipynb`. 3D multimer and interface visualization for the production frontend is tracked as GitHub Issue #4 for the UI team. — **Reversibility:** reversible — [tracked externally in issue #4]

### Workflow Granularity & Downstream Contract Export
- **D-06:** Two-Tier Workflow Structure — Organize the notebook into two clean sections:
  1. *Part 1: Quickstart Facade* — A 1-line `analyze_quaternary(target_input)` call providing instant end-to-end characterization and summary inspection.
  2. *Part 2: Modular Session Walkthrough* — A step-wise walkthrough using `QuaternarySession` running stages 1 through 6 individually (`run_stage_1_uniprot_subunit` through `run_stage_6_aggregate`) with intermediate inspection cells to demonstrate engine modularity. — **Reversibility:** costly — [shapes overall notebook outline and cell sequencing]
- **D-07:** Dual Export Formats — Conclude the workflow by exporting the standardized frontend JSON contract (`quaternary_structure_output.json`) via `session.to_ui(format="json")`, while also providing direct Python dictionary and Pandas DataFrame accessors (`session.to_ui(format="dict")` / `format="dataframe"`) for immediate programmatic scripting. — **Reversibility:** reversible — [facade export utility calls]

### Showcase Demonstration Targets & Scientific Narrative
- **D-08:** Dual Showcase Reference Targets — Pre-configure two distinct runnable demonstration proteins:
  1. *Positive Control:* A well-characterized multimer with rich experimental ground truth in PDB and PISA (e.g. GroEL chaperone `P0A6F5` or Insulin `P01308`).
  2. *Uncharacterized Target:* An uncharacterized protein from *Haemophilus influenzae* (Proteome ID `UP000000579`, e.g. `P44101` / `P44500`) to demonstrate graceful fallback handling and homology/predictive assembly inference (directly addressing QUAT-09). — **Reversibility:** reversible — [parameter preset configurations]
  - **D-09:** High-Yield Scientific Commentary — Provide comprehensive, educational markdown cells explaining quaternary structure fundamentals, biological interpretation of stoichiometry formulas ($A_2B$, $A_{14}$), buried surface area ($\Delta G$, hydrogen bonds), and confidence score provenance (experimental vs homology vs AlphaFold-Multimer). — **Reversibility:** reversible — [markdown narrative content]

### The Agent's Discretion
- Selection of specific color palette for the HTML metric summary cards (harmonized with the dark-theme `show_json` styling from `UniProtKB.ipynb`).
- Cell ordering and markdown headings structure within Part 1 and Part 2.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Engine & Façade API
- `quaternary_pipeline.py` — Top-level façade module exposing `analyze_quaternary`, `QuaternaryEngine`, `QuaternarySession`, `QuaternaryConfig`, and Pydantic models.
- `.planning/phases/02-core-quaternary-engine-api-abstraction-module/02-CONTEXT.md` — Locked architectural decisions for session state machine, non-fatal fallbacks, and UI export contract.

### Project Notebook Conventions
- `UniProtKB.ipynb` §Cell 9 — Canonical implementation of `show_json(data, max_depth=1)` collapsible dark tree viewer using `renderjson`.
- `Structure_Prediction.ipynb` — Existing 3D and bioinformatic notebook workflows in repository.

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` §QUAT-06, QUAT-07, QUAT-09 — Requirements for high-level notebook abstraction, interactive summaries, and *Haemophilus influenzae* benchmark.
- `.planning/ROADMAP.md` §Phase 3 — Success criteria and phased plan deliverables.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `quaternary_pipeline.analyze_quaternary`: One-line entry point returning validated `QuaternaryStructureOutput`.
- `quaternary.session.QuaternarySession`: Stateful session supporting stage-wise execution (`run_stage_1_...` through `run_stage_6_...`) and `session.to_ui()`.
- `UniProtKB.ipynb`: Provides the battle-tested, dark-themed `show_json` tree viewer function utilizing `IPython.display.HTML`.

### Established Patterns
- Pydantic v2 data models serialize cleanly via `.model_dump()` and `.model_dump_json()`.
- Non-fatal fallbacks mark stages as `unavailable` with provenance recorded, ensuring top-to-bottom notebook execution never halts abruptly on remote API outages.
- High-level calls isolate all HTTP, retry, and JSON parsing logic from notebook cells.

### Integration Points
- `Quaternary_Structure.ipynb` sits at the repository root alongside existing analysis notebooks (`UniProtKB.ipynb`, `Foldseek_Swiss_model.ipynb`).
- Output file `quaternary_structure_output.json` will be written to the workspace root or designated export path for frontend and Phase 4 validation consumption.
</code_context>

<specifics>
## Specific Ideas
- User guidance: "the ui will be handled by someone else no need to go much ui heavy, just something enough for a simple demo and explanation"
- User guidance: "json style viewer with html view similar to uniprot notebook"
- User guidance: "no 3d rendering req. already handled in a diff notebook. but add an issue for the ui team to add the 3d rendering as well" -> Tracked in GitHub Issue #4.
</specifics>

<deferred>
## Deferred Ideas
- Frontend 3D multimer/complex viewer component: logged in GitHub repository as [Issue #4](https://github.com/aryanthepain/Bioinformatics_server/issues/4).
</deferred>

---

*Phase: 03-abstracted-interactive-jupyter-notebook*
*Context gathered: 2026-10-04*
