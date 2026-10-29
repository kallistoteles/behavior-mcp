"""A semantic snapshot is trusted input, distinct from the legacy audit clock."""

import pytest

from behavior_mcp.policy import TrustedContext
from behavior_mcp.schemas import OperationError


def capture(context):
    fn = getattr(context, "snapshot", None)
    assert callable(fn), "Trusted semantic snapshot boundary is missing"
    return fn()


def test_legacy_context_is_preserved():
    ctx = TrustedContext("p", "w", "actor", lambda: "audit")
    assert ctx.clock() == "audit"
    with pytest.raises(OperationError):
        capture(ctx)


@pytest.mark.parametrize("now", [-1, True, 1.5, "10", 9007199254740992, None])
def test_bad_trusted_time_fails_closed(now):
    assert "semantic_clock" in TrustedContext.__dataclass_fields__, (
        "Missing explicit trusted provider"
    )
    ctx = TrustedContext("p", "w", "actor", lambda: "audit", semantic_clock=lambda: now)
    with pytest.raises(OperationError):
        capture(ctx)


def test_snapshot_captures_provider_once():
    assert "semantic_clock" in TrustedContext.__dataclass_fields__
    calls = []
    ctx = TrustedContext(
        "p", "w", "actor", lambda: "audit", semantic_clock=lambda: calls.append(1) or 10
    )
    snap = capture(ctx)
    assert snap == {
        "now": 10,
        "audit_time": "audit",
        "profile": "utc-unix-milliseconds.v1",
        "actor": "actor",
        "worker": "actor",
    }
    assert len(calls) == 1
