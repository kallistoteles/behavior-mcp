"""Queue and time-dependent read retries preserve original operations."""

import copy
import json
from dataclasses import replace

import pytest

from behavior_mcp.server import Application
from tests.fixtures.expanded import active, read_args
from tests.integration.test_work_queue_runtime import request, run


def test_time_dependent_read_retry_is_original(tmp_path):
    now = [10]
    app, sid, _, _, _ = active(tmp_path, "work-queue", clock=lambda: now[0])
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Example"},
    )
    run(
        app,
        sid,
        "claim",
        "claim",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )
    request = read_args(sid, "jobs__expired", "original-read")
    before = app.execute("capability_read", request)
    assert before["result"]["response"]["value"] == [], before
    now[0] = 20
    assert app.execute("capability_read", request) == before
    later = app.execute("capability_read", dict(request, operation_id="new-read"))
    assert later["result"]["response"]["value"] == [{"id": "w1"}], later


@pytest.mark.parametrize("phase", ["commit_before_commit", "commit_after_commit"])
@pytest.mark.parametrize(
    "change", ["commit_grant", "capability", "worker", "activation"]
)
def test_queue_recovery_after_authority_changes(
    tmp_path, subprocess_python, phase, change
):
    from tests.fixtures.runtime import authored

    app, sid, _, proposal, policy = active(tmp_path, "work-queue")
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Example"},
    )
    args = request(
        app,
        sid,
        "claim",
        "uncertain",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )
    e = app.execute("transition_evaluate", args)
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
if '2.1.0' not in adapters.HANDLERS:
 authoring_v2.CLOSURE=['authoring_v2.py','fragments_v2.py']
 adapters.HANDLERS['2.1.0']=authoring_v2
ctx=TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-28T00:00:00Z',semantic_clock=lambda:10)
app=Application(Path(sys.argv[1]),ctx,'local-queue',fault=lambda stage:os._exit(76) if stage==sys.argv[2] else None)
app.execute('transition_commit',json.loads(sys.argv[3]))
"""
    assert (
        subprocess_python(script, tmp_path, phase, json.dumps(commit)).returncode == 76
    )
    published = phase == "commit_after_commit"
    if change == "activation" and published:
        changed = copy.deepcopy(proposal)
        changed["metadata"] = {"title": "Revised deployment"}
        d = authored(app, changed)
        history = app.execute("system_inspect", {"system_id": sid})["result"][
            "history_anchor"
        ]
        response = app.execute(
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": history,
                "operation_id": "replace",
            },
        )
        assert response["outcome"] == "activated", response
    changed = copy.deepcopy(policy)
    changed["version"] = 2
    if change == "commit_grant" or (change == "activation" and not published):
        changed["operations"].remove("transition_commit")
    if change == "capability":
        changed["runtime_actions"].remove("jobs__claim")
    app.artifacts.install_policy(changed)
    ctx = (
        replace(app.context, actor_id="worker-2") if change == "worker" else app.context
    )
    recovering = Application(tmp_path, ctx, app.policy_id)
    result = recovering.execute(
        "system_recover", {"system_id": sid, "operation_id": "uncertain"}
    )
    assert result["request_status"] == "completed", result
    assert result["result"]["status"] == (
        "committed" if published else "not_committed"
    ), result
    assert recovering.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]["position"] == 1 + int(published)
