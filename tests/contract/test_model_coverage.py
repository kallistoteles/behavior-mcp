import pytest

from behavior_mcp.server import Application
from tests.fixtures.runtime import composed_proposal


def test_discovery_labels_two_bounded_host_adapters(trusted_setup):
    root, ctx, _, _ = trusted_setup
    models = Application(root, ctx, "local-delegation").execute("models_list", {})[
        "result"
    ]["models"]
    by_kind = {m["model_kind"]: m for m in models}
    assert {k for k, m in by_kind.items() if m["authoring_supported"]} == {
        "request_flow",
        "state_machine",
    }
    for kind in ["request_flow", "state_machine"]:
        assert by_kind[kind]["schema_origin"].startswith("behavior-mcp")
        assert (
            by_kind[kind]["authoring_schema"]["$id"] == "urn:behavior-mcp:authoring:v1"
        )
        assert "v0.14.0" in by_kind[kind]["provenance"]
    assert (
        not by_kind["approval"]["authoring_supported"]
        and not by_kind["work_queue"]["authoring_supported"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", {"other": "Other"}),
        ("requires", [{"source": "code"}]),
        ("emits", []),
        ("effects", [{"code": "eval"}]),
    ],
)
def test_unsupported_machine_extensions_are_structured_refusals(
    trusted_setup, proposal, field, value
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    source = composed_proposal(proposal)
    source["models"][1][field] = value
    assert (
        app.execute("definition_propose", {"proposal": source})["outcome"]
        == "invalid_input"
    )


def test_invalid_enum_is_a_model_diagnostic_not_infrastructure(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    proposal["declarations"]["enums"][0]["cases"][1]["name"] = "OPEN"
    p = app.execute("definition_propose", {"proposal": proposal})["result"]
    result = app.execute(
        "definition_validate", {"proposal_id": p["proposal_id"], "proposal_revision": 1}
    )
    assert result["outcome"] == "model_invalid", result


def test_model_problem_descriptions_come_from_public_upstream_classes(trusted_setup):
    import inspect

    from behavior import Approval, RequestFlow, StateMachine, WorkQueue

    root, ctx, _, _ = trusted_setup
    models = Application(root, ctx, "local-delegation").execute("models_list", {})[
        "result"
    ]["models"]
    classes = {
        "request_flow": RequestFlow,
        "state_machine": StateMachine,
        "approval": Approval,
        "work_queue": WorkQueue,
    }
    for model in models:
        assert model["description"] == inspect.getdoc(classes[model["model_kind"]])
        assert model["description"]
