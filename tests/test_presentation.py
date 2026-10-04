"""
Unit Tests for Quaternary Presentation Library (quaternary.presentation).

Deterministically verifies isolated behavior of:
- validate_target_input (UniProtKB accessions, FASTA headers, non-IUPAC handling, empty strings)
- render_validation_status (success/error banners, checkmark/warning icons)
- show_json (collapsible dark tree viewer, depth configuration, dicts & Pydantic models)
- render_quaternary_summary_card (oligomeric metrics, consensus badges, segregated provenance)
- render_component_identity_table (target subunit, partner complexes, stoichiometric copies)
- render_interface_contact_table (biophysical contact parameters, monomer empty fallback)
- render_dynamic_equilibrium_display (multi-assembly crystallography states, invariant fallback)
- render_functional_inference_card (molecular function, biological process, mechanism, GO badges)
- render_evidence_coverage_dashboard (database audit rows, hit badges, scientific uncertainties)

Architectural Verification:
Every render_* and show_json function must return an IPython.display.HTML object without
triggering display() side-effects.
"""

import pytest
from IPython.display import HTML

from quaternary.presentation import (
    validate_target_input,
    render_validation_status,
    show_json,
    render_quaternary_summary_card,
    render_component_identity_table,
    render_interface_contact_table,
    render_dynamic_equilibrium_display,
    render_functional_inference_card,
    render_evidence_coverage_dashboard,
)
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


# ---------------------------------------------------------------------------
# 1. Pre-Flight Input Validation Tests
# ---------------------------------------------------------------------------

def test_validate_target_input_valid_accessions():
    """Verify validation of canonical UniProt accessions."""
    valid_ids = ["P0A6F5", "P01308", "P44101", "Q9Y263", "O15552", "P69905"]
    for acc in valid_ids:
        is_valid, msg = validate_target_input(acc)
        assert is_valid is True, f"Expected {acc} to be valid"
        assert "Valid UniProtKB accession" in msg
        assert acc in msg


def test_validate_target_input_valid_fasta():
    """Verify validation of multiline FASTA input."""
    fasta = (
        ">sp|P0A6F5|GROEL_ECOLI 60 kDa chaperonin OS=Escherichia coli\n"
        "MAAKDVKFGNDARVKMLRGVNVLADAVKVTLGPKGRNVVLDKSFGAPTITKDGVSVARE\n"
        "IELEDKFENMGAQMVKEVASKANDAAGDGTTTATVLAQAIITEGLKAVAAGMNPMDLKRG\n"
    )
    is_valid, msg = validate_target_input(fasta)
    assert is_valid is True
    assert "Valid FASTA sequence" in msg
    assert "residues" in msg


def test_validate_target_input_valid_raw_sequence():
    """Verify validation of raw single-line amino acid sequence."""
    raw_seq = "MAAKDVKFGNDARVKMLRGVNVLADAVKVTLGPKGRNVVLDKSFGAPTITKDGV"
    is_valid, msg = validate_target_input(raw_seq)
    assert is_valid is True
    assert "Valid raw amino acid sequence" in msg


def test_validate_target_input_invalid_inputs():
    """Verify rejection of empty, malformed, non-IUPAC, or header-only strings."""
    # Empty / whitespace
    assert validate_target_input("")[0] is False
    assert validate_target_input("   ")[0] is False
    assert validate_target_input(None)[0] is False  # type: ignore

    # Header-only FASTA
    is_valid, msg = validate_target_input(">only_header_no_residues\n")
    assert is_valid is False
    assert "FASTA format requires a header line" in msg or "contains no amino acid" in msg

    # Non-IUPAC characters in FASTA
    is_valid, msg = validate_target_input(">seq\nMAAK1234$#@!\n")
    assert is_valid is False
    assert "invalid non-IUPAC" in msg

    # Random invalid string
    is_valid, msg = validate_target_input("NOT_AN_ACCESSION_OR_SEQ")
    assert is_valid is False
    assert "Invalid input" in msg


# ---------------------------------------------------------------------------
# 2. Validation Status Banner Rendering
# ---------------------------------------------------------------------------

def test_render_validation_status_banners():
    """Verify HTML banner generation for success and warning states."""
    # Success banner
    success_html = render_validation_status(True, "Input verified successfully.")
    assert isinstance(success_html, HTML)
    assert "INPUT VERIFIED" in success_html.data
    assert "#1e3a24" in success_html.data  # green bg
    assert "#2ea043" in success_html.data  # green border
    assert "Input verified successfully." in success_html.data

    # Warning banner
    fail_html = render_validation_status(False, "Invalid sequence format.")
    assert isinstance(fail_html, HTML)
    assert "VALIDATION WARNING" in fail_html.data
    assert "#4a1c1c" in fail_html.data  # red bg
    assert "#f85149" in fail_html.data  # red border
    assert "Invalid sequence format." in fail_html.data


