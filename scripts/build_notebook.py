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
def build_wave_2_cells() -> list[nbf.NotebookNode]:
    """Generate cells for Wave 2: Visual helpers, Part 1 facade, and Part 2 modular session."""
    cells = []

    # 1. Visual Helpers Markdown
    visual_md = r"""## Interactive Visualization Helpers & Biological Summary Displays

We define two presentation utilities:
1. `show_json(data, max_depth=1)`: Interactive dark tree viewer with collapsible arrows using `renderjson@1.4.0` (matching `UniProtKB.ipynb`).
2. `render_quaternary_summary_card(output)`: Formatted biological summary card highlighting assembly classification, stoichiometry, subunit count, and segregated confidence provenance.
"""
    cells.append(create_markdown_cell(visual_md))

    # 2. Visual Helpers Code Cell
    visual_code = r'''# Collapsible JSON Tree Viewer and Styled Biological Summary Card

def show_json(data, max_depth=1):
    """
    Renders JSON in a VS Code style dark tree view with collapsible arrows.
    Supports Pydantic models, dictionaries, lists, and JSON strings.
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass
    elif hasattr(data, "__dict__") and not isinstance(data, dict):
        data = vars(data)

    container_id = f"json_viewer_{uuid.uuid4().hex[:8]}"
    json_str = json.dumps(data, default=str)

    html_code = f"""
    <div id="{container_id}" style="background-color: #1e1e1e; padding: 14px; border-radius: 6px; font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace; font-size: 13px; text-align: left; overflow-x: auto;">
        <noscript><pre style="color: #d4d4d4; margin: 0;">{json_str}</pre></noscript>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/renderjson@1.4.0/renderjson.min.js"></script>
    <script>
        (function() {{
            if (typeof renderjson !== 'undefined') {{
                renderjson.set_show_to_level({max_depth});
                renderjson.set_icons('&#9654; ', '&#9660; ');
                var container = document.getElementById("{container_id}");
                if (container) {{
                    container.innerHTML = '';
                    container.appendChild(renderjson({json_str}));
                }}
            }} else {{
                var container = document.getElementById("{container_id}");
                if (container) {{
                    container.innerHTML = '<pre style="color: #d4d4d4; margin: 0; font-family: monospace;">' + JSON.stringify({json_str}, null, 2) + '</pre>';
                }}
            }}
        }})();
    </script>

    <style>
        #{container_id} .renderjson {{ color: #d4d4d4; line-height: 1.5; }}
        #{container_id} .renderjson .disclosure {{ color: #808080; cursor: pointer; text-decoration: none; font-weight: bold; margin-right: 2px; }}
        #{container_id} .renderjson .disclosure:hover {{ color: #ffffff; }}
        #{container_id} .renderjson .syntax {{ color: #ffd700; }}
        #{container_id} .renderjson .string {{ color: #ce9178; }}
        #{container_id} .renderjson .number {{ color: #b5cea8; }}
        #{container_id} .renderjson .boolean {{ color: #569cd6; }}
        #{container_id} .renderjson .key {{ color: #9cdcfe; }}
        #{container_id} .renderjson .keyword {{ color: #c586c0; }}
    </style>
    """
    display(HTML(html_code))


def render_quaternary_summary_card(output: QuaternaryStructureOutput) -> None:
    """Render a styled HTML summary table displaying top-level biological metrics."""
    if not isinstance(output, QuaternaryStructureOutput):
        if isinstance(output, dict):
            output = QuaternaryStructureOutput.model_validate(output)

    assembly_type = output.stoichiometry.assembly_type
    assembly_val = assembly_type.value if hasattr(assembly_type, "value") else str(assembly_type)
    formula = getattr(output.stoichiometry, "formula", None) or getattr(output.stoichiometry, "stoichiometry_formula", "Uncharacterized")
    total_subunits = getattr(output.stoichiometry, "total_subunits", None) or getattr(output.stoichiometry, "total_subunit_count", 1)
    oligo_state = getattr(output, "oligomeric_state", None) or f"{total_subunits}-mer"

    conflict_detected = False
    if hasattr(output, "experimental_conflict") and output.experimental_conflict:
        conflict_detected = getattr(output.experimental_conflict, "conflict_detected", False)
    elif hasattr(output, "experimental_conflicts") and output.experimental_conflicts:
        conflict_detected = bool(output.experimental_conflicts)

    if conflict_detected:
        conflict_badge = '<span style="background: #5a1e1e; color: #ff7b72; padding: 3px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">&#9888; CONFLICT DETECTED</span>'
    else:
        conflict_badge = '<span style="background: #1e3a24; color: #7ee787; padding: 3px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">&#10004; CONSENSUS ALIGNED</span>'

    prov = getattr(output, "confidence_provenance", None)
    pisa = getattr(prov, "pdbe_pisa", None) if prov else None
    if pisa and getattr(pisa, "dissociation_energy_kcal_mol", None) is not None:
        pisa_score = f"{pisa.dissociation_energy_kcal_mol:.1f} kcal/mol"
    elif pisa and getattr(pisa, "buried_surface_area_angstrom2", None) is not None:
        pisa_score = f"{pisa.buried_surface_area_angstrom2:.0f} Å²"
    else:
        pisa_score = "N/A"

    swiss = getattr(prov, "swissmodel", None) if prov else None
    swiss_qmqe = f"{swiss.qmqe:.2f}" if (swiss and getattr(swiss, "qmqe", None) is not None) else (
        f"{swiss.gmqe:.2f}" if (swiss and getattr(swiss, "gmqe", None) is not None) else "N/A"
    )

    af = getattr(prov, "alphafold_db", None) if prov else None
    af_plddt = f"{af.global_plddt:.1f}" if (af and getattr(af, "global_plddt", None) is not None) else "N/A"

    afm = getattr(prov, "alphafold_multimer", None) if prov else None
    af_iptm = f"{afm.iptm:.2f}" if (afm and getattr(afm, "iptm", None) is not None) else "N/A"

    interfaces_list = getattr(output, "interfaces", None) or getattr(output, "interface_contacts", [])
    interfaces_count = len(interfaces_list) if interfaces_list else 0

    card_html = f"""
    <div style="background-color: #1e1e1e; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 15px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #c9d1d9;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 12px; margin-bottom: 16px;">
            <div style="font-size: 18px; font-weight: 700; color: #58a6ff;">
                &#129516; Quaternary Structure Summary: <span style="color: #79c0ff;">{output.analysis_id}</span>
            </div>
            <div>{conflict_badge}</div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 18px;">
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #58a6ff;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Assembly Type</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{assembly_val}</div>
            </div>
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #7ee787;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Stoichiometry</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{formula}</div>
            </div>
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #d2a8ff;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Subunits / Oligomer</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{total_subunits} ({oligo_state})</div>
            </div>
            <div style="background: #252526; padding: 12px; border-radius: 6px; border-left: 3px solid #ffa657;">
                <div style="font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px;">Interface Contacts</div>
                <div style="font-size: 16px; font-weight: bold; color: #f0f6fc; margin-top: 4px;">{interfaces_count} Pairwise</div>
            </div>
        </div>

        <div style="background: #161b22; border-radius: 6px; padding: 14px; border: 1px solid #30363d;">
            <div style="font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px;">
                &#128202; Segregated Confidence Metrics (Zero Synthetic Blending)
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; font-size: 12.5px;">
                <div><span style="color: #8b949e;">PDBe PISA Score:</span> <strong style="color: #58a6ff;">{pisa_score}</strong></div>
                <div><span style="color: #8b949e;">SWISS-MODEL QMQE:</span> <strong style="color: #7ee787;">{swiss_qmqe}</strong></div>
                <div><span style="color: #8b949e;">AlphaFold pLDDT:</span> <strong style="color: #d2a8ff;">{af_plddt}</strong></div>
                <div><span style="color: #8b949e;">AlphaFold ipTM:</span> <strong style="color: #ffa657;">{af_iptm}</strong></div>
            </div>
        </div>
    </div>
    """
    display(HTML(card_html))

print(" Visualization helpers initialized: show_json(), render_quaternary_summary_card()")
'''
    cells.append(create_code_cell(visual_code))

    # 3. Part 1 Markdown Header
    part1_md = r"""## Part 1: High-Level Quickstart Facade (Single-Line Execution)

The quickest way to characterize a target protein's quaternary structure is via `analyze_quaternary()`.
This single high-level function:
1. Initializes an internal analysis session.
2. Coordinates experimental queries (UniProt SUBUNIT, RCSB PDB assemblies, PDBe PISA interface chemistry).
3. Evaluates homology templates (SWISS-MODEL) and predictive structural models (AlphaFold-DB / Multimer).
4. Synthesizes a unified, validated `QuaternaryStructureOutput` contract.
"""
    cells.append(create_markdown_cell(part1_md))

    # 4. Part 1 Execution Cell
    part1_code = r'''# Execute complete quaternary characterization via high-level façade
print(f"[START] Executing analyze_quaternary for target: {TARGET_PROTEIN} ...")
t0 = time.time()
output = analyze_quaternary(TARGET_PROTEIN, config=config, enable_multimer=ENABLE_MULTIMER)
elapsed = time.time() - t0
print(f"[COMPLETE] Characterization completed in {elapsed:.2f}s | Status: {output.status.value}")
'''
    cells.append(create_code_cell(part1_code))

    # 5. Part 1 Summary Card Display Cell
    part1_summary_code = r'''# Render formatted biological metric summary table
render_quaternary_summary_card(output)
'''
    cells.append(create_code_cell(part1_summary_code))

    # 6. Part 1 JSON Tree Inspection Cell
    part1_tree_code = r'''# Collapsible dark-tree inspection of the complete QuaternaryStructureOutput
print("Interactive JSON Inspection (click arrows to expand/collapse nested nodes):")
show_json(output, max_depth=1)
'''
    cells.append(create_code_cell(part1_tree_code))

    # 7. Part 2 Markdown Header
    part2_md = r"""## Part 2: Step-by-Step Modular Session Walkthrough

For scientific workflows requiring fine-grained control or intermediate stage inspection, `QuaternarySession` exposes individual stage runners (`run_stage_1_...` through `run_stage_6_...`).

Each stage updates internal session state independently with non-fatal fallbacks, preserving evidence provenance across all experimental and predictive providers.
"""
    cells.append(create_markdown_cell(part2_md))

    # 8. Part 2 Session Initialization Cell
    part2_init_code = r'''# Instantiate modular QuaternarySession
session = QuaternarySession(TARGET_PROTEIN, config=config)
print(f" QuaternarySession created:")
print(f"  - Session ID: {session.session_id}")
print(f"  - Target: {session.target_input}")
print(f"  - Initial Status: {session.status.value}")
'''
    cells.append(create_code_cell(part2_init_code))

    # 9. Part 2 Stages 1 & 2 Cell
    part2_stages_1_2_code = r'''# Stage 1: UniProt SUBUNIT Annotation & Stage 2: RCSB PDB Experimental Assemblies
print("[STAGE 1/6: UNIPROT SUBUNIT] Querying curated subunit annotations...")
r1 = session.run_stage_1_uniprot_subunit()
print(f"  -> Status: {r1.status.value} | Summary: {r1.details.get('summary', 'Completed')}")

print("\n[STAGE 2/6: PDB EXPERIMENTAL] Searching experimental biological assemblies...")
r2 = session.run_stage_2_pdb_experimental()
assemblies_found = r2.data.get('assemblies', []) if r2.data else []
print(f"  -> Status: {r2.status.value} | Assemblies Found: {len(assemblies_found)}")
'''
    cells.append(create_code_cell(part2_stages_1_2_code))

    # 10. Part 2 Stages 3 & 4 Cell
    part2_stages_3_4_code = r'''# Stage 3: PDBe PISA Interface Biophysics & Stage 4: SWISS-MODEL Homology Templates
print("[STAGE 3/6: PISA INTERFACES] Computing interface contacts and solvation free energy...")
r3 = session.run_stage_3_pisa_interfaces()
interfaces_found = r3.data.get('interfaces', []) if r3.data else []
print(f"  -> Status: {r3.status.value} | Interfaces Analyzed: {len(interfaces_found)}")

print("\n[STAGE 4/6: SWISS-MODEL HOMOLOGY] Querying oligomeric homology templates...")
r4 = session.run_stage_4_swiss_model()
models_found = r4.data.get('models', []) if r4.data else []
print(f"  -> Status: {r4.status.value} | Homology Models: {len(models_found)}")
'''
    cells.append(create_code_cell(part2_stages_3_4_code))

    # 11. Part 2 Stages 5 & 6 Cell
    part2_stages_5_6_code = r'''# Stage 5: AlphaFold Structural Context & Stage 6: Multi-Evidence Synthesis
print(f"[STAGE 5/6: ALPHAFOLD CONTEXT] Inspecting structural predictions (Multimer enabled: {ENABLE_MULTIMER})...")
r5 = session.run_stage_5_alphafold_context(enable_multimer=ENABLE_MULTIMER)
print(f"  -> Status: {r5.status.value}")

print("\n[STAGE 6/6: SYNTHESIS AGGREGATOR] Resolving consensus quaternary stoichiometry...")
r6 = session.run_stage_6_aggregate()
print(f"  -> Status: {r6.status.value}")
print(f"  -> Final Stoichiometry Formula: {session.output.stoichiometry.stoichiometry_formula}")
print(f"  -> Assembly Classification: {session.output.stoichiometry.assembly_type.value}")
'''
    cells.append(create_code_cell(part2_stages_5_6_code))

    # 12. Part 2 Stage Results Tree Inspection Cell
    part2_stages_tree_code = r'''# Inspect multi-stage evidence payloads across all 6 stages
print("Multi-Stage Evidence Payloads (StageResult dictionary):")
show_json(session.stage_results, max_depth=1)
'''
    cells.append(create_code_cell(part2_stages_tree_code))

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
    cells = build_wave_1_cells() + build_wave_2_cells()
    nb = assemble_notebook(cells)
    write_notebook(nb)


if __name__ == "__main__":
    main()

