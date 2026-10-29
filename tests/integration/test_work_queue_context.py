"""Current time and worker identity are trusted; proposed deadlines are bounded."""

import pytest

from tests.fixtures.expanded import active
from tests.integration.test_work_queue_runtime import request, run


@pytest.mark.parametrize("role", ["input", "bindings", "context_proposals"])
@pytest.mark.parametrize("trusted", ["now", "actor", "worker"])
def test_trusted_binding_cannot_be_overridden(tmp_path, role, trusted):
    app, sid, _, _, _ = active(tmp_path, "work-queue")
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Example"},
    )
    args = request(
        app,
        sid,
        "claim",
        "forged",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )
    args[role][trusted] = 100 if trusted == "now" else "forged"
    result = app.execute("transition_evaluate", args)
    assert result["request_status"] == "refused", result
    assert result["error"]["operation_may_have_committed"] is False


def test_original_time_survives_retry_and_delayed_commit(tmp_path):
    now = [10]
    app, sid, _, _, _ = active(tmp_path, "work-queue", clock=lambda: now[0])
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Example"},
    )
    args = request(
        app,
        sid,
        "claim",
        "claim",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )
    e = app.execute("transition_evaluate", args)
    assert e["outcome"] == "evaluation_allowed", e
    now[0] = 100
    assert app.execute("transition_evaluate", args) == e
    committed = app.execute(
        "transition_commit",
        {
            "system_id": sid,
            "operation_id": "claim",
            "evaluation_token": e["result"]["evaluation_token"],
        },
    )
    assert committed["outcome"] == "committed", committed
    run(app, sid, "complete", "expired", inputs={"generation": 1}, expected="DENY")
