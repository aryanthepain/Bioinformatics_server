"""Comprehensive test suite for Quaternary rigor, biological disambiguation, and function inference."""

import pytest

from quaternary.clients import MultimerPredictorClient, UniProtClient
from quaternary.config import QuaternaryConfig
from quaternary.engine import QuaternaryEngine
from quaternary.function_inference import FunctionInferenceEngine, MechanisticArchetype
from quaternary.models import (
    ConfidenceProvenance,
    EvidenceStatus,
    InterfaceContact,
    QuaternaryStructureOutput,
    StageResult,
    StageStatus,
    TargetSelfAssembly,
)
from quaternary.session import QuaternarySession


@pytest.fixture
def offline_config():
    return QuaternaryConfig(offline_mode=True)


def test_groel_biological_disambiguation(offline_config):
    """Verify GroEL (P0A6F5) self-assembly is disambiguated as A14 and GroEL-GroES as A14B7."""
    engine = QuaternaryEngine(config=offline_config)
    session = engine.create_session("P0A6F5")
    output: QuaternaryStructureOutput = session.run_stage_6_synthesis()

    # 1. Target Self-Assembly
    assert output.target_self_assembly.formula == "A14"
    assert output.target_self_assembly.subunit_count == 14
    assert output.target_self_assembly.symmetry == "D7"
    assert output.target_self_assembly.confidence_status == EvidenceStatus.CONFIRMED
    assert output.quaternary_status == "HOMOMER"

    # 2. Hetero Functional Complex Disambiguation
    assert len(output.functional_complexes) >= 1
    groel_es = output.functional_complexes[0]
    assert groel_es.stoichiometry == "A14B7"
    assert "P0A6F9" in groel_es.partner_uniprot_accessions
    assert "CPX-1882" in (groel_es.complex_portal_id or "") or "CPX-2113" in (groel_es.complex_portal_id or "")

    # 3. Non-Zero Biophysical Interfaces (D-02 / D-03)
    assert len(output.interfaces) >= 1
    first_iface = output.interfaces[0]
    assert first_iface.buried_surface_area_angstrom2 > 0.0
    assert first_iface.solvation_free_energy_kcal_mol != 0.0

    # 4. Functional Inference & Coverage
    assert output.inferred_function is not None
    assert output.inferred_function.archetype_name == "chaperonin_barrel"
    assert "folding" in output.inferred_function.molecular_function.lower() or "chaperone" in output.inferred_function.molecular_function.lower()
    assert output.evidence_coverage is not None
    assert len(output.evidence_coverage.databases_queried) >= 7


def test_insulin_dynamic_equilibrium(offline_config):
    """Verify Insulin (P01308) retains dynamic equilibria across A6, A2, and A states."""
    session = QuaternarySession(target_input="P01308", config=offline_config)
    output: QuaternaryStructureOutput = session.run_stage_6_synthesis()

    assert output.target_self_assembly.formula == "A6"
    assert len(output.observed_assemblies) >= 3

    stoich_map = {obs.pdb_id: obs for obs in output.observed_assemblies}
    assert "4INS" in stoich_map
    assert stoich_map["4INS"].stoichiometry == "A6"
    assert stoich_map["4INS"].primary_physiological_state == "Storage Hexamer"
    assert stoich_map["4INS"].delta_g_diss_kcal_mol > 0

    assert "2INS" in stoich_map
    assert stoich_map["2INS"].stoichiometry == "A2"
    assert stoich_map["2INS"].primary_physiological_state == "Intermediate Dimer"

    assert "9INS" in stoich_map
    assert stoich_map["9INS"].stoichiometry == "A"
    assert stoich_map["9INS"].primary_physiological_state == "Active Circulating Monomer"


