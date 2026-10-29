"""Allowed and refused retries retain their original public subject across restart."""

import copy
import json
from dataclasses import replace

import pytest

from behavior_mcp.server import Application
from tests.fixtures.expanded import active, read_args
from tests.fixtures.runtime import authored, evaluate_commit


def test_approval_refusal_read_and_commit_retry(tmp_path):
    app, sid, _, _, _ = active(tmp_path)
    evaluate_commit(app, sid, "new_subject", "create-subject", input={"new_id": "s1"})
    _, commit = evaluate_commit(
        app,
        sid,
        "review__approve",
        "approve",
        bindings={"subject": "s1"},
        input={"decision_id": "d1"},
    )
    args = {
        "system_id": sid,
        "capability_id": "review__reject",
        "bindings": {"subject": "s1"},
        "input": {"decision_id": "d2"},
        "expected_activation_revision": 1,
        "operation_id": "duplicate",
    }
    refused = app.execute("transition_evaluate", args)
    assert refused["outcome"] == "semantic_refusal", refused
    read_request = read_args(sid, "mcp_review_status", "read", {"subject": "s1"})
    read = app.execute("capability_read", read_request)
    assert read["outcome"] == "read", read
    app = Application(tmp_path, app.context, app.policy_id)
    assert app.execute("transition_evaluate", args) == refused
    assert app.execute("capability_read", read_request) == read
    recovered = app.execute("system_recover", {"system_id": sid})
    assert recovered["request_status"] == "completed", recovered


@pytest.mark.parametrize("phase", ["commit_before_commit", "commit_after_commit"])
@pytest.mark.parametrize(
    "change", ["commit_grant", "capability", "actor", "activation"]
)
def test_approval_crash_and_changed_authority(
    tmp_path, subprocess_python, phase, change
):
    app, sid, _, proposal, policy = active(tmp_path)
    evaluate_commit(app, sid, "new_subject", "subject", input={"new_id": "s1"})
    request = {
        "system_id": sid,
        "capability_id": "review__approve",
        "bindings": {"subject": "s1"},
        "input": {"decision_id": "d1"},
        "expected_activation_revision": 1,
        "operation_id": "uncertain",
    }
    e = app.execute("transition_evaluate", request)
    assert e["outcome"] == "evaluation_allowed", e
    commit = {
        "system_id": sid,
        "operation_id": "uncertain",
        "evaluation_token": e["result"]["evaluation_token"],
    }
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp import adapters,authoring_v2
from behavior_mcp.policy import TrustedContext
from behavior_mcp.server import Application
if '2.0.0' not in adapters.HANDLERS:
 authoring_v2.CLOSURE=['authoring_v2.py','fragments_v2.py']
 adapters.HANDLERS['2.0.0']=authoring_v2
ctx=TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-28T00:00:00Z',semantic_clock=lambda:10)
app=Application(Path(sys.argv[1]),ctx,'local-expanded',fault=lambda stage:os._exit(76) if stage==sys.argv[2] else None)
app.execute('transition_commit',json.loads(sys.argv[3]))
"""
    assert (
        subprocess_python(script, tmp_path, phase, json.dumps(commit)).returncode == 76
    )
    published = phase == "commit_after_commit"
    if change == "activation" and published:
        changed = copy.deepcopy(proposal)
        changed["models"][0]["approve_threshold"] = 1
        d = authored(app, changed)
        history = app.execute("system_inspect", {"system_id": sid})["result"][
            "history_anchor"
        ]
        r = app.execute(
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": history,
                "operation_id": "replace",
            },
        )
        assert r["outcome"] == "activated", r
    changed = copy.deepcopy(policy)
    changed["version"] = 2
    if change == "commit_grant" or (change == "activation" and not published):
        changed["operations"].remove("transition_commit")
    if change == "capability":
        changed["runtime_actions"].remove("review__approve")
    app.artifacts.install_policy(changed)
    ctx = (
        replace(app.context, actor_id="other-actor")
        if change == "actor"
        else app.context
    )
    recovering = Application(tmp_path, ctx, app.policy_id)
    r = recovering.execute(
        "system_recover", {"system_id": sid, "operation_id": "uncertain"}
    )
    assert r["request_status"] == "completed", r
    assert r["result"]["status"] == ("committed" if published else "not_committed"), r
    assert r["result"]["operation_may_have_committed"] is False
    current = recovering.execute("system_inspect", {"system_id": sid})
    assert current["result"]["history_anchor"]["position"] == 1 + int(published)
    assert (
        recovering.execute(
            "system_recover", {"system_id": sid, "operation_id": "uncertain"}
        )["result"]
        == r["result"]
    )
