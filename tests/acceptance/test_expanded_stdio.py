"""Real operator CLI and stdio clients use the same bounded v2 contracts."""

import json
import subprocess
import sys
import time

import pytest
from mcp import Client, StdioServerParameters

from tests.fixtures.expanded import example


@pytest.mark.parametrize("family", ["approval", "work-queue"])
async def test_operator_install_and_stdio_restart(tmp_path, family):
    policy = example(
        "host-policy-v2" if family == "approval" else "host-policy-v2-work-queue"
    )
    admin = tmp_path / "admin.json"
    admin.write_text(
        json.dumps(
            {
                "workspace_root": str(tmp_path),
                "workspace_id": "workspace-1",
                "issuer_id": "local-operator",
                "allowed_principals": ["agent-session"],
            }
        )
    )
    document = tmp_path / "policy.json"
    document.write_text(json.dumps(policy))
    installed = subprocess.run(
        [
            sys.executable,
            "-m",
            "behavior_mcp.admin",
            "install-policy",
            "--workspace",
            str(tmp_path),
            "--trusted-config",
            str(admin),
            "--document",
            str(document),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert installed.returncode == 0, installed.stderr
    launcher = tmp_path / "launcher.json"
    launcher.write_text(
        json.dumps(
            {
                "workspace_root": str(tmp_path),
                "workspace_id": "workspace-1",
                "principal_id": "agent-session",
                "actor_id": "actor-1",
                "policy_id": policy["policy_id"],
            }
        )
    )
    server = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "behavior_mcp.server",
            "serve",
            "--workspace",
            str(tmp_path),
            "--host-config",
            str(launcher),
        ],
    )

    async def call(client, name, args):
        result = (await client.call_tool(name, args)).structured_content
        assert result["request_status"] == "completed", json.dumps(result)
        return result

    async with Client(server, read_timeout_seconds=30) as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 20
        catalog = await call(client, "models_list", {})
        assert len(catalog["result"]["models"]) == 6
        saved = (
            await call(client, "definition_propose", {"proposal": example(family)})
        )["result"]
        admitted = await call(
            client,
            "definition_validate",
            {
                "proposal_id": saved["proposal_id"],
                "proposal_revision": saved["proposal_revision"],
            },
        )
        definition = admitted["result"]["definition"]
        created = await call(
            client,
            "systems_create",
            {
                "definition_id": definition["definition_id"],
                "operation_id": "cli-create",
            },
        )
        receipt = created["result"]["receipt"]
        sid = receipt["system_id"]
        await call(
            client,
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": definition["definition_id"],
                "expected_activation_revision": 0,
                "expected_history": receipt["history_anchor"],
                "operation_id": "cli-activate",
            },
        )
        inventory = (await call(client, "capabilities_list", {"system_id": sid}))[
            "result"
        ]["capabilities"]

        async def transition(capability, opid, inputs, bindings=None, proposals=None):
            if family == "work-queue" and bindings:
                declared = next(c for c in inventory if c["name"] == capability)
                bindings = {
                    p["name"]: "w1" for p in declared["params"] if p["role"] == "state"
                }
            args = {
                "system_id": sid,
                "capability_id": capability,
                "operation_id": opid,
                "expected_activation_revision": 1,
                "bindings": bindings or {},
                "input": inputs,
            }
            if proposals is not None:
                args["context_proposals"] = proposals
            evaluated = await call(client, "transition_evaluate", args)
            return await call(
                client,
                "transition_commit",
                {
                    "system_id": sid,
                    "operation_id": opid,
                    "evaluation_token": evaluated["result"]["evaluation_token"],
                },
            )

        if family == "approval":
            await transition("new_subject", "subject", {"new_id": "s1"})
            await transition(
                "review__approve", "approve", {"decision_id": "d1"}, {"subject": "s1"}
            )
            read = {
                "system_id": sid,
                "capability_id": "mcp_review_status",
                "operation_id": "stdio-read",
                "expected_activation_revision": 1,
                "bindings": {"subject": "s1"},
                "input": {},
            }
        else:
            await transition(
                "jobs__enqueue",
                "enqueue",
                {"id": "w1", "available_at": 0, "label": "Example"},
            )
            await transition(
                "jobs__claim",
                "claim",
                {"expected_generation": 0},
                {"work": "w1"},
                {"lease_until": int(time.time() * 1000) + 30000},
            )
            await transition(
                "jobs__complete", "complete", {"generation": 1}, {"work": "w1"}
            )
            read = {
                "system_id": sid,
                "capability_id": "mcp_jobs_terminal",
                "operation_id": "stdio-read",
                "expected_activation_revision": 1,
                "bindings": {"work": "w1"},
                "input": {},
            }
        original = await call(client, "capability_read", read)
    async with Client(server, read_timeout_seconds=30) as client:
        assert await call(client, "capability_read", read) == original
        recovered = await call(client, "system_recover", {"system_id": sid})
        assert (
            recovered["result"]["active"]["definition_id"]
            == definition["definition_id"]
        ), recovered
        assert (
            recovered["result"]["history_anchor"]
            == original["result"]["history_anchor"]
        ), recovered