# ---------------------------------------------------------------------------
# 3. Interactive JSON Tree Viewer (show_json)
# ---------------------------------------------------------------------------

def test_show_json_renders_html_object():
    """Verify show_json constructs pure HTML with renderjson.js and unique IDs."""
    data = {"name": "GroEL", "subunits": 14, "tags": ["chaperonin", "cage"]}
    html_obj = show_json(data, max_depth=2)

    assert isinstance(html_obj, HTML)
    html = html_obj.data
    assert "json_viewer_" in html
    assert "renderjson.min.js" in html
    assert "renderjson.set_show_to_level(2)" in html
    assert "GroEL" in html
    assert "chaperonin" in html


def test_show_json_supports_pydantic_and_strings():
    """Verify show_json serializes Pydantic models and raw JSON strings."""
    st = Stoichiometry.from_formula("A14B7")
    html_pydantic = show_json(st, max_depth=1)
    assert isinstance(html_pydantic, HTML)
    assert "A14B7" in html_pydantic.data

    raw_json_str = '{"assembly": "heteromer", "copies": 21}'
    html_str = show_json(raw_json_str)
    assert isinstance(html_str, HTML)
    assert "heteromer" in html_str.data


# ---------------------------------------------------------------------------
# 4. Quaternary Summary Card
# ---------------------------------------------------------------------------

def test_render_quaternary_summary_card():
    """Verify render_quaternary_summary_card formats biological metrics and provenance."""
    output = QuaternaryStructureOutput(
        analysis_id="TEST_AN_001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=Stoichiometry.from_formula("A14"),
        confidence_provenance=ConfidenceProvenance(
            pdbe_pisa=PisaConfidence(dissociation_energy_kcal_mol=14.2),
            swissmodel=SwissModelConfidence(qmqe=0.85, gmqe=0.91),
            alphafold_db=AlphaFoldConfidence(global_plddt=93.4),
            alphafold_multimer=MultimerConfidence(iptm=0.88, ptm=0.82),
        ),
        interfaces=[
            InterfaceContact(chain_1="A", chain_2="B", buried_surface_area_angstrom2=1200.0)
        ],
    )

    card = render_quaternary_summary_card(output)
    assert isinstance(card, HTML)
    html = card.data

    assert "TEST_AN_001" in html
    assert "HOMOMER" in html
    assert "A14" in html
    assert "14" in html
    assert "14.2 kcal/mol" in html
    assert "QMQE: 0.85 | GMQE: 0.91" in html
    assert "93.4" in html
    assert "ipTM: 0.88 | pTM: 0.82" in html
    assert "CONSENSUS ALIGNED" in html
    assert "1 Pairwise" in html


def test_render_quaternary_summary_card_dict_input_and_conflict():
    """Verify render_quaternary_summary_card accepts dict input and displays conflict badge."""
    output_dict = {
        "analysis_id": "TEST_CONFLICT_001",
        "target_accession_or_sequence": "P01308",
        "quaternary_status": "CONFLICTING",
        "stoichiometry": {"formula": "A2", "assembly_type": "homomer", "total_subunits": 2},
        "conflicts": [{"source_a": "PDB", "source_b": "AlphaFold", "description": "Stoichiometry disagreement"}],
        "confidence_provenance": {},
        "interfaces": [],
    }

    card = render_quaternary_summary_card(output_dict)  # type: ignore
    assert isinstance(card, HTML)
    assert "CONFLICT DETECTED" in card.data
    assert "A2" in card.data


# ---------------------------------------------------------------------------
# 5. Component Identity Table
# ---------------------------------------------------------------------------

