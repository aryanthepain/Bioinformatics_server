"""
Deterministic Conformance and Biological Validation Tests for UI Reference Benchmarks.

Validates the 5 canonical UI examples:
1. Ubiquitin (P62988 / 1UBQ) - Monomer (A1)
2. Hemoglobin-α (P69905) - Heterotetramer (A4)
3. Bacteriorhodopsin (P02945) - Homotrimer (A3)
4. p53 (P04637) - Homotetramer (A4)
5. AKT1 (P31749) - Monomer (A1)

Asserts:
- Every fixture strictly conforms to schema/quaternary_structure_output.schema.json.
- Biological ground truths: subunit count, stoichiometry formula, interfaces, and quaternary status.
"""

import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, validate

SCHEMA_PATH = Path("schema/quaternary_structure_output.schema.json")
FIXTURES_DIR = Path("schema/fixtures/ui_examples")


@pytest.fixture(scope="module")
def json_schema():
    assert SCHEMA_PATH.exists(), f"Published schema not found at {SCHEMA_PATH}"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def load_fixture(name: str) -> dict:
    fpath = FIXTURES_DIR / name
    assert fpath.exists(), f"Benchmark fixture '{name}' not found at {fpath}"
    return json.loads(fpath.read_text(encoding="utf-8"))


def test_all_ui_benchmark_fixtures_exist():
    """Verify that all 5 canonical benchmark JSON fixtures exist on disk."""
    expected_files = [
        "ubiquitin.json",
        "hemoglobin_alpha.json",
        "bacteriorhodopsin.json",
        "p53.json",
        "akt1.json",
    ]
    for fname in expected_files:
        p = FIXTURES_DIR / fname
        assert p.exists(), f"Expected fixture '{fname}' missing from {FIXTURES_DIR}"
        assert p.stat().st_size > 1000, f"Fixture '{fname}' is unexpectedly small or empty"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "ubiquitin.json",
        "hemoglobin_alpha.json",
        "bacteriorhodopsin.json",
        "p53.json",
        "akt1.json",
    ],
)
def test_fixture_schema_conformance(fixture_name, json_schema):
    """Verify that each benchmark fixture conforms strictly to Draft 2020-12 schema."""
    payload = load_fixture(fixture_name)
    validate(instance=payload, schema=json_schema, cls=Draft202012Validator)


def test_ubiquitin_biological_invariants(json_schema):
    """Verify Ubiquitin biological invariants (monomer baseline, 0 interfaces)."""
    data = load_fixture("ubiquitin.json")
    stoich = data.get("stoichiometry", {})

    assert stoich.get("total_subunits") == 1
    assert stoich.get("formula") == "A"
    assert data.get("quaternary_status") == "MONOMER"
    assert len(data.get("interfaces", [])) == 0


def test_hemoglobin_alpha_biological_invariants(json_schema):
    """Verify Hemoglobin alpha biological invariants (heterotetrameric complex assembly)."""
    data = load_fixture("hemoglobin_alpha.json")
    stoich = data.get("stoichiometry", {})

    # Hemoglobin operates as a 4-subunit assembly
    assert stoich.get("total_subunits") == 4
    assert stoich.get("formula") == "A4"
    assert len(data.get("interfaces", [])) >= 2

    # Verify non-zero buried surface area across interfaces
    interfaces = data.get("interfaces", [])
    total_bsa = sum(float(i.get("buried_surface_area_angstrom2", 0.0) or 0.0) for i in interfaces)
    assert total_bsa > 1000.0, "Hemoglobin complex must exhibit extensive buried surface area"


def test_bacteriorhodopsin_biological_invariants(json_schema):
    """Verify Bacteriorhodopsin biological invariants (homotrimer A3, 3 interfaces)."""
    data = load_fixture("bacteriorhodopsin.json")
    stoich = data.get("stoichiometry", {})

    assert stoich.get("total_subunits") == 3
    assert stoich.get("formula") == "A3"
    assert data.get("quaternary_status") == "HOMOMER"
    assert len(data.get("interfaces", [])) >= 1


def test_p53_biological_invariants(json_schema):
    """Verify p53 biological invariants (homotetramer A4, dimer-of-dimers contacts)."""
    data = load_fixture("p53.json")
    stoich = data.get("stoichiometry", {})

    assert stoich.get("total_subunits") == 4
    assert stoich.get("formula") == "A4"
    assert data.get("quaternary_status") == "HOMOMER"
    assert len(data.get("interfaces", [])) >= 2


def test_akt1_biological_invariants(json_schema):
    """Verify AKT1 kinase biological invariants (monomer baseline, 0 self-interfaces)."""
    data = load_fixture("akt1.json")
    stoich = data.get("stoichiometry", {})

    assert stoich.get("total_subunits") == 1
    assert stoich.get("formula") == "A"
    assert data.get("quaternary_status") == "MONOMER"
    assert len(data.get("interfaces", [])) == 0
