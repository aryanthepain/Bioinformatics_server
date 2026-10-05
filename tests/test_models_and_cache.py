"""Unit tests for Quaternary Engine domain models, configuration, and cache backends."""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from quaternary.cache import JsonDirectoryCache, SqliteCache, get_cache_backend
from quaternary.config import QuaternaryConfig
from quaternary.models import (
    AlphaFoldConfidence,
    AssemblyType,
    ConfidenceProvenance,
    ConflictRecord,
    EvidenceCoverage,
    EvidenceStatus,
    ExperimentalConflict,
    FunctionalComplex,
    InferredFunction,
    InterfaceContact,
    MultimerConfidence,
    ObservedAssembly,
    PisaConfidence,
    QuaternaryStructureOutput,
    ResidueRange,
    StageResult,
    StageStatus,
    Stoichiometry,
    SwissModelConfidence,
    TargetSelfAssembly,
)


# ==========================================
# Config Tests
# ==========================================

def test_quaternary_config_defaults(tmp_path: Path) -> None:
    cfg = QuaternaryConfig()
    assert cfg.cache_enabled is True
    assert cfg.cache_backend == "json"
    assert cfg.timeout == 30.0
    assert cfg.max_retries == 3
    assert cfg.offline_mode is False
    assert cfg.force_refresh is False


def test_quaternary_config_kwargs_override(tmp_path: Path) -> None:
    custom_dir = tmp_path / "custom_cache"
    cfg = QuaternaryConfig(
        cache_backend="sqlite",
        cache_dir=custom_dir,
        timeout=15.0,
        offline_mode=True,
    )
    assert cfg.cache_backend == "sqlite"
    assert cfg.cache_dir == custom_dir
    assert cfg.timeout == 15.0
    assert cfg.offline_mode is True


def test_quaternary_config_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QUATERNARY_CACHE_BACKEND", "sqlite")
    monkeypatch.setenv("QUATERNARY_OFFLINE_MODE", "true")
    monkeypatch.setenv("QUATERNARY_TIMEOUT", "45.5")
    cfg = QuaternaryConfig()
    assert cfg.cache_backend == "sqlite"
    assert cfg.offline_mode is True
    assert cfg.timeout == 45.5


# ==========================================
# Domain Model Tests
# ==========================================

def test_stoichiometry_parsing() -> None:
    # Monomer
    s_mono = Stoichiometry.from_formula("A")
    assert s_mono.assembly_type == AssemblyType.MONOMER
    assert s_mono.total_subunits == 1
    assert s_mono.chains == {"A": 1}

    # Homomer
    s_homo = Stoichiometry.from_formula("A2", symmetry="C2")
    assert s_homo.assembly_type == AssemblyType.HOMOMER
    assert s_homo.total_subunits == 2
    assert s_homo.chains == {"A": 2}
    assert s_homo.symmetry == "C2"

    # Heteromer
    s_hetero = Stoichiometry.from_formula("A2B2", symmetry="D2")
    assert s_hetero.assembly_type == AssemblyType.HETEROMER
    assert s_hetero.total_subunits == 4
    assert s_hetero.chains == {"A": 2, "B": 2}

    # Complex heteromer
    s_complex = Stoichiometry.from_formula("A4B4C2")
    assert s_complex.assembly_type == AssemblyType.HETEROMER
    assert s_complex.total_subunits == 10
    assert s_complex.chains == {"A": 4, "B": 4, "C": 2}

    # Uncharacterized
    s_unchar = Stoichiometry.from_formula("UNCHARACTERIZED")
    assert s_unchar.assembly_type == AssemblyType.UNCHARACTERIZED
    assert s_unchar.total_subunits == 0


