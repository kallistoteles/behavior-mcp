"""Native analysis recognizes explicit guards; the MCP adapter supplies none."""

from behavior_mcp.adapters import build
from tests.fixtures.expanded import example


def test_canonical_lifecycle_is_lowered_but_not_certified():
    module = build(example("lifecycle"))
    analysis = module.safety_analysis.to_dict()
    assert analysis["status"] == "Lowered"
    assert analysis["issues"] == []
    assert analysis["is_certified"] is False
    assert len(module.model_receipts) == 0
    assert len(analysis["policies"]) == 3


def test_missing_whole_guard_remains_visible():
    proposal = example("lifecycle")
    next(a for a in proposal["actions"] if a["name"] == "stop_parent")["requires"] = []
    analysis = build(proposal).safety_analysis.to_dict()
    assert any(
        issue["code"] == "SAFETY_UNSUPPORTED_LIFECYCLE" for issue in analysis["issues"]
    ), analysis