def test_novel_sequence_fallback_uncharacterized(offline_config):
    """Verify an uncharacterized synthetic sequence yields UNCHARACTERIZED/INSUFFICIENT EVIDENCE status and never defaults to MONOMER."""
    synthetic_seq = "MKLLVVLALLAASARAEAGELVAKLEEARAKVEALEARVKALEEE"
    session = QuaternarySession(target_input=synthetic_seq, config=offline_config)
    output: QuaternaryStructureOutput = session.run_stage_6_synthesis()

    # Quaternary status & self assembly must NOT default to MONOMER
    assert output.quaternary_status == "UNCHARACTERIZED"
    assert output.target_self_assembly.formula == "UNCHARACTERIZED"
    assert output.target_self_assembly.confidence_status in (EvidenceStatus.UNCHARACTERIZED, EvidenceStatus.INSUFFICIENT_EVIDENCE)
    assert output.experimental_oligomeric_state == "UNKNOWN"
    assert output.predicted_oligomeric_state == "UNKNOWN"
    assert output.fallback_representation == "MONOMER BASELINE"
    assert output.status in (EvidenceStatus.UNCHARACTERIZED, EvidenceStatus.INSUFFICIENT_EVIDENCE)

    # Functional inference must report uncharacterized with low confidence
    assert output.inferred_function.status in (EvidenceStatus.UNCHARACTERIZED, EvidenceStatus.INSUFFICIENT_EVIDENCE)
    assert output.inferred_function.confidence <= 0.30
    assert "Uncharacterized" in output.inferred_function.molecular_function

    # Observed assemblies should be empty
    assert len(output.observed_assemblies) == 0



def test_conflict_retention_when_sources_disagree(offline_config):
    """Verify conflicts list explicitly retains discrepancies when predictive multimer differs from experimental PDB."""
    session = QuaternarySession(target_input="P0A6F5", config=offline_config)
    # Run preliminary stages
    session.run_stage_1_sequence_and_accession()
    session.run_stage_2_experimental_assemblies()
    session.run_stage_3_thermodynamic_qualification()
    session.run_stage_4_homology_and_partners()

    # Simulate Stage 5 multimer execution predicting conflicting stoichiometry (e.g. A2 instead of A14)
    session.stages[5] = StageResult(
        stage_number=5,
        stage_name="Predictive Multimer Modeling",
        status=StageStatus.SUCCESS,
        data={
            "multimer_prediction_executed": True,
            "predicted_stoichiometry": "A2",
            "iptm": 0.45,
            "ptm": 0.50,
            "model_confidence": 0.46,
        },
    )

    output = session.run_stage_6_synthesis()

    # Conflicts list must record the divergence
    assert len(output.conflicts) >= 1
    divergence = [c for c in output.conflicts if c.source_a == "AlphaFold-Multimer Predictor"]
    assert len(divergence) == 1
    record = divergence[0]
    assert record.stoichiometry_a == "A2"
    assert record.stoichiometry_b == "A14"
    assert "diverges" in record.rationale
    assert "Precedence given to experimental" in record.resolution
    assert output.experimental_conflict.conflict_detected is True


def test_quaternary_to_function_inference_archetypes():
    """Verify prebuilt biophysical archetypes synthesize concordant mechanistic hypotheses."""
    engine = FunctionInferenceEngine()

    # 1. Chaperonin D7 barrel
    groel_target = TargetSelfAssembly(
        formula="A14",
        subunit_count=14,
        symmetry="D7",
        confidence_status=EvidenceStatus.CONFIRMED,
    )
    ifaces = [
        InterfaceContact(
            chain_1="A",
            chain_2="B",
            buried_surface_area_angstrom2=1850.0,
            solvation_free_energy_kcal_mol=-8.5,
        )
    ]
    prov = ConfidenceProvenance()
    res = engine.infer_function(
        target_self_assembly=groel_target,
        interfaces=ifaces,
        confidence_provenance=prov,
        go_terms=[{"id": "GO:0006457", "name": "protein folding"}],
        function_text="Assists the folding of de novo synthesized polypeptides.",
    )
    assert res.archetype_name == "chaperonin_barrel"
    assert "protein folding" in res.molecular_function.lower() or "chaperone" in res.molecular_function.lower()
    assert res.confidence >= 0.70

    # 2. bZIP homodimer
    dimer_target = TargetSelfAssembly(
        formula="A2",
        subunit_count=2,
        symmetry="C2",
        confidence_status=EvidenceStatus.CONFIRMED,
    )
    res_dimer = engine.infer_function(
        target_self_assembly=dimer_target,
        interfaces=ifaces,
        confidence_provenance=prov,
        go_terms=[{"id": "GO:0003700", "name": "DNA-binding transcription factor"}],
    )
    assert res_dimer.archetype_name == "homodimer_regulatory"
    assert "transcription" in res_dimer.molecular_function.lower() or "signaling" in res_dimer.molecular_function.lower()


