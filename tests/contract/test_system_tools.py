import pytest

from behavior_mcp.schemas import validate_output
from behavior_mcp.server import Application
from tests.fixtures.runtime import create_active


@pytest.mark.parametrize("failure", ["creating", "missing", "invalid"])
def test_system_listing_keeps_healthy_systems_discoverable(
    trusted_setup, proposal, failure
):
    from behavior_mcp.storage import connect, transaction

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    healthy, _, _, _ = create_active(app, proposal, "healthy")
    affected, _, _, _ = create_active(app, proposal, "affected")
    path = artifacts.system_path(affected)
    if failure == "creating":
        with connect(path) as db, transaction(db):
            db.execute("DELETE FROM system_meta WHERE key='descriptor'")
    elif failure == "missing":
        path.unlink()
    else:
        path.write_bytes(b"invalid sqlite database")
    before = path.read_bytes() if path.exists() else None
    listed = app.execute("systems_list", {})
    assert listed["request_status"] == "completed", listed
    by_id = {s["system_id"]: s for s in listed["result"]["systems"]}
    assert by_id[healthy]["lifecycle"] == "active"
    assert by_id[affected] == {
        "system_id": affected,
        "lifecycle": "creating" if failure == "creating" else "recovery_required",
        "active": None,
    }
    assert (path.read_bytes() if path.exists() else None) == before
    assert (
        app.execute("system_inspect", {"system_id": healthy})["result"]["active"]
        is not None
    )


