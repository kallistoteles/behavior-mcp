"""Trusted limits restrict transport, reads and verifier resources, never semantics."""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from mcp import Client, StdioServerParameters

from behavior_mcp.schemas import OperationError
from behavior_mcp.server import Application, bounded_frames, decode_frame
from tests.fixtures.runtime import authored, create_active, evaluate_commit


def test_limits_apply_to_frames_depth_pages_and_public_profile(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    default = Application(root, ctx, "local-delegation")
    assert hasattr(default, "limits"), (
        "Operational limits must come from trusted configuration"
    )
    assert (
        default.limits.frame_bytes,
        default.limits.nesting_depth,
        default.limits.page_default,
        default.limits.page_max,
        default.limits.verification_workers,
    ) == (1048576, 32, 50, 100, 2)
    restricted = Application(
        root,
        ctx,
        "local-delegation",
        limits={
            "frame_bytes": 64,
            "nesting_depth": 2,
            "page_max": 1,
            "verification_workers": 1,
            "verification_profiles": {
                "bounded": {"rlimit": 1, "wall_clock_guard_ms": 1000}
            },
        },
    )
    assert list(bounded_frames([b"{}\n"], limits=restricted.limits)) == [b"{}"]
    with pytest.raises(OperationError, match="limit"):
        list(bounded_frames([b"x" * 65 + b"\n"], limits=restricted.limits))
    with pytest.raises(OperationError, match="depth"):
        decode_frame(b"[[[]]]", limits=restricted.limits)
    sid, definition, _, _ = create_active(restricted, proposal)
    for i in range(2):
        evaluate_commit(
            restricted,
            sid,
            "record__new",
            f"limit-{i}",
            input={"request_id": f"r{i}", "label": "Example"},
        )
    page = restricted.execute("state_read", {"system_id": sid, "entity": "Record"})
    assert len(page["result"]["records"]) == 1 and page["result"]["next_cursor"]
    assert (
        restricted.execute("state_read", {"system_id": sid, "limit": 2})["outcome"]
        == "invalid_input"
    )
    report = restricted.execute(
        "definition_verify",
        {"definition_id": definition["definition_id"], "profile_id": "bounded"},
    )
    assert report["request_status"] == "completed", report
    assert report["result"]["verification_status"] != "verified"
    assert report["result"]["report"]["profile"]["rlimit"] == 1
    assert report["result"]["report"]["profile"]["wall_clock_guard_ms"] == 1000
    assert (
        restricted.execute("models_list", {"limits": {"verification_workers": 2}})[
            "outcome"
        ]
        == "invalid_input"
    )


@pytest.mark.parametrize(
    "limits",
    [
        {"frame_bytes": 1048577},
        {"nesting_depth": 33},
        {"page_max": 101},
        {"page_default": 2, "page_max": 1},
        {"verification_workers": 3},
        {"verification_workers": True},
        {"unknown": 1},
        {"verification_profiles": {"invented": {}}},
        {"verification_profiles": {"bounded": {"rlimit": 20001}}},
        {"verification_profiles": {"bounded": {"command": "no"}}},
    ],
)
def test_invalid_trusted_limits_are_refused(trusted_setup, limits):
    root, ctx, _, _ = trusted_setup
    with pytest.raises(OperationError) as error:
        Application(root, ctx, "local-delegation", limits=limits)
    assert error.value.code == "HOST_LIMITS_INVALID"


def test_verification_worker_limit_is_enforced(trusted_setup, proposal, monkeypatch):
    from behavior_mcp import verification

    root, ctx, _, _ = trusted_setup
    assert hasattr(Application(root, ctx, "local-delegation"), "limits")
    app = Application(root, ctx, "local-delegation", limits={"verification_workers": 1})
    definition = authored(app, proposal)
    entered, release = threading.Event(), threading.Event()
    original = verification.subprocess.Popen

    def waiting(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(verification.subprocess, "Popen", waiting)
    args = {"definition_id": definition["definition_id"], "profile_id": "bounded"}
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(app.execute, "definition_verify", args)
        assert entered.wait(5)
        try:
            second = app.execute("definition_verify", args)
            assert second["error"]["code"] == "VERIFICATION_CAPACITY", second
        finally:
            release.set()
        assert first.result()["request_status"] == "completed"


async def test_launcher_uses_configured_transport_limits(trusted_setup):
    root, ctx, _, _ = trusted_setup
    config = root / "limits-launcher.json"
    config.write_text(
        json.dumps(
            {
                "workspace_root": str(root),
                "workspace_id": ctx.workspace_id,
                "principal_id": ctx.principal_id,
                "actor_id": ctx.actor_id,
                "policy_id": "local-delegation",
                "limits": {"frame_bytes": 4096, "nesting_depth": 16, "page_max": 1},
            }
        )
    )
    parameters = StdioServerParameters(
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
    async with Client(parameters, read_timeout_seconds=5) as client:
        assert (await client.call_tool("models_list", {})).structured_content[
            "request_status"
        ] == "completed"
