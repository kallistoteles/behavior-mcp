"""Advertised schemas stay complete, strict and bounded to their fixed tool stage."""

import copy
import json

from jsonschema import Draft202012Validator

from behavior_mcp.server import Application
from tests.fixtures.expanded import active


def test_fixed_tool_catalog_schemas_fit_one_mebibyte(trusted_setup):
    root, context, _, _ = trusted_setup
    tools = Application(root, context, "local-delegation").tools()
    payload = [
        {"name": t.name, "inputSchema": t.input_schema, "outputSchema": t.output_schema}
        for t in tools
    ]
    assert len(json.dumps(payload).encode()) <= 1048576


def test_tool_schemas_reject_other_stages_and_preserve_closed_results(tmp_path):
    app, sid, definition, _, _ = active(tmp_path)
    tools = {t.name: t for t in app.tools()}
    results = {
        "models_list": app.execute("models_list", {}),
        "system_inspect": app.execute("system_inspect", {"system_id": sid}),
        "definition_get": app.execute(
            "definition_get", {"definition_id": definition["definition_id"]}
        ),
    }
    for name, result in results.items():
        validator = Draft202012Validator(tools[name].output_schema)
        validator.validate(result)
        wrong = copy.deepcopy(result)
        wrong["result"]["invented"] = True
        assert not validator.is_valid(wrong)
        for other, response in results.items():
            if other != name:
                assert not validator.is_valid(response)
    for tool in tools.values():
        Draft202012Validator.check_schema(tool.input_schema)
        Draft202012Validator.check_schema(tool.output_schema)
        assert tool.output_schema["type"] == "object"


def test_schema_specialization_preserves_failure_and_legacy_variants(
    trusted_setup, proposal
):
    root, context, _, _ = trusted_setup
    app = Application(root, context, "local-delegation")
    for tool in app.tools():
        response = app.execute(tool.name, {"invented": True})
        Draft202012Validator(tool.output_schema).validate(response)
    from tests.fixtures.runtime import authored

    definition = authored(app, proposal)
    response = app.execute(
        "definition_get", {"definition_id": definition["definition_id"]}
    )
    advertised = next(t for t in app.tools() if t.name == "definition_get")
    Draft202012Validator(advertised.output_schema).validate(response)


def test_stage_specialization_matches_original_contract_fixtures():
    from behavior_mcp.schemas import load_schema, resource, stage_result_schema

    legacy = json.loads(resource("example-results.json").read_text())
    from tests.fixtures.expanded import example

    for result in [*legacy["valid"].values(), *example("expanded-results")]:
        advertised = Draft202012Validator(stage_result_schema(result["stage"]))
        assert advertised.is_valid(result), result
    for result in legacy["invalid"].values():
        generic = any(
            Draft202012Validator(load_schema(name)).is_valid(result)
            for name in ["result", "expanded-result"]
        )
        advertised = Draft202012Validator(stage_result_schema(result["stage"]))
        assert advertised.is_valid(result) == generic
