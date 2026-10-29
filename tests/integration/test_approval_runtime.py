"""Approval outcomes and counts come exclusively from the public implementation."""

from dataclasses import replace

from behavior_mcp.server import Application
from tests.fixtures.expanded import active, read_args
from tests.fixtures.remaining_models import approval_module, reference_store
from tests.fixtures.runtime import evaluate_commit


def test_approval_threshold_duplicate_and_exact_public_read(tmp_path):
    app, sid, definition, _, _ = active(tmp_path, two_actors=True)
    evaluate_commit(app, sid, "new_actor", "actor-two", input={"new_id": "actor-2"})
    evaluate_commit(app, sid, "new_subject", "subject", input={"new_id": "s1"})
    oracle = approval_module()
    store = reference_store(
        oracle, [{"entity": "Subject", "value": {"id": "s1", "label": "Record"}}]
    )
    for index, (actor, choice, expected) in enumerate(
        [
            ("actor-1", "approve", "ALLOW"),
            ("actor-1", "reject", "DENY"),
            ("actor-2", "approve", "ALLOW"),
        ]
    ):
        app = Application(tmp_path, replace(app.context, actor_id=actor), app.policy_id)
        args = {
            "system_id": sid,
            "capability_id": "review__" + choice,
            "bindings": {"subject": "s1"},
            "input": {"decision_id": f"d{index}"},
            "expected_activation_revision": 1,
            "operation_id": f"choice-{index}",
        }
        expected_eval = store.evaluate(
            oracle,
            "review__" + choice,
            bindings=args["bindings"],
            input=args["input"],
            context={"actor": actor},
            commit_time=app.context.clock(),
        )
        result = app.execute("transition_evaluate", args)
        assert expected_eval.decision.result == expected
        assert result["outcome"] == (
            "evaluation_allowed" if expected == "ALLOW" else "semantic_refusal"
        ), result
        if expected == "ALLOW":
            committed = app.execute(
                "transition_commit",
                {
                    "system_id": sid,
                    "operation_id": args["operation_id"],
                    "evaluation_token": result["result"]["evaluation_token"],
                },
            )
            assert committed["outcome"] == "committed", committed
            store.commit(oracle, expected_eval.bundle)
        read = app.execute(
            "capability_read",
            read_args(sid, "mcp_review_status", f"read-{index}", {"subject": "s1"}),
        )
        public = store.read_intent(
            oracle,
            {
                "capability": "mcp_review_status",
                "targets": {"subject": "s1"},
                "input": {},
            },
            context={},
        )
        assert (
            read["result"]["response"]["value"] == public.response.as_dict()["value"]
        ), read
    state = app.execute(
        "state_read", {"system_id": sid, "entity": "Subject", "record_id": "s1"}
    )
    assert state["result"]["records"][0]["value"]["label"] == "Record"
