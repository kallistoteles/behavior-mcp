import copy

import pytest
from behavior import InMemoryBackend, Store

from behavior_mcp.server import Application
from tests.fixtures.public_models import SEED, reference_module
from tests.fixtures.runtime import authored, create_active, evaluate_commit


@pytest.mark.parametrize("decision", ["DENY", "INVALID_INPUT"])
def test_refused_evaluation_retry_returns_original_after_restart_and_state_changes(
    trusted_setup, proposal, decision
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    if decision == "DENY":
        evaluate_commit(
            app,
            sid,
            "record__new",
            "original-new",
            input={"request_id": "r1", "label": "Example"},
        )
        evaluate_commit(
            app,
            sid,
            "record__finish",
            "original-finish",
            bindings={"record": "r1"},
            input={"outcome": "Complete"},
        )
        capability, bindings, inputs = (
            "record__finish",
            {"record": "r1"},
            {"outcome": "Again"},
        )
    else:
        capability, bindings, inputs = "record__new", {}, {"request_id": "invalid"}
    args = {
        "system_id": sid,
        "capability_id": capability,
        "bindings": bindings,
        "input": inputs,
        "expected_activation_revision": 1,
        "operation_id": "original-refusal",
    }
    first = app.execute("transition_evaluate", args)
    assert first["result"]["core_decision"]["result"] == decision
    evaluate_commit(
        app,
        sid,
        "record__new",
        "intervening-new",
        input={"request_id": "r2", "label": "Later"},
    )
    before = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    definition = authored(app, changed)
    activated = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "operation_id": "new-deployment",
            "expected_activation_revision": 1,
            "expected_history": before,
        },
    )
    assert activated["outcome"] == "activated", activated
    reopened = Application(root, ctx, "local-delegation")
    assert reopened.execute("transition_evaluate", args) == first
    assert (
        reopened.execute(
            "transition_evaluate", dict(args, input={"outcome": "Changed"})
        )["outcome"]
        == "conflict"
    )
    assert (
        reopened.execute("system_inspect", {"system_id": sid})["result"][
            "history_anchor"
        ]
        == before
    )


def test_runtime_decisions_match_public_core(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, definition, created, activated = create_active(app, proposal)
    m = reference_module()
    oracle = Store.create(InMemoryBackend(), m, Store.genesis_for(m, SEED))
    expected = oracle.evaluate(
        m,
        "record__new",
        bindings={},
        input={"request_id": "r1", "label": "Example"},
        context={"actor": "actor-1"},
        commit_time=ctx.clock(),
    )
    actual, committed = evaluate_commit(
        app, sid, "record__new", "new-1", input={"request_id": "r1", "label": "Example"}
    )
    oracle.commit(m, expected.bundle)
    assert actual["result"]["decision"]["result"] == expected.decision.result
    assert committed["result"]["receipt"]["result_state"] == oracle.current().as_dict()
    before = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    missing = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r2"},
            "expected_activation_revision": 1,
            "operation_id": "missing",
        },
    )
    assert missing["outcome"] == "semantic_refusal"
    assert missing["result"]["core_decision"]["result"] == "INVALID_INPUT"
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
        == before
    )
    evaluate_commit(
        app,
        sid,
        "record__finish",
        "finish-1",
        bindings={"record": "r1"},
        input={"outcome": "Complete"},
    )
    refused = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__finish",
            "bindings": {"record": "r1"},
            "input": {"outcome": "Again"},
            "expected_activation_revision": 1,
            "operation_id": "again",
        },
    )
    assert refused["result"]["core_decision"]["result"] == "DENY"
    read = app.execute(
        "state_read", {"system_id": sid, "entity": "Record", "record_id": "r1"}
    )
    assert read["result"]["records"][0]["value"]["status"] == "Done"
    old = app.execute(
        "state_read",
        {"system_id": sid, "entity": "Record", "record_id": "r1", "history": before},
    )
    assert old["result"]["records"][0]["value"]["status"] == "Open"
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"][
            "position"
        ]
        == 2
    )
