from concurrent.futures import ThreadPoolExecutor

from behavior_mcp.server import Application
from tests.fixtures.runtime import create_active, evaluate_commit


def test_equal_genesis_stores_remain_isolated_during_simultaneous_use(
    trusted_setup, proposal
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    one, d, c1, a1 = create_active(app, proposal, "1")
    two, _, c2, _ = create_active(app, proposal, "2")
    assert one != two
    assert c1["result"]["receipt"]["store_id"] == c2["result"]["receipt"]["store_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(
                evaluate_commit,
                app,
                sid,
                "record__new",
                "new-" + suffix,
                input={"request_id": "r1", "label": suffix},
            )
            for sid, suffix in [(one, "1"), (two, "2")]
        ]
        for job in jobs:
            job.result()
    for sid, label in [(one, "1"), (two, "2")]:
        value = app.execute(
            "state_read", {"system_id": sid, "entity": "Record", "record_id": "r1"}
        )
        assert value["result"]["records"][0]["value"]["label"] == label
    changed = Application(root, ctx, "local-delegation").execute(
        "system_recover", {"system_id": one}
    )
    assert changed["request_status"] == "completed", changed
    assert (
        app.execute("system_inspect", {"system_id": two})["result"]["history_anchor"][
            "position"
        ]
        == 1
    )


def test_stale_evaluation_conflicts_and_policy_updates_serialize(
    trusted_setup, proposal, policy_document, subprocess_python
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    base = {
        "system_id": sid,
        "capability_id": "record__new",
        "bindings": {},
        "input": {"request_id": "r1", "label": "Example"},
        "expected_activation_revision": 1,
        "operation_id": "first",
    }
    first = app.execute("transition_evaluate", base)
    second = app.execute(
        "transition_evaluate",
        dict(base, operation_id="second", input={"request_id": "r2", "label": "Other"}),
    )
    assert (
        app.execute(
            "transition_commit",
            {
                "system_id": sid,
                "evaluation_token": first["result"]["evaluation_token"],
                "operation_id": "first",
            },
        )["outcome"]
        == "committed"
    )
    assert (
        app.execute(
            "transition_commit",
            {
                "system_id": sid,
                "evaluation_token": second["result"]["evaluation_token"],
                "operation_id": "second",
            },
        )["outcome"]
        == "conflict"
    )
    import json

    policy_document.update(
        version=2,
        operations=[
            o for o in policy_document["operations"] if o != "transition_commit"
        ],
    )
    script = "from pathlib import Path; import json,sys; from behavior_mcp.artifacts import ArtifactStore; ArtifactStore(Path(sys.argv[1])).install_policy(json.loads(sys.argv[2]))"
    assert subprocess_python(script, root, json.dumps(policy_document)).returncode == 0
    new = app.execute(
        "transition_evaluate",
        dict(base, operation_id="third", input={"request_id": "r3", "label": "Other"}),
    )
    assert (
        app.execute(
            "transition_commit",
            {
                "system_id": sid,
                "evaluation_token": new["result"]["evaluation_token"],
                "operation_id": "third",
            },
        )["outcome"]
        == "unauthorized"
    )


def test_competing_activations_publish_one_new_revision(trusted_setup, proposal):
    import threading

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, c, _ = create_active(app, proposal)
    barrier = threading.Barrier(2)

    def activate(opid):
        barrier.wait(timeout=10)
        return app.execute(
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": c["result"]["receipt"]["history_anchor"],
                "operation_id": opid,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(activate, name) for name in ["compete-one", "compete-two"]
        ]
        results = [future.result() for future in pending]
    assert sorted(r["outcome"] for r in results) == ["activated", "conflict"]
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"][
            "activation_revision"
        ]
        == 2
    )
    from behavior_mcp.storage import connect

    with connect(artifacts.system_path(sid)) as db:
        assert db.execute("SELECT COUNT(*) FROM activations").fetchone()[0] == 2


def test_concurrent_administrative_policy_update_waits_for_activation(
    trusted_setup, proposal, policy_document
):
    import json
    import subprocess
    import sys
    import threading

    root, ctx, _, artifacts = trusted_setup
    entered = threading.Event()
    proceed = threading.Event()
    enabled = {"value": False}

    def fault(stage):
        if enabled["value"] and stage == "activation_before_commit":
            entered.set()
            assert proceed.wait(15)

    app = Application(root, ctx, "local-delegation", fault=fault)
    sid, d, c, _ = create_active(app, proposal)
    enabled["value"] = True
    policy_document.update(
        version=2,
        operations=[
            op for op in policy_document["operations"] if op != "definition_activate"
        ],
    )
    script = """from pathlib import Path
import json,sys
from behavior_mcp.storage import file_lock
from behavior_mcp.artifacts import ArtifactStore
root=Path(sys.argv[1])
try:
    with file_lock(root/'policy.lock',blocking=False):
        raise SystemExit(3)
except BlockingIOError:
    print('blocked',flush=True)
ArtifactStore(root).install_policy(json.loads(sys.argv[2]))
print('installed',flush=True)
"""
    with ThreadPoolExecutor(max_workers=1) as pool:
        activation = pool.submit(
            app.execute,
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": c["result"]["receipt"]["history_anchor"],
                "operation_id": "policy-race",
            },
        )
        assert entered.wait(10)
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(root), json.dumps(policy_document)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert child.stdout.readline().strip() == "blocked"
            assert child.poll() is None
            proceed.set()
            result = activation.result(timeout=20)
            stdout, stderr = child.communicate(timeout=20)
            assert child.returncode == 0, (stdout, stderr)
            assert result["outcome"] == "activated", result
            assert result["result"]["receipt"]["policy"]["policy_version"] == 1
            assert artifacts.policy("local-delegation")["version"] == 2
        finally:
            proceed.set()
            if child.poll() is None:
                child.kill()
                child.wait()
