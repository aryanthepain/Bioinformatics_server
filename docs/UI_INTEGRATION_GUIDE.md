# Quaternary Structure Engine: UI Developer Integration Guide

**Contract Version:** Draft 2020-12  
**Adapter Module:** `quaternary.ui_adapter`  
**Shared Contract:** `UI/backend/app/schemas.py:LevelResult`  
**TypeScript Definitions:** `schema/types/quaternary.ts`  
**Published Schema:** `schema/quaternary_structure_output.schema.json`

---

## 1. Executive Integration Overview

The Quaternary Protein Structure & Complex Annotation Engine provides an out-of-the-box, drop-in adapter (`quaternary.ui_adapter`) designed specifically for the fullstack bioinformatics application (`UI` branch).

In the UI application architecture, each structural level (primary, secondary, tertiary, quaternary) reports its biological findings through a unified schema: **`LevelResult`** (defined in `UI/backend/app/schemas.py`). 

By importing `quaternary.ui_adapter.analyze`, the backend server receives live experimental assemblies, PDBe PISA interface chemistry, and functional inference without requiring any modifications to frontend React/TypeScript rendering components.

```
┌────────────────────────────────┐         ┌────────────────────────────────┐
│   UI Server (app.runner)       │         │   Quaternary Adapter Module    │
│   quaternary(sequence, ctx)    │───────> │   quaternary.ui_adapter        │
└────────────────────────────────┘         └────────────────┬───────────────┘
                                                            │
                                           ┌────────────────▼───────────────┐
                                           │   QuaternarySession            │
                                           │   Stages 1–6 Biological Engine │
                                           └────────────────┬───────────────┘
                                                            │
┌────────────────────────────────┐         ┌────────────────▼───────────────┐
│   Frontend React / TS UI       │ <────── │   LevelResult                  │
│   (Residue Map, Tables, Cards) │         │   (Headline, Tracks, Tables)   │
└────────────────────────────────┘         └────────────────────────────────┘
```

---

## 2. Drop-In Replacement Instructions (Backend)

In `UI/backend/app/levels/` (or wherever structural level runners are dispatched), replace the placeholder import with the live quaternary adapter:

### Before (Placeholder):
```python
# UI/backend/app/levels/placeholders.py or runner.py
from .placeholders import quaternary
```

### After (Production Quaternary Engine):
```python
# Direct drop-in replacement
from quaternary.ui_adapter import analyze as quaternary
```

### Signature Conformance:
The function matches the exact signature expected by the UI runner:
```python
def quaternary(sequence: str, ctx: StageContext | None = None) -> LevelResult:
    ...
```

- **`sequence`:** Standard IUPAC amino acid string (25 to 1,000 residues).
- **`ctx`:** Optional runner context object offering progress telemetry (`ctx.report(message)`) and cancellation checking (`ctx.is_cancelled`).
- **Return Value:** A validated `LevelResult` instance with `source="live"` and `raw` containing the full `QuaternaryStructureOutput` dictionary.

---

## 3. Data Dictionary & LevelResult Field Mappings

The table below details how the domain properties of `QuaternaryStructureOutput` translate into the UI presentation elements of `LevelResult`:

| `LevelResult` Field | Component in UI | Derived From `QuaternaryStructureOutput` | Description / Example |
| :--- | :--- | :--- | :--- |
| **`source`** | Data Source Badge | Literal `"live"` | Replaces `"placeholder"` with `"live"` data badge. |
| **`headline.value`** | Card Large Metric | `stoichiometry.assembly_type` + `formula` | e.g. `"Heterotetramer (α2β2)"`, `"Homotetramer (A4)"`, `"Monomer"`. |
| **`headline.label`** | Metric Caption | Literal `"quaternary assembly"` | Standardized label for all quaternary cards. |
| **`summary`** | Plain Language Header | Dynamic biological synthesis | One-sentence summary stating assembly type, subunit count, and total buried surface area. |
| **`metrics[]`** | Key Figures Grid | Subunit count, Stoichiometry, Status, Total BSA | Displayed as stat tiles and grouped under `"Biophysics"`. |
| **`tracks[key="interfaces"]`** | Residue Map Row | `interfaces[].interface_residues_chain_1` | Interactive marker track showing 1-based interface contact residues. |
| **`tables[key="components"]`** | Structured Table | `target_self_assembly` + `functional_complexes` | Macromolecular subunit identity, copy numbers, and functional complex roles. |
| **`tables[key="interfaces"]`** | Structured Table | `interfaces[]` (PISA) | Pairwise chains, Buried Surface Area ($\text{Å}^2$), Solvation $\Delta^i G$, H-bonds, salt bridges. |
| **`notes[]`** | Highlight Box | `inferred_function` | Observation note containing molecular function and oligomeric mechanism hypothesis. |
| **`links[]`** | Resource Links | Accession & PDB IDs | Direct clickable URLs to UniProtKB, RCSB PDB, and PDBe PISA. |
| **`raw`** | JSON Export / Dev Tools | `output.model_dump(mode="json")` | Complete validated dictionary matching `schema/quaternary_structure_output.schema.json`. |

