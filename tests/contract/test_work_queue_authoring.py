"""The queue slice requires all public registrations, typed time and exact discovery."""

import pytest

from behavior_mcp.adapters import build, discovery
from behavior_mcp.schemas import OperationError
from tests.fixtures.expanded import example


def test_all_nine_queue_capabilities_are_admitted_and_discoverable():
    import json

    proposal = example("work-queue")
    module = build(proposal)
    wire = json.loads(module.to_wire_json())
    assert {a["name"] for a in wire["actions"]} == {
        "jobs__" + name for name in proposal["models"][0]["capabilities"]
    }
    assert {r["name"] for r in wire["reads"]} == {
        "jobs__ready",
        "jobs__expired",
        "mcp_jobs_terminal",
    }
    queue = next(x for x in discovery() if x["model_kind"] == "work_queue")
    assert any(v["adapter_version"] == "2.1.0" for v in queue["adapter_versions"])


@pytest.mark.parametrize(
    "missing",
    [
        "enqueue",
        "claim",
        "renew",
        "complete",
        "retry",
        "fail",
        "recover",
        "exhaust",
        "cancel",
    ],
)
def test_missing_registration_is_rejected(missing):
    proposal = example("work-queue")
    del proposal["models"][0]["capabilities"][missing]
    with pytest.raises(OperationError):
        build(proposal)
