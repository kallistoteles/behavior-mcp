import copy
import json
from dataclasses import replace

import pytest

from behavior_mcp.server import Application
from tests.fixtures.runtime import authored, create_active, evaluate_commit


@pytest.mark.parametrize("phase", ["commit_before_commit", "commit_after_commit"])
@pytest.mark.parametrize(
    "change", ["commit_grant", "capability", "actor", "activation"]
)
def test_reconcile_crashed_transition_without_fresh_execution_authority(
    trusted_setup, proposal, policy_document, subprocess_python, phase, change
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    evaluated = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "reconcile-original",
        },
    )
    args = {
        "system_id": sid,
        "operation_id": "reconcile-original",
        "evaluation_token": evaluated["result"]["evaluation_token"],
    }
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation',fault=lambda stage:os._exit(76) if stage==sys.argv[2] else None)
app.execute('transition_commit',json.loads(sys.argv[3]))
"""
    assert subprocess_python(script, root, phase, json.dumps(args)).returncode == 76
    published = phase == "commit_after_commit"
    next_activation = None
    if change == "activation":
        revised = copy.deepcopy(proposal)
        revised["models"][0]["transitions"][0]["id"] = "complete"
        definition = authored(app, revised)
        history = app.execute("system_inspect", {"system_id": sid})["result"][
            "history_anchor"
        ]
        next_activation = {
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "operation_id": "reconcile-activation",
            "expected_activation_revision": 1,
            "expected_history": history,
        }
        assert app.execute("definition_activate", next_activation)["outcome"] == (
            "activated" if published else "conflict"
        )
    updated = copy.deepcopy(policy_document)
    updated["version"] = 2
    if change == "commit_grant" or (change == "activation" and not published):
        updated["operations"].remove("transition_commit")
    if change == "capability":
        updated["construction"]["allowed_capability_names"].remove("record__new")
    artifacts.install_policy(updated)
    recovery_context = (
        replace(ctx, actor_id="other-actor") if change == "actor" else ctx
    )
    recovering = Application(root, recovery_context, "local-delegation")
    recovered = recovering.execute(
        "system_recover", {"system_id": sid, "operation_id": "reconcile-original"}
    )
    assert recovered["request_status"] == "completed", recovered
    assert recovered["result"]["status"] == (
        "committed" if published else "not_committed"
    )
    assert recovered["result"]["operation_may_have_committed"] is False
    assert recovering.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]["position"] == int(published)
    if change == "activation" and not published:
        assert (
            recovering.execute("definition_activate", next_activation)["outcome"]
            == "activated"
        )
    # Once resolved, later restoration never silently replays the old operation.
    restored = copy.deepcopy(policy_document)
    restored["version"] = 3
    artifacts.install_policy(restored)
    assert app.execute(
        "system_recover", {"system_id": sid, "operation_id": "reconcile-original"}
    )["result"]["status"] == ("committed" if published else "not_committed")
    evaluate_commit(
        app,
        sid,
        "record__new",
        "new-after-reconciliation",
        input={"request_id": "r2", "label": "Later"},
    )
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"][
            "position"
        ]
        == int(published) + 1
    )


def test_recovery_without_receipt_read_grant_never_retries_commit(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup

    def interrupt(stage):
        if stage == "commit_before_commit":
            raise OSError("uncertain commit")

    app = Application(root, ctx, "local-delegation", fault=interrupt)
    sid, _, _, _ = create_active(app, proposal)
    evaluated = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "no-read",
        },
    )
    assert (
        app.execute(
            "transition_commit",
            {
                "system_id": sid,
                "operation_id": "no-read",
                "evaluation_token": evaluated["result"]["evaluation_token"],
            },
        )["request_status"]
        == "unknown"
    )
    policy_document.update(version=2)
    policy_document["operations"].remove("operation_get")
    artifacts.install_policy(policy_document)
    reopened = Application(root, ctx, "local-delegation")
    assert (
        reopened.execute(
            "system_recover", {"system_id": sid, "operation_id": "no-read"}
        )["outcome"]
        == "unauthorized"
    )
    assert (
        reopened.execute("system_inspect", {"system_id": sid})["result"][
            "history_anchor"
        ]["position"]
        == 0
    )


@pytest.mark.parametrize("same_candidate", [True, False])
def test_recovery_uses_core_identity_when_another_operation_has_published(
    trusted_setup, proposal, policy_document, subprocess_python, same_candidate
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    evaluations = []
    for opid, record_id in [
        ("first", "r1"),
        ("second", "r1" if same_candidate else "r2"),
    ]:
        result = app.execute(
            "transition_evaluate",
            {
                "system_id": sid,
                "capability_id": "record__new",
                "bindings": {},
                "input": {"request_id": record_id, "label": "Example"},
                "expected_activation_revision": 1,
                "operation_id": opid,
            },
        )
        assert result["outcome"] == "evaluation_allowed", result
        evaluations.append(
            {
                "system_id": sid,
                "operation_id": opid,
                "evaluation_token": result["result"]["evaluation_token"],
            }
        )
    published = app.execute("transition_commit", evaluations[0])
    assert published["outcome"] == "committed", published
    script = """import os,sys,json
from pathlib import Path
from behavior import Store
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
original=Store.open
def interrupted(backend):
 if getattr(backend,'operation',None) and backend.operation['operation_id']=='second': os._exit(76)
 return original(backend)
Store.open=staticmethod(interrupted)
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation')
app.execute('transition_commit',json.loads(sys.argv[2]))
"""
    assert subprocess_python(script, root, json.dumps(evaluations[1])).returncode == 76
    policy_document.update(version=2)
    policy_document["operations"].remove("transition_commit")
    artifacts.install_policy(policy_document)
    recovered = app.execute(
        "system_recover", {"system_id": sid, "operation_id": "second"}
    )
    assert recovered["request_status"] == "completed", recovered
    assert recovered["result"]["status"] == (
        "committed" if same_candidate else "not_committed"
    ), recovered
    if same_candidate:
        assert (
            recovered["result"]["receipt"]["record_id"]
            == published["result"]["receipt"]["record_id"]
        )
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"][
            "position"
        ]
        == 1
    )


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
