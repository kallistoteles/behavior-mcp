"""Explicit operator grants for isolated model acceptance workspaces."""

import copy
import json
from pathlib import Path

from behavior_mcp.adapters import HANDLERS
from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.policy import Delegation, TrustedContext
from behavior_mcp.server import Application
from tests.fixtures.runtime import create_active

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "specs/002-remaining-behavior-models/contracts"


def example(name):
    return json.loads((CONTRACTS / "examples" / f"{name}.json").read_text())


def setup(root, name="approval", *, clock=None, actor="actor-1", two_actors=False):
    proposal = example(name)
    assert proposal["adapter_version"] in HANDLERS, (
        "Exact model checkpoint is not yet supported"
    )
    policy = example(
        {
            "approval": "host-policy-v2",
            "work-queue": "host-policy-v2-work-queue",
            "lifecycle": "host-policy-v2-safety",
            "field-ownership": "host-policy-v2-field-ownership",
        }.get(name, "host-policy-v2")
    )
    if two_actors:
        new_actor = {
            "kind": "create_entity",
            "name": "new_actor",
            "entity": "Actor",
            "values": {"name": {"op": "literal", "value": "two"}},
            "requires": [],
        }
        proposal["actions"].append(new_actor)
        policy["allowed_adapters"][0]["allowed_action_descriptors"].append(
            copy.deepcopy(new_actor)
        )
        policy["allowed_adapters"][0]["allowed_action_names"].append("new_actor")
        policy["runtime_actions"].append("new_actor")
    ctx = TrustedContext(
        "agent-session",
        "workspace-1",
        actor,
        lambda: "2026-10-28T00:00:00Z",
        semantic_clock=clock or (lambda: 10),
    )
    artifacts = ArtifactStore(root)
    artifacts.install_policy(
        Delegation.from_document(policy, "local-operator").document
    )
    return Application(root, ctx, policy["policy_id"]), proposal, policy


def active(root, name="approval", **kwargs):
    app, proposal, policy = setup(root, name, **kwargs)
    sid, definition, created, activated = create_active(app, proposal)
    return app, sid, definition, proposal, policy


def read_args(sid, capability, opid, bindings=None):
    return {
        "system_id": sid,
        "capability_id": capability,
        "operation_id": opid,
        "bindings": bindings or {},
        "input": {},
        "expected_activation_revision": 1,
    }


def retained_lifecycle(root):
    """Restore exact certificate/definition identities; never fabricate or relabel proof."""
    import shutil

    fixture = Path(__file__).parent / "adapter_versions/v2_3_0"
    manifest = json.loads((fixture / "manifest.json").read_text())
    shutil.copytree(fixture / "workspace", root, dirs_exist_ok=True)
    context = TrustedContext(
        "agent-session",
        "workspace-1",
        "actor-1",
        lambda: "2026-10-28T00:00:00Z",
        semantic_clock=lambda: 10,
    )
    app = Application(root, context, manifest["policy_id"])
    definition = app.artifacts.definition(manifest["definition_id"])
    return (
        app,
        manifest["system_id"],
        definition,
        example("lifecycle"),
        example("host-policy-v2-safety"),
    )