def test_interface_models() -> None:
    contact = InterfaceContact(
        chain_1="A",
        chain_2="B",
        buried_surface_area_angstrom2=1420.5,
        solvation_free_energy_kcal_mol=-12.4,
        hydrogen_bonds_count=6,
        salt_bridges_count=2,
        interface_residues_chain_1=[12, 14, 15, 18],
        interface_residues_chain_2=[104, 106, 110],
    )
    dumped = contact.model_dump()
    assert dumped["chain_1"] == "A"
    assert dumped["buried_surface_area_angstrom2"] == 1420.5
    assert len(dumped["interface_residues_chain_1"]) == 4


def test_experimental_conflict_retention() -> None:
    conflict = ExperimentalConflict(
        conflict_detected=True,
        rcsb_annotated_assembly="A2B2 heterotetramer",
        pisa_thermodynamic_state="Monomer in solution (delta_g = +2.3 kcal/mol)",
        dissociation_energy_kcal_mol=2.3,
        conflict_rationale="PISA calculates positive dissociation free energy, indicating crystal packing artifact.",
    )
    assert conflict.conflict_detected is True
    assert "crystal packing" in conflict.conflict_rationale


def test_confidence_provenance_segregation() -> None:
    # Verifies D-08: source confidence metrics remain strictly segregated without blended scores
    prov = ConfidenceProvenance(
        pdbe_pisa=PisaConfidence(dissociation_energy_kcal_mol=-8.5, buried_surface_area_angstrom2=1250.0),
        swissmodel=SwissModelConfidence(qmqe=0.78, gmqe=0.82, coverage=0.95),
        alphafold_db=AlphaFoldConfidence(global_plddt=88.4),
        alphafold_multimer=MultimerConfidence(iptm=0.86, ptm=0.89, model_confidence=0.87),
    )
    dumped = prov.model_dump()
    assert dumped["pdbe_pisa"]["dissociation_energy_kcal_mol"] == -8.5
    assert dumped["swissmodel"]["qmqe"] == 0.78
    assert dumped["alphafold_db"]["global_plddt"] == 88.4
    assert dumped["alphafold_multimer"]["iptm"] == 0.86
    assert "blended_score" not in dumped


def test_quaternary_structure_output() -> None:
    stoich = Stoichiometry.from_formula("A2")
    out = QuaternaryStructureOutput(
        analysis_id="quat-test-001",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=stoich,
        stages_completed=[1, 2],
    )
    assert out.analysis_id == "quat-test-001"
    assert out.stoichiometry.total_subunits == 2


def test_new_biological_domain_models() -> None:
    # TargetSelfAssembly
    tsa = TargetSelfAssembly(
        formula="A14",
        assembly_type=AssemblyType.HOMOMER,
        subunit_count=14,
        symmetry="D7",
        confidence_status=EvidenceStatus.CONFIRMED,
    )
    assert tsa.formula == "A14"
    assert tsa.subunit_count == 14
    assert tsa.confidence_status == EvidenceStatus.CONFIRMED

    # FunctionalComplex
    fc = FunctionalComplex(
        name="GroEL-GroES complex",
        stoichiometry="A14B7",
        partner_uniprot_accessions=["P0A6F9"],
        partner_names=["GroES"],
        complex_portal_id="CPX-1882",
        evidence="Complex Portal curated",
    )
    assert fc.name == "GroEL-GroES complex"
    assert fc.partner_uniprot_accessions == ["P0A6F9"]

    # ObservedAssembly
    oa = ObservedAssembly(
        pdb_id="1GFL",
        assembly_id="1",
        stoichiometry="A14",
        biological_assembly_type="HOMOMER",
        is_target_self=True,
        delta_g_diss_kcal_mol=20.11,
    )
    assert oa.delta_g_diss_kcal_mol == 20.11
    assert oa.is_target_self is True

    # InferredFunction
    inf = InferredFunction(
        molecular_function="ATP-dependent protein folding chaperone",
        biological_process="Protein folding",
        oligomeric_mechanism_hypothesis="Chaperonin barrel",
        archetype_name="chaperonin_barrel",
        confidence=0.92,
        status=EvidenceStatus.CONFIRMED,
    )
    assert inf.archetype_name == "chaperonin_barrel"
    assert inf.confidence == 0.92

    # EvidenceCoverage
    ec = EvidenceCoverage(
        databases_queried=[{"database": "UniProtKB", "queried": True}],
        evidence_gaps=["No live multimer runner"],
    )
    assert len(ec.databases_queried) == 1
    assert len(ec.evidence_gaps) == 1

    # ConflictRecord
    cr = ConflictRecord(
        source_a="RCSB PDB",
        source_b="PDBe PISA",
        stoichiometry_a="A14B7",
        stoichiometry_b="A14",
        rationale="Author annotated complex vs isolated self-assembly",
    )
    assert cr.source_a == "RCSB PDB"


