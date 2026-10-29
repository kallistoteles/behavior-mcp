"""Retained contexts must identify the complete exact source/schema closure."""

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from behavior_mcp.schemas import OperationError


def test_unpublished_versions_cannot_be_proposed(trusted_setup):
    assert importlib.util.find_spec("behavior_mcp.adapters"), (
        "Versioned artifact boundary is absent"
    )
    adapters = importlib.import_module("behavior_mcp.adapters")
    path = (
        Path(__file__).resolve().parents[2]
        / "specs/002-remaining-behavior-models/contracts/examples/approval.json"
    )
    proposal = json.loads(path.read_text())
    proposal["adapter_version"] = "2.999.0"
    with pytest.raises(OperationError) as caught:
        adapters.construction_context(proposal)
    assert caught.value.category == "unsupported"


def test_safety_analysis_and_inventory_are_separate_inspectable_artifacts(tmp_path):
    from tests.fixtures.expanded import setup
    from tests.fixtures.runtime import authored

    app, proposal, _ = setup(tmp_path, "field-ownership")
    definition = authored(app, proposal)
    result = app.execute(
        "definition_get", {"definition_id": definition["definition_id"]}
    )
    assert result["request_status"] == "completed", result
    kinds = {a["kind"] for a in result["result"]["artifacts"]}
    assert {"safety_analysis", "capability_inventory"} <= kinds
    analysis = next(
        a["document"]
        for a in result["result"]["artifacts"]
        if a["kind"] == "safety_analysis"
    )
    assert analysis["is_certified"] is False
    assert analysis["policy_set_hash"] == definition["policy_set_hash"]


def test_repeated_policy_identity_must_match(tmp_path):
    import copy

    from behavior_mcp.schemas import validate_output
    from tests.fixtures.expanded import setup
    from tests.fixtures.runtime import authored

    app, proposal, _ = setup(tmp_path, "field-ownership")
    definition = authored(app, proposal)
    result = app.execute(
        "definition_get", {"definition_id": definition["definition_id"]}
    )
    assert result["request_status"] == "completed", result
    result = copy.deepcopy(result)
    result["subject"]["policy_set_hash"] = definition["policy_set_hash"]
    result["result"]["definition"]["policy_set_hash"] = "sha256:" + "1" * 64
    with pytest.raises(OperationError):
        validate_output(result, expanded=True)