def test_extensible_archetype_registry():
    """Verify users can register custom mechanistic archetypes that are matched during inference."""
    engine = FunctionInferenceEngine()

    custom_arch = MechanisticArchetype(
        name="custom_octamer_pore",
        stoichiometry_pattern=r"^A8$",
        symmetry_pattern=r"C8",
        molecular_function="Membrane pore-forming toxin",
        biological_process="Target cell lysis and pore assembly",
        mechanism_template="Octameric beta-barrel inserted into target cell lipid bilayer",
    )
    engine.register_archetype(custom_arch)

    matched = engine.match_archetype("A8", "C8")
    assert matched is not None
    assert matched.name == "custom_octamer_pore"
    assert "pore-forming" in matched.molecular_function.lower()


def test_real_execution_policy_multimer():
    """Verify MultimerPredictorClient returns UNAVAILABLE when compute endpoint is absent without fake numbers."""
    cfg = QuaternaryConfig(offline_mode=False)
    client = MultimerPredictorClient(config=cfg)

    # Calling run_multimer_prediction without live backend returns UNAVAILABLE
    res = client.run_multimer_prediction(
        sequence="MKLLVVLALLA",
        hypothesis="A2",
        enable_multimer=True,
        dry_run=False,
    )
    assert res["status"] == "UNAVAILABLE"
    assert "No live GPU or external multimer runner configured" in res["reason"]

    # Must NOT emit fake metrics
    assert "iptm" not in res or res.get("iptm") is None
    assert "ptm" not in res or res.get("ptm") is None
    assert "model_confidence" not in res or res.get("model_confidence") is None

    # Calling through session also results in StageStatus.UNAVAILABLE
    session = QuaternarySession("P0A6F5", config=cfg)
    r5 = session.run_stage_5_predictive_multimer(enable_multimer=True, hypothesis="A2")
    assert r5.status == StageStatus.UNAVAILABLE
    assert r5.data.get("status") == "UNAVAILABLE"
    assert "iptm" not in r5.data or r5.data.get("iptm") is None


def test_assembly_aware_candidate_ranking_penalizes_fragments():
    """Verify D-02: assembly-aware ranking penalizes isolated domain fragments (1DK7) over full biological assemblies (1AON, 1GRL)."""
    cfg = QuaternaryConfig(offline_mode=True)
    session = QuaternarySession("P0A6F5", config=cfg)
    s2 = session.run_stage_2_experimental_assemblies()

    scoring = s2.data.get("candidate_scoring", [])
    assert len(scoring) >= 2

    # Map candidate IDs to their scores
    score_by_id = {c["pdb_id"].upper(): c["score"] for c in scoring}
    assert "1DK7" in score_by_id
    assert "1AON" in score_by_id or "1GRL" in score_by_id

    # 1AON/1GRL (intact tetradecamer assemblies) must outscore 1DK7 (apical domain fragment)
    top_score = max(score_by_id.get("1AON", 0.0), score_by_id.get("1GRL", 0.0))
    dk7_score = score_by_id["1DK7"]
    assert top_score > dk7_score
    assert scoring[0]["pdb_id"].upper() in ("1AON", "1GRL")


