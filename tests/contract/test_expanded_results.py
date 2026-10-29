"""Strict versioned results and private diagnostics remain distinct from semantic success."""

import copy

import pytest

from behavior_mcp.schemas import OperationError, validate_output
from tests.fixtures.expanded import active, read_args
from tests.fixtures.runtime import evaluate_commit


def test_v2_cannot_drop_policy_identity_or_fall_back_to_legacy_shape(tmp_path):
    app, _, definition, _, _ = active(tmp_path)
    result = app.execute(
        "definition_get", {"definition_id": definition["definition_id"]}
    )
    validate_output(result)
    for key in ["policy_set_hash", "inventory_ref", "format"]:
        changed = copy.deepcopy(result)
        changed["result"]["definition"].pop(key)
        with pytest.raises(OperationError):
            validate_output(changed)
    changed = copy.deepcopy(result)
    changed["result"]["definition"]["release"]["adapter_version"] = "1"
    with pytest.raises(OperationError):
        validate_output(changed)


def test_read_failure_redacts_diagnostics_and_never_claims_uncertain_commit(
    tmp_path, monkeypatch
):
    import behavior_mcp.proof_worker as workers

    app, sid, _, _, _ = active(tmp_path)
    evaluate_commit(app, sid, "new_subject", "subject", input={"new_id": "s1"})
    before = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]

    def fail(*_, **__):
        raise RuntimeError("credential=do-not-expose /private/path")

    monkeypatch.setattr(workers, "run_bounded", fail)
    result = app.execute(
        "capability_read",
        read_args(sid, "mcp_review_status", "failed-read", {"subject": "s1"}),
    )
    assert result["outcome"] == "infrastructure_failure", result
    assert result["error"]["operation_may_have_committed"] is False
    assert "do-not-expose" not in str(result)
    assert "/private/path" not in str(result)
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
        == before
    )
    validate_output(result)


def test_invalid_unsupported_authority_and_conflict_are_distinct(tmp_path):
    app, sid, _, _, policy = active(tmp_path)
    malformed = app.execute("capability_read", {"system_id": sid})
    unsupported = app.execute(
        "definition_propose",
        {
            "proposal": {
                "format": "behavior-mcp.authoring.v2",
                "adapter_profile": "structured-models.v2",
                "adapter_version": "99.0.0",
            }
        },
    )
    conflict = app.execute(
        "capability_read",
        read_args(sid, "mcp_review_status", "stale", {"subject": "s1"})
        | {"expected_activation_revision": 2},
    )
    from behavior_mcp.policy import Delegation

    policy.update(version=2, operations=[])
    app.artifacts.install_policy(
        Delegation.from_document(policy, "local-operator").document
    )
    denied = app.execute("models_list", {})
    assert malformed["outcome"] == "invalid_input", malformed
    assert unsupported["outcome"] == "unsupported", unsupported
    assert conflict["outcome"] == "conflict", conflict
    assert denied["outcome"] == "unauthorized", denied
    for response in [malformed, unsupported, conflict, denied]:
        validate_output(response)
        assert response["error"]["operation_may_have_committed"] is False
