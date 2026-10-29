"""Approval authoring is bounded data and public model admission."""

import pytest

from behavior_mcp.adapters import build
from behavior_mcp.schemas import OperationError
from tests.fixtures.expanded import example


def test_approval_module_and_public_receipt():
    m = build(example("approval"))
    receipt = m.model_receipts[0]
    assert receipt.model_kind == "approval"
    assert receipt.model["approve_threshold"] == 2
    assert receipt.model["reject_threshold"] == 1
    assert {a["id"] for a in receipt.model["capabilities"]} == {"approve", "reject"}


@pytest.mark.parametrize("threshold", [0, -1])
def test_invalid_threshold_is_public_model_error(threshold):
    from behavior import BehaviorError

    doc = example("approval")
    doc["models"][0]["approve_threshold"] = threshold
    with pytest.raises((BehaviorError, OperationError)):
        build(doc)


def test_unknown_fragment_reference_is_a_model_error():
    from behavior import BehaviorError

    doc = example("approval")
    doc["models"][0]["eligible"] = {"op": "param", "name": "missing"}
    with pytest.raises((BehaviorError, OperationError)):
        from behavior_mcp.authoring_v2 import build as draft_build

        draft_build(doc)


def test_open_condition_can_use_trusted_actor_symbol():
    from behavior_mcp.authoring_v2 import build as draft_build

    doc = example("approval")
    doc["models"][0]["open_when"] = {
        "op": "eq",
        "left": {"op": "param", "name": "actor"},
        "right": {"op": "param", "name": "actor"},
    }
    m = draft_build(doc)
    assert m.model_receipts[0].model["capabilities"][0]["open"]
