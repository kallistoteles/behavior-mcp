import pytest

from behavior_mcp.policy import Delegation
from behavior_mcp.schemas import OperationError


@pytest.mark.parametrize(
    "field,value",
    [
        ("extra", True),
        ("operations", ["policy_update"]),
        ("effects", {"allow_external_commands": True}),
        ("system_scope", {"kind": "glob", "pattern": "*"}),
        ("system_creation", {"allowed": True}),
    ],
)
def test_closed_policy_rejects_unknown_or_partial_rules(policy_document, field, value):
    policy_document[field] = value
    with pytest.raises(OperationError):
        Delegation.from_document(policy_document, "local-operator")


def test_forged_issuer_is_rejected(policy_document):
    with pytest.raises(OperationError):
        Delegation.from_document(policy_document, "impostor")


def test_required_profile_is_explicit(policy_document):
    del policy_document["system_creation"]["core_policy_profile"]
    with pytest.raises(OperationError):
        Delegation.from_document(policy_document, "local-operator")
