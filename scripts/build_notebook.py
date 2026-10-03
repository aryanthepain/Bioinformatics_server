"""
Programmatic Builder for Quaternary_Structure.ipynb

Constructs, validates, and serializes Quaternary_Structure.ipynb using nbformat v4.
Provides modular builders across Wave 1 (Scaffold & Input), Wave 2 (Two-Tier Visuals),
and Wave 3 (Export, Dual Showcase & Biological Commentary).
"""

from pathlib import Path
import nbformat as nbf


def create_markdown_cell(source: str) -> nbf.NotebookNode:
    """Create a clean markdown cell."""
    return nbf.v4.new_markdown_cell(source=source.strip())


def create_code_cell(source: str) -> nbf.NotebookNode:
    """Create a clean code cell."""
    return nbf.v4.new_code_cell(source=source.strip())


def build_wave_1_cells() -> list[nbf.NotebookNode]:
    """Generate cells for Wave 1: Scaffold, imports, config, validation, and dual-mode input."""
    cells = []

    # 1. Title & Executive Overview
    title_md = r"""# Quaternary Protein Structure & Complex Annotation Engine

### High-Level End-to-End Pipeline for Protein Oligomeric State & Interface Characterization

---

## Executive Overview & Biological Context
Proteins execute biological functions primarily as multi-chain macromolecular complexes. **Quaternary structure** defines the three-dimensional geometric arrangement, subunit stoichiometry ($A_n$, $A_n B_m$), and interface binding chemistry of these multi-chain assemblies.

This notebook provides an abstracted, interactive scientific interface to determine:
- **Oligomeric State & Assembly Classification:** Monomer, homomer, or heteromer.
- **Stoichiometry Formula:** Exact subunit stoichiometry (e.g., $A_{14}$ tetradecamer for GroEL, $A_2 B_2$ heterotetramer for Hemoglobin).
- **Interface Contact Geometry:** Buried surface area ($\text{Å}^2$), solvation free energy gain ($\Delta G$), hydrogen bonds, and salt bridges.
- **Multi-Evidence Consensus:** Experimental validation (PDB, PDBe PISA), homology modeling (SWISS-MODEL), and predictive biophysics (AlphaFold-Multimer).

> **Architectural Principle:** All computations and remote biophysical services are coordinated strictly through the high-level façade in `quaternary_pipeline.py`. Zero raw HTTP calls, manual endpoint orchestration, or low-level parser boilerplate are exposed in notebook code cells.
"""
    cells.append(create_markdown_cell(title_md))

    # 2. Imports Cell
    imports_code = """# Core Standard Library & Display Utilities
import sys
import os
import re
import json
import time
import uuid
from pathlib import Path
from IPython.display import display, HTML, Markdown

# High-Level Quaternary Pipeline Façade API
# NOTE: Zero raw HTTP calls (requests.get, urllib) are permitted in this notebook.
from quaternary_pipeline import (
    analyze_quaternary,
    QuaternarySession,
    QuaternaryConfig,
    AssemblyType,
    QuaternaryStructureOutput,
)

print(" Quaternary Pipeline high-level API successfully initialized.")
"""
    cells.append(create_code_cell(imports_code))

    # 3. Configuration Cell
    config_code = """# Pipeline Configuration & Execution Settings
# Controls caching (JSON/SQLite backends), request timeouts, and execution parameters.
config = QuaternaryConfig(
    cache_enabled=True,
    cache_backend="json",
    cache_dir=".quaternary_cache",
    timeout=30.0,
    offline_mode=False
)

print(f" QuaternaryConfig Active:")
print(f"  - Caching Enabled: {config.cache_enabled} (Backend: {config.cache_backend})")
print(f"  - Cache Directory: {config.cache_dir}")
print(f"  - Network Timeout: {config.timeout}s")
print(f"  - Offline Fixture Mode: {config.offline_mode}")
"""
    cells.append(create_code_cell(config_code))

    # 4. Pre-Flight Validation Markdown
    validation_md = """## Input Validation & Pre-Flight Verification
Before dispatching multi-stage structural analyses, input identifiers or sequences must be verified.
The pipeline accepts:
1. **UniProtKB Accession:** e.g., `P0A6F5` (GroEL), `P01308` (Insulin), `P44101` (*H. influenzae*).
2. **FASTA Amino Acid Sequence:** Standard IUPAC 20-amino-acid sequence string.
"""
    cells.append(create_markdown_cell(validation_md))

    # 5. Pre-Flight Validation Functions Cell
    validation_code = r'''import re
from IPython.display import display, HTML

# Regex pattern adhering strictly to UniProtKB accession format specifications
UNIPROT_ACCESSION_REGEX = re.compile(
    r"^[O,P,Q][0-9][A-Z,0-9]{3}[0-9]|[A-N,R-Z][0-9]([A-Z][A-Z,0-9]{2}[0-9]){1,2}$"
)

# Standard IUPAC Amino Acid single-letter codes
VALID_AA_REGEX = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY\s]+$", re.IGNORECASE)


def validate_target_input(target_input: str) -> tuple[bool, str]:
    """
    Validate target protein input (UniProt accession or FASTA sequence).

    Returns:
        tuple[bool, str]: (is_valid, descriptive_status_message)
    """
    if not target_input or not isinstance(target_input, str):
        return False, "Input cannot be empty. Please provide a valid UniProt accession or FASTA sequence."

    cleaned = target_input.strip()

    # Check FASTA header + sequence
    if cleaned.startswith(">"):
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if len(lines) < 2:
            return False, "FASTA format requires a header line ('>header') followed by amino acid sequence."
        seq = "".join(lines[1:]).replace(" ", "")
        if not seq:
            return False, "FASTA sequence contains no amino acid characters."
        if not VALID_AA_REGEX.match(seq):
            return False, "FASTA sequence contains invalid non-IUPAC amino acid characters."
        return True, f"Valid FASTA sequence ({len(seq)} residues)."

    # Check raw single-line sequence (length >= 10 and pure AA characters)
    if len(cleaned) >= 10 and VALID_AA_REGEX.match(cleaned) and not UNIPROT_ACCESSION_REGEX.match(cleaned):
        return True, f"Valid raw amino acid sequence ({len(cleaned)} residues)."

    # Check UniProt Accession
    if UNIPROT_ACCESSION_REGEX.match(cleaned.upper()):
        return True, f"Valid UniProtKB accession format: '{cleaned.upper()}'"

    return False, (
        f"Invalid input '{cleaned}'. Must be a valid UniProt accession (e.g. 'P0A6F5', 'P01308') "
        "or a standard IUPAC amino acid sequence."
    )


def render_validation_status(is_valid: bool, msg: str) -> None:
    """Render a clean, styled HTML banner indicating pre-flight input status."""
    bg_color = "#1e3a24" if is_valid else "#4a1c1c"
    border_color = "#2ea043" if is_valid else "#f85149"
    icon = "&#10004;" if is_valid else "&#9888;"
    status_label = "INPUT VERIFIED" if is_valid else "VALIDATION WARNING"

    html = f"""
    <div style="background-color: {bg_color}; border-left: 5px solid {border_color};
                padding: 12px 16px; border-radius: 4px; margin: 10px 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                color: #e6edf3; font-size: 13.5px; line-height: 1.5;">
        <span style="font-weight: 700; color: {border_color}; margin-right: 8px;">{icon} {status_label}:</span>
        <span>{msg}</span>
    </div>
    """
    display(HTML(html))
'''
    cells.append(create_code_cell(validation_code))

    # 6. Dual-Mode Input Selection Markdown
    input_md = """## Interactive Target Selection (Dual-Mode Input)

You can select a pre-configured showcase target below, or enter any custom UniProt accession.
- **Positive Control (GroEL chaperonin `P0A6F5`):** Well-characterized tetradecamer ($A_{14}$) with abundant experimental PDB/PISA ground truth.
- **Positive Control (Insulin `P01308`):** Classical hexameric / dimeric peptide hormone.
- **Uncharacterized Benchmark (*H. influenzae* `P44101`):** Proteome `UP000000579` uncharacterized target illustrating predictive and homology fallback.
- **Headless / Batch Mode:** If executed without a GUI widget environment, the declarative variables below (`TARGET_PROTEIN`, `ENABLE_MULTIMER`) are utilized automatically.
"""
    cells.append(create_markdown_cell(input_md))

    # 7. Dual-Mode Input Selection Code
    input_code = """# Declarative Execution Defaults (Dual-Mode Fallback)
# These variables take precedence in headless execution, test suites, or CI pipelines.
TARGET_PROTEIN = "P0A6F5"  # Default: GroEL chaperonin (Positive Control - 14-mer)
ENABLE_MULTIMER = False    # Opt-in flag for AlphaFold-Multimer predictive modeling

try:
    import ipywidgets as widgets

    preset_dropdown = widgets.Dropdown(
        options=[
            ("GroEL Chaperonin (Positive Control - 14-mer) [P0A6F5]", "P0A6F5"),
            ("Insulin (Positive Control - Hexamer) [P01308]", "P01308"),
            ("Haemophilus influenzae uncharacterized (QUAT-09) [P44101]", "P44101"),
            ("Custom Accession / FASTA", "CUSTOM"),
        ],
        value="P0A6F5",
        description="Preset:",
        style={"description_width": "80px"},
        layout=widgets.Layout(width="480px"),
    )

    accession_text = widgets.Text(
        value="P0A6F5",
        description="Target ID:",
        placeholder="Enter UniProt accession or sequence",
        style={"description_width": "80px"},
        layout=widgets.Layout(width="480px"),
    )

    multimer_checkbox = widgets.Checkbox(
        value=False,
        description="Enable AlphaFold-Multimer (Stage 5 dry-run / opt-in)",
        style={"description_width": "initial"},
    )

    def on_preset_change(change):
        if change["new"] != "CUSTOM":
            accession_text.value = change["new"]
            global TARGET_PROTEIN
            TARGET_PROTEIN = change["new"]

    def on_text_change(change):
        global TARGET_PROTEIN
        TARGET_PROTEIN = change["new"].strip()

    def on_multimer_change(change):
        global ENABLE_MULTIMER
        ENABLE_MULTIMER = bool(change["new"])

    preset_dropdown.observe(on_preset_change, names="value")
    accession_text.observe(on_text_change, names="value")
    multimer_checkbox.observe(on_multimer_change, names="value")

    ui_panel = widgets.VBox([
        widgets.HTML("<b>Select or Enter Protein Target:</b>"),
        preset_dropdown,
        accession_text,
        multimer_checkbox,
    ])
    display(ui_panel)

except (ImportError, Exception) as e:
    print(f"Interactive ipywidgets unavailable ({e}). Using declarative variables:")
    print(f"  TARGET_PROTEIN = '{TARGET_PROTEIN}'")
    print(f"  ENABLE_MULTIMER = {ENABLE_MULTIMER}")
"""
    cells.append(create_code_cell(input_code))

    # 8. Pre-Flight Check Execution Cell
    verify_input_code = """# Run pre-flight validation on current selection
is_valid, validation_msg = validate_target_input(TARGET_PROTEIN)
render_validation_status(is_valid, f"Target '{TARGET_PROTEIN}': {validation_msg}")
if not is_valid:
    raise ValueError(f"Pre-flight verification failed for input '{TARGET_PROTEIN}': {validation_msg}")
"""
    cells.append(create_code_cell(verify_input_code))

    return cells


def assemble_notebook(cells: list[nbf.NotebookNode]) -> nbf.NotebookNode:
    """Create a validated v4 notebook from cells."""
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
            "mimetype": "text/x-python",
            "codemirror_mode": {"name": "ipython", "version": 3},
            "pygments_lexer": "ipython3",
        },
    }
    nbf.validate(nb)
    return nb


def write_notebook(nb: nbf.NotebookNode, output_path: str = "Quaternary_Structure.ipynb") -> None:
    """Write notebook to file with utf-8 encoding."""
    target = Path(output_path)
    with open(target, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f" Notebook successfully written to {target.resolve()} ({len(nb.cells)} cells).")


def main() -> None:
    """Build Quaternary_Structure.ipynb."""
    cells = build_wave_1_cells()
    nb = assemble_notebook(cells)
    write_notebook(nb)


if __name__ == "__main__":
    main()
