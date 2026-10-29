"""Composition uses public contributed handles and final whole-module admission."""

import copy

import pytest
from behavior import BehaviorError

from behavior_mcp.adapters import build
from tests.fixtures.expanded import example


def approval_flow():
    proposal = example("approval")
    proposal["adapter_version"] = "2.3.0"
    proposal["declarations"]["entities"] = []
    proposal["actions"] = []
    proposal["declarations"]["enums"] = [
        {
            "name": "Status",
            "cases": [
                {"name": "OPEN", "value": "Open"},
                {"name": "DONE", "value": "Done"},
            ],
        }
    ]
    flow = {
        "model_kind": "request_flow",
        "model_id": "record",
        "actor": "Actor",
        "status_enum": "Status",
        "payload": {"label": {"kind": "string"}},
        "creations": [
            {
                "id": "new",
                "to": "Open",
                "inputs": {"label": {"kind": "string"}},
                "values": {
                    "requester": {"op": "param", "name": "actor"},
                    "label": {"op": "param", "name": "label"},
                },
                "requires": [],
            }
        ],
        "transitions": [],
    }
    proposal["models"][0]["subject"] = {"model_id": "record", "output": "request"}
    proposal["models"].insert(0, flow)
    return proposal


def queue_machine():
    proposal = example("work-queue")
    proposal["adapter_version"] = "2.3.0"
    proposal["declarations"]["enums"] = [
        {
            "name": "Phase",
            "cases": [
                {"name": "OPEN", "value": "Open"},
                {"name": "DONE", "value": "Done"},
            ],
        }
    ]
    proposal["declarations"]["entities"] = [
        {"name": "Auxiliary", "fields": {"phase": {"kind": "enum", "name": "Phase"}}}
    ]
    proposal["models"].append(
        {
            "model_kind": "state_machine",
            "model_id": "auxiliary",
            "subject": "Auxiliary",
            "state_field": "phase",
            "entry_states": ["Open"],
            "transitions": [
                {
                    "id": "finish",
                    "from": ["Open"],
                    "to": "Done",
                    "inputs": {},
                    "requires": [],
                    "assignments": [],
                }
            ],
        }
    )
    proposal["actions"] = [
        {
            "kind": "create_entity",
            "name": "new_auxiliary",
            "entity": "Auxiliary",
            "values": {"phase": {"op": "enum", "enum": "Phase", "case": "OPEN"}},
            "requires": [],
        }
    ]
    return proposal


@pytest.mark.parametrize(
    "builder,kinds",
    [
        (approval_flow, {"approval", "request_flow"}),
        (queue_machine, {"work_queue", "state_machine"}),
    ],
)
def test_composed_modules_use_existing_models(builder, kinds):
    proposal = builder()
    module = build(proposal)
    assert {r.model_kind for r in module.model_receipts} == kinds
    assert module.behavior_version


def test_authoring_order_is_explicit_and_no_dependency_is_guessed():
    proposal = approval_flow()
    proposal["models"].reverse()
    module = build(proposal)
    assert len(module.model_receipts) == 2
    broken = copy.deepcopy(proposal)
    broken["models"][0]["subject"] = {"model_id": "absent", "output": "request"}
    from behavior_mcp.schemas import OperationError

    with pytest.raises(OperationError):
        build(broken)


def test_conflicting_model_ownership_is_native_refusal():
    proposal = queue_machine()
    duplicate = copy.deepcopy(proposal["models"][1])
    duplicate["model_id"] = "competing"
    proposal["models"].append(duplicate)
    with pytest.raises(BehaviorError):
        build(proposal)


