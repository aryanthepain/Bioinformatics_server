"""Unit tests for homology modeling, interactome, structural context, and predictive multimer clients."""

from __future__ import annotations

import pytest

from quaternary.clients import (
    AlphaFoldClient,
    IntActClient,
    MultimerPredictorClient,
    SwissModelClient,
)
from quaternary.config import QuaternaryConfig


# ==========================================
# SWISS-MODEL Homology Tests
# ==========================================

def test_swissmodel_client_offline_fixture() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = SwissModelClient(cfg)
    models = client.get_homology_models("P0A6F5")

    assert isinstance(models, list)
    assert len(models) >= 2

    # Check top qualifying model
    top = models[0]
    assert top["template_pdb_id"] == "1AON"
    assert top["template_oligomeric_state"] == "homo-14-mer"
    assert top["qmqe"] == 0.88
    assert top["qualifying_homology"] is True

    # Check non-qualifying model
    low = models[2]
    assert low["qmqe"] == 0.52
    assert low["qualifying_homology"] is False


# ==========================================
# IntAct Physical Interactor Tests
# ==========================================

def test_intact_client_physical_filter() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = IntActClient(cfg)
    partners = client.get_physical_interactors("P0A6F5")

    assert isinstance(partners, list)
    partner_accs = [p["partner_accession"] for p in partners]

    # Physical interactors must be included
    assert "P0A6F9" in partner_accs
    assert "P0A699" in partner_accs

    # Synthetic genetic interaction (P0A6Y8) must be filtered out
    assert "P0A6Y8" not in partner_accs


# ==========================================
# AlphaFold DB Monomer Boundary Tests (D-05)
# ==========================================

def test_alphafold_client_monomer_boundary_enforcement() -> None:
    """Verifies D-05: AlphaFold DB client strictly provides monomer context and never asserts oligomeric state."""
    cfg = QuaternaryConfig(offline_mode=True)
    client = AlphaFoldClient(cfg)
    context = client.get_structural_context("P0A6F5")

    assert context["accession"] == "P0A6F5"
    assert context["global_plddt"] == 94.6
    assert "pdb_url" in context

    # Strict D-05 assertions
    assert context["monomer_context_only"] is True
    assert context["asserts_oligomeric_state"] is False
    assert context["quaternary_status"] == "uncharacterized"


def test_alphafold_esmfold_fallback() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = AlphaFoldClient(cfg)
    fallback = client.query_esmfold_fallback("MAAKDVKFGNDARVKMLRGV")

    assert fallback["monomer_context_only"] is True
    assert fallback["asserts_oligomeric_state"] is False
    assert fallback["quaternary_status"] == "uncharacterized"


# ==========================================
# Predictive Multimer Opt-In Tests (D-06)
# ==========================================

def test_multimer_predictor_requires_opt_in() -> None:
    """Verifies D-06: predictive multimer fails closed without caller opt-in."""
    cfg = QuaternaryConfig(offline_mode=True)
    client = MultimerPredictorClient(cfg)

    with pytest.raises(ValueError, match="enable_multimer=True"):
        client.run_multimer_prediction("MAAKDVKFGNDARVKMLRGV", hypothesis="A2", enable_multimer=False)


def test_multimer_predictor_requires_hypothesis() -> None:
    """Verifies D-06: predictive multimer requires concrete hypothesis."""
    cfg = QuaternaryConfig(offline_mode=True)
    client = MultimerPredictorClient(cfg)

    with pytest.raises(ValueError, match="concrete hypothesis"):
        client.run_multimer_prediction("MAAKDVKFGNDARVKMLRGV", hypothesis="", enable_multimer=True)


def test_multimer_predictor_dry_run_simulation() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = MultimerPredictorClient(cfg)

    # Propose hypothesis
    proposals = client.propose_hypothesis("P0A6F5", partners=[{"partner_accession": "P0A6F9"}])
    assert proposals["multimer_hypothesis_eligible"] is True
    assert len(proposals["suggested_hypotheses"]) >= 2

    # Execute simulation
    res = client.run_multimer_prediction(
        "MAAKDVKFGNDARVKMLRGV",
        hypothesis="A2",
        enable_multimer=True,
        dry_run=True,
    )
    assert res["predicted_stoichiometry"] == "A2"
    assert res["iptm"] == 0.84
    assert res["ptm"] == 0.81
    assert res["model_confidence"] == 0.834
    assert res["simulation_mode"] is True
