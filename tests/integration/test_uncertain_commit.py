import pytest

from behavior_mcp.server import Application
from tests.fixtures.runtime import create_active, evaluate_commit


def test_lost_commit_ack_retry_never_reevaluates(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    e, committed = evaluate_commit(
        app, sid, "record__new", "new-1", input={"request_id": "r1", "label": "Example"}
    )
    args = {
        "system_id": sid,
        "evaluation_token": e["result"]["evaluation_token"],
        "operation_id": "new-1",
    }
    retried = Application(root, ctx, "local-delegation").execute(
        "transition_commit", args
    )
    assert retried["outcome"] == "already_committed", retried
    assert retried["result"]["receipt"] == committed["result"]["receipt"]
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"][
            "position"
        ]
        == 1
    )
    status = app.execute("operation_get", {"system_id": sid, "operation_id": "new-1"})
    assert status["result"]["status"] == "committed"
    assert status["result"]["operation_kind"] == "transition"


@pytest.mark.parametrize("phase", ["commit_before_commit", "commit_after_commit"])
def test_process_crash_recovers_original_bundle(
    trusted_setup, proposal, subprocess_python, phase
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    e = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "crash-new",
        },
    )
    import json

    args = {
        "system_id": sid,
        "evaluation_token": e["result"]["evaluation_token"],
        "operation_id": "crash-new",
    }
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation',fault=lambda stage:os._exit(76) if stage==sys.argv[2] else None)
app.execute('transition_commit',json.loads(sys.argv[3]))
"""
    assert subprocess_python(script, root, phase, json.dumps(args)).returncode == 76
    recovered = Application(root, ctx, "local-delegation").execute(
        "system_recover", {"system_id": sid, "operation_id": "crash-new"}
    )
    assert recovered["result"]["status"] == "committed", recovered
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"][
            "position"
        ]
        == 1
    )
    assert app.execute("transition_commit", args)["outcome"] == "already_committed"


def test_uncertain_commit_is_system_scoped_and_recovery_records_current_authority(
    trusted_setup, proposal, policy_document
):
    root, ctx, policy, artifacts = trusted_setup
    once = {"failed": False}

    def fault(stage):
        if stage == "commit_before_commit" and not once["failed"]:
            once["failed"] = True
            raise OSError("uncertain acknowledgment")

    app = Application(root, ctx, "local-delegation", fault=fault)
    one, _, _, _ = create_active(app, proposal, "1")
    two, _, _, _ = create_active(app, proposal, "2")
    request = {
        "system_id": one,
        "capability_id": "record__new",
        "bindings": {},
        "input": {"request_id": "r1", "label": "Example"},
        "expected_activation_revision": 1,
        "operation_id": "uncertain",
    }
    e = app.execute("transition_evaluate", request)
    unknown = app.execute(
        "transition_commit",
        {
            "system_id": one,
            "evaluation_token": e["result"]["evaluation_token"],
            "operation_id": "uncertain",
        },
    )
    assert unknown["request_status"] == "unknown", unknown
    assert (
        app.execute("transition_evaluate", dict(request, operation_id="replacement"))[
            "outcome"
        ]
        == "conflict"
    )
    evaluate_commit(
        app,
        two,
        "record__new",
        "other-system",
        input={"request_id": "r1", "label": "Other"},
    )
    from behavior_mcp.systems import SystemManager

    manager = SystemManager(root, ctx, artifacts, policy)
    original = manager.operation(one, "uncertain")["bundle"]
    policy_document.update(version=2)
    artifacts.install_policy(policy_document)
    recovered = Application(root, ctx, "local-delegation").execute(
        "system_recover", {"system_id": one, "operation_id": "uncertain"}
    )
    assert recovered["result"]["status"] == "committed", recovered
    record = manager.operation(one, "uncertain")
    assert record["bundle"] == original
    assert record["policy"]["policy_version"] == 1
    assert record["commit_authorization"]["policy_version"] == 2
    assert record["commit_authorization"]["principal_id"] == ctx.principal_id