def test_all_fixed_runtime_tools_and_wrong_scope_tokens(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    one, _, _, _ = create_active(app, proposal, "1")
    two, _, _, _ = create_active(app, proposal, "2")
    listing = app.execute("systems_list", {"limit": 1})
    assert len(listing["result"]["systems"]) == 1
    assert listing["result"]["next_cursor"]
    assert (
        len(
            app.execute(
                "systems_list", {"limit": 1, "cursor": listing["result"]["next_cursor"]}
            )["result"]["systems"]
        )
        == 1
    )
    assert {
        x["name"]
        for x in app.execute("capabilities_list", {"system_id": one})["result"][
            "capabilities"
        ]
    } == {"record__new", "record__finish"}
    evaluated = app.execute(
        "transition_evaluate",
        {
            "system_id": one,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "bound-op",
        },
    )
    bad = app.execute(
        "transition_commit",
        {
            "system_id": two,
            "evaluation_token": evaluated["result"]["evaluation_token"],
            "operation_id": "bound-op",
        },
    )
    assert bad["outcome"] == "conflict"
    missing = app.execute("system_inspect", {"system_id": "../../host"})
    assert missing["outcome"] in {"invalid_input", "unauthorized"}
    for name in ["state_read", "system_inspect", "capabilities_list", "system_recover"]:
        result = app.execute(name, {"system_id": one})
        validate_output(result)
    assert (
        app.execute(
            "definition_activate",
            {
                "system_id": one,
                "definition_id": "forged",
                "operation_id": "x",
                "expected_activation_revision": 1,
                "expected_history": {},
                "approved": True,
            },
        )["outcome"]
        == "invalid_input"
    )


@pytest.mark.parametrize(
    "name,args",
    [
        ("systems_create", {"definition_id": "d", "operation_id": "o"}),
        ("systems_list", {}),
        ("system_inspect", {"system_id": "s"}),
        (
            "definition_activate",
            {
                "system_id": "s",
                "definition_id": "d",
                "expected_activation_revision": 0,
                "expected_history": {
                    "format": "behavior.history_ref.v1",
                    "store": "sha256:" + "0" * 64,
                    "state": "sha256:" + "0" * 64,
                    "position": 0,
                    "record": "sha256:" + "0" * 64,
                },
                "operation_id": "o",
            },
        ),
        ("capabilities_list", {"system_id": "s"}),
        ("state_read", {"system_id": "s"}),
        (
            "transition_evaluate",
            {
                "system_id": "s",
                "capability_id": "a",
                "bindings": {},
                "input": {},
                "expected_activation_revision": 1,
                "operation_id": "o",
            },
        ),
        (
            "transition_commit",
            {"system_id": "s", "evaluation_token": "t", "operation_id": "o"},
        ),
        ("operation_get", {"system_id": "s", "operation_id": "o"}),
        ("system_recover", {"system_id": "s"}),
    ],
)
def test_every_runtime_tool_requires_current_grant(
    trusted_setup, policy_document, name, args
):
    root, ctx, _, artifacts = trusted_setup
    policy_document.update(version=2, operations=[])
    artifacts.install_policy(policy_document)
    assert (
        Application(root, ctx, "local-delegation").execute(name, args)["outcome"]
        == "unauthorized"
    )


def test_fresh_commit_uses_commit_grant_without_receipt_read_grant(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup
    policy_document.update(
        version=2,
        operations=[o for o in policy_document["operations"] if o != "operation_get"],
    )
    artifacts.install_policy(policy_document)
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    from tests.fixtures.runtime import evaluate_commit

    evaluate_commit(
        app,
        sid,
        "record__new",
        "fresh-no-read",
        input={"request_id": "r1", "label": "Example"},
    )


def test_state_pagination_cursor_fits_contract_and_binds_original_snapshot(
    trusted_setup, proposal
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal, "1")
    from tests.fixtures.runtime import evaluate_commit

    for number in [1, 2]:
        evaluate_commit(
            app,
            sid,
            "record__new",
            f"page-{number}",
            input={"request_id": f"r{number}", "label": "Example"},
        )
    first = app.execute(
        "state_read", {"system_id": sid, "entity": "Record", "limit": 1}
    )
    cursor = first["result"]["next_cursor"]
    assert cursor and len(cursor) <= 256
    evaluate_commit(
        app, sid, "record__new", "page-3", input={"request_id": "r3", "label": "Later"}
    )
    second = app.execute(
        "state_read",
        {
            "system_id": sid,
            "entity": "Record",
            "limit": 1,
            "cursor": cursor,
            "history": first["result"]["history_anchor"],
        },
    )
    assert second["request_status"] == "completed", second
    assert (
        second["result"]["records"][0]["id"] == "r2"
        and second["result"]["next_cursor"] is None
    )
    other, _, _, _ = create_active(app, proposal, "2")
    assert (
        app.execute(
            "state_read",
            {"system_id": other, "entity": "Record", "limit": 1, "cursor": cursor},
        )["request_status"]
        != "completed"
    )


def test_every_system_operation_denies_another_system_with_all_operation_grants_present(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    one, _, _, _ = create_active(app, proposal, "1")
    two, d2, c2, a2 = create_active(app, proposal, "2")
    e = app.execute(
        "transition_evaluate",
        {
            "system_id": two,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "other-evaluation",
        },
    )
    policy_document.update(version=2, system_scope={"kind": "ids", "system_ids": [one]})
    artifacts.install_policy(policy_document)
    cases = [
        ("system_inspect", {"system_id": two}),
        ("capabilities_list", {"system_id": two}),
        ("state_read", {"system_id": two}),
        ("system_recover", {"system_id": two}),
        ("operation_get", {"system_id": two, "operation_id": "other-evaluation"}),
        (
            "transition_evaluate",
            {
                "system_id": two,
                "capability_id": "record__new",
                "bindings": {},
                "input": {"request_id": "r2", "label": "Example"},
                "expected_activation_revision": 1,
                "operation_id": "denied-evaluation",
            },
        ),
        (
            "transition_commit",
            {
                "system_id": two,
                "evaluation_token": e["result"]["evaluation_token"],
                "operation_id": "other-evaluation",
            },
        ),
        (
            "definition_activate",
            {
                "system_id": two,
                "definition_id": d2["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": c2["result"]["receipt"]["history_anchor"],
                "operation_id": "denied-activation",
            },
        ),
        (
            "definition_activate",
            {
                "system_id": two,
                "definition_id": d2["definition_id"],
                "expected_activation_revision": 0,
                "expected_history": c2["result"]["receipt"]["history_anchor"],
                "operation_id": "activate-2",
            },
        ),
        (
            "systems_create",
            {"definition_id": d2["definition_id"], "operation_id": "create-2"},
        ),
    ]
    for name, args in cases:
        result = app.execute(name, args)
        assert result["outcome"] == "unauthorized", (name, result)
    listed = app.execute("systems_list", {})
    assert [item["system_id"] for item in listed["result"]["systems"]] == [one]
