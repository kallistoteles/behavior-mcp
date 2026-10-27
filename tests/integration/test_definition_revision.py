import copy

from behavior_mcp.server import Application
from tests.fixtures.runtime import create_active, evaluate_commit


def test_explicit_parent_revision_after_restart_preserves_system_and_history(
    trusted_setup, proposal
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    one, original, _, a1 = create_active(app, proposal, "1")
    two, _, _, _ = create_active(app, proposal, "2")
    evaluate_commit(
        app,
        one,
        "record__new",
        "initial-record",
        input={"request_id": "r1", "label": "Example"},
    )
    old = app.execute("system_inspect", {"system_id": one})["result"]
    other = app.execute("system_inspect", {"system_id": two})["result"]
    app = Application(root, ctx, "local-delegation")
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    p = app.execute(
        "definition_propose",
        {"proposal": changed, "parent_definition_id": original["definition_id"]},
    )["result"]
    revised = app.execute(
        "definition_validate", {"proposal_id": p["proposal_id"], "proposal_revision": 1}
    )["result"]["definition"]
    assert revised["parent_definition_id"] == original["definition_id"]
    assert (
        revised["behavior_hash"] != original["behavior_hash"]
        and revised["schema_hash"] == original["schema_hash"]
    )
    assert revised["models"][0]["model_hash"] != original["models"][0]["model_hash"]
    assert app.execute("system_inspect", {"system_id": one})["result"] == old
    activated = app.execute(
        "definition_activate",
        {
            "system_id": one,
            "definition_id": revised["definition_id"],
            "expected_activation_revision": 1,
            "expected_history": old["history_anchor"],
            "operation_id": "revision-activation",
        },
    )
    assert activated["outcome"] == "activated", activated
    assert app.execute("system_inspect", {"system_id": two})["result"] == other
    evaluate_commit(
        app,
        one,
        "record__complete",
        "revised-finish",
        bindings={"record": "r1"},
        input={"outcome": "Complete"},
    )
    recovery = app.execute("system_recover", {"system_id": one})
    report = artifacts.get(recovery["evidence"][0]["report_ref"])["report"]
    assert report["replay"]["data"]["ok"] and report["replay"]["behavior"]["ok"]
    assert {d["definition_id"] for d in report["replay"]["definitions"]} == {
        original["definition_id"],
        revised["definition_id"],
    }
    assert (
        app.execute("operation_get", {"system_id": one, "operation_id": "activate-1"})[
            "result"
        ]["receipt"]
        == a1["result"]["receipt"]
    )
