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
  standard amino acids, 25 to 1,000 residues.
- `ctx` lets you talk to the interface while you work:
  - `ctx.report("Waiting for Swiss-Model… 2 min")` shows a live progress message.
  - `ctx.sleep(20)` waits, but stops immediately if the user cancels.
    Use it instead of `time.sleep` in polling loops.
  - `ctx.check_cancelled()` can be called between long steps.
- If your module cannot handle this input, `raise LevelSkipped("reason")`
  (from `app.jobs`). The level is shown as skipped with your reason.
- Any other exception marks your level as failed. The other levels still run.
- Never put API tokens in code. Read them from environment variables.

Then register it in `backend/app/levels/__init__.py` by replacing the
placeholder function for your level.

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
    caption="Foldseek search with the Swiss-Model model",
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

`Mapping_protein_function_from_tertiary_structure.ipynb` already computes
everything the tertiary section displays:

| Notebook output | Goes into |
| --- | --- |
| `identify_structure()` top hit per database | `tables` (Structural matches), `evidence`, `headline` (best E-value) |
| Foldseek hit query start and end positions | `tracks` (`blocks`, `overview=False`), one per database |
| Per-residue local quality (QMEAN, 0–1), which Swiss-Model stores in the PDB B-factor column — verify on a real model file | `tracks` (`states`, `overview=True`), banded into the four `confidence-*` tones |
| `analyze_properties()` pI, GRAVY, instability, weight | `metrics` with `group="Physicochemical profile · ProtParam"` |
| atom count and spatial dimensions | key-figure `metrics` |
| `generate_wet_lab_report()` solubility, purification, assay | `notes` with `kind="recommendation"` |

The placeholder in `backend/app/levels/placeholders.py` (`tertiary`) produces
exactly this shape, so it is a useful template.

If your module produces something this shape cannot express, raise it with
the UI owner — the contract can grow, but it should grow in one place.
