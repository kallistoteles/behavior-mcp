"""Public whole-module Safety analysis owns permission classification."""

import copy

import pytest
from behavior import BehaviorError

from behavior_mcp.adapters import build
from behavior_mcp.schemas import OperationError
from tests.fixtures.expanded import example


@pytest.mark.parametrize("permission", ["writers", "creators", "removers"])
def test_missing_permission_is_reported_by_public_analysis(permission):
    doc = example("field-ownership")
    if permission == "writers":
        doc["safety"][0]["writers"]["phase"] = []
    else:
        doc["safety"][0][permission] = []
    try:
        module = build(doc)
    except (BehaviorError, OperationError):
        return
    analysis = module.safety_analysis.to_dict()
    assert analysis["issues"] or analysis["status"] != "Lowered", analysis


def test_policy_only_change_has_separate_identity():
    proposal = example("field-ownership")
    proposal["declarations"]["entities"][0]["fields"]["label"] = {"kind": "string"}
    proposal["actions"][0]["values"]["label"] = {"op": "literal", "value": "Parent"}
    module = build(proposal)
    changed = copy.deepcopy(proposal)
    changed["safety"][0]["writers"]["label"] = []
    next_module = build(changed)
    assert module.behavior_version == next_module.behavior_version
    assert (
        module.safety_analysis.to_dict()["policy_set_hash"]
        != next_module.safety_analysis.to_dict()["policy_set_hash"]
    )


def test_policy_label_is_not_a_semantic_identity():
    proposal = example("field-ownership")
    module = build(proposal)
    proposal["safety"][0]["id"] = "other_control"
    rebuilt = build(proposal)
    assert (
        module.safety_analysis.to_dict()["policy_set_hash"]
        == rebuilt.safety_analysis.to_dict()["policy_set_hash"]
    )


@pytest.mark.parametrize("false_guard", [False, True])
def test_false_or_same_value_writes_still_require_permission(false_guard):
    proposal = example("field-ownership")
    proposal["actions"].append(
        {
            "kind": "set_field",
            "name": "unapproved",
            "entity": "Parent",
            "field": "phase",
            "value": {"op": "enum", "enum": "ParentPhase", "case": "STOPPED"},
            "requires": [{"op": "literal", "value": not false_guard}],
        }
    )
    with pytest.raises(BehaviorError):
        build(proposal)


def test_overlapping_policies_do_not_union_permissions():
    proposal = example("field-ownership")
    restricted = copy.deepcopy(proposal["safety"][0])
    restricted["id"] = "restricted"
    restricted["writers"]["phase"] = []
    proposal["safety"].append(restricted)
    with pytest.raises(BehaviorError):
        build(proposal)