def test_quaternary_structure_output_roundtrip() -> None:
    stoich = Stoichiometry.from_formula("A14", symmetry="D7")
    tsa = TargetSelfAssembly(
        formula="A14",
        assembly_type=AssemblyType.HOMOMER,
        subunit_count=14,
        symmetry="D7",
        confidence_status=EvidenceStatus.CONFIRMED,
    )
    fc = FunctionalComplex(
        name="GroEL-GroES complex",
        stoichiometry="A14B7",
        partner_uniprot_accessions=["P0A6F9"],
        partner_names=["GroES"],
        complex_portal_id="CPX-1882",
        evidence="Complex Portal curated",
    )
    oa = ObservedAssembly(
        pdb_id="1GFL",
        assembly_id="1",
        stoichiometry="A14",
        biological_assembly_type="HOMOMER",
        is_target_self=True,
        delta_g_diss_kcal_mol=20.11,
    )
    iface = InterfaceContact(
        chain_1="A",
        chain_2="B",
        buried_surface_area_angstrom2=1450.0,
        solvation_free_energy_kcal_mol=-12.5,
        hydrogen_bonds_count=12,
        salt_bridges_count=4,
    )
    cr = ConflictRecord(
        source_a="RCSB PDB Author",
        source_b="PDBe PISA",
        stoichiometry_a="A14",
        stoichiometry_b="A14",
        rationale="No conflict detected",
    )
    prov = ConfidenceProvenance(
        pdbe_pisa=PisaConfidence(dissociation_energy_kcal_mol=20.11, buried_surface_area_angstrom2=69000.0),
        swissmodel=SwissModelConfidence(qmqe=0.85, gmqe=0.90, coverage=0.98),
        alphafold_db=AlphaFoldConfidence(global_plddt=92.5),
    )
    inf = InferredFunction(
        molecular_function="ATP-dependent protein folding chaperone",
        biological_process="Protein folding",
        oligomeric_mechanism_hypothesis="Double-ring chaperonin barrel",
        archetype_name="chaperonin_barrel",
        confidence=0.95,
        status=EvidenceStatus.CONFIRMED,
    )
    ec = EvidenceCoverage(
        databases_queried=[{"database": "UniProtKB", "queried": True}],
        evidence_gaps=[],
    )

    out = QuaternaryStructureOutput(
        analysis_id="quat-test-roundtrip",
        target_accession_or_sequence="P0A6F5",
        quaternary_status="HOMOMER",
        stoichiometry=stoich,
        target_self_assembly=tsa,
        functional_complexes=[fc],
        observed_assemblies=[oa],
        interfaces=[iface],
        conflicts=[cr],
        confidence_provenance=prov,
        inferred_function=inf,
        evidence_coverage=ec,
        status=EvidenceStatus.CONFIRMED,
        stages_completed=[1, 2, 3, 4, 6],
    )

    json_str = out.model_dump_json()
    reloaded = QuaternaryStructureOutput.model_validate_json(json_str)

    assert reloaded.analysis_id == "quat-test-roundtrip"
    assert reloaded.target_self_assembly is not None
    assert reloaded.target_self_assembly.formula == "A14"
    assert len(reloaded.functional_complexes) == 1
    assert reloaded.functional_complexes[0].name == "GroEL-GroES complex"
    assert len(reloaded.observed_assemblies) == 1
    assert reloaded.observed_assemblies[0].delta_g_diss_kcal_mol == 20.11
    assert len(reloaded.interfaces) == 1
    assert reloaded.interfaces[0].solvation_free_energy_kcal_mol == -12.5
    assert reloaded.inferred_function is not None
    assert reloaded.inferred_function.archetype_name == "chaperonin_barrel"
    assert reloaded.status == EvidenceStatus.CONFIRMED


