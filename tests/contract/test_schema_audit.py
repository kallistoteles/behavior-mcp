"""Fixed packaged contracts are audited once by the gate; caller data is always checked."""

import importlib.metadata
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, SchemaError

from behavior_mcp import schemas
from tests.fixtures.expanded import example


def test_gate_audits_every_packaged_schema():
    packaged = Path(
        str(
            importlib.metadata.distribution("behavior-mcp").locate_file(
                "behavior_mcp/contracts"
            )
        )
    )
    names = {
        p.name.removesuffix(".schema.json") for p in packaged.glob("*.schema.json")
    }
    assert set(schemas.audit_schemas()) == names


def test_gate_refuses_invalid_host_schema(tmp_path, monkeypatch):
    broken = tmp_path / "broken.schema.json"
    broken.write_text('{"type":"not-a-json-schema-type"}')
    monkeypatch.setattr(schemas, "resource", lambda _: broken)
    schemas._schema.cache_clear()
    try:
        with pytest.raises(SchemaError):
            schemas.audit_schemas()
    finally:
        schemas._schema.cache_clear()


def test_runtime_checks_requests_without_repeating_host_schema_audit(monkeypatch):
    def forbidden(*_, **__):
        raise AssertionError("Host schema meta-validation belongs to the quality gate")

    monkeypatch.setattr(Draft202012Validator, "check_schema", forbidden)
    schemas._schema.cache_clear()
    schemas.validate_input("definition_propose", {"proposal": example("approval")})
    with pytest.raises(schemas.OperationError) as failure:
        schemas.validate_input(
            "definition_propose", {"proposal": example("approval"), "approved": True}
        )
    assert failure.value.code == "SCHEMA_INVALID"
