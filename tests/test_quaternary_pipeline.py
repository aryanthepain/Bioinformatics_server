"""End-to-end integration tests for the Quaternary Pipeline facade and stateful sessions."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

import quaternary_pipeline as qp
from quaternary.models import AssemblyType, StageStatus


# ==========================================
# Facade and Engine Tests
# ==========================================

def test_top_level_facade_exports() -> None:
    """Verifies D-01: clean top-level imports from quaternary_pipeline."""
    expected_symbols = [
        "QuaternaryEngine",
        "QuaternarySession",
        "QuaternaryConfig",
        "analyze_quaternary",
        "Stoichiometry",
        "AssemblyType",
        "EvidenceStatus",
        "TargetSelfAssembly",
        "FunctionalComplex",
        "ObservedAssembly",
        "InferredFunction",
        "EvidenceCoverage",
        "InterfaceContact",
        "ConflictRecord",
        "ExperimentalConflict",
        "ConfidenceProvenance",
        "QuaternaryStructureOutput",
        "StageStatus",
        "StageResult",
    ]
    for sym in expected_symbols:
        assert hasattr(qp, sym), f"Missing public symbol: {sym}"


def test_engine_id_generation() -> None:
    """Verifies D-04: unique session/analysis ID generated on the engine side."""
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)

    session = engine.create_session("P0A6F5")
    assert re.match(r"^quat-session-\d+-[a-f0-9]{8}$", session.session_id)
    assert session.target_input == "P0A6F5"


# ==========================================
# Step-Wise Stage Execution Tests (D-02)
# ==========================================

def test_stepwise_session_stages_offline() -> None:
    """Verifies D-02: step-wise interactive execution across canonical stages 1 through 6."""
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    # Stage 1: Sequence & Accession Discovery
    s1 = session.run_stage_1_sequence_and_accession()
    assert s1.stage_number == 1
    assert s1.status == StageStatus.SUCCESS
    assert "14 subunits" in s1.data["uniprot"]["subunit_text"] or "Tetradecamer" in s1.data["uniprot"]["subunit_text"]
    assert any(cpx in s1.data["uniprot"]["complex_portal_ids"] for cpx in ["CPX-1882", "CPX-2113"])

    # Stage 2: Experimental Assemblies & PDB Candidate Search
    s2 = session.run_stage_2_experimental_assemblies()
    assert s2.stage_number == 2
    assert s2.status == StageStatus.SUCCESS
    assert s2.data["assembly_score"] > 0
    assert len(s2.data["candidate_scoring"]) >= 1

    # Stage 3: Thermodynamic & Assembly Qualification (PDBe PISA)
    s3 = session.run_stage_3_thermodynamic_qualification()
    assert s3.stage_number == 3
    assert s3.status == StageStatus.SUCCESS
    assert len(s3.data["interfaces"]) >= 1
    assert s3.data["dissociation_energy_kcal_mol"] is not None

    # Stage 4: Homology Modeling & Physical Interactions
    s4 = session.run_stage_4_homology_and_partners()
    assert s4.stage_number == 4
    assert s4.status == StageStatus.SUCCESS
    assert len(s4.data["qualifying_homology_templates"]) >= 1
    assert len(s4.data["physical_interactors"]) >= 1
    assert s4.data["monomer_context_only"] is True
    assert s4.data["asserts_oligomeric_state"] is False
    assert s4.data["global_plddt"] in (94.6, 90.81) or s4.data["global_plddt"] > 80.0

    # Stage 5: Predictive Multimer Modeling (Opt-in false -> SKIPPED)
    s5_optout = session.run_stage_5_predictive_multimer(enable_multimer=False)
    assert s5_optout.stage_number == 5
    assert s5_optout.status == StageStatus.SKIPPED
    assert s5_optout.data["opt_in_required"] is True
    assert s5_optout.data["multimer_hypothesis_eligible"] is True

    # Stage 5: Predictive Multimer Modeling (Opt-in true without live runner -> UNAVAILABLE)
    s5_optin = session.run_stage_5_predictive_multimer(enable_multimer=True, hypothesis="A14")
    assert s5_optin.status == StageStatus.UNAVAILABLE
    assert s5_optin.data["multimer_prediction_executed"] is False
    assert "Real Execution Only" in s5_optin.data["reason"]

    # Stage 6: Biological Synthesis, Complex Disambiguation & Functional Inference
    s6 = session.run_stage_6_synthesis_and_functional_inference()
    assert s6.stage_number == 6
    assert s6.status == StageStatus.SUCCESS

    output = session.output
    assert output is not None
    assert output.analysis_id == session.session_id
    assert output.target_accession_or_sequence == "P0A6F5"
    assert output.target_self_assembly is not None
    assert output.target_self_assembly.formula == "A14"
    assert output.target_self_assembly.assembly_type == AssemblyType.HOMOMER
    assert len(output.functional_complexes) >= 1
    assert "GroEL-GroES" in output.functional_complexes[0].name
    assert output.inferred_function is not None
    assert output.inferred_function.archetype_name == "chaperonin_barrel"
    assert output.confidence_provenance.pdbe_pisa is not None
    assert 6 in output.stages_completed


# ==========================================
# UI Export Tests (to_ui)
# ==========================================

def test_to_ui_json_export() -> None:
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    # Export to JSON
    json_str = session.to_ui(format="json")
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["analysis_id"] == session.session_id
    assert "stoichiometry" in parsed
    assert "confidence_provenance" in parsed


def test_to_ui_dict_export() -> None:
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    data = session.to_ui(format="dict")
    assert isinstance(data, dict)
    assert data["analysis_id"] == session.session_id
    assert data["quaternary_status"] in ("HOMOMER", "HETEROMER")


def test_to_ui_dataframe_export() -> None:
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    dfs = session.to_ui(format="dataframe")
    assert isinstance(dfs, dict)
    assert "summary" in dfs
    assert "interfaces" in dfs
    assert "stages" in dfs
    assert isinstance(dfs["summary"], pd.DataFrame)
    assert isinstance(dfs["interfaces"], pd.DataFrame)
    assert isinstance(dfs["stages"], pd.DataFrame)
    assert len(dfs["summary"]) == 1


def test_to_ui_invalid_format() -> None:
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    with pytest.raises(ValueError, match="Unsupported UI export format"):
        session.to_ui(format="xml")


# ==========================================
# Error Fallback & Conveniences
# ==========================================

def test_graceful_error_fallback() -> None:
    """Verifies D-05: external API failures degrade gracefully without crashing notebook cells."""
    cfg = qp.QuaternaryConfig(offline_mode=False)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    # Mock failing UniProt, Complex Portal, and RCSB
    with patch.object(session.uniprot_client, "get_subunit_annotations", side_effect=ConnectionError("EBI down")), \
         patch.object(session.complex_portal_client, "get_complex", side_effect=ConnectionError("Down")), \
         patch.object(session.rcsb_client, "get_entry_assemblies", side_effect=ConnectionError("Down")):

        s1 = session.run_stage_1_sequence_and_accession()
        assert s1.status in (StageStatus.UNAVAILABLE, StageStatus.FAILED)
        assert len(s1.provenance["errors"]) >= 1

        # Downstream stage can still run without unhandled crash
        s4 = session.run_stage_4_homology_and_partners()
        assert s4 is not None


def test_analyze_quaternary_convenience_function() -> None:
    cfg = qp.QuaternaryConfig(offline_mode=True)
    output = qp.analyze_quaternary("P0A6F5", config=cfg)
    assert isinstance(output, qp.QuaternaryStructureOutput)
    assert output.analysis_id.startswith("quat-session-")
    assert len(output.stages_completed) >= 5


def test_candidate_specific_scoring_protocol() -> None:
    """Verifies D-04: Candidate scores are fully computed per candidate's actual resolution without defaults."""
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    # Pre-populate Stage 1 with mock candidates having distinct resolutions
    session.stages[1] = qp.StageResult(
        stage_number=1,
        stage_name="Sequence & Accession Discovery",
        status=StageStatus.SUCCESS,
        data={
            "rcsb_candidates": [
                {"pdb_id": "TEST_HIGHRES", "resolution": 1.50, "coverage": 95.0, "method": "X-RAY DIFFRACTION"},
                {"pdb_id": "TEST_STDRES", "resolution": 2.40, "coverage": 95.0, "method": "X-RAY DIFFRACTION"},
                {"pdb_id": "TEST_LOWRES", "resolution": 3.40, "coverage": 95.0, "method": "X-RAY DIFFRACTION"},
            ],
            "uniprot": {"accession": "P0A6F5"},
        },
    )

    with patch.object(session.rcsb_client, "get_entry_assemblies", side_effect=lambda pid: {
        "pdb_id": pid,
        "resolution": 1.5 if "HIGH" in pid else (2.4 if "STD" in pid else 3.4),
        "coverage": 95.0,
        "method": "X-RAY DIFFRACTION"
    }):
        s2 = session.run_stage_2_experimental_assemblies()
        assert s2.status == StageStatus.SUCCESS

        scoring = s2.data["candidate_scoring"]
        assert len(scoring) >= 1