---

## 4. Residue Map Track Specifications

The residue map renders quaternary interface contact residues across the linear sequence:

- **Style:** `"marks"` (renders as vertical pin markers rather than continuous colored blocks).
- **Tone:** `"ink"` (deep dark ink tone from the UI design system; avoids arbitrary hex codes).
- **Indexing:** **1-based inclusive** (`start=i, end=i` where $1 \le i \le \text{length}$).
- **Overview Flag:** `overview=True` (ensures interface contact residues appear on the combined global residue map alongside secondary structure and Pfam domains).
- **Contiguous Merging:** Contiguous adjacent interface residues (e.g. residues 325, 326, 327) are automatically coalesced into compact segments (`start=325, end=327`).

```json
{
  "key": "interfaces",
  "label": "Interface residues",
  "caption": "Quaternary · PISA & RCSB",
  "style": "marks",
  "segments": [
    { "start": 325, "end": 356, "tone": "ink", "label": "Interface contact" }
  ],
  "legend": [
    { "label": "Interface contact residue", "tone": "ink" }
  ],
  "overview": true
}
```

---

## 5. UI Reference Benchmarks & Fixture Walkthrough

The 5 canonical proteins from `origin/UI:UI/backend/app/examples.py` are pre-computed and stored under `schema/fixtures/ui_examples/`:

1. **`ubiquitin.json` (`ubiquitin`)**:
   - Reference: PDB `1UBQ` / UniProt `P62988` (76 residues)
   - Status: `MONOMER` ($A_1$) | 0 interfaces
   - Biological Insight: Verified monomer baseline; ensures non-specific crystal contacts are not misidentified as assemblies.

2. **`hemoglobin_alpha.json` (`hemoglobin-alpha`)**:
   - Reference: UniProt `P69905` (142 residues)
   - Status: `HOMOMER` / Heterotetramer ($A_4$, $\alpha_2\beta_2$) | 5 interfaces
   - Biological Insight: Demonstrates heterocomplex partner assembly with $\beta$-globin and cooperative oxygenation interfaces.

3. **`bacteriorhodopsin.json` (`bacteriorhodopsin`)**:
   - Reference: UniProt `P02945` (249 residues)
   - Status: `HOMOMER` ($A_3$ homotrimer) | 3 interfaces
   - Biological Insight: Membrane-embedded proton pump with cyclic $C_3$ symmetry.

4. **`p53.json` (`p53`)**:
   - Reference: UniProt `P04637` (393 residues)
   - Status: `HOMOMER` ($A_4$ homotetramer) | 6 interfaces
   - Biological Insight: Tumor suppressor transcription factor; oligomerization domain (residues 325–356) forms a dimer-of-dimers.

5. **`akt1.json` (`akt1`)**:
   - Reference: UniProt `P31749` (480 residues)
   - Status: `MONOMER` ($A_1$) | 0 interfaces
   - Biological Insight: Monomeric signal transduction kinase; autoinhibited conformation in solution.

---

## 6. Frontend 3D Viewer Integration (GitHub Issue #4)

Frontend developers integrating 3D structural viewers (e.g. Mol*, py3Dmol, or NGL Viewer) can access complete structural coordinates and interface metadata directly from `LevelResult.raw`:

```typescript
import { QuaternaryStructureOutput } from "./schema/types/quaternary";

function render3DComplex(levelResult: LevelResult) {
  const rawQuat = levelResult.raw as QuaternaryStructureOutput;
  if (!rawQuat || !rawQuat.observed_assemblies.length) return;

  const topAssembly = rawQuat.observed_assemblies[0];
  const pdbId = topAssembly.pdb_id;
  const assemblyId = topAssembly.assembly_id;

  // Load biological assembly in Mol* or NGL
  viewer.loadPdbAssembly(pdbId, assemblyId);

  // Highlight interface contact residues
  rawQuat.interfaces.forEach((iface) => {
    viewer.highlightResidues(iface.chain_1, iface.interface_residues_chain_1, "#10b981");
    viewer.highlightResidues(iface.chain_2, iface.interface_residues_chain_2, "#3b82f6");
  });
}
```

---

## 7. Verification & Testing

To verify the adapter and contracts locally:
```bash
# Test UI Adapter
pytest tests/test_ui_adapter.py -v

# Test Published JSON Schema Conformance
pytest tests/test_ui_contract.py -v

# Test 5 Benchmark Proteome Invariants
pytest tests/test_benchmarks.py -v
```