def composed_setup(root, builder, family):
    from behavior_mcp.policy import Delegation
    from tests.fixtures.expanded import setup
    from tests.fixtures.runtime import create_active

    app, _, policy = setup(root, family)
    proposal = builder()
    policy["version"] = 2
    grant = copy.deepcopy(policy["allowed_adapters"][0])
    grant["adapter_version"] = "2.3.0"
    grant["allowed_model_kinds"] = [m["model_kind"] for m in proposal["models"]]
    grant["allowed_model_ids"] = [m["model_id"] for m in proposal["models"]]
    grant["allowed_entity_declarations"] = proposal["declarations"]["entities"]
    grant["allowed_enum_declarations"] = proposal["declarations"]["enums"]
    grant["allowed_action_descriptors"] = proposal["actions"]
    if family == "approval":
        grant["allowed_action_names"] = [
            "record__new",
            "review__approve",
            "review__reject",
        ]
        grant["state_fields"] = [
            {
                "entity": {"model_id": "record", "output": "request"},
                "field": "status",
                "values": ["Open", "Done"],
                "edges": [],
            }
        ]
    else:
        grant["allowed_action_names"] += ["new_auxiliary", "auxiliary__finish"]
        grant["state_fields"] = [
            {
                "entity": "Auxiliary",
                "field": "phase",
                "values": ["Open", "Done"],
                "edges": [{"from": "Open", "to": "Done"}],
            }
        ]
    policy["runtime_actions"] = grant["allowed_action_names"]
    policy["allowed_adapters"].append(grant)
    app.artifacts.install_policy(
        Delegation.from_document(policy, "local-operator").document
    )
    sid, definition, _, _ = create_active(app, proposal)
    return app, sid, definition


def test_approval_composes_with_request_flow_through_mcp(tmp_path):
    from tests.fixtures.expanded import read_args
    from tests.fixtures.runtime import evaluate_commit

    app, sid, definition = composed_setup(tmp_path, approval_flow, "approval")
    evaluate_commit(
        app,
        sid,
        "record__new",
        "request",
        input={"request_id": "r1", "label": "Record"},
    )
    evaluate_commit(
        app,
        sid,
        "review__approve",
        "approve",
        bindings={"subject": "r1"},
        input={"decision_id": "d1"},
    )
    result = app.execute(
        "capability_read",
        read_args(sid, "mcp_review_status", "status", {"subject": "r1"}),
    )
    assert result["request_status"] == "completed", result
    assert (
        app.execute("system_recover", {"system_id": sid})["request_status"]
        == "completed"
    )


def test_composed_queue_uses_one_core_concurrency_boundary(tmp_path):
    from tests.fixtures.runtime import evaluate_commit
    from tests.integration.test_work_queue_runtime import request, run

    app, sid, definition = composed_setup(tmp_path, queue_machine, "work-queue")
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Record"},
    )
    evaluate_commit(app, sid, "new_auxiliary", "auxiliary", input={"new_id": "a1"})
    old = app.execute(
        "transition_evaluate",
        request(
            app,
            sid,
            "claim",
            "before-other-model",
            inputs={"expected_generation": 0},
            proposals={"lease_until": 20},
        ),
    )
    assert old["outcome"] == "evaluation_allowed", old
    evaluate_commit(
        app, sid, "auxiliary__finish", "finish-auxiliary", bindings={"subject": "a1"}
    )
    conflict = app.execute(
        "transition_commit",
        {
            "system_id": sid,
            "operation_id": "before-other-model",
            "evaluation_token": old["result"]["evaluation_token"],
        },
    )
    assert conflict["outcome"] == "conflict", conflict
    run(
        app,
        sid,
        "claim",
        "after-other-model",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )


def test_cyclic_declaration_authoring_is_explicitly_unsupported():
    from behavior_mcp.schemas import OperationError

    proposal = approval_flow()
    proposal["declarations"]["entities"] += [
        {"name": "Left", "fields": {"right": {"kind": "ref", "entity": "Right"}}},
        {"name": "Right", "fields": {"left": {"kind": "ref", "entity": "Left"}}},
    ]
    with pytest.raises(OperationError) as error:
        build(proposal)
    assert error.value.code == "AUTHORING_REFERENCE_UNRESOLVED"


def test_expanded_schema_change_cannot_activate_by_matching_field_names(tmp_path):
    from tests.fixtures.expanded import active
    from tests.fixtures.runtime import authored

    app, sid, original, proposal, _ = active(tmp_path, "work-queue")
    proposal["models"][0]["payload"]["extra"] = {"kind": "string"}
    candidate = authored(app, proposal)
    assert candidate["schema_hash"] != original["schema_hash"]
    current = app.execute("system_inspect", {"system_id": sid})["result"]
    response = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": candidate["definition_id"],
            "expected_activation_revision": 1,
            "expected_history": current["history_anchor"],
            "operation_id": "schema-upgrade",
        },
    )
    assert response["outcome"] == "unsupported", response
    assert response["error"]["code"] == "SCHEMA_MIGRATION_UNSUPPORTED"
    assert app.execute("system_inspect", {"system_id": sid})["result"] == current
