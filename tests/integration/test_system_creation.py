from behavior_mcp.server import Application
from tests.fixtures.runtime import authored


def test_creation_is_inactive_and_retry_does_not_reset_history(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    d = authored(app, proposal)
    args = {
        "definition_id": d["definition_id"],
        "operation_id": "creation-1",
        "label": "Example",
    }
    first = app.execute("systems_create", args)
    assert first["outcome"] == "created", first
    system_id = first["result"]["receipt"]["system_id"]
    assert (
        app.execute("system_inspect", {"system_id": system_id})["result"]["lifecycle"]
        == "inactive"
    )
    assert (
        app.execute("capabilities_list", {"system_id": system_id})["outcome"]
        == "semantic_refusal"
    )
    second = Application(root, ctx, "local-delegation").execute("systems_create", args)
    assert second["outcome"] == "already_created"
    assert second["result"]["receipt"] == first["result"]["receipt"]
    wrong = dict(args, definition_id="different")
    assert app.execute("systems_create", wrong)["outcome"] == "conflict"


def test_creation_capacity_and_scope_do_not_create_permissions(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    d = authored(app, proposal)
    policy_document["system_creation"]["max_systems"] = 1
    policy_document["version"] = 2
    artifacts.install_policy(policy_document)
    assert (
        app.execute(
            "systems_create",
            {"definition_id": d["definition_id"], "operation_id": "one"},
        )["outcome"]
        == "created"
    )
    assert (
        app.execute(
            "systems_create",
            {"definition_id": d["definition_id"], "operation_id": "two"},
        )["outcome"]
        == "unauthorized"
    )
