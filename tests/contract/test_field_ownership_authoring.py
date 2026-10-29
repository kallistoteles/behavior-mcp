"""Safety analysis is retained separately from operational lowering receipts."""

from behavior_mcp.adapters import build
from tests.fixtures.expanded import example


def test_field_ownership_analyzes_generated_and_authored_actions():
    module = build(example("field-ownership"))
    analysis = module.safety_analysis.to_dict()
    assert analysis["status"] == "Lowered"
    assert analysis["is_certified"] is False
    assert len(module.model_receipts) == 1
    assert analysis["policy_set_hash"]
    assert analysis["policies"]
    assert any(a["name"] == "parent__stop" for a in analysis["inventory"]["actions"])
