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
    for line in combined_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # Comments explaining the rule are allowed
        assert "requests.get(" not in stripped, f"Raw requests.get found: {stripped}"
        assert "requests.post(" not in stripped, f"Raw requests.post found: {stripped}"
        assert "urllib.request" not in stripped, f"Raw urllib.request found: {stripped}"
        assert "http://" not in stripped and "https://" not in stripped, f"Raw URL found in code: {stripped}"


def test_preflight_validation_logic(notebook):
    """Test the extracted validate_target_input function directly."""
    # Find cell defining validate_target_input
    validation_cell = None
    for c in notebook.cells:
        if c.cell_type == "code" and "def validate_target_input" in c.source:
            validation_cell = c.source
            break

    assert validation_cell is not None, "validate_target_input cell not found in notebook."

    # Execute validation function definition in a clean namespace
    ns = {"re": re, "display": lambda x: None, "HTML": lambda x: x}
    exec(validation_cell, ns)
    validate_func = ns["validate_target_input"]

    # 1. Valid UniProt Accessions
    assert validate_func("P0A6F5")[0] is True  # GroEL
    assert validate_func("P01308")[0] is True  # Insulin
    assert validate_func("P44101")[0] is True  # H. influenzae
    assert validate_func("Q9Y263")[0] is True

    # 2. Valid FASTA format
    fasta_valid = ">sp|P0A6F5|GROEL_ECOLI Chaperonin\nMAAKDVKFGNDARVKMLRGVNVLADAVKVTLGPKGRNVVLDKSFGAPTITKDGVSVAREIELEDKFE"
    is_valid, msg = validate_func(fasta_valid)
    assert is_valid is True

    # 3. Invalid inputs
    assert validate_func("")[0] is False
    assert validate_func("INVALID_123")[0] is False
    assert validate_func("12345")[0] is False
    assert validate_func(">header_only_no_sequence\n")[0] is False


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
