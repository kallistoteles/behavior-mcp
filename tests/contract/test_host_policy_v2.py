"""Trusted v2 grammar is a complete grant, never agent authority."""

import copy
import json
from pathlib import Path

import pytest

from behavior_mcp.policy import Delegation
from behavior_mcp.schemas import OperationError, validate

CONTRACTS = (
    Path(__file__).resolve().parents[2]
    / "specs/002-remaining-behavior-models/contracts"
)


@pytest.mark.parametrize(
    "name", ["host-policy-v2", "host-policy-v2-work-queue", "host-policy-v2-safety"]
)
def test_operator_policies_are_closed_and_accepted(name):
    doc = json.loads((CONTRACTS / f"examples/{name}.json").read_text())
    validate("host-policy-v2", doc)
    from behavior_mcp.adapters import HANDLERS

    if doc["allowed_adapters"][0]["adapter_version"] not in HANDLERS:
        with pytest.raises(OperationError) as caught:
            Delegation.from_document(doc, "local-operator")
        assert caught.value.code == "ADAPTER_UNAVAILABLE"
        return
    delegation = Delegation.from_document(doc, "local-operator")
    assert delegation.document == doc
    duplicate = copy.deepcopy(doc)
    duplicate["allowed_adapters"].append(duplicate["allowed_adapters"][0])
    with pytest.raises(OperationError):
        Delegation.from_document(duplicate, "local-operator")


def test_v2_approval_schema():
    doc = json.loads((CONTRACTS / "examples/activation-approval-v2.json").read_text())
    validate("activation-approval-v2", doc)
    doc["agent_approved"] = True
    with pytest.raises(OperationError):
        validate("activation-approval-v2", doc)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("allowed_model_ids", [], "MODEL_ID_DENIED"),
        ("allowed_action_names", [], "CAPABILITIES_DENIED"),
        ("allowed_read_names", [], "CAPABILITIES_DENIED"),
        ("allowed_entity_declarations", [], "DECLARATION_DENIED"),
        ("allowed_condition_ops", [], "CONDITION_OP_DENIED"),
        ("allowed_action_descriptors", [], "ACTION_DESCRIPTOR_DENIED"),
        ("allow_new_records", False, "CREATION_EFFECT_DENIED"),
    ],
)
def test_candidate_is_completely_scoped(field, value, code):
    from behavior_mcp.adapters import HANDLERS, build
    from tests.fixtures.expanded import example

    assert "2.0.0" in HANDLERS
    doc = example("host-policy-v2")
    doc["allowed_adapters"][0][field] = value
    delegation = Delegation.from_document(doc, "local-operator")
    proposal = example("approval")
    with pytest.raises(OperationError) as caught:
        delegation.check_candidate(proposal, build(proposal), existing=False)
    assert caught.value.code == code


def test_required_condition_is_a_whole_structural_root():
    from behavior_mcp.adapters import HANDLERS, build
    from tests.fixtures.expanded import example

    assert "2.0.0" in HANDLERS
    doc = example("host-policy-v2")
    doc["allowed_adapters"][0]["required_model_conditions"] = [
        {
            "model_id": "review",
            "slot": "eligible",
            "capability_id": None,
            "expression": {"op": "literal", "value": False},
        }
    ]
    proposal = example("approval")
    with pytest.raises(OperationError) as error:
        Delegation.from_document(doc, "local-operator").check_candidate(
            proposal, build(proposal), existing=False
        )
    assert error.value.code == "MODEL_CONDITION_DENIED"


def test_required_safety_cannot_be_ignored_for_operational_only_model(tmp_path):
    from behavior_mcp.artifacts import ArtifactStore
    from behavior_mcp.policy import TrustedContext
    from behavior_mcp.server import Application
    from tests.fixtures.expanded import example
    from tests.fixtures.runtime import authored

    doc = example("host-policy-v2")
    doc["allowed_adapters"][0]["required_safety"] = example("host-policy-v2-safety")[
        "allowed_adapters"
    ][0]["required_safety"]
    assert doc["allowed_adapters"][0]["required_safety"]
    artifacts = ArtifactStore(tmp_path)
    artifacts.install_policy(Delegation.from_document(doc, "local-operator").document)
    ctx = TrustedContext(
        "agent-session", "workspace-1", "actor-1", lambda: "2026-10-28T00:00:00Z"
    )
    app = Application(tmp_path, ctx, doc["policy_id"])
    d = authored(app, example("approval"))
    c = app.execute(
        "systems_create",
        {"definition_id": d["definition_id"], "operation_id": "create"},
    )
    assert c["outcome"] == "created", c
    receipt = c["result"]["receipt"]
    activated = app.execute(
        "definition_activate",
        {
            "system_id": receipt["system_id"],
            "definition_id": d["definition_id"],
            "operation_id": "activate",
            "expected_activation_revision": 0,
            "expected_history": receipt["history_anchor"],
        },
    )
    assert activated["outcome"] == "unauthorized", activated
    assert activated["error"]["code"] == "SAFETY_EVIDENCE_REQUIRED"


def test_exact_approval_binds_policy_set_even_with_same_behavior(tmp_path):
    from behavior_mcp.admin import AdminAuthority, install_approval
    from tests.fixtures.expanded import active, example
    from tests.fixtures.runtime import authored

    app, sid, original, proposal, policy = active(tmp_path, "field-ownership")
    proposal["safety"][0]["writers"]["phase"].append({"action": "remove_parent"})
    candidate = authored(app, proposal)
    assert candidate["behavior_hash"] == original["behavior_hash"]
    assert candidate["policy_set_hash"] != original["policy_set_hash"]
    current = app.execute("system_inspect", {"system_id": sid})["result"]
    args = {
        "system_id": sid,
        "definition_id": candidate["definition_id"],
        "expected_activation_revision": 1,
        "expected_history": current["history_anchor"],
        "operation_id": "approved-activation",
    }
    assert app.execute("definition_activate", args)["outcome"] == "unauthorized"
    document = example("activation-approval-v2")
    document.update(
        approval_id="exact-policy-change",
        system_id=sid,
        definition_id=candidate["definition_id"],
        behavior_hash=candidate["behavior_hash"],
        schema_hash=candidate["schema_hash"],
        policy_id=policy["policy_id"],
        policy_version=1,
        expected_activation_revision=1,
        history_anchor=current["history_anchor"],
        policy_set_hash=original["policy_set_hash"],
        required_evidence_refs=[],
        exceptions=["safety_scope"],
    )
    authority = AdminAuthority(
        "local-operator", "workspace-1", tmp_path, ("agent-session",)
    )
    with pytest.raises(OperationError) as error:
        install_approval(tmp_path, document, authority)
    assert error.value.code == "APPROVAL_SUBJECT_DENIED"
    document["policy_set_hash"] = candidate["policy_set_hash"]
    install_approval(tmp_path, document, authority)
    activated = app.execute("definition_activate", args)
    assert activated["outcome"] == "activated", activated
    assert (
        activated["result"]["receipt"]["policy_set_hash"]
        == candidate["policy_set_hash"]
    )
    updated = copy.deepcopy(policy)
    updated["version"] = 2
    app.artifacts.install_policy(
        Delegation.from_document(updated, "local-operator").document
    )
    retry = dict(
        args, operation_id="not-approved-again", expected_activation_revision=2
    )
    assert app.execute("definition_activate", retry)["outcome"] == "unauthorized"
