"""
Tests for Quaternary_Structure.ipynb Visualizations and Workflow Sequencing

Asserts show_json rendering, HTML summary card metric presentation, rich biological
audit tables (Component Identity, Interface Contacts, Evidence Coverage, Dynamic Multi-Assembly,
Functional Inference), canonical Part 1 -> Part 2 cell sequence integrity, and
zero hardcoded statistics in markdown cells.
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
    EvidenceStatus,
    TargetSelfAssembly,
    FunctionalComplex,
    ObservedAssembly,
    InferredFunction,
    EvidenceCoverage,
    ConfidenceProvenance,
    PisaConfidence,
    SwissModelConfidence,
    AlphaFoldConfidence,
    MultimerConfidence,
    InterfaceContact,
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
    """Extract and execute visual helper functions from notebook code cells."""
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
        "re": __import__("re"),
        "display": mock_display,
        "HTML": HTML,
        "QuaternaryStructureOutput": QuaternaryStructureOutput,
    }

    exec(visual_cell, ns)
    return {
        "show_json": ns["show_json"],
        "render_quaternary_summary_card": ns["render_quaternary_summary_card"],
        "render_component_identity_table": ns["render_component_identity_table"],
        "render_interface_contact_table": ns["render_interface_contact_table"],
        "render_functional_inference_card": ns["render_functional_inference_card"],
        "render_dynamic_equilibrium_display": ns["render_dynamic_equilibrium_display"],
        "render_evidence_coverage_dashboard": ns["render_evidence_coverage_dashboard"],
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

    assert "TEST_GROEL_001" in card_html
    assert "HOMOMER" in card_html
    assert "A14" in card_html
    assert "14" in card_html
    assert "-12.5 kcal/mol" in card_html
    assert "0.88" in card_html
    assert "91.5" in card_html
    assert "0.85" in card_html
    assert "CONSENSUS ALIGNED" in card_html


def test_component_identity_table_renders_valid_html(visual_helpers):
    """Verify render_component_identity_table formats target and partner complexes."""
    render_table = visual_helpers["render_component_identity_table"]
    displayed = visual_helpers["displayed_items"]

    displayed.clear()
    mock_output = QuaternaryStructureOutput(
        analysis_id="TEST_COMP_001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=Stoichiometry.from_formula("A14"),
        target_self_assembly=TargetSelfAssembly(
            formula="A14",
            assembly_type=AssemblyType.HOMOMER,
            subunit_count=14,
            symmetry="D7",
            confidence_status=EvidenceStatus.CONFIRMED,
        ),
        functional_complexes=[
            FunctionalComplex(
                name="GroEL-GroES Chaperonin Complex",
                stoichiometry="A14B7",
                partner_uniprot_accessions=["P0A6G7"],
                partner_names=["Co-chaperonin GroES"],
                complex_portal_id="CPX-1896",
                evidence="Curated Complex Portal entry",
            )
        ],
        metadata={"gene_name": "groEL", "organism": "Escherichia coli"},
    )

    render_table(mock_output)
    assert len(displayed) == 1
    table_html = displayed[0].data

    assert "Macromolecular Component Identity Table" in table_html
    assert "TARGET SUBUNIT" in table_html
    assert "PARTNER COMPLEX" in table_html
    assert "P0A6F5" in table_html
    assert "P0A6G7" in table_html
    assert "14" in table_html
    assert "7" in table_html
    assert "groEL (Escherichia coli)" in table_html
    assert "Co-chaperonin GroES" in table_html


def test_interface_contact_table_renders_valid_html(visual_helpers):
    """Verify render_interface_contact_table formats BSA, ΔiG, and residues."""
    render_iface = visual_helpers["render_interface_contact_table"]
    displayed = visual_helpers["displayed_items"]

    # 1. With interfaces
    displayed.clear()
    mock_output = QuaternaryStructureOutput(
        analysis_id="TEST_IFACE_001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=Stoichiometry.from_formula("A14"),
        interfaces=[
            InterfaceContact(
                chain_1="A",
                chain_2="B",
                buried_surface_area_angstrom2=1500.4,
                solvation_free_energy_kcal_mol=-23.4,
                hydrogen_bonds_count=16,
                salt_bridges_count=2,
                interface_residues_chain_1=[2, 3, 4, 6, 8, 13, 65],
                interface_residues_chain_2=[22, 25, 26, 29, 33, 34],
            )
        ],
    )

    render_iface(mock_output)
    assert len(displayed) == 1
    iface_html = displayed[0].data

    assert "Pairwise Interface Contact Residues" in iface_html
    assert "1,500.4 &#197;&#178;" in iface_html or "1,500.4 Å²" in iface_html
    assert "-23.40 kcal/mol" in iface_html
    assert "16" in iface_html
    assert "2" in iface_html
    assert "A &mdash; B" in iface_html or "A — B" in iface_html

    # 2. Empty interfaces (monomer baseline)
    displayed.clear()
    mock_monomer = QuaternaryStructureOutput(
        analysis_id="TEST_MONO_001",
        target_accession_or_sequence="P44101",
        quaternary_status="MONOMER",
        stoichiometry=Stoichiometry.from_formula("A"),
        interfaces=[],
    )
    render_iface(mock_monomer)
    assert len(displayed) == 1
    assert "No multimer interfaces detected" in displayed[0].data


def test_functional_inference_card_renders_valid_html(visual_helpers):
    """Verify render_functional_inference_card renders molecular function, hypothesis, and badges."""
    render_card = visual_helpers["render_functional_inference_card"]
    displayed = visual_helpers["displayed_items"]

    displayed.clear()
    mock_output = QuaternaryStructureOutput(
        analysis_id="TEST_FUNC_001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=Stoichiometry.from_formula("A14"),
        inferred_function=InferredFunction(
            molecular_function="Molecular Chaperone (Protein Folding & Refolding Cage)",
            biological_process="Protein folding, stress response, aggregation prevention",
            oligomeric_mechanism_hypothesis="Double-ring tetradecamer creates an enclosed hydrophilic folding chamber.",
            archetype_name="CHAPERONIN_CAGE",
            confidence=0.95,
            status=EvidenceStatus.CONFIRMED,
            functional_homologs=[
                {"pdb_id": "1AON", "identity": 0.99, "function": "Chaperonin folding cage"}
            ],
            go_terms=[
                {"id": "GO:0006457", "name": "protein folding"},
                {"id": "GO:0051082", "name": "unfolded protein binding"},
            ],
        ),
    )

    render_card(mock_output)
    assert len(displayed) == 1
    card_html = displayed[0].data

    assert "Executive Bio-Mechanistic Card: Functional Inference" in card_html
    assert "HIGH CONFIDENCE (0.95)" in card_html
    assert "Molecular Chaperone" in card_html
    assert "Double-ring tetradecamer" in card_html
    assert "PDB 1AON" in card_html
    assert "protein folding" in card_html


def test_dynamic_equilibrium_display_renders_valid_html(visual_helpers):
    """Verify render_dynamic_equilibrium_display renders multi-assembly equilibrium states."""
    render_display = visual_helpers["render_dynamic_equilibrium_display"]
    displayed = visual_helpers["displayed_items"]

    displayed.clear()
    mock_output = QuaternaryStructureOutput(
        analysis_id="TEST_EQUIL_001",
        target_accession_or_sequence="P01308",
        quaternary_status="HOMOMER",
        stoichiometry=Stoichiometry.from_formula("A2"),
        observed_assemblies=[
            ObservedAssembly(
                pdb_id="4INS",
                assembly_id="1",
                stoichiometry="A6",
                biological_assembly_type="Hexamer (Storage Form)",
                conditions="Zinc-stabilized hexamer in storage buffer",
                is_target_self=False,
                delta_g_diss_kcal_mol=-24.5,
                primary_physiological_state="Storage Hexamer",
            ),
            ObservedAssembly(
                pdb_id="2INS",
                assembly_id="1",
                stoichiometry="A2",
                biological_assembly_type="Dimer (Active Form)",
                conditions="Zinc-free physiological dimer",
                is_target_self=True,
                delta_g_diss_kcal_mol=-12.2,
                primary_physiological_state="Active Circulating Dimer",
            ),
        ],
    )

    render_display(mock_output)
    assert len(displayed) == 1
    equil_html = displayed[0].data

    assert "Dynamic Multi-Assembly Equilibrium & Observed States" in equil_html
    assert "PDB 4INS" in equil_html
    assert "A6" in equil_html
    assert "Storage Hexamer" in equil_html
    assert "PDB 2INS" in equil_html
    assert "A2" in equil_html
    assert "Target Self-Assembly" in equil_html


def test_evidence_coverage_dashboard_renders_valid_html(visual_helpers):
    """Verify render_evidence_coverage_dashboard renders queried databases and gaps."""
    render_dash = visual_helpers["render_evidence_coverage_dashboard"]
    displayed = visual_helpers["displayed_items"]

    displayed.clear()
    mock_output = QuaternaryStructureOutput(
        analysis_id="TEST_COV_001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=Stoichiometry.from_formula("A14"),
        evidence_coverage=EvidenceCoverage(
            databases_queried=[
                {"database": "UniProtKB", "queried": True, "hit": True},
                {"database": "Complex Portal", "queried": True, "hit": True},
                {"database": "PDBe PISA", "queried": True, "hit": True},
                {"database": "ColabFold / AlphaFold-Multimer", "queried": False, "hit": False},
            ],
            evidence_gaps=["External multimer live compute absent"],
        ),
    )

    render_dash(mock_output)
    assert len(displayed) == 1
    dash_html = displayed[0].data

    assert "Evidence Coverage & Gaps Dashboard" in dash_html
    assert "UniProtKB" in dash_html
    assert "HIT FOUND" in dash_html
    assert "ColabFold / AlphaFold-Multimer" in dash_html
    assert "SKIPPED / UNCONFIGURED" in dash_html
    assert "External multimer live compute absent" in dash_html


def test_notebook_cell_sequence_integrity(notebook):
    """Verify Part 1 precedes Part 2, and all canonical stages 1 through 6 are present in order without obsolete aliases."""
    sources = [c.source for c in notebook.cells]

    # Find Part 1 and Part 2 positions
    part1_idx = next(i for i, s in enumerate(sources) if "Part 1: High-Level Quickstart Facade" in s)
    part2_idx = next(i for i, s in enumerate(sources) if "Part 2: Step-by-Step Modular Session Walkthrough" in s)

    assert part1_idx < part2_idx, "Part 1 must precede Part 2 in notebook layout."

    # Verify canonical stage runner calls appear in sequence in code cells
    code_sources = [c.source for c in notebook.cells if c.cell_type == "code"]
    combined_code = "\n".join(code_sources)

    canonical_methods = [
        "run_stage_1_sequence_and_accession",
        "run_stage_2_experimental_assemblies",
        "run_stage_3_thermodynamic_qualification",
        "run_stage_4_homology_and_partners",
        "run_stage_5_predictive_multimer",
        "run_stage_6_synthesis_and_functional_inference",
    ]

    last_pos = -1
    for method in canonical_methods:
        pos = combined_code.find(method)
        assert pos != -1, f"Missing canonical method call in notebook: {method}"
        assert pos > last_pos, f"Stage method out of order: {method}"
        last_pos = pos

    # Assert zero obsolete aliases
    obsolete_methods = [
        "run_stage_1_uniprot_subunit",
        "run_stage_2_pdb_experimental",
        "run_stage_3_pisa_interfaces",
        "run_stage_4_swiss_model",
        "run_stage_5_alphafold_context",
        "run_stage_6_aggregate",
    ]
    for old_m in obsolete_methods:
        assert old_m not in combined_code, f"Obsolete method {old_m} found in notebook code!"


def test_no_hardcoded_statistics_in_markdown(notebook):
    """Enforce D-12: Zero hardcoded run statistics in markdown cells."""
    md_sources = "\n".join(c.source for c in notebook.cells if c.cell_type == "markdown")

    forbidden_patterns = [
        "ipTM: 0.84",
        "pTM: 0.81",
        "ipTM: 0.79",
        "ipTM: 0.40",
        "ipTM = 0.84",
        "ipTM = 0.53",
        "QMQE: 0.79",
        "GMQE: 0.85",
        "QMQE: 0.88",
        "pLDDT: 90.8",
        "pLDDT: 52.9",
        "pLDDT: 90.1",
        "BSA = 1,500.35",
        "ΔG = -23.42",
        "BSA = 596.08",
        "ΔG = -16.22",
        "Assembly Score: 8.0",
        "Assembly Score: 9.0",
        "Assembly Score: 5.0",
    ]

    for pat in forbidden_patterns:
        assert pat not in md_sources, f"Hardcoded static metric found in markdown: '{pat}'"
