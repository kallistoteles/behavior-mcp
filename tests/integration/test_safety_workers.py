"""Public worker evidence must be bounded, complete and scoped to its definition."""

import pytest

from behavior_mcp.schemas import OperationError


def test_safety_tools_are_fixed_commands_with_closed_schemas(trusted_setup):
    from behavior_mcp.server import Application

    root, context, _, _ = trusted_setup
    names = {t.name for t in Application(root, context, "local-delegation").tools()}
    assert {
        "definition_safety_certify",
        "definition_safety_verify_evidence",
        "state_validate_safety",
    } <= names


def test_owned_staging_cleanup_exists(tmp_path):
    from importlib import import_module, util

    assert util.find_spec("behavior_mcp.safety"), "Safety staging boundary is absent"
    safety = import_module("behavior_mcp.safety")
    assert callable(safety.cleanup_staging)


def test_chunks_are_bounded_and_system_evidence_is_private(tmp_path):
    from tests.fixtures.expanded import active

    app, sid, d, _, _ = active(tmp_path, "field-ownership")
    request = {
        "definition_id": d["definition_id"],
        "evidence_ref": d["safety_analysis_ref"],
        "offset": 0,
        "limit": 17,
    }
    chunk = app.execute("definition_get", request)
    assert chunk["request_status"] == "completed", chunk
    import base64

    assert len(base64.b64decode(chunk["result"]["data"])) == 17
    assert chunk["result"]["offset"] == 0
    for bad in (0, 65537):
        assert (
            app.execute("definition_get", dict(request, limit=bad))["outcome"]
            == "invalid_input"
        )
    history = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    private = app.execute(
        "state_validate_safety",
        {
            "system_id": sid,
            "definition_id": d["definition_id"],
            "expected_history": history,
        },
    )
    assert private["request_status"] == "completed", private
    denied = app.execute(
        "definition_get",
        dict(request, evidence_ref=private["result"]["validation_ref"]),
    )
    assert denied["outcome"] == "unauthorized", denied


@pytest.mark.parametrize(
    "name",
    [
        "definition_safety_certify",
        "definition_safety_verify_evidence",
        "state_validate_safety",
    ],
)
def test_new_boundary_errors_are_closed_envelopes(trusted_setup, name):
    from behavior_mcp.server import Application

    root, context, _, _ = trusted_setup
    result = Application(root, context, "local-delegation").execute(name, {})
    assert result["outcome"] == "invalid_input", result
    assert result["error"]["operation_may_have_committed"] is False


def test_cleanup_deletes_only_bounded_owned_dead_jobs(tmp_path, monkeypatch):
    import json
    import os

    from behavior_mcp.safety import cleanup_staging

    staging = tmp_path / ".proof-staging"
    staging.mkdir()
    for index in range(70):
        directory = staging / f"job-{index:03}"
        directory.mkdir()
        (directory / "owner.json").write_text(
            json.dumps({"format": "behavior-mcp.proof-job.v1", "pid": 1073741824})
        )
        (directory / "bundle.json").write_text('{"claimed_certificate":true}')
    live = staging / "job-live"
    live.mkdir()
    (live / "owner.json").write_text(
        json.dumps({"format": "behavior-mcp.proof-job.v1", "pid": os.getpid()})
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "authoritative").write_text("preserve")
    (staging / "job-symlink").symlink_to(outside, target_is_directory=True)
    from pathlib import Path

    original = Path.iterdir
    visited = []

    def counted(path):
        for entry in original(path):
            if path == staging:
                visited.append(entry)
            yield entry

    monkeypatch.setattr(Path, "iterdir", counted)
    cleanup_staging(tmp_path)
    assert len(visited) <= 64
    assert sum(d.name.startswith("job-0") for d in staging.iterdir()) >= 6
    assert live.exists() and (outside / "authoritative").read_text() == "preserve"
    assert not (tmp_path / "host.sqlite").exists()


def test_failed_proof_releases_slot_and_owned_staging(tmp_path, monkeypatch):
    import behavior_mcp.safety as safety
    from tests.fixtures.expanded import retained_lifecycle

    app, _, definition, _, _ = retained_lifecycle(tmp_path)
    monkeypatch.setattr(safety, "check_proof_dependencies", lambda: {})

    def failed(*_, **__):
        raise OperationError(
            "infrastructure", "TEST_WORKER_FAILURE", "Expected test interruption"
        )

    monkeypatch.setattr(safety, "run_bounded", failed)
    result = app.execute(
        "definition_safety_certify",
        {"definition_id": definition["definition_id"], "profile_id": "safety-default"},
    )
    assert result["request_status"] == "failed", result
    assert safety.PROOF_WORKERS.acquire(blocking=False)
    safety.PROOF_WORKERS.release()
    assert not list((tmp_path / ".proof-staging").iterdir())


