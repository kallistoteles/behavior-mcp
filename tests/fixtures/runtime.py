"""Generic tool journeys; expected decisions are independently checked against Core."""


def authored(app, proposal):
    p = app.execute("definition_propose", {"proposal": proposal})
    assert p["request_status"] == "completed", p
    s = p["result"]
    d = app.execute(
        "definition_validate",
        {"proposal_id": s["proposal_id"], "proposal_revision": s["proposal_revision"]},
    )
    assert d["outcome"] == "admitted", d
    return d["result"]["definition"]


def create_active(app, proposal, suffix="1"):
    definition = authored(app, proposal)
    created = app.execute(
        "systems_create",
        {
            "definition_id": definition["definition_id"],
            "operation_id": "create-" + suffix,
        },
    )
    assert created["outcome"] == "created", created
    receipt = created["result"]["receipt"]
    activated = app.execute(
        "definition_activate",
        {
            "system_id": receipt["system_id"],
            "definition_id": definition["definition_id"],
            "expected_activation_revision": 0,
            "expected_history": receipt["history_anchor"],
            "operation_id": "activate-" + suffix,
        },
    )
    assert activated["outcome"] == "activated", activated
    return receipt["system_id"], definition, created, activated


def evaluate_commit(
    app, system_id, capability, operation_id, *, bindings=None, input=None
):
    inspected = app.execute("system_inspect", {"system_id": system_id})
    assert inspected["request_status"] == "completed", inspected
    e = app.execute(
        "transition_evaluate",
        {
            "system_id": system_id,
            "capability_id": capability,
            "bindings": bindings or {},
            "input": input or {},
            "expected_activation_revision": inspected["result"]["active"][
                "activation_revision"
            ],
            "operation_id": operation_id,
        },
    )
    assert e["outcome"] == "evaluation_allowed", e
    r = app.execute(
        "transition_commit",
        {
            "system_id": system_id,
            "evaluation_token": e["result"]["evaluation_token"],
            "operation_id": operation_id,
        },
    )
    assert r["outcome"] == "committed", r
    return e, r


def composed_proposal(proposal):
    import copy

    result = copy.deepcopy(proposal)
    result["declarations"]["entities"].append(
        {"name": "Auxiliary", "fields": {"status": {"enum": "Status"}}}
    )
    result["models"].append(
        {
            "model_kind": "state_machine",
            "model_id": "auxiliary",
            "subject_entity": "Auxiliary",
            "state_field": "status",
            "subject_param": "auxiliary",
            "entry_states": ["Open"],
            "transitions": [
                {
                    "id": "finish",
                    "from": ["Open"],
                    "to": "Done",
                    "inputs": {},
                    "assignments": [],
                }
            ],
        }
    )
    return result
