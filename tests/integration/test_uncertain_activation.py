import copy

import pytest

from behavior_mcp.server import Application
from tests.fixtures.runtime import authored, create_active


def test_activation_retry_resolves_original_before_stale_cas(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, created, original = create_active(app, proposal)
    first_args = {
        "system_id": sid,
        "definition_id": d["definition_id"],
        "expected_activation_revision": 0,
        "expected_history": created["result"]["receipt"]["history_anchor"],
        "operation_id": "activate-1",
    }
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    d2 = authored(app, changed)
    a2 = app.execute(
        "definition_activate",
        dict(
            first_args,
            definition_id=d2["definition_id"],
            expected_activation_revision=1,
            operation_id="activate-2",
        ),
    )
    assert a2["outcome"] == "activated", a2
    policy_document.update(
        version=2,
        operations=[
            o for o in policy_document["operations"] if o != "definition_activate"
        ],
    )
    artifacts.install_policy(policy_document)
    retried = Application(root, ctx, "local-delegation").execute(
        "definition_activate", first_args
    )
    assert retried["outcome"] == "already_activated", retried
    assert retried["result"]["receipt"] == original["result"]["receipt"]
    assert (
        retried["result"]["observed_current_deployment"]["definition_id"]
        == d2["definition_id"]
    )
    assert (
        app.execute(
            "definition_activate", dict(first_args, definition_id=d2["definition_id"])
        )["outcome"]
        == "conflict"
    )
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"][
            "activation_revision"
        ]
        == 2
    )


@pytest.mark.parametrize(
    "phase,revision", [("activation_before_commit", 0), ("activation_after_commit", 1)]
)
def test_activation_process_crash_has_one_atomic_receipt(
    trusted_setup, proposal, subprocess_python, phase, revision
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    d = authored(app, proposal)
    c = app.execute(
        "systems_create",
        {"definition_id": d["definition_id"], "operation_id": "create-crash"},
    )["result"]["receipt"]
    sid = c["system_id"]
    import json

    request = {
        "system_id": sid,
        "definition_id": d["definition_id"],
        "expected_activation_revision": 0,
        "expected_history": c["history_anchor"],
        "operation_id": "activation-crash",
    }
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation',fault=lambda stage:os._exit(75) if stage==sys.argv[2] else None)
app.execute('definition_activate',json.loads(sys.argv[3]))
"""
    assert subprocess_python(script, root, phase, json.dumps(request)).returncode == 75
    inspected = app.execute("system_inspect", {"system_id": sid})["result"]
    assert (
        inspected["active"]["activation_revision"] if inspected["active"] else 0
    ) == revision
    replay = app.execute("definition_activate", request)
    assert replay["outcome"] == ("already_activated" if revision else "activated"), (
        replay
    )
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"][
            "activation_revision"
        ]
        == 1
    )
