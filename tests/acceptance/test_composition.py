import copy

from behavior_mcp.server import Application
from tests.fixtures.runtime import composed_proposal, create_active, evaluate_commit


def test_composed_new_system_runtime_and_conflict_diagnostics(trusted_setup, proposal):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    source = composed_proposal(proposal)
    sid, definition, _, _ = create_active(app, source)
    assert len(definition["models"]) == 2
    capabilities = app.execute("capabilities_list", {"system_id": sid})["result"][
        "capabilities"
    ]
    assert {c["name"] for c in capabilities} == {
        "record__new",
        "record__finish",
        "auxiliary__finish",
    }
    machine = next(c for c in capabilities if c["name"] == "auxiliary__finish")
    assert (
        machine["params"][0]["role"] == "state"
        and machine["params"][0]["type"]["name"] == "Auxiliary"
    )
    evaluate_commit(
        app,
        sid,
        "record__new",
        "composed-new",
        input={"request_id": "r1", "label": "Example"},
    )
    evaluate_commit(
        app,
        sid,
        "record__finish",
        "composed-finish",
        bindings={"record": "r1"},
        input={"outcome": "Complete"},
    )
    assert (
        Application(root, ctx, "local-delegation").execute(
            "system_recover", {"system_id": sid}
        )["request_status"]
        == "completed"
    )
    conflict = copy.deepcopy(source)
    conflict["models"][1]["subject_entity"] = "Record"
    conflict["models"][1]["subject_param"] = "record"
    p = app.execute("definition_propose", {"proposal": conflict})["result"]
    refused = app.execute(
        "definition_validate", {"proposal_id": p["proposal_id"], "proposal_revision": 1}
    )
    assert refused["outcome"] == "model_invalid"
    assert "CONFLICTING_OWNERSHIP" in [
        d["code"] for d in refused["result"]["diagnostics"]
    ]
    assert (
        app.execute(
            "state_read", {"system_id": sid, "entity": "Record", "record_id": "r1"}
        )["result"]["records"][0]["value"]["status"]
        == "Done"
    )
