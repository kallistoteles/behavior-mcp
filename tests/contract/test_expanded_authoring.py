"""Closed expanded input and installed exact-version validators."""

import copy
import json
from pathlib import Path

import pytest

from behavior_mcp.schemas import OperationError, load_schema, validate

CONTRACTS = (
    Path(__file__).resolve().parents[2]
    / "specs/002-remaining-behavior-models/contracts"
)


@pytest.mark.parametrize(
    "name,version",
    [
        ("approval", "2.0.0"),
        ("work-queue", "2.1.0"),
        ("field-ownership", "2.2.0"),
        ("lifecycle", "2.3.0"),
    ],
)
def test_installed_exact_authoring_schema(name, version):
    doc = json.loads((CONTRACTS / f"examples/{name}.json").read_text())
    schema = load_schema(f"authoring-v2-{version}")
    assert schema["properties"]["adapter_version"]["const"] == version
    validate(f"authoring-v2-{version}", doc)
    invalid = copy.deepcopy(doc)
    invalid["unknown"] = True
    with pytest.raises(OperationError):
        validate(f"authoring-v2-{version}", invalid)
    for invalid_version in ("latest", "2.99.0", None):
        invalid = copy.deepcopy(doc)
        invalid["adapter_version"] = invalid_version
        with pytest.raises(OperationError):
            validate(f"authoring-v2-{version}", invalid)


def test_identifier_and_model_bounds():
    doc = json.loads((CONTRACTS / "examples/approval.json").read_text())
    doc["models"][0]["model_id"] = "x" * 65
    with pytest.raises(OperationError):
        validate("authoring-v2-2.0.0", doc)