def test_pure_proof_releases_locks_and_reauthorizes_disclosure(tmp_path, monkeypatch):
    import copy
    import json
    import threading

    import behavior_mcp.safety as safety
    from tests.fixtures.expanded import retained_lifecycle
    from tests.fixtures.runtime import evaluate_commit

    app, sid, definition, _, policy = retained_lifecycle(tmp_path)
    doc = app.artifacts.find("safety_assessment_evidence")[0][1]
    public = {
        "assessment": app.artifacts.get(doc["report"]["assessment_ref"]),
        "certificate": app.artifacts.get(doc["report"]["certificate_ref"]),
        "bundle": app.artifacts.get(doc["bundle_ref"]),
    }
    started = threading.Event()
    release = threading.Event()
    responses = []

    def blocked(*_, **__):
        started.set()
        assert release.wait(10)
        return json.dumps(public).encode()

    monkeypatch.setattr(safety, "run_bounded", blocked)
    monkeypatch.setattr(safety, "check_proof_dependencies", lambda: {})
    thread = threading.Thread(
        target=lambda: responses.append(
            app.execute(
                "definition_safety_certify",
                {
                    "definition_id": definition["definition_id"],
                    "profile_id": "safety-default",
                },
            )
        )
    )
    thread.start()
    try:
        assert started.wait(5)
        evaluate_commit(
            app,
            sid,
            "new_parent",
            "concurrent-parent",
            input={"new_id": "p_concurrent"},
        )
        updated = copy.deepcopy(policy)
        updated["version"] = 2
        updated["operations"].remove("definition_safety_certify")
        app.artifacts.install_policy(updated)
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive()
    assert responses[0]["outcome"] == "unauthorized", responses
    assert responses[0]["result"] == {}


def test_real_native_proof_cancellation_stops_descendants(tmp_path):
    import os
    import threading
    import time
    from pathlib import Path

    from behavior_mcp.proof_worker import PROOF_WORKERS
    from behavior_mcp.verification import CANCELLATION
    from tests.fixtures.expanded import retained_lifecycle

    app, _, definition, _, _ = retained_lifecycle(tmp_path)
    cancelled = threading.Event()
    responses = []

    def run():
        token = CANCELLATION.set(cancelled)
        try:
            responses.append(
                app.execute(
                    "definition_safety_certify",
                    {
                        "definition_id": definition["definition_id"],
                        "profile_id": "safety-default",
                    },
                )
            )
        finally:
            CANCELLATION.reset(token)

    def processes():
        table = {}
        for directory in Path("/proc").iterdir():
            if not directory.name.isdecimal():
                continue
            try:
                stat = (directory / "stat").read_text()
                end = stat.rfind(")")
                tail = stat[end + 2 :].split()
                table[int(directory.name)] = (
                    int(tail[1]),
                    tail[0],
                    stat[stat.find("(") + 1 : end],
                )
            except (OSError, ValueError, IndexError):
                continue
        return table

    before = processes()
    thread = threading.Thread(target=run)
    thread.start()
    native = []
    seen_at = {}
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            table = processes()
            descendants = {
                pid
                for pid, row in table.items()
                if row[0] == os.getpid() and pid not in before
            }
            for _ in range(8):
                descendants |= {
                    pid for pid, row in table.items() if row[0] in descendants
                }
            candidates = [
                pid
                for pid in descendants
                if "lean" in table[pid][2] and table[pid][0] != os.getpid()
            ]
            for pid in candidates:
                seen_at.setdefault(pid, time.monotonic())
            native = [
                pid for pid in candidates if time.monotonic() - seen_at[pid] >= 0.1
            ]
            if native or not thread.is_alive():
                break
            time.sleep(0.02)
        assert native, (
            "Declared native proof worker never reached the pinned checker",
            responses,
        )
    finally:
        cancelled.set()
        thread.join(5)
    assert not thread.is_alive()
    assert responses[0]["error"]["code"] == "WORKER_CANCELLED", responses
    deadline = time.monotonic() + 2
    while (
        any(
            pid in processes() and processes()[pid][1] not in {"Z", "X"}
            for pid in native
        )
        and time.monotonic() < deadline
    ):
        time.sleep(0.02)
    assert all(
        pid not in processes() or processes()[pid][1] in {"Z", "X"} for pid in native
    )
    assert PROOF_WORKERS.acquire(blocking=False)
    PROOF_WORKERS.release()
