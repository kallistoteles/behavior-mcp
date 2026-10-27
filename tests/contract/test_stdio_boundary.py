import pytest

from behavior_mcp.schemas import OperationError
from behavior_mcp.server import bounded_frames, decode_frame, make_server


def test_frame_limits_apply_before_decoding():
    with pytest.raises(OperationError):
        list(bounded_frames([b"x" * (1048576 + 1)]))
    assert list(bounded_frames([b'{"a":', b"1}\n"])) == [b'{"a":1}']
    with pytest.raises(OperationError):
        decode_frame(b"[" * 33 + b"0" + b"]" * 33)
    with pytest.raises(OperationError):
        decode_frame(b'{"password":"x",bad}')
    assert decode_frame(b'{"message":"[\\""}') == {"message": '["'}


def test_incomplete_frame_and_duplicate_keys_refused():
    with pytest.raises(OperationError):
        list(bounded_frames([b"{}"]))
    with pytest.raises(OperationError):
        decode_frame(b'{"a":1,"a":2}')


def test_public_sdk_owns_protocol_dispatch():
    from mcp.server import Server

    server = make_server(None)
    assert isinstance(server, Server)
    assert server.get_request_handler("tools/list") is not None
    assert server.get_request_handler("tools/call") is not None
    assert server.get_request_handler("host/policy") is None


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
async def test_sdk_protocol_modes(mode):
    from mcp import Client

    async with Client(make_server(None), mode=mode) as client:
        assert (await client.list_tools()).tools == []
        assert client.protocol_version == ("2025-11-25" if mode == "legacy" else mode)


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
async def test_real_stdio_sdk_launch(tmp_path, mode):
    import json
    import sys

    from mcp import Client, StdioServerParameters

    config = tmp_path / "launcher.json"
    config.write_text(
        json.dumps(
            {
                "workspace_root": str(tmp_path),
                "workspace_id": "workspace-1",
                "principal_id": "agent-session",
                "actor_id": "actor-1",
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
            str(tmp_path),
            "--host-config",
            str(config),
        ],
    )
    async with Client(params, mode=mode, read_timeout_seconds=10) as client:
        tools = (await client.list_tools()).tools
        assert "models_list" in {tool.name for tool in tools}
        assert "policy_update" not in {tool.name for tool in tools}
