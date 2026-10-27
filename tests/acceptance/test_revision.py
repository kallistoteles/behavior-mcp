import copy

from behavior_mcp.server import Application
from tests.fixtures.runtime import authored, create_active, evaluate_commit


def test_persistent_revision_and_original_history_evidence(trusted_setup, proposal):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal, "1")
    other, _, _, _ = create_active(app, proposal, "2")
    evaluate_commit(
        app,
        sid,
        "record__new",
        "create-record",
        input={"request_id": "r1", "label": "Example"},
    )
    original_head = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    d2 = authored(Application(root, ctx, "local-delegation"), changed)
    assert (
        app.execute(
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d2["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": original_head,
                "operation_id": "revision",
            },
        )["outcome"]
        == "activated"
    )
    evaluate_commit(
        app,
        sid,
        "record__complete",
        "finish-record",
        bindings={"record": "r1"},
        input={"outcome": "Complete"},
    )
    restarted = Application(root, ctx, "local-delegation")
    recovery = restarted.execute("system_recover", {"system_id": sid})
    evidence = artifacts.get(recovery["evidence"][0]["report_ref"])["report"]["replay"]
    assert evidence["data"]["ok"] and evidence["behavior"]["ok"]
    assert (
        restarted.execute("system_inspect", {"system_id": other})["result"]["active"][
            "activation_revision"
        ]
        == 1
    )
    historical = restarted.execute(
        "state_read",
        {
            "system_id": sid,
            "entity": "Record",
            "record_id": "r1",
            "history": original_head,
        },
    )
    assert historical["result"]["read_definition_id"] == d["definition_id"]
    assert historical["result"]["records"][0]["value"]["status"] == "Open"