def test_render_component_identity_table():
    """Verify render_component_identity_table displays target subunit and partner complexes."""
    output = QuaternaryStructureOutput(
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

    table = render_component_identity_table(output)
    assert isinstance(table, HTML)
    html = table.data

    assert "Macromolecular Component Identity Table" in html
    assert "TARGET SUBUNIT" in html
    assert "PARTNER COMPLEX" in html
    assert "groEL (Escherichia coli)" in html
    assert "P0A6F5" in html
    assert "P0A6G7" in html
    assert "Co-chaperonin GroES" in html
    assert "14" in html
    assert "7" in html


# ---------------------------------------------------------------------------
# 6. Interface Contact Table
# ---------------------------------------------------------------------------

def test_render_interface_contact_table_with_interfaces():
    """Verify render_interface_contact_table displays contact parameters and residue lists."""
    output = QuaternaryStructureOutput(
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

    table = render_interface_contact_table(output)
    assert isinstance(table, HTML)
    html = table.data

    assert "Pairwise Interface Contact Residues & Thermodynamics" in html
    assert "1,500.4 &#197;&#178;" in html or "1,500.4 Å²" in html
    assert "-23.40 kcal/mol" in html
    assert "16" in html
    assert "2" in html
    assert "A &mdash; B" in html or "A — B" in html


def test_render_interface_contact_table_monomer_fallback():
    """Verify render_interface_contact_table renders fallback banner when interfaces are empty."""
    monomer = QuaternaryStructureOutput(
        analysis_id="TEST_MONO_001",
        target_accession_or_sequence="P44101",
        quaternary_status="MONOMER",
        stoichiometry=Stoichiometry.from_formula("A"),
        interfaces=[],
    )

    table = render_interface_contact_table(monomer)
    assert isinstance(table, HTML)
    assert "No multimer interfaces detected (consistent with monomeric baseline)." in table.data


# ---------------------------------------------------------------------------
# 7. Dynamic Multi-Assembly Equilibrium Display
# ---------------------------------------------------------------------------

def test_render_dynamic_equilibrium_display_with_assemblies():
    """Verify render_dynamic_equilibrium_display renders multi-assembly cards."""
    output = QuaternaryStructureOutput(
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
                conditions="Zinc-stabilized hexamer",
                is_target_self=False,
                delta_g_diss_kcal_mol=-24.5,
                primary_physiological_state="Storage Hexamer",
            ),
            ObservedAssembly(
                pdb_id="2INS",
                assembly_id="1",
                stoichiometry="A2",
                biological_assembly_type="Dimer (Active Form)",
                conditions="Zinc-free dimer",
                is_target_self=True,
                delta_g_diss_kcal_mol=-12.2,
                primary_physiological_state="Active Circulating Dimer",
            ),
        ],
    )

    display_html = render_dynamic_equilibrium_display(output)
    assert isinstance(display_html, HTML)
    html = display_html.data

    assert "Dynamic Multi-Assembly Equilibrium & Observed States" in html
    assert "PDB 4INS" in html
    assert "A6" in html
    assert "Storage Hexamer" in html
    assert "PDB 2INS" in html
    assert "A2" in html
    assert "Target Self-Assembly" in html


def test_render_dynamic_equilibrium_display_empty_fallback():
    """Verify render_dynamic_equilibrium_display renders invariant fallback when no assemblies."""
    output = QuaternaryStructureOutput(
        analysis_id="TEST_EQUIL_EMPTY",
        target_accession_or_sequence="P44101",
        quaternary_status="MONOMER",
        stoichiometry=Stoichiometry.from_formula("A"),
        observed_assemblies=[],
    )

    display_html = render_dynamic_equilibrium_display(output)
    assert isinstance(display_html, HTML)
    assert "Single invariant quaternary state observed." in display_html.data


# ---------------------------------------------------------------------------
# 8. Functional Inference Card
# ---------------------------------------------------------------------------

def test_render_functional_inference_card_with_function():
    """Verify render_functional_inference_card renders function, mechanism, and badges."""
    output = QuaternaryStructureOutput(
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

    card = render_functional_inference_card(output)
    assert isinstance(card, HTML)
    html = card.data

    assert "Executive Bio-Mechanistic Card: Functional Inference" in html
    assert "HIGH CONFIDENCE (0.95)" in html
    assert "Molecular Chaperone" in html
    assert "Double-ring tetradecamer creates an enclosed hydrophilic folding chamber." in html
    assert "PDB 1AON" in html
    assert "protein folding" in html


def test_render_functional_inference_card_empty_fallback():
    """Verify render_functional_inference_card renders baseline fallback banner when function is None."""
    output = QuaternaryStructureOutput(
        analysis_id="TEST_FUNC_EMPTY",
        target_accession_or_sequence="P44101",
        quaternary_status="MONOMER",
        stoichiometry=Stoichiometry.from_formula("A"),
        inferred_function=None,
    )

    card = render_functional_inference_card(output)
    assert isinstance(card, HTML)
    assert "Uncharacterized / Novel sequence baseline." in card.data


# ---------------------------------------------------------------------------
# 9. Evidence Coverage Dashboard
# ---------------------------------------------------------------------------

def test_render_evidence_coverage_dashboard_with_coverage():
    """Verify render_evidence_coverage_dashboard renders queried databases and gap alerts."""
    output = QuaternaryStructureOutput(
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

    dash = render_evidence_coverage_dashboard(output)
    assert isinstance(dash, HTML)
    html = dash.data

    assert "Evidence Coverage & Gaps Dashboard" in html
    assert "UniProtKB" in html
    assert "HIT FOUND" in html
    assert "ColabFold / AlphaFold-Multimer" in html
    assert "SKIPPED / UNCONFIGURED" in html
    assert "External multimer live compute absent" in html


def test_render_evidence_coverage_dashboard_empty_fallback():
    """Verify render_evidence_coverage_dashboard renders fallback banner when coverage is None."""
    output = QuaternaryStructureOutput(
        analysis_id="TEST_COV_EMPTY",
        target_accession_or_sequence="P44101",
        quaternary_status="MONOMER",
        stoichiometry=Stoichiometry.from_formula("A"),
        evidence_coverage=None,
    )

    dash = render_evidence_coverage_dashboard(output)
    assert isinstance(dash, HTML)
    assert "No coverage audit recorded." in dash.data
