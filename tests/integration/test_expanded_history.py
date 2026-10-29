"""Host definition/policy versions remain distinguishable when Core hashes coincide."""

import pytest

from behavior_mcp.adapters import historical_module
from tests.fixtures.expanded import active
from tests.fixtures.runtime import authored


def test_policy_revision_does_not_replace_active_or_historical_artifacts(tmp_path):
    app, sid, original, proposal, _ = active(tmp_path, "field-ownership")
    proposal["safety"][0]["writers"]["phase"].append({"action": "remove_parent"})
    candidate = authored(app, proposal)
    assert candidate["behavior_hash"] == original["behavior_hash"]
    assert candidate["policy_set_hash"] != original["policy_set_hash"]
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"][
            "definition_id"
        ]
        == original["definition_id"]
    )
    retained, module = historical_module(app.artifacts, original["definition_id"])
    assert retained == original and module.behavior_version == original["behavior_hash"]
    assert (
        app.artifacts.get(original["safety_analysis_ref"])["policy_set_hash"]
        == original["policy_set_hash"]
    )


def test_original_read_subject_survives_behavior_revision(tmp_path):
    from tests.fixtures.expanded import read_args
    from tests.fixtures.runtime import evaluate_commit

    app, sid, original, proposal, _ = active(tmp_path)
    evaluate_commit(app, sid, "new_subject", "subject", input={"new_id": "s1"})
    evaluate_commit(
        app,
        sid,
        "review__approve",
        "approve",
        bindings={"subject": "s1"},
        input={"decision_id": "d1"},
    )
    request = read_args(sid, "mcp_review_status", "original-read", {"subject": "s1"})
    before = app.execute("capability_read", request)
    proposal["models"][0]["approve_threshold"] = 1
    next_definition = authored(app, proposal)
    history = app.execute("system_inspect", {"system_id": sid})["result"][
        "history_anchor"
    ]
    activated = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": next_definition["definition_id"],
            "operation_id": "revision",
            "expected_activation_revision": 1,
            "expected_history": history,
        },
    )
    assert activated["outcome"] == "activated", activated
    assert app.execute("capability_read", request) == before
    fresh = app.execute(
        "capability_read",
        dict(request, operation_id="new-read", expected_activation_revision=2),
    )
    assert fresh["result"]["definition_id"] == next_definition["definition_id"], fresh
    assert fresh["result"]["response"]["value"] != before["result"]["response"]["value"]
    recovered = app.execute("system_recover", {"system_id": sid})
    assert recovered["request_status"] == "completed", recovered


@pytest.mark.parametrize("field", ["safety_evidence_refs", "state_validation_ref"])
def test_recovery_requires_original_activation_safety_artifacts(tmp_path, field):
    from behavior_mcp.storage import connect, transaction
    from tests.fixtures.expanded import retained_lifecycle

    app, sid, _, _, _ = retained_lifecycle(tmp_path)
    import json

    with connect(app.artifacts.system_path(sid)) as db:
        activation = json.loads(
            db.execute(
                "SELECT document FROM activations ORDER BY revision LIMIT 1"
            ).fetchone()[0]
        )
    reference = activation[field][0] if field.endswith("refs") else activation[field]
    assert reference
    with connect(app.artifacts.path) as db, transaction(db):
        db.execute("DELETE FROM blobs WHERE id=?", (reference,))
    result = app.execute("system_recover", {"system_id": sid})
    assert result["request_status"] == "failed", result
    assert result["outcome"] != "recovered", result


def test_historical_replay_does_not_require_fresh_model_authoring(
    tmp_path, monkeypatch
):
    import behavior_mcp.operations as operations

    app, sid, _, _, _ = active(tmp_path, "field-ownership")
    from tests.fixtures.runtime import evaluate_commit

    evaluate_commit(app, sid, "new_parent", "parent", input={"new_id": "p1"})

    def unavailable(*_, **__):
        raise RuntimeError("Fresh model authoring deliberately unavailable")

    monkeypatch.setattr(operations, "reconstruct", unavailable)
    recovered = app.execute("system_recover", {"system_id": sid})
    assert recovered["request_status"] == "completed", recovered
    assert recovered["result"]["history_anchor"]["position"] == 1
