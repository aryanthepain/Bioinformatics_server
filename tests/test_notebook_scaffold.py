"""
Tests for Quaternary_Structure.ipynb Scaffold & Validation

Asserts notebook schema validity, high-level API isolation (no raw requests.get/post),
pre-flight regex validation logic, and dual-mode parameter loading.
"""

from pathlib import Path
import re
import pytest
import nbformat


@pytest.fixture(scope="module")
def notebook():
    """Load and validate Quaternary_Structure.ipynb."""
    nb_path = Path("Quaternary_Structure.ipynb")
    assert nb_path.exists(), "Quaternary_Structure.ipynb must exist at project root."
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    nbformat.validate(nb)
    return nb


def test_notebook_file_exists_and_valid_schema(notebook):
    """Verify Quaternary_Structure.ipynb exists and adheres to nbformat v4."""
    assert notebook.nbformat == 4
    assert len(notebook.cells) >= 5
    # Verify presence of title and markdown cells
    md_cells = [c.source for c in notebook.cells if c.cell_type == "markdown"]
    assert any("Quaternary Protein Structure & Complex Annotation Engine" in m for m in md_cells)


def test_notebook_no_raw_http(notebook):
    """
    Enforce QUAT-06: Code cells must never invoke raw HTTP requests directly.
    All networking must be abstracted inside quaternary_pipeline.
    """
    code_cells = [c.source for c in notebook.cells if c.cell_type == "code"]
    combined_code = "\n".join(code_cells)

    # Assert high-level import
    assert "from quaternary_pipeline import" in combined_code
    assert "analyze_quaternary" in combined_code

    # Assert no raw HTTP calls
    forbidden_clients = ["requests.get(", "requests.post(", "urllib.request", "httpx.", "aiohttp."]
    for line in combined_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # Comments explaining the rule are allowed
        for client in forbidden_clients:
            assert client not in stripped, f"Raw HTTP client call found: {stripped}"

        # Ensure no bioinformatics API endpoint URLs are called directly in cells
        bio_api_hosts = ["rest.uniprot.org", "data.rcsb.org", "ebi.ac.uk", "swissmodel.expasy.org", "alphafold.ebi.ac.uk"]
        for host in bio_api_hosts:
            assert host not in stripped, f"Bioinformatics API URL found directly in code: {stripped}"


def test_preflight_validation_logic(notebook):
    """Verify validate_target_input is cleanly imported from quaternary.presentation without inline definitions."""
    code_cells = [c.source for c in notebook.cells if c.cell_type == "code"]
    combined_code = "\n".join(code_cells)

    # Enforce D-01 & D-03: Modular import and zero inline boilerplate
    assert "from quaternary.presentation import" in combined_code and "validate_target_input" in combined_code
    assert "def validate_target_input" not in combined_code, (
        "Inline definition of validate_target_input found; should be imported from quaternary.presentation"
    )

    # Execute and test function behavior
    from quaternary.presentation import validate_target_input

    # 1. Valid UniProt Accessions
    assert validate_target_input("P0A6F5")[0] is True  # GroEL
    assert validate_target_input("P01308")[0] is True  # Insulin
    assert validate_target_input("P44101")[0] is True  # H. influenzae
    assert validate_target_input("Q9Y263")[0] is True

    # 2. Valid FASTA format
    fasta_valid = ">sp|P0A6F5|GROEL_ECOLI Chaperonin\nMAAKDVKFGNDARVKMLRGVNVLADAVKVTLGPKGRNVVLDKSFGAPTITKDGVSVAREIELEDKFE"
    is_valid, msg = validate_target_input(fasta_valid)
    assert is_valid is True

    # 3. Invalid inputs
    assert validate_target_input("")[0] is False
    assert validate_target_input("INVALID_123")[0] is False
    assert validate_target_input("12345")[0] is False
    assert validate_target_input(">header_only_no_sequence\n")[0] is False


def test_dual_mode_fallback(notebook):
    """Verify that declarative fallback variables exist and can be loaded cleanly."""
    input_cell = None
    for c in notebook.cells:
        if c.cell_type == "code" and "TARGET_PROTEIN =" in c.source:
            input_cell = c.source
            break

    assert input_cell is not None, "Dual-mode input cell not found."

    # Verify fallback declarative assignments are present
    assert "TARGET_PROTEIN = " in input_cell
    assert "ENABLE_MULTIMER = " in input_cell
    assert "P0A6F5" in input_cell
    assert "P01308" in input_cell
    assert "P44101" in input_cell


def test_canonical_stage_headers(notebook):
    """Verify notebook contains canonical stage markdown headers for Stages 1 through 6."""
    md_sources = "\n".join(c.source for c in notebook.cells if c.cell_type == "markdown")
    for stage_num in range(1, 7):
        assert f"Stage {stage_num}" in md_sources, f"Missing header for Stage {stage_num}"


def test_no_obsolete_stage_methods(notebook):
    """Verify zero obsolete stage method names exist in any code cell."""
    code_sources = "\n".join(c.source for c in notebook.cells if c.cell_type == "code")
    obsolete_methods = [
        "run_stage_1_uniprot_subunit",
        "run_stage_2_pdb_experimental",
        "run_stage_3_pisa_interfaces",
        "run_stage_4_swiss_model",
        "run_stage_5_alphafold_context",
        "run_stage_6_aggregate",
    ]
    for method in obsolete_methods:
        assert method not in code_sources, f"Obsolete method {method} found in notebook code!"


def test_target_selection_card_modularization(notebook):
    """
    Enforce D-13: Cell 5 renders target selection via render_target_selection_card,
    with zero inline panel_html raw string formatting.
    """
    code_cells = [c.source for c in notebook.cells if c.cell_type == "code"]
    combined_code = "\n".join(code_cells)

    assert "render_target_selection_card" in combined_code
    # Locate the cell rendering the target selection card
    card_cell = next((c for c in code_cells if "render_target_selection_card(" in c), None)
    assert card_cell is not None, "Target selection card render cell not found in notebook."
    assert "panel_html =" not in card_cell, "Raw panel_html string assignment found in target selection cell!"
    assert "display(render_target_selection_card(" in card_cell


def test_no_redundant_visual_helper_cells(notebook):
    """
    Enforce D-13: The redundant Wave 2 visual helper code cell is absent.
    All helpers are imported once in setup and not redefined or re-imported.
    """
    code_cells = [c.source for c in notebook.cells if c.cell_type == "code"]
    wave2_helper_cells = [
        c for c in code_cells
        if "Interactive Visualization Helpers & Biological Summary Displays" in c
        or "def render_quaternary_summary_card" in c
    ]
    assert len(wave2_helper_cells) == 0, "Redundant visual helper code cell found in notebook!"


