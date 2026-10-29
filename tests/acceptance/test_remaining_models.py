"""Agent-independent persistent acceptance journeys through the public MCP surface."""

from tests.fixtures.expanded import active, read_args
from tests.fixtures.runtime import evaluate_commit


def test_approval(tmp_path):
    app, sid, d, _, _ = active(tmp_path)
    evaluate_commit(app, sid, "new_subject", "subject", input={"new_id": "s1"})
    evaluate_commit(
        app,
        sid,
        "review__approve",
        "decision",
        bindings={"subject": "s1"},
        input={"decision_id": "d1"},
    )
    result = app.execute(
        "capability_read",
        read_args(sid, "mcp_review_status", "read", {"subject": "s1"}),
    )
    assert result["request_status"] == "completed", result
    assert result["result"]["definition_id"] == d["definition_id"]


def test_work_queue(tmp_path):
    from tests.integration.test_work_queue_runtime import run

    app, sid, d, _, _ = active(tmp_path, "work-queue")
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Example"},
    )
    run(
        app,
        sid,
        "claim",
        "claim",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )
    run(app, sid, "complete", "complete", inputs={"generation": 1})
    reads = app.execute(
        "capability_read",
        read_args(sid, "mcp_jobs_terminal", "terminal", {"work": "w1"}),
    )
    assert reads["request_status"] == "completed", reads


def test_field_ownership(tmp_path):
    from behavior_mcp.adapters import build
    from tests.fixtures.expanded import example

    proposal = example("field-ownership")
    module = build(proposal)
    assert module.safety_analysis.to_dict()["is_certified"] is False


def test_field_ownership_persists_and_recovers(tmp_path):
    from behavior_mcp.server import Application

    app, sid, d, _, _ = active(tmp_path, "field-ownership")
    evaluate_commit(app, sid, "new_parent", "new-parent", input={"new_id": "p1"})
    evaluate_commit(app, sid, "parent__stop", "stop", bindings={"subject": "p1"})
    observed = app.execute("definition_get", {"definition_id": d["definition_id"]})
    assert observed["request_status"] == "completed", observed
    assert any(
        a["kind"] == "safety_analysis" and a["document"]["is_certified"] is False
        for a in observed["result"]["artifacts"]
    )
    app = Application(tmp_path, app.context, app.policy_id)
    assert (
        app.execute("system_recover", {"system_id": sid})["request_status"]
        == "completed"
    )
    value = app.execute(
        "state_read", {"system_id": sid, "entity": "Parent", "record_id": "p1"}
    )
    assert value["result"]["records"][0]["value"]["phase"] == "Stopped", value


def test_lifecycle_dependency(tmp_path):
    from tests.fixtures.expanded import retained_lifecycle

    app, sid, d, _, _ = retained_lifecycle(tmp_path)
    evaluate_commit(app, sid, "new_parent", "parent-2", input={"new_id": "p2"})
    evaluate_commit(
        app,
        sid,
        "new_child",
        "child-2",
        bindings={"parent": "p2"},
        input={"new_id": "c2"},
    )
    before = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    refused = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "stop_parent",
            "bindings": {"subject": "p2"},
            "input": {},
            "operation_id": "refused-stop",
            "expected_activation_revision": 1,
        },
    )
    assert refused["outcome"] == "semantic_refusal", refused
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
        == before
    )
    evaluate_commit(app, sid, "finish_child", "finish-2", bindings={"subject": "c2"})
    evaluate_commit(app, sid, "stop_parent", "stop-2", bindings={"subject": "p2"})
    recovered = app.execute("system_recover", {"system_id": sid})
    assert recovered["request_status"] == "completed", recovered


def test_revision_and_composition(tmp_path):
    from tests.fixtures.runtime import authored
    from tests.integration.test_expanded_composition import (
        approval_flow,
        composed_setup,
    )

    app, sid, original = composed_setup(tmp_path, approval_flow, "approval")
    proposal = approval_flow()
    proposal["metadata"] = {"title": "Editable after restart"}
    next_definition = authored(app, proposal)
    assert next_definition["definition_id"] != original["definition_id"]
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"][
            "definition_id"
        ]
        == original["definition_id"]
    )
    assert (
        app.execute("system_recover", {"system_id": sid})["request_status"]
        == "completed"
    )


def test_support_and_authority(tmp_path):
    from tests.contract.test_expanded_catalog import (
        test_exact_six_family_support_matrix,
    )
    from tests.integration.test_expanded_isolation import (
        test_equal_definitions_have_independent_state_reads_activation_and_recovery,
    )

    test_exact_six_family_support_matrix()
    test_equal_definitions_have_independent_state_reads_activation_and_recovery(
        tmp_path
    )
