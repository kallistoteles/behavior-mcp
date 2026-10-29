"""State validity is acquired through Core and repeated at activation."""

from behavior import InMemoryBackend, Store, validate_safety_snapshot

from behavior_mcp.adapters import build
from tests.fixtures.expanded import example, setup
from tests.fixtures.runtime import authored


def test_public_valid_and_invalid_snapshot_without_detached_substitute():
    import pytest

    module = build(example("lifecycle"))
    good = Store.create(InMemoryBackend(), module, Store.genesis_for(module, []))
    valid = validate_safety_snapshot(good, module, at=good.current_history())
    assert valid.status == "Valid" and valid.matches_anchor(
        module, good.current_history()
    )
    seed = [
        {"entity": "Parent", "value": {"id": "p1", "phase": "Stopped"}},
        {"entity": "Child", "value": {"id": "c1", "phase": "Active", "owner": "p1"}},
    ]
    bad = Store.create(InMemoryBackend(), module, Store.genesis_for(module, seed))
    invalid = validate_safety_snapshot(bad, module, at=bad.current_history())
    assert invalid.status == "Invalid"
    assert not invalid.matches_anchor(module, bad.current_history())
    with pytest.raises(TypeError):
        validate_safety_snapshot({}, module)


def test_required_certificate_does_not_automatically_activate(tmp_path):
    app, proposal, _ = setup(tmp_path, "lifecycle")
    definition = authored(app, proposal)
    created = app.execute(
        "systems_create",
        {"definition_id": definition["definition_id"], "operation_id": "create"},
    )
    assert created["outcome"] == "created", created
    receipt = created["result"]["receipt"]
    sid = receipt["system_id"]
    args = {
        "system_id": sid,
        "definition_id": definition["definition_id"],
        "expected_activation_revision": 0,
        "expected_history": receipt["history_anchor"],
        "operation_id": "activate",
    }
    refused = app.execute("definition_activate", args)
    assert refused["outcome"] == "unauthorized", refused
    before = app.execute("system_inspect", {"system_id": sid})
    assert before["result"]["active"] is None


def test_certified_definition_still_requires_fresh_state_and_activation(tmp_path):
    from tests.fixtures.expanded import retained_lifecycle

    app, _, definition, _, _ = retained_lifecycle(tmp_path)
    created = app.execute(
        "systems_create",
        {"definition_id": definition["definition_id"], "operation_id": "second-create"},
    )
    assert created["outcome"] == "created", created
    receipt = created["result"]["receipt"]
    sid = receipt["system_id"]
    observed = app.execute(
        "state_validate_safety",
        {
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "expected_history": receipt["history_anchor"],
        },
    )
    assert observed["result"]["validation_status"] == "Valid", observed
    assert app.execute("system_inspect", {"system_id": sid})["result"]["active"] is None
    activated = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "expected_activation_revision": 0,
            "expected_history": receipt["history_anchor"],
            "operation_id": "second-activate",
        },
    )
    assert activated["outcome"] == "activated", activated
    assert activated["result"]["receipt"]["state_validation_ref"] is not None


def test_invalid_incoming_state_blocks_even_a_real_certificate(tmp_path):
    import copy

    from behavior_mcp.policy import Delegation
    from tests.fixtures.expanded import retained_lifecycle
    from tests.fixtures.runtime import evaluate_commit

    app, sid, incoming, proposal, policy = retained_lifecycle(tmp_path)
    unguarded = copy.deepcopy(proposal)
    unguarded["safety"] = []
    stop = next(a for a in unguarded["actions"] if a["name"] == "stop_parent")
    stop["requires"] = []
    delegation = copy.deepcopy(policy)
    delegation["version"] = 2
    grant = delegation["allowed_adapters"][0]
    grant["required_safety"] = []
    grant["required_policy_ids"] = []
    grant["allowed_action_descriptors"].append(stop)
    grant["required_guard_roots"] = [
        r
        for r in grant["required_guard_roots"]
        if r["capability"] != {"action": "stop_parent"}
    ]
    app.artifacts.install_policy(
        Delegation.from_document(delegation, "local-operator").document
    )
    definition = authored(app, unguarded)

    def activate(target, op):
        current = app.execute("system_inspect", {"system_id": sid})["result"]
        return app.execute(
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": target["definition_id"],
                "expected_activation_revision": current["active"][
                    "activation_revision"
                ],
                "expected_history": current["history_anchor"],
                "operation_id": op,
            },
        )

    assert activate(definition, "unguarded-activation")["outcome"] == "activated"
    evaluate_commit(app, sid, "new_parent", "bad-parent", input={"new_id": "p_bad"})
    evaluate_commit(
        app,
        sid,
        "new_child",
        "bad-child",
        bindings={"parent": "p_bad"},
        input={"new_id": "c_bad"},
    )
    evaluate_commit(
        app, sid, "stop_parent", "unguarded-stop", bindings={"subject": "p_bad"}
    )
    restored = copy.deepcopy(policy)
    restored["version"] = 3
    app.artifacts.install_policy(
        Delegation.from_document(restored, "local-operator").document
    )
    history = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    observed = app.execute(
        "state_validate_safety",
        {
            "system_id": sid,
            "definition_id": incoming["definition_id"],
            "expected_history": history,
        },
    )
    assert observed["result"]["validation_status"] == "Invalid", observed
    blocked = activate(incoming, "invalid-activation")
    assert blocked["outcome"] == "unauthorized", blocked
    assert blocked["error"]["code"] == "SAFETY_STATE_INVALID"
    evaluate_commit(
        app, sid, "finish_child", "repair-child", bindings={"subject": "c_bad"}
    )
    moved = app.execute(
        "state_validate_safety",
        {
            "system_id": sid,
            "definition_id": incoming["definition_id"],
            "expected_history": history,
        },
    )
    assert moved["outcome"] == "conflict", moved
    final = activate(incoming, "valid-activation")
    assert final["outcome"] == "activated", final
    assert (
        final["result"]["receipt"]["state_validation_ref"]
        != observed["result"]["validation_ref"]
    )
