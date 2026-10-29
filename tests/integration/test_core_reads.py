"""Read execution must remain an authoritative public Core operation."""

import importlib
import importlib.util

from tests.fixtures.remaining_models import approval_module, reference_store


def test_public_read_and_replay():
    assert importlib.util.find_spec("behavior_mcp.reads"), (
        "Scoped read service is absent"
    )
    service = importlib.import_module("behavior_mcp.reads")
    m = approval_module()
    store = reference_store(
        m, [{"entity": "Subject", "value": {"id": "s1", "label": "Example"}}]
    )
    result = service.execute_read(
        store,
        m,
        {"capability": "mcp_review_status", "targets": {"subject": "s1"}, "input": {}},
        {},
        store.current(),
    )
    expected = store.read_intent(
        m,
        {"capability": "mcp_review_status", "targets": {"subject": "s1"}, "input": {}},
        context={},
        at=store.current(),
    )
    assert result.response.as_dict() == expected.response.as_dict()
    assert store.replay_read(m, result.record).matches


def test_read_journal_is_observational_during_recovery(tmp_path):
    from behavior_mcp.server import Application
    from tests.fixtures.expanded import active, read_args
    from tests.fixtures.runtime import evaluate_commit

    app, sid, _, _, _ = active(tmp_path)
    evaluate_commit(app, sid, "new_subject", "subject", input={"new_id": "s1"})
    request = read_args(sid, "mcp_review_status", "interrupted", {"subject": "s1"})

    def interrupt(stage):
        if stage == "after_read_pending":
            raise RuntimeError("interrupted after durable capture")

    interrupted = Application(
        tmp_path, app.context, app.policy_id, fault=interrupt
    ).execute("capability_read", request)
    assert interrupted["request_status"] == "failed", interrupted
    assert interrupted["error"]["operation_may_have_committed"] is False
    report = app.execute(
        "operation_get", {"system_id": sid, "operation_id": "interrupted"}
    )
    assert report["result"]["status"] == "pending", report
    recovered = app.execute(
        "system_recover", {"system_id": sid, "operation_id": "interrupted"}
    )
    assert recovered["outcome"] == "operation_status", recovered
    assert recovered["result"]["status"] == "pending"
    evaluate_commit(
        app,
        sid,
        "review__approve",
        "approve",
        bindings={"subject": "s1"},
        input={"decision_id": "d1"},
    )
    read = app.execute("capability_read", request)
    assert read["request_status"] == "completed", read
    assert read["result"]["history_anchor"]["position"] == 1
    assert (
        app.execute(
            "system_recover", {"system_id": sid, "operation_id": "interrupted"}
        )["result"]["status"]
        == "completed"
    )
