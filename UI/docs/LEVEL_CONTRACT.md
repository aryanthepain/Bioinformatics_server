# Connecting an analysis module to the UI

Every structural level reports its results in **one shared shape**, called a
`LevelResult`. The interface only knows how to draw that shape, so connecting a
module means writing one function that turns your module's output into a
`LevelResult`. Nothing in the frontend needs to change.

The models live in `backend/app/schemas.py`.

## The function your module provides

```python
from app.jobs import StageContext
from app.schemas import LevelResult

def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    ...
```

- `sequence` is already cleaned and validated: uppercase, only the 20
  standard amino acids, 25 to 1,000 residues. (A few non-standard letters
  such as X or U are replaced before this; see `app/sequence.py`.)
- `ctx` lets you talk to the interface while you work:
  - `ctx.report("Foldseek is searching · 0:40 elapsed")` shows a live progress message.
  - `ctx.sleep(20)` waits, but stops immediately if the user cancels.
    Use it instead of `time.sleep` in polling loops.
  - `ctx.check_cancelled()` can be called between long steps.
- If your module cannot handle this input, `raise LevelSkipped("reason")`
  (from `app.jobs`). The level is shown as skipped with your reason.
- Any other exception marks your level as failed. The other levels still run.
- Never put API tokens in code. Read them from environment variables.

Then register it in `backend/app/levels/__init__.py` by replacing the
placeholder function for your level.

**Optional: a slower background step.** A level whose module has a fast part and a
slow part can show the fast result first. Register two more functions with it:
`refine(sequence, result, ctx) -> LevelResult`, which runs after `result` is shown
and returns the result that replaces it, and `needs_refinement(result) -> bool`
(for example after a cached result). While `refine` runs, the level's tab says so
above the result and the prediction is recomputed when it finishes. If `refine`
fails or the user stops the analysis, the first result stays. The primary level
uses this for its optional remote EMBL-EBI BLASTp and InterProScan (only when
`PFP_EBI_EMAIL` is set), the secondary level for its comparison with experimental
PDB structures.

## Where each field appears

Each level gets a summary card and a full analysis section on the results page.

| Field | Shown as | Example |
| --- | --- | --- |
| `source` | "live" or "placeholder" tag | `"live"` |
| `headline` | The large dark tile, and the summary card | `Headline(value="9.9e−21", label="best structural-match E-value")` |
| `summary` | The opening sentence of the section | `"The model matches cytochrome c folds."` |
| `metrics` without `group` | Key-figure tiles (use up to four) | `Metric(label="Model atoms", value="824")` |
| `metrics` with `group` | A titled property list in the side column | `Metric(label="GRAVY", value="−0.706", group="Physicochemical profile · ProtParam")` |
| `tracks` | Rows of the residue maps (see below) | |
| `tables` | Titled tables | homology hits, Foldseek matches |
| `notes` | Highlighted cards: `recommendation`, `observation` or `caution` | wet-lab advice |
| `evidence` | Reasoning lines marked ✓ (positive), − (negative) or • (neutral) | `EvidenceItem(polarity="positive", text="…")` |
| `links` | External references | `Link(label="PDB 3ZOO", url="https://www.rcsb.org/structure/3ZOO")` |
| `raw` | Collapsible "Raw module output" (JSON-safe dict) | your original results |

Values are **display-ready strings**: format numbers yourself
(`f"{value:.2f}"`), because the interface shows them exactly as given.
A `hint` on a metric becomes a tooltip.

## Residue-map tracks

A track is one row of a residue map. Positions are **1-based and inclusive**,
like UniProt (residue 1 is the first amino acid; `start=5, end=10` covers six
residues).

| `style` | Use it for | Rule |
| --- | --- | --- |
| `blocks` | Labelled regions, like domains or alignment coverage | Give each segment a `label`; segments must not overlap |
| `states` | A per-residue category, like helix/strand/coil or model quality | Segments must cover every residue exactly once, in order |
| `marks` | Specific positions, like interface or binding residues | Short segments; gaps are fine |

`overview=True` (the default) also puts the track on the combined residue map
at the top of the page. Give **exactly one** track per level `overview=True`;
mark the rest `overview=False` so they appear only in the level's own section.

Colours are chosen by **tone**, never by hex code, so every level matches the
design: `accent`, `ink`, `neutral`, `helix`, `strand`, `coil`, `uncertain`,
`confidence-very-high`, `confidence-high`, `confidence-low`,
`confidence-very-low`. Always add a `legend` so readers know what each tone means.

## Tables

```python
Table(
    key="structural-matches",
    title="Structural matches",
    caption="Foldseek search of the AlphaFold DB structure",
    columns=[
        TableColumn(key="database", label="Database", mono=True),
        TableColumn(key="match", label="Match"),
        TableColumn(key="evalue", label="E-value", align="right", mono=True),
    ],
    rows=[{"database": "pdb100", "match": "3zoo_A cytochrome c", "evalue": "9.9e−21"}],
)
```

Every row uses the column `key`s. Right-aligned columns (numbers) shrink to fit;
left-aligned columns (names) take the remaining width.

## Worked example: the tertiary notebook

`Tertiary_protein_identification.ipynb` computes everything the tertiary section
displays (`backend/app/levels/tertiary.py`):

| Notebook output | Goes into |
| --- | --- |
| mean pLDDT (`analyze_structure`) | `headline`, `metrics` group "Confidence · pLDDT" |
| per-residue pLDDT (B-factor column of the AlphaFold DB file) | `tracks` (`states`), banded into the four `confidence-*` tones |
| DSSP states (pydssp) | `tracks` (`states`, `overview=False`) and `metrics` group "Secondary structure" |
| `identify_structure()` top hit per database | `tables` (Structural matches), `links` |
| the printed report (CONFIDENCE, DISORDER, COMPACTNESS, SURFACE, HOMOLOGY…) | `evidence`, one line each |
| `transfer_uniprot_annotation()` sites and function | `tables` (Functional sites), `tracks` (`marks`), `notes` |
| `analyze_properties()` pI, GRAVY, instability, weight, atoms, size | `metrics` |

Residue tracks are drawn only when the structure's residues line up with the query
(the structure is that of the primary level's closest match).

The placeholder in `backend/app/levels/placeholders.py` (`tertiary`) produces
exactly this shape, so it is a useful template.

If your module produces something this shape cannot express, raise it with
the UI owner — the contract can grow, but it should grow in one place.