def test_thermodynamic_sign_conventions() -> None:
    # Enforce D-11:
    # Stable assemblies have positive dissociation free energy: delta_g_diss_kcal_mol > 0
    # Favorable pairwise interfaces have negative solvation free energy: solvation_free_energy_kcal_mol < 0
    stable_assembly = ObservedAssembly(
        pdb_id="1GFL",
        assembly_id="1",
        stoichiometry="A14",
        biological_assembly_type="HOMOMER",
        delta_g_diss_kcal_mol=20.11,
    )
    assert stable_assembly.delta_g_diss_kcal_mol is not None
    assert stable_assembly.delta_g_diss_kcal_mol > 0, "Stable biological assembly must have positive Delta G diss"

    favorable_interface = InterfaceContact(
        chain_1="A",
        chain_2="B",
        buried_surface_area_angstrom2=1250.0,
        solvation_free_energy_kcal_mol=-15.3,
    )
    assert favorable_interface.solvation_free_energy_kcal_mol < 0, "Favorable interface must have negative solvation free energy"


# ==========================================
# Cache Tests
# ==========================================

def test_json_directory_cache(tmp_path: Path) -> None:
    cache = JsonDirectoryCache(tmp_path / "json_cache")
    assert cache.get("uniprot", "P12345") is None

    payload = {"accession": "P12345", "name": "GroEL"}
    cache.set("uniprot", "P12345", payload)

    cached = cache.get("uniprot", "P12345")
    assert cached == payload

    # Test overwrite
    updated = {"accession": "P12345", "name": "GroEL-v2"}
    cache.set("uniprot", "P12345", updated)
    assert cache.get("uniprot", "P12345") == updated

    # Test clear
    cache.clear()
    assert cache.get("uniprot", "P12345") is None


def test_sqlite_cache(tmp_path: Path) -> None:
    db_file = tmp_path / "test_cache.db"
    cache = SqliteCache(db_file)
    assert cache.get("rcsb", "4HHB") is None

    payload = {"entry_id": "4HHB", "formula": "A2B2"}
    cache.set("rcsb", "4HHB", payload)

    cached = cache.get("rcsb", "4HHB")
    assert cached == payload

    # Test overwrite
    updated = {"entry_id": "4HHB", "formula": "A2B2-updated"}
    cache.set("rcsb", "4HHB", updated)
    assert cache.get("rcsb", "4HHB") == updated

    # Test clear
    cache.clear()
    assert cache.get("rcsb", "4HHB") is None


def test_get_cache_backend_factory(tmp_path: Path) -> None:
    # Disabled
    cfg_disabled = QuaternaryConfig(cache_enabled=False)
    assert get_cache_backend(cfg_disabled) is None

    # JSON backend
    cfg_json = QuaternaryConfig(cache_backend="json", cache_dir=tmp_path / "j")
    backend_json = get_cache_backend(cfg_json)
    assert isinstance(backend_json, JsonDirectoryCache)

    # SQLite backend
    cfg_sqlite = QuaternaryConfig(cache_backend="sqlite", sqlite_db_path=tmp_path / "s.db")
    backend_sqlite = get_cache_backend(cfg_sqlite)
    assert isinstance(backend_sqlite, SqliteCache)
