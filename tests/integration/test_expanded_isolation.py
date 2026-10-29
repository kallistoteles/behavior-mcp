"""Equal immutable artifacts never establish workspace, system or caller authority."""

import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from behavior_mcp.policy import Delegation
from behavior_mcp.server import Application
from tests.fixtures.expanded import active, read_args
from tests.fixtures.runtime import create_active, evaluate_commit


def test_equal_definitions_have_independent_state_reads_activation_and_recovery(
    tmp_path,
):
    app, one, definition, proposal, _ = active(tmp_path)
    two, same, _, _ = create_active(app, proposal, "two")
    assert one != two and same["module_ref"] == definition["module_ref"]
    assert same["behavior_hash"] == definition["behavior_hash"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                evaluate_commit,
                app,
                sid,
                "new_subject",
                "operation-" + rid,
                input={"new_id": rid},
            )
            for sid, rid in [(one, "one"), (two, "two")]
        ]
        for future in futures:
            future.result()
    for sid, rid in [(one, "one"), (two, "two")]:
        read = app.execute(
            "capability_read",
            read_args(sid, "mcp_review_status", "read-" + rid, {"subject": rid}),
        )
        assert read["request_status"] == "completed", read
        assert read["subject"]["system_id"] == sid
        records = app.execute("state_read", {"system_id": sid, "entity": "Subject"})[
            "result"
        ]["records"]
        assert [r["value"]["id"] for r in records] == [rid]
    reused = app.execute(
        "operation_get", {"system_id": two, "operation_id": "operation-one"}
    )
    assert reused["outcome"] == "conflict", reused
    before = app.execute("system_inspect", {"system_id": two})
    current = app.execute("system_inspect", {"system_id": one})["result"]
    changed = app.execute(
        "definition_activate",
        {
            "system_id": one,
            "definition_id": definition["definition_id"],
            "expected_activation_revision": 1,
            "expected_history": current["history_anchor"],
            "operation_id": "independent-activation",
        },
    )
    assert changed["outcome"] == "activated", changed
    recovered = Application(tmp_path, app.context, app.policy_id).execute(
        "system_recover", {"system_id": one}
    )
    assert recovered["request_status"] == "completed", recovered
    assert app.execute("system_inspect", {"system_id": two}) == before


@pytest.mark.parametrize("scope", ["system", "principal", "workspace"])
def test_current_scope_controls_operation_read_and_shared_definition_evidence(
    tmp_path, scope
):
    app, one, definition, proposal, policy = active(tmp_path)
    two, _, _, _ = create_active(app, proposal, "two")
    evaluate_commit(app, one, "new_subject", "original", input={"new_id": "s1"})
    request = read_args(one, "mcp_review_status", "original-read", {"subject": "s1"})
    assert app.execute("capability_read", request)["request_status"] == "completed"
    if scope == "system":
        policy = copy.deepcopy(policy)
        policy.update(version=2, system_scope={"kind": "ids", "system_ids": [two]})
        app.artifacts.install_policy(
            Delegation.from_document(policy, "local-operator").document
        )
        other = app
    else:
        context = replace(app.context, **{scope + "_id": "other-" + scope})
        other = Application(tmp_path, context, app.policy_id)
    for name, args in [
        ("operation_get", {"system_id": one, "operation_id": "original"}),
        ("capability_read", request),
        ("system_recover", {"system_id": one}),
    ]:
        result = other.execute(name, args)
        assert result["outcome"] == "unauthorized", result
        assert result["error"]["operation_may_have_committed"] is False
    if scope != "system":
        assert (
            other.execute(
                "definition_get", {"definition_id": definition["definition_id"]}
            )["outcome"]
            == "unauthorized"
        )


def test_forged_host_context_and_approval_are_rejected(tmp_path):
    app, sid, definition, _, _ = active(tmp_path)
    before = app.execute("system_inspect", {"system_id": sid})
    request = read_args(sid, "mcp_review_status", "forged", {"subject": "s1"})
    for field, value in [
        ("principal_id", "local-operator"),
        ("actor", "actor-1"),
        ("approved", True),
        ("now", 10),
    ]:
        result = app.execute("capability_read", dict(request, **{field: value}))
        assert result["outcome"] == "invalid_input", result
    activation = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "expected_activation_revision": 1,
            "expected_history": before["result"]["history_anchor"],
            "operation_id": "forged-approval",
            "approval_id": "agent-generated-approval",
        },
    )
    assert activation["outcome"] == "invalid_input", activation
    assert app.execute("system_inspect", {"system_id": sid}) == before
