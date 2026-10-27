import json
import sys

import pytest
from mcp import Client, StdioServerParameters

from behavior_mcp.server import Application, make_server


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
@pytest.mark.parametrize("transport", ["memory", "stdio"])
async def test_durable_agent_independent_authoring(
    trusted_setup, proposal, mode, transport
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
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
    server = (
        make_server(app)
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
    async with Client(server, mode=mode, read_timeout_seconds=15) as client:
        tools = await client.list_tools()
        assert "definition_propose" in {t.name for t in tools.tools}
        p = (
            await client.call_tool("definition_propose", {"proposal": proposal})
        ).structured_content["result"]
        a = (
            await client.call_tool(
                "definition_validate",
                {"proposal_id": p["proposal_id"], "proposal_revision": 1},
            )
        ).structured_content
        assert a["outcome"] == "admitted"
        definition = a["result"]["definition"]
        proof = (
            await client.call_tool(
                "definition_verify",
                {"definition_id": definition["definition_id"], "profile_id": "bounded"},
            )
        ).structured_content
        assert proof["request_status"] == "completed", proof
        assert all(t.input_schema and t.output_schema for t in tools.tools)
    reopened = Application(root, ctx, "local-delegation")
    second_server = make_server(reopened) if transport == "memory" else server
    async with Client(second_server, mode=mode, read_timeout_seconds=15) as client:
        loaded = (
            await client.call_tool(
                "definition_get", {"definition_id": definition["definition_id"]}
            )
        ).structured_content
        assert loaded["request_status"] == "completed", loaded
        inspection = loaded["result"]
        assert inspection["kind"] == "definition_inspection"
        assert inspection["definition"] == definition
        assert inspection["source"] == p
        by_ref = {a["artifact_ref"]: a for a in inspection["artifacts"]}
        from behavior import BehaviorModule

        restored = BehaviorModule.from_wire_json(
            by_ref[definition["module_ref"]]["document"]["wire_json"]
        )
        assert restored.behavior_version == definition["behavior_hash"]
        assert (
            by_ref[definition["construction_context_ref"]]["document"]
            == p["construction_context"]
        )
        for model in definition["models"]:
            assert (
                by_ref[model["receipt_ref"]]["document"]["model"]
                == model["canonical_document"]
            )
        retained = next(
            e
            for e in inspection["evidence"]
            if e["artifact_ref"] == proof["evidence"][0]["report_ref"]
        )
        assert retained["document"]["report"] == proof["result"]
        assert retained["document"]["subject"] == proof["subject"]
    assert (
        reopened.execute(
            "definition_get", {"proposal_id": p["proposal_id"], "proposal_revision": 1}
        )["result"]
        == p
    )
    assert not list((root / "systems").glob("*.sqlite"))
