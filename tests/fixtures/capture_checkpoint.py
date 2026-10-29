"""Create a retained, isolated public-operation workspace at a release checkpoint."""

import hashlib
import json
from pathlib import Path

from behavior_mcp import adapters
from behavior_mcp.schemas import resource
from tests.fixtures.expanded import active
from tests.fixtures.runtime import evaluate_commit


def capture(version: str, name: str) -> dict:
    root = (
        Path(__file__).parent / "adapter_versions" / ("v" + version.replace(".", "_"))
    )
    workspace = root / "workspace"
    if workspace.exists():
        raise RuntimeError("A retained checkpoint cannot be overwritten")
    workspace.mkdir(parents=True)
    app, sid, definition, proposal, policy = active(workspace, name)
    if name == "approval":
        evaluate_commit(
            app, sid, "new_subject", "baseline-subject", input={"new_id": "s1"}
        )
    if name == "work-queue":
        from tests.integration.test_work_queue_runtime import run

        run(
            app,
            sid,
            "enqueue",
            "baseline-enqueue",
            inputs={"id": "w1", "available_at": 0, "label": "Example"},
        )
        run(
            app,
            sid,
            "claim",
            "baseline-claim",
            inputs={"expected_generation": 0},
            proposals={"lease_until": 20},
        )
    if name == "field-ownership":
        evaluate_commit(
            app, sid, "new_parent", "baseline-parent", input={"new_id": "p1"}
        )
        evaluate_commit(
            app, sid, "parent__stop", "baseline-stop", bindings={"subject": "p1"}
        )
    context = adapters.construction_context(proposal)
    files = {
        name: digest.removeprefix("bytes-sha256:")
        for name, digest in context["adapter_files"].items()
    }
    for name, digest in files.items():
        file = (
            resource(Path(name).name)
            if name.startswith("contracts/")
            else Path(adapters.__file__).parent / name
        )
        assert hashlib.sha256(file.read_bytes()).hexdigest() == digest
    for lock in workspace.rglob("*.lock"):
        lock.unlink()
    manifest = {
        "format": "behavior-mcp.adapter-checkpoint.v1",
        "version": version,
        "system_id": sid,
        "definition_id": definition["definition_id"],
        "behavior_hash": definition["behavior_hash"],
        "schema_hash": definition["schema_hash"],
        "policy_id": policy["policy_id"],
        "construction_context": context,
        "closure": files,
        "workspace_files": {
            str(p.relative_to(workspace)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in workspace.rglob("*")
            if p.is_file()
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def capture_restored_lifecycle(source: Path) -> dict:
    """Retain an actually certified/check-verified workspace, then deploy through MCP."""
    import shutil

    from behavior_mcp.adapters import reconstruct
    from behavior_mcp.artifacts import ArtifactStore
    from behavior_mcp.policy import TrustedContext
    from behavior_mcp.server import Application

    root = Path(__file__).parent / "adapter_versions/v2_3_0"
    workspace = root / "workspace"
    if workspace.exists():
        raise RuntimeError("A retained checkpoint cannot be overwritten")
    shutil.copytree(source, workspace)
    artifacts = ArtifactStore(workspace)
    d = artifacts.find("definition")[0][1]
    definition, module, snapshot = reconstruct(artifacts, d["definition_id"])
    context = TrustedContext(
        "agent-session",
        "workspace-1",
        "actor-1",
        lambda: "2026-10-28T00:00:00Z",
        semantic_clock=lambda: 10,
    )
    app = Application(workspace, context, "local-lifecycle")
    created = app.execute(
        "systems_create",
        {
            "definition_id": definition["definition_id"],
            "operation_id": "checkpoint-create",
        },
    )
    assert created["outcome"] == "created", created
    receipt = created["result"]["receipt"]
    sid = receipt["system_id"]
    activated = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "expected_activation_revision": 0,
            "expected_history": receipt["history_anchor"],
            "operation_id": "checkpoint-activate",
        },
    )
    assert activated["outcome"] == "activated", activated
    evaluate_commit(app, sid, "new_parent", "baseline-parent", input={"new_id": "p1"})
    evaluate_commit(
        app,
        sid,
        "new_child",
        "baseline-child",
        bindings={"parent": "p1"},
        input={"new_id": "c1"},
    )
    evaluate_commit(
        app, sid, "finish_child", "baseline-finish", bindings={"subject": "c1"}
    )
    evaluate_commit(
        app, sid, "stop_parent", "baseline-stop", bindings={"subject": "p1"}
    )
    assert (
        app.execute("system_recover", {"system_id": sid})["request_status"]
        == "completed"
    )
    for lock in workspace.rglob("*.lock"):
        lock.unlink()
    closure = adapters.construction_context(snapshot["proposal"])
    manifest = {
        "format": "behavior-mcp.adapter-checkpoint.v1",
        "version": "2.3.0",
        "system_id": sid,
        "definition_id": definition["definition_id"],
        "behavior_hash": definition["behavior_hash"],
        "schema_hash": definition["schema_hash"],
        "policy_id": app.policy_id,
        "construction_context": closure,
        "closure": {
            k: v.removeprefix("bytes-sha256:")
            for k, v in closure["adapter_files"].items()
        },
        "workspace_files": {
            str(p.relative_to(workspace)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in workspace.rglob("*")
            if p.is_file()
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
