import pytest

from behavior_mcp.server import Application
from tests.fixtures.runtime import create_active, evaluate_commit


def test_restart_and_recovery_preserve_two_systems(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    one, _, _, _ = create_active(app, proposal, "1")
    two, _, _, _ = create_active(app, proposal, "2")
    evaluate_commit(
        app, one, "record__new", "new-1", input={"request_id": "r1", "label": "Example"}
    )
    recovered = Application(root, ctx, "local-delegation")
    assert (
        recovered.execute("system_recover", {"system_id": one})["request_status"]
        == "completed"
    )
    assert (
        recovered.execute("system_inspect", {"system_id": one})["result"][
            "history_anchor"
        ]["position"]
        == 1
    )
    assert (
        recovered.execute("system_inspect", {"system_id": two})["result"][
            "history_anchor"
        ]["position"]
        == 0
    )


def test_missing_artifacts_cannot_be_silently_rebuilt(trusted_setup, proposal):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
    from behavior_mcp.storage import connect, transaction

    with connect(artifacts.path) as db, transaction(db):
        db.execute("DELETE FROM blobs WHERE id=?", (d["module_ref"],))
    result = Application(root, ctx, "local-delegation").execute(
        "system_recover", {"system_id": sid}
    )
    assert result["request_status"] != "completed"


@pytest.mark.parametrize("phase", ["create_before_commit", "create_after_commit"])
def test_recover_incomplete_creation_uses_reserved_system(
    trusted_setup, proposal, subprocess_python, phase
):
    import json

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    from tests.fixtures.runtime import authored

    d = authored(app, proposal)
    args = {"definition_id": d["definition_id"], "operation_id": "incomplete-create"}
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation',fault=lambda stage:os._exit(77) if stage==sys.argv[2] else None)
app.execute('systems_create',json.loads(sys.argv[3]))
"""
    assert subprocess_python(script, root, phase, json.dumps(args)).returncode == 77
    ids = artifacts.system_ids()
    assert len(ids) == 1
    recovered = app.execute("system_recover", {"system_id": ids[0]})
    assert recovered["request_status"] == "completed", recovered
    assert app.execute("systems_create", args)["outcome"] == "already_created"
    assert artifacts.system_ids() == ids


def test_creation_inspection_does_not_deny_published_core_outcome(
    trusted_setup, proposal, subprocess_python
):
    import json

    from tests.fixtures.runtime import authored

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    d = authored(app, proposal)
    args = {"definition_id": d["definition_id"], "operation_id": "creation-status"}
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation',fault=lambda stage:os._exit(77) if stage=='create_after_commit' else None)
app.execute('systems_create',json.loads(sys.argv[2]))
"""
    assert subprocess_python(script, root, json.dumps(args)).returncode == 77
    sid = artifacts.system_ids()[0]
    result = app.execute(
        "operation_get", {"system_id": sid, "operation_id": args["operation_id"]}
    )
    assert result["result"]["status"] == "unknown", result
    assert result["result"]["operation_may_have_committed"] is True
    assert (
        app.execute("system_recover", {"system_id": sid})["request_status"]
        == "completed"
    )
    assert (
        app.execute(
            "operation_get", {"system_id": sid, "operation_id": args["operation_id"]}
        )["result"]["status"]
        == "committed"
    )


@pytest.mark.parametrize("phase", ["reservation", "backend_schema"])
def test_creation_prepublication_crashes_have_recoverable_reservations(
    trusted_setup, proposal, subprocess_python, phase
):
    import json

    from tests.fixtures.runtime import authored

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    d = authored(app, proposal)
    args = {
        "definition_id": d["definition_id"],
        "operation_id": "prepublication-create",
    }
    script = """import os,sys,json
from pathlib import Path
from contextlib import contextmanager
from behavior_mcp import sqlite_backend
from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
phase=sys.argv[2]
if phase=='reservation':
 original=ArtifactStore.bind_operation
 def bind(self,*args,**kwargs):
  result=original(self,*args,**kwargs)
  if kwargs.get('create_capacity') is not None: os._exit(88)
  return result
 ArtifactStore.bind_operation=bind
else:
 original=sqlite_backend.transaction
 @contextmanager
 def interrupted(db):
  with original(db):
   yield db
   os._exit(88)
 sqlite_backend.transaction=interrupted
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation')
app.execute('systems_create',json.loads(sys.argv[3]))
"""
    assert subprocess_python(script, root, phase, json.dumps(args)).returncode == 88
    reserved = artifacts.system_ids()
    if phase == "reservation":
        assert len(reserved) == 1
        recovered = app.execute("system_recover", {"system_id": reserved[0]})
        assert recovered["request_status"] == "completed", recovered
        assert (
            app.execute("systems_create", args)["result"]["receipt"]["system_id"]
            == reserved[0]
        )
    else:
        assert reserved == [], (
            "Backend preparation must finish durably before a reservation is published"
        )
        assert app.execute("systems_create", args)["outcome"] == "created"
    assert len(artifacts.system_ids()) == 1


def test_activation_recovery_lost_ack_preserves_uncertainty(
    trusted_setup, proposal, monkeypatch
):
    from behavior_mcp.systems import SystemManager
    from tests.fixtures.runtime import authored

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    d = authored(app, proposal)
    created = app.execute(
        "systems_create",
        {"definition_id": d["definition_id"], "operation_id": "create-recover"},
    )["result"]["receipt"]
    sid = created["system_id"]
    args = {
        "system_id": sid,
        "definition_id": d["definition_id"],
        "operation_id": "recover-activation",
        "expected_activation_revision": 0,
        "expected_history": created["history_anchor"],
    }
    artifacts.bind_operation(
        args["operation_id"], sid, ctx.principal_id, "activation", args
    )

    def fault(stage):
        if stage == "activation_after_commit":
            raise OSError("lost acknowledgment")

    recovering = Application(root, ctx, "local-delegation", fault=fault)
    result = recovering.execute(
        "system_recover", {"system_id": sid, "operation_id": args["operation_id"]}
    )
    assert result["request_status"] == "unknown", result
    assert result["error"]["operation_may_have_committed"] is True
    assert (
        app.execute(
            "operation_get", {"system_id": sid, "operation_id": args["operation_id"]}
        )["result"]["status"]
        == "committed"
    )
    assert app.execute("definition_activate", args)["outcome"] == "already_activated"

    # A failure while merely inspecting recovery metadata cannot imply a fresh mutation.
    monkeypatch.setattr(
        SystemManager,
        "operation",
        lambda *args: (_ for _ in ()).throw(OSError("read failed")),
    )
    read = app.execute(
        "system_recover", {"system_id": sid, "operation_id": args["operation_id"]}
    )
    assert read["request_status"] == "failed"
    assert read["error"]["operation_may_have_committed"] is False


def test_whole_system_recovery_preserves_uncertain_operation_scope(
    trusted_setup, proposal
):
    root, ctx, _, _ = trusted_setup
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
            "operation_id": "whole-recovery",
        },
    )

    def before(stage):
        if stage == "commit_before_commit":
            raise OSError("commit interrupted")

    interrupted = Application(root, ctx, "local-delegation", fault=before).execute(
        "transition_commit",
        {
            "system_id": sid,
            "operation_id": "whole-recovery",
            "evaluation_token": evaluated["result"]["evaluation_token"],
        },
    )
    assert interrupted["request_status"] == "unknown", interrupted

    def after(stage):
        if stage == "commit_after_commit":
            raise OSError("recovery acknowledgment lost")

    result = Application(root, ctx, "local-delegation", fault=after).execute(
        "system_recover", {"system_id": sid}
    )
    assert result["request_status"] == "unknown", result
    assert result["error"]["operation_may_have_committed"] is True
    assert result["subject"]["operation_id"] == "whole-recovery"
    status = app.execute(
        "operation_get", {"system_id": sid, "operation_id": "whole-recovery"}
    )
    assert status["result"]["status"] == "committed"


