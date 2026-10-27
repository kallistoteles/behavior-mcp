import pytest
from behavior import InMemoryBackend, Store

from behavior_mcp.authoring import build, capabilities, construction_context
from behavior_mcp.schemas import OperationError
from tests.fixtures.public_models import SEED, reference_module


def test_public_lowering_matches_independent_definition(proposal):
    module = build(proposal)
    expected = reference_module()
    assert module.behavior_version == expected.behavior_version
    assert module.schema_hash == expected.schema_hash
    assert module.model_receipts[0].model_hash == expected.model_receipts[0].model_hash
    assert {x["name"] for x in capabilities(module)} == {
        "record__new",
        "record__finish",
    }
    assert (
        next(x for x in capabilities(module) if x["name"] == "record__new")["params"][
            0
        ]["name"]
        == "request_id"
    )
    assert construction_context(proposal)["fixed_entities"][0]["name"] == "Actor"


def test_multiple_inputs_use_public_positional_binding(proposal):
    flow = proposal["models"][0]
    flow["payload"]["another"] = "string"
    flow["creations"][0]["inputs"]["another"] = "string"
    flow["creations"][0]["initializer"]["another"] = {
        "source": "input",
        "name": "another",
    }
    module = build(proposal)
    store = Store.create(InMemoryBackend(), module, Store.genesis_for(module, SEED))
    allowed = store.evaluate(
        module,
        "record__new",
        bindings={},
        input={"request_id": "r1", "label": "label", "another": "value"},
        context={"actor": "actor-1"},
        commit_time="2026-10-26T00:00:00Z",
    )
    assert allowed.decision.result == "ALLOW"
    store.commit(module, allowed.bundle)
    assert store.load("Record", "r1")["value"]["another"] == "value"


@pytest.mark.parametrize(
    "field,value",
    [("requires", [{"evil": "eval"}]), ("emits", []), ("source_code", "print(1)")],
)
def test_unsupported_programs_guards_and_effects_refused(proposal, field, value):
    proposal["models"][0][field] = value
    with pytest.raises(OperationError):
        build(proposal)


def test_authority_rejects_invalid_state_target(proposal):
    proposal["models"][0]["transitions"][0]["to"] = "Missing"
    from behavior import BehaviorError

    with pytest.raises(BehaviorError):
        build(proposal)


def test_json_object_member_sorting_cannot_change_enum_declaration_identity(proposal):
    import json

    original = build(proposal)
    transported = build(json.loads(json.dumps(proposal, sort_keys=True)))
    assert original.behavior_version == transported.behavior_version
    assert original.schema_hash == transported.schema_hash