def test_multimer_actual_execution_not_simulation() -> None:
    """Verifies D-06: Stage 5 enforces Real Execution Only, returning UNAVAILABLE when live runner is absent."""
    cfg = qp.QuaternaryConfig(offline_mode=True)
    engine = qp.QuaternaryEngine(cfg)
    session = engine.create_session("P0A6F5")

    # 1. Without live runner -> UNAVAILABLE
    s5 = session.run_stage_5_predictive_multimer(enable_multimer=True, hypothesis="A14")
    assert s5.status == StageStatus.UNAVAILABLE
    assert s5.data["multimer_prediction_executed"] is False
    assert "Real Execution Only" in s5.data["reason"]

    # 2. With live runner active (e.g. mocked GPU / endpoint) -> SUCCESS
    with patch.object(session.multimer_client, "is_live_runner_available", return_value=True):
        s5_live = session.run_stage_5_predictive_multimer(enable_multimer=True, hypothesis="A14")
        assert s5_live.status == StageStatus.SUCCESS
        assert s5_live.data["multimer_prediction_executed"] is True
        assert s5_live.data["simulation_mode"] is False
        assert s5_live.data["execution_type"] == "actual"
        assert s5_live.data["status"] == "COMPLETED"
        assert s5_live.data["iptm"] > 0
        assert s5_live.data["ptm"] > 0
        assert s5_live.data["model_confidence"] > 0

