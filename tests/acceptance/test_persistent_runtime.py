import json
import sys

import pytest
from mcp import Client, StdioServerParameters

from behavior_mcp.server import Application, make_server
from tests.fixtures.runtime import create_active


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
@pytest.mark.parametrize("transport", ["memory", "stdio"])
async def test_two_sessions_recover_a_persistent_runtime(
    trusted_setup, proposal, mode, transport
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
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

    def server():
        return (
            make_server(Application(root, ctx, "local-delegation"))
            if transport == "memory"
            else StdioServerParameters(
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
        )

    async with Client(server(), mode=mode, read_timeout_seconds=20) as client:
        assert len((await client.list_tools()).tools) == 20
        evaluated = (
            await client.call_tool(
                "transition_evaluate",
                {
                    "system_id": sid,
                    "capability_id": "record__new",
                    "bindings": {},
                    "input": {"request_id": "r1", "label": "Example"},
                    "expected_activation_revision": 1,
                    "operation_id": "new-session",
                },
            )
        ).structured_content
        assert evaluated["outcome"] == "evaluation_allowed", evaluated
        args = {
            "system_id": sid,
            "evaluation_token": evaluated["result"]["evaluation_token"],
            "operation_id": "new-session",
        }
        committed = (
            await client.call_tool("transition_commit", args)
        ).structured_content
        assert committed["outcome"] == "committed", committed
    async with Client(server(), mode=mode, read_timeout_seconds=20) as client:
        retry = (await client.call_tool("transition_commit", args)).structured_content
        assert retry["outcome"] == "already_committed", retry
        read = (
            await client.call_tool(
                "state_read", {"system_id": sid, "entity": "Record", "record_id": "r1"}
            )
        ).structured_content
        assert read["result"]["records"][0]["value"]["label"] == "Example"
