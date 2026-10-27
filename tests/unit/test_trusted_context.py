from dataclasses import FrozenInstanceError

import pytest

from behavior_mcp.policy import Delegation, TrustedContext
from behavior_mcp.schemas import OperationError


def test_context_is_host_owned_and_immutable(context):
    with pytest.raises(FrozenInstanceError):
        context.principal_id = "admin"


def test_grants_are_explicit_and_scoped(context, policy_document):
    policy = Delegation.from_document(policy_document, "local-operator")
    policy.authorize(context, "definition_propose")
    policy.authorize(context, "definition_activate", "system-1")
    with pytest.raises(OperationError):
        policy.authorize(
            TrustedContext("impostor", "workspace-1", "actor-1", context.clock),
            "definition_propose",
        )
    policy_document["operations"] = []
    denied = Delegation.from_document(policy_document, "local-operator")
    with pytest.raises(OperationError):
        denied.authorize(context, "models_list")
    policy_document["operations"] = ["definition_activate"]
    policy_document["system_scope"] = {"kind": "ids", "system_ids": ["system-1"]}
    exact = Delegation.from_document(policy_document, "local-operator")
    exact.authorize(context, "definition_activate", "system-1")
    with pytest.raises(OperationError):
        exact.authorize(context, "definition_activate", "system-2")


def test_policy_returns_no_mutable_authority(context, policy_document):
    policy = Delegation.from_document(policy_document, "local-operator")
    policy.document["operations"].clear()
    policy.authorize(context, "models_list")
