"""Domain policies cannot establish host authority or waive proof requirements."""

import pytest

from behavior_mcp.adapters import HANDLERS, build
from behavior_mcp.policy import Delegation
from behavior_mcp.schemas import OperationError
from tests.fixtures.expanded import example


def test_ownership_version_is_not_inherited_from_queue():
    assert "2.2.0" in HANDLERS, (
        "FieldOwnership has not been delivered through its own immutable checkpoint"
    )
    assert "field_ownership" not in HANDLERS["2.1.0"].KINDS


@pytest.mark.parametrize("remove_policy", [False, True])
def test_policy_cannot_remove_required_protection(remove_policy):
    doc = example("field-ownership")
    if remove_policy:
        doc["safety"] = []
    else:
        doc["safety"][0]["writers"] = {}
    module = build(doc)
    policy = Delegation.from_document(
        example("host-policy-v2-field-ownership"), "local-operator"
    )
    with pytest.raises(OperationError) as caught:
        policy.check_candidate(doc, module, existing=True)
    assert caught.value.code in {"REQUIRED_POLICY_MISSING", "PROTECTED_FIELD_MISSING"}
