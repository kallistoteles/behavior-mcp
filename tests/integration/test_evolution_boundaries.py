import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from behavior import Store

from behavior_mcp.server import Application
from tests.fixtures.runtime import authored, create_active, evaluate_commit


def test_schema_change_and_stale_history_do_not_activate(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
    before = app.execute("system_inspect", {"system_id": sid})["result"]
    changed = copy.deepcopy(proposal)
    changed["models"][0]["payload"]["extra"] = "string"
    changed["models"][0]["creations"][0]["initializer"]["extra"] = {
        "source": "literal",
        "value": "",
    }
    schema_revision = authored(app, changed)
    args = {
        "system_id": sid,
        "definition_id": schema_revision["definition_id"],
        "expected_activation_revision": 1,
        "expected_history": before["history_anchor"],
        "operation_id": "schema-change",
    }
    assert app.execute("definition_activate", args)["outcome"] == "unsupported"
    assert app.execute("system_inspect", {"system_id": sid})["result"] == before
    evaluate_commit(
        app,
        sid,
        "record__new",
        "intervening",
        input={"request_id": "r1", "label": "Example"},
    )
    assert (
        app.execute(
            "definition_activate",
            dict(args, definition_id=d["definition_id"], operation_id="stale-head"),
        )["outcome"]
        == "conflict"
    )


def test_all_writers_share_activation_validation_boundary(
    trusted_setup, proposal, monkeypatch
):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
    e = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__new",
            "bindings": {},
            "input": {"request_id": "r1", "label": "Example"},
            "expected_activation_revision": 1,
            "operation_id": "racing-commit",
        },
    )
    head = app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
    original = Store.export_seed_at
    reached = threading.Event()
    proceed = threading.Event()

    def pause(store, module, anchor):
        result = original(store, module, anchor)
        reached.set()
        assert proceed.wait(10)
        return result

    monkeypatch.setattr(Store, "export_seed_at", pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        activation = pool.submit(
            app.execute,
            "definition_activate",
            {
                "system_id": sid,
                "definition_id": d["definition_id"],
                "expected_activation_revision": 1,
                "expected_history": head,
                "operation_id": "racing-activation",
            },
        )
        assert reached.wait(10)
        commit = pool.submit(
            app.execute,
            "transition_commit",
            {
                "system_id": sid,
                "evaluation_token": e["result"]["evaluation_token"],
                "operation_id": "racing-commit",
            },
        )
        assert not commit.done()
        proceed.set()
        assert activation.result()["outcome"] == "activated"
        assert commit.result()["outcome"] == "conflict"


def test_corrupt_current_state_is_not_converted_on_activation(trusted_setup, proposal):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
    evaluate_commit(
        app, sid, "record__new", "first", input={"request_id": "r1", "label": "Example"}
    )
    before = app.execute("system_inspect", {"system_id": sid})["result"]
    from behavior_mcp.storage import connect, transaction

    with connect(artifacts.system_path(sid)) as db, transaction(db):
        row = db.execute(
            "SELECT document FROM core_versions WHERE entity=? AND id=?",
            ("Record", "r1"),
        ).fetchone()
        doc = json.loads(row["document"])
        doc["value"]["status"] = "Missing"
        db.execute(
            "UPDATE core_versions SET document=? WHERE entity=? AND id=?",
            (json.dumps(doc), "Record", "r1"),
        )
    result = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": d["definition_id"],
            "expected_activation_revision": 1,
            "expected_history": before["history_anchor"],
            "operation_id": "invalid-state",
        },
    )
    assert result["request_status"] != "completed", result
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"]
        == before["active"]
    )


def test_missing_initialized_store_is_not_recreated_as_empty_history(
    trusted_setup, proposal
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, _, _, _ = create_active(app, proposal)
    evaluate_commit(
        app,
        sid,
        "record__new",
        "committed-before-loss",
        input={"request_id": "r1", "label": "Example"},
    )
    path = artifacts.system_path(sid)
    path.unlink()  # Infrastructure-loss injection, never an MCP state mutation.
    recovered = app.execute("system_recover", {"system_id": sid})
    assert recovered["request_status"] != "completed", recovered
    assert not path.exists(), (
        "Recovery must fail closed rather than recreate lost history"
    )