@pytest.mark.parametrize("phase", ["commit_before_commit", "commit_after_commit"])
async def test_cancellation_never_establishes_rollback(trusted_setup, proposal, phase):
    import threading

    import anyio

    root, ctx, _, _ = trusted_setup
    reached = threading.Event()
    proceed = threading.Event()

    def fault(stage):
        if stage == phase:
            reached.set()
            assert proceed.wait(10)

    app = Application(root, ctx, "local-delegation", fault=fault)
    sid, _, _, _ = create_active(app, proposal)
    e = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "cancelled",
        },
    )
    args = {
        "system_id": sid,
        "evaluation_token": e["result"]["evaluation_token"],
        "operation_id": "cancelled",
    }
    async with anyio.create_task_group() as group:
        group.start_soon(app.call_tool, "transition_commit", args)
        assert await anyio.to_thread.run_sync(reached.wait, 10)
        group.cancel_scope.cancel()
        proceed.set()
    retry = Application(root, ctx, "local-delegation").execute(
        "transition_commit", args
    )
    assert retry["outcome"] == "already_committed", retry
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"][
            "position"
        ]
        == 1
    )


async def test_real_server_startup_recovers_interrupted_commit_under_owner_lock(
    trusted_setup, proposal, subprocess_python
):
    import json
    import sys

    from mcp import Client, StdioServerParameters

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
            "operation_id": "startup-commit",
        },
    )
    args = {
        "system_id": sid,
        "evaluation_token": e["result"]["evaluation_token"],
        "operation_id": "startup-commit",
    }
    script = """import os,sys,json
from pathlib import Path
from behavior_mcp.server import Application
from behavior_mcp.policy import TrustedContext
app=Application(Path(sys.argv[1]),TrustedContext('agent-session','workspace-1','actor-1',lambda:'2026-10-26T00:00:00Z'),'local-delegation',fault=lambda stage:os._exit(78) if stage=='commit_before_commit' else None)
app.execute('transition_commit',json.loads(sys.argv[2]))
"""
    assert subprocess_python(script, root, json.dumps(args)).returncode == 78
    config = root / "launcher.json"
    config.write_text(
        json.dumps(
            {
                "workspace_root": str(root),
                "workspace_id": ctx.workspace_id,
                "principal_id": ctx.principal_id,
                "actor_id": ctx.actor_id,
                "policy_id": "local-delegation",
            }
        )
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "behavior_mcp.server",
            "serve",
            "--workspace",
            str(root),
            "--host-config",
            str(config),
        ],
    )
    async with Client(params, mode="2026-07-28", read_timeout_seconds=20) as client:
        state = (
            await client.call_tool("system_inspect", {"system_id": sid})
        ).structured_content
        assert state["result"]["history_anchor"]["position"] == 1, state
        import subprocess

        second = subprocess.run(
            [sys.executable, *params.args],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert second.returncode != 0
    assert app.execute("transition_commit", args)["outcome"] == "already_committed"
