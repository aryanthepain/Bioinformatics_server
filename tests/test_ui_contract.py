"""
Deterministic Conformance Tests for Quaternary UI JSON Data Contract.

Verifies:
1. JSON Schema Draft 2020-12 definition integrity via Draft202012Validator.check_schema.
2. Conformance of canonical root quaternary_structure_output.json against the schema.
3. Conformance of dynamic QuaternarySession.to_ui(format="dict") output against the schema.
4. Correct failure and error reporting for invalid/negative payloads violating the schema.
"""

import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, validate
from jsonschema.exceptions import ValidationError

from quaternary.config import QuaternaryConfig
from quaternary.session import QuaternarySession


@pytest.fixture(scope="module")
def schema_path():
    p = Path("schema/quaternary_structure_output.schema.json")
    assert p.exists(), "Published JSON schema must exist at schema/quaternary_structure_output.schema.json"
    return p


@pytest.fixture(scope="module")
def published_schema(schema_path):
    content = schema_path.read_text(encoding="utf-8")
    schema_dict = json.loads(content)
    return schema_dict


@pytest.fixture(scope="module")
def canonical_payload_path():
    p = Path("quaternary_structure_output.json")
    assert p.exists(), "Canonical output payload must exist at root quaternary_structure_output.json"
    return p


def test_schema_draft_2020_12_integrity(published_schema):
    """Verify that published JSON schema is a syntactically valid Draft 2020-12 schema."""
    assert published_schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert published_schema.get("title") == "QuaternaryStructureOutput"
    assert "properties" in published_schema
    assert "required" in published_schema

    # Metaschema validation: raises SchemaError if invalid
    Draft202012Validator.check_schema(published_schema)


def test_canonical_root_payload_conformance(published_schema, canonical_payload_path):
    """Verify that canonical root quaternary_structure_output.json conforms strictly to the schema."""
    payload = json.loads(canonical_payload_path.read_text(encoding="utf-8"))

    # Should validate without error
    validate(instance=payload, schema=published_schema, cls=Draft202012Validator)

    # Core required keys check
    for req_field in ["analysis_id", "target_accession_or_sequence", "quaternary_status", "stoichiometry"]:
        assert req_field in payload


def test_dynamic_session_to_ui_conformance(published_schema):
    """Verify that live QuaternarySession.to_ui(format='dict') generates schema-conforming payload."""
    cfg = QuaternaryConfig(offline_mode=True, cache_enabled=True)
    session = QuaternarySession("P0A6F5", config=cfg)
    session.run_stage_1_sequence_and_accession()
    session.run_stage_2_experimental_assemblies()
    session.run_stage_3_thermodynamic_qualification()
    session.run_stage_4_homology_and_partners()
    session.run_stage_5_predictive_multimer(enable_multimer=False)
    session.run_stage_6_synthesis_and_functional_inference()

    ui_dict = session.to_ui(format="dict")
    assert isinstance(ui_dict, dict)

    # Ensure dynamic dict passes strict jsonschema validation
    validate(instance=ui_dict, schema=published_schema, cls=Draft202012Validator)


def test_negative_payload_validation_errors(published_schema, canonical_payload_path):
    """Verify that invalid payloads trigger jsonschema.ValidationError."""
    payload = json.loads(canonical_payload_path.read_text(encoding="utf-8"))

    # Test 1: Missing required field (analysis_id)
    corrupted_payload = dict(payload)
    del corrupted_payload["analysis_id"]
    with pytest.raises(ValidationError) as exc_info:
        validate(instance=corrupted_payload, schema=published_schema, cls=Draft202012Validator)
    assert "'analysis_id' is a required property" in str(exc_info.value)

    # Test 2: Invalid type for stoichiometry (expected object, pass int)
    corrupted_payload2 = dict(payload)
    corrupted_payload2["stoichiometry"] = 12345
    with pytest.raises(ValidationError):
        validate(instance=corrupted_payload2, schema=published_schema, cls=Draft202012Validator)

    # Test 3: Invalid type for stages_completed (expected array, pass string)
    corrupted_payload3 = dict(payload)
    corrupted_payload3["stages_completed"] = "not-an-array"
    with pytest.raises(ValidationError):
        validate(instance=corrupted_payload3, schema=published_schema, cls=Draft202012Validator)
