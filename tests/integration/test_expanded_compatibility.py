"""Actual retained workspaces must survive expanded authoring releases."""

import hashlib
import json
import shutil
from pathlib import Path

from behavior_mcp.server import Application

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/legacy_v1"


def test_retained_v1_workspace(tmp_path, context):
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    root = tmp_path / "workspace"
    shutil.copytree(FIXTURE / "workspace", root)
    app = Application(root, context, "local-delegation")
    sid = manifest["system_id"]
    for name in ("system_inspect", "capabilities_list", "system_recover"):
        response = app.execute(name, {"system_id": sid})
        assert response["request_status"] == "completed", response
    for name, digest in manifest["frozen_files"].items():
        from behavior_mcp import authoring
        from behavior_mcp.schemas import resource

        path = (
            Path(authoring.__file__)
            if name.startswith("src/")
            else resource(Path(name).name)
        )
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
        == manifest["history"]
    )


def test_explicit_dispatch_boundary():
    from importlib import import_module
    from importlib.util import find_spec

    import behavior_mcp

    assert find_spec("behavior_mcp.adapters"), (
        "Exact profile/version dispatcher is missing"
    )
    adapters = import_module("behavior_mcp.adapters")
    assert callable(adapters.construction_context)
    assert callable(adapters.reconstruct)
    assert behavior_mcp.__file__


def test_explicit_legacy_grant_in_v2_policy(trusted_setup, proposal, policy_document):
    from behavior_mcp.adapters import build
    from behavior_mcp.policy import Delegation
    from tests.fixtures.expanded import example

    document = example("host-policy-v2")
    legacy = {
        "adapter_profile": "scalar-models.v1",
        "adapter_version": "1",
        **{k: policy_document[k] for k in ("construction", "effects", "state")},
    }
    document["allowed_adapters"].append(legacy)
    delegation = Delegation.from_document(document, "local-operator")
    delegation.check_candidate(proposal, build(proposal), existing=False)


def test_explicit_legacy_fork_preserves_original_operation_evidence(tmp_path, context):
    import copy

    from behavior_mcp.policy import Delegation
    from tests.fixtures.expanded import example
    from tests.fixtures.runtime import authored, evaluate_commit

    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    root = tmp_path / "workspace"
    shutil.copytree(FIXTURE / "workspace", root)
    app = Application(root, context, "local-delegation")
    original = manifest["definition"]
    source = app.artifacts.proposal(
        original["source"]["proposal_id"], original["source"]["proposal_revision"]
    )["proposal"]
    legacy_policy = app.artifacts.policy("local-delegation")
    fork = copy.deepcopy(source)
    fork.update(
        format="behavior-mcp.authoring.v2",
        adapter_profile="structured-models.v2",
        adapter_version="2.3.0",
        actions=[],
        safety=[],
    )
    fork["declarations"]["nominals"] = []
    for model in fork["models"]:
        model["actor"] = "Actor"
        model["payload"] = {name: {"kind": "string"} for name in model["payload"]}
        for creation in model["creations"]:
            creation["inputs"] = {
                name: {"kind": "string"} for name in creation["inputs"]
            }
            creation["requires"] = []
            creation["values"] = {}
            for name, value in creation.pop("initializer").items():
                creation["values"][name] = (
                    {"op": "literal", "value": value["value"]}
                    if value["source"] == "literal"
                    else {
                        "op": "param",
                        "name": "actor"
                        if value["source"] == "host_actor"
                        else value["name"],
                    }
                )
        for transition in model["transitions"]:
            transition["inputs"] = {
                name: {"kind": "string"} for name in transition["inputs"]
            }
            transition["requires"] = []
            transition["assignments"] = [
                {
                    "target": {
                        "op": "field",
                        "value": {"op": "param", "name": model["model_id"]},
                        "name": a["target_field"],
                    },
                    "value": {"op": "param", "name": a["input"]},
                }
                for a in transition["assignments"]
            ]
    policy = example("host-policy-v2")
    policy.update(policy_id="local-delegation", version=2)
    grant = policy["allowed_adapters"][0]
    grant.update(
        adapter_version="2.3.0",
        allowed_model_kinds=["request_flow"],
        allowed_model_ids=["record"],
        allowed_entity_declarations=[],
        allowed_enum_declarations=fork["declarations"]["enums"],
        allowed_action_names=["record__new", "record__finish"],
        allowed_read_names=[],
        allowed_action_descriptors=[],
        model_parameter_bounds=[],
        allowed_derived_functions=[],
    )
    grant["allowed_field_refs"] = [
        {"entity": {"model_id": "record", "output": "request"}, "fields": ["outcome"]}
    ]
    grant["state_fields"] = [
        {
            "entity": {"model_id": "record", "output": "request"},
            "field": "status",
            "values": ["Open", "Done"],
            "edges": [{"from": "Open", "to": "Done"}],
        }
    ]
    policy["allowed_adapters"].append(
        {
            "adapter_profile": "scalar-models.v1",
            "adapter_version": "1",
            **{k: legacy_policy[k] for k in ("construction", "effects", "state")},
        }
    )
    policy["runtime_actions"] = ["record__new", "record__finish"]
    policy["runtime_reads"] = []
    app.artifacts.install_policy(
        Delegation.from_document(policy, "local-operator").document
    )
    old = copy.deepcopy(source)
    old["metadata"] = {"title": "Still editable v1"}
    assert authored(app, old)["release"]["adapter_profile"] == "scalar-models.v1"
    definition = authored(app, fork)
    assert definition["schema_hash"] == original["schema_hash"]
    assert (
        app.execute("system_inspect", {"system_id": manifest["system_id"]})["result"][
            "active"
        ]["definition_id"]
        == original["definition_id"]
    )
    response = app.execute(
        "definition_activate",
        {
            "system_id": manifest["system_id"],
            "definition_id": definition["definition_id"],
            "expected_activation_revision": 1,
            "expected_history": manifest["history"],
            "operation_id": "explicit-upgrade",
        },
    )
    assert response["outcome"] == "activated", response
    evaluate_commit(
        app,
        manifest["system_id"],
        "record__finish",
        "finish-after-upgrade",
        bindings={"record": "r1"},
        input={"outcome": "Done"},
    )
    original_operation = app.execute(
        "operation_get",
        {"system_id": manifest["system_id"], "operation_id": "baseline-new"},
    )
    assert original_operation["request_status"] == "completed", original_operation
    assert (
        original_operation["subject"]["release"]["adapter_profile"]
        == "scalar-models.v1"
    )
    assert (
        original_operation["result"]["observed_current_deployment"]["definition_id"]
        == definition["definition_id"]
    )
