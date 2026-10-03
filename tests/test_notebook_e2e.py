"""
End-to-End Headless Execution & Schema Validation Test for Quaternary_Structure.ipynb

Executes all code cells in Quaternary_Structure.ipynb sequentially in a shared namespace
under offline fixture mode, asserting zero unhandled exceptions and verifying that
quaternary_structure_output.json is produced and conforms strictly to the Pydantic v2 contract.
"""

from pathlib import Path
import json
import pytest
import nbformat
from IPython.display import HTML

from quaternary.config import QuaternaryConfig
from quaternary.models import QuaternaryStructureOutput


@pytest.fixture(scope="module")
def notebook_path():
    """Ensure Quaternary_Structure.ipynb exists."""
    p = Path("Quaternary_Structure.ipynb")
    assert p.exists(), "Quaternary_Structure.ipynb must exist at project root."
    return p


def test_notebook_markdown_commentary_content(notebook_path):
    """
    Verify Task 2 & 3 requirements:
    Notebook contains educational commentary on Stoichiometry, Interface Biophysics,
    Confidence Provenance, and Dual Showcase documentation for GroEL and H. influenzae.
    """
    with open(notebook_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    md_sources = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")

    # Stoichiometry & Notation
    assert "Stoichiometry & Notation Guide" in md_sources
    assert "A_{14}" in md_sources or "A_{2}" in md_sources

    # Interface Biophysics & BSA
    assert "Buried Surface Area" in md_sources
    assert "Solvation Free Energy" in md_sources or "Delta G" in md_sources or "\u0394G" in md_sources or r"\Delta G" in md_sources

    # Confidence Provenance
    assert "Zero Synthetic Blending" in md_sources
    assert "ExperimentalConflict" in md_sources or "Crystallographic vs Solution" in md_sources

    # Dual Showcase Target references
    assert "P0A6F5" in md_sources
    assert "P44101" in md_sources
    assert "UP000000579" in md_sources


def test_notebook_e2e_execution(notebook_path, tmp_path, monkeypatch):
    """
    Execute all code cells of Quaternary_Structure.ipynb sequentially in offline mode.
    Verify zero exceptions, successful execution of all stages, and valid output JSON contract.
    """
    with open(notebook_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    # Clean previous output artifact if present
    output_contract_path = Path("quaternary_structure_output.json")
    if output_contract_path.exists():
        output_contract_path.unlink()

    # Prepare shared execution namespace
    execution_ns = {
        "__name__": "__main__",
        "display": lambda *args, **kwargs: None,
        "HTML": HTML,
    }

    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    assert len(code_cells) >= 10, "Notebook should contain multiple code cells."

    # Force offline mode for deterministic, non-flaky execution
    # Inject config override after cell 2 or in namespace
    executed_cells = 0
    for idx, cell in enumerate(code_cells):
        code = cell.source

        # In configuration cell, enforce offline_mode=True
        if "config = QuaternaryConfig(" in code:
            code = code.replace("offline_mode=False", "offline_mode=True")

        try:
            compiled_code = compile(code, f"<cell_{idx}>", "exec")
            exec(compiled_code, execution_ns)
            executed_cells += 1
        except Exception as exc:
            pytest.fail(f"Cell {idx} failed with unhandled exception:\nCode:\n{code}\nError: {exc}")

    assert executed_cells == len(code_cells), "All code cells must execute successfully."

    # Verify quaternary_structure_output.json was generated
    assert output_contract_path.exists(), "quaternary_structure_output.json must be created by export cell."
    assert output_contract_path.stat().st_size > 50, "Exported JSON must not be empty."

    # Validate against QuaternaryStructureOutput schema
    json_bytes = output_contract_path.read_text(encoding="utf-8")
    parsed_output = QuaternaryStructureOutput.model_validate_json(json_bytes)

    assert parsed_output.analysis_id is not None
    assert parsed_output.stoichiometry is not None
    assert parsed_output.stoichiometry.assembly_type is not None
    assert parsed_output.confidence_provenance is not None
