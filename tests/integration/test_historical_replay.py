import copy

import pytest

from behavior_mcp.policy import Delegation
from behavior_mcp.schemas import OperationError
from behavior_mcp.server import Application
from behavior_mcp.systems import SystemManager
from tests.fixtures.runtime import authored, create_active, evaluate_commit


def test_replay_uses_original_modules_and_does_not_relabel_policy(
    trusted_setup, proposal, policy_document
):
    root, ctx, policy, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, a = create_active(app, proposal)
    evaluate_commit(
        app, sid, "record__new", "first", input={"request_id": "r1", "label": "Example"}
    )
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    d2 = authored(app, changed)
    head = app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
    assert (
        app.execute(
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d2["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": head,
                "operation_id": "new-version",
            },
        )["outcome"]
        == "activated"
    )
    evaluate_commit(
        app,
        sid,
        "record__complete",
        "second",
        bindings={"record": "r1"},
        input={"outcome": "Complete"},
    )
    policy_document.update(version=2)
    artifacts.install_policy(policy_document)
    manager = SystemManager(
        root,
        ctx,
        artifacts,
        Delegation.from_document(policy_document, "local-operator"),
    )
    replay = manager.replay(sid)
    assert replay["data"]["ok"] and replay["behavior"]["ok"]
    assert replay["behavior"]["checked"] == 2
    assert {x["behavior_hash"] for x in replay["definitions"]} == {
        d["behavior_hash"],
        d2["behavior_hash"],
    }
    original = app.execute(
        "operation_get", {"system_id": sid, "operation_id": "activate-1"}
    )["result"]["receipt"]
    assert (
        original == a["result"]["receipt"] and original["policy"]["policy_version"] == 1
    )
    assert artifacts.policy("local-delegation", 1)["version"] == 1
    assert replay["release"]["core_version"] == "0.15.0"


def test_missing_original_module_blocks_historical_replay(trusted_setup, proposal):
    root, ctx, policy, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
    evaluate_commit(
        app, sid, "record__new", "first", input={"request_id": "r1", "label": "Example"}
    )
    from behavior_mcp.storage import connect, transaction

    with connect(artifacts.path) as db, transaction(db):
        db.execute("DELETE FROM blobs WHERE id=?", (d["module_ref"],))
    with pytest.raises(OperationError):
        SystemManager(root, ctx, artifacts, policy).replay(sid)
