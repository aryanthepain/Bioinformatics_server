"""
Tests for Quaternary_Structure.ipynb Visualizations and Workflow Sequencing

Asserts show_json rendering, HTML summary card metric presentation, and
Part 1 -> Part 2 cell sequence integrity.
"""

from pathlib import Path
import json
import pytest
import nbformat
from IPython.display import HTML

from quaternary.models import (
    QuaternaryStructureOutput,
    Stoichiometry,
    AssemblyType,
    ConfidenceProvenance,
    PisaConfidence,
    SwissModelConfidence,
    AlphaFoldConfidence,
    MultimerConfidence,
    StageStatus,
)


@pytest.fixture(scope="module")
def notebook():
    """Load and validate Quaternary_Structure.ipynb."""
    nb_path = Path("Quaternary_Structure.ipynb")
    assert nb_path.exists(), "Quaternary_Structure.ipynb must exist."
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    nbformat.validate(nb)
    return nb


@pytest.fixture(scope="module")
def visual_helpers(notebook):
    """Extract and execute visual helper functions (show_json, render_quaternary_summary_card)."""
    visual_cell = None
    for c in notebook.cells:
        if c.cell_type == "code" and "def show_json" in c.source and "def render_quaternary_summary_card" in c.source:
            visual_cell = c.source
            break

    assert visual_cell is not None, "Visual helpers code cell not found in notebook."

    displayed_items = []

    def mock_display(item):
        displayed_items.append(item)

    ns = {
        "json": json,
        "uuid": __import__("uuid"),
        "display": mock_display,
        "HTML": HTML,
        "QuaternaryStructureOutput": QuaternaryStructureOutput,
    }

    exec(visual_cell, ns)
    return {
        "show_json": ns["show_json"],
        "render_quaternary_summary_card": ns["render_quaternary_summary_card"],
        "displayed_items": displayed_items,
    }


def test_show_json_renders_valid_html(visual_helpers):
    """Verify show_json works for both dicts and Pydantic models with renderjson script."""
    show_json = visual_helpers["show_json"]
    displayed = visual_helpers["displayed_items"]

    # 1. Test dictionary
    displayed.clear()
    dummy_dict = {"key": "value", "numbers": [1, 2, 3]}
    show_json(dummy_dict, max_depth=2)
    assert len(displayed) == 1
    html_obj = displayed[0]
    assert isinstance(html_obj, HTML)
    html_text = html_obj.data
    assert "json_viewer_" in html_text
    assert "renderjson.set_show_to_level(2)" in html_text
    assert "renderjson.min.js" in html_text

    # 2. Test Pydantic model
    displayed.clear()
    mock_stoichiometry = Stoichiometry.from_formula("A14")
    show_json(mock_stoichiometry, max_depth=1)
    assert len(displayed) == 1
    assert "A14" in displayed[0].data


def test_summary_card_renders_quaternary_metrics(visual_helpers):
    """Verify render_quaternary_summary_card formats biological metrics properly."""
    render_card = visual_helpers["render_quaternary_summary_card"]
    displayed = visual_helpers["displayed_items"]

    displayed.clear()
    mock_output = QuaternaryStructureOutput(
        analysis_id="TEST_GROEL_001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="SUCCESS",
        stoichiometry=Stoichiometry.from_formula("A14"),
        confidence_provenance=ConfidenceProvenance(
            pdbe_pisa=PisaConfidence(dissociation_energy_kcal_mol=-12.5),
            swissmodel=SwissModelConfidence(qmqe=0.88),
            alphafold_db=AlphaFoldConfidence(global_plddt=91.5),
            alphafold_multimer=MultimerConfidence(iptm=0.85),
        ),
        interfaces=[],
    )

    render_card(mock_output)
    assert len(displayed) == 1
    card_html = displayed[0].data

    # Check key metric labels and values
    assert "TEST_GROEL_001" in card_html
    assert "HOMOMER" in card_html
    assert "A14" in card_html
    assert "14" in card_html
    assert "-12.5 kcal/mol" in card_html  # PISA score
    assert "0.88" in card_html  # QMQE
    assert "91.5" in card_html  # pLDDT
    assert "0.85" in card_html  # ipTM
    assert "CONSENSUS ALIGNED" in card_html


def test_notebook_cell_sequence_integrity(notebook):
    """Verify Part 1 precedes Part 2, and all stages 1 through 6 are present in order."""
    sources = [c.source for c in notebook.cells]

    # Find Part 1 and Part 2 positions
    part1_idx = next(i for i, s in enumerate(sources) if "Part 1: High-Level Quickstart Facade" in s)
    part2_idx = next(i for i, s in enumerate(sources) if "Part 2: Step-by-Step Modular Session Walkthrough" in s)

    assert part1_idx < part2_idx, "Part 1 must precede Part 2 in notebook layout."

    # Verify stage runner calls appear in sequence in code cells
    code_sources = [c.source for c in notebook.cells if c.cell_type == "code"]
    combined_code = "\n".join(code_sources)

    stage_methods = [
        "run_stage_1_uniprot_subunit",
        "run_stage_2_pdb_experimental",
        "run_stage_3_pisa_interfaces",
        "run_stage_4_swiss_model",
        "run_stage_5_alphafold_context",
        "run_stage_6_aggregate",
    ]

    last_pos = -1
    for method in stage_methods:
        pos = combined_code.find(method)
        assert pos != -1, f"Missing method call in notebook: {method}"
        assert pos > last_pos, f"Stage method out of order: {method}"
        last_pos = pos
