import copy

import pytest

from behavior_mcp.schemas import validate_output
from behavior_mcp.server import Application


@pytest.mark.parametrize("artifact", ["source", "module", "hash", "context"])
def test_verification_refuses_mismatched_retained_definition(
    trusted_setup, proposal, artifact
):
    from behavior_mcp.artifacts import encode
    from behavior_mcp.storage import connect, transaction
    from tests.fixtures.runtime import authored

    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    definition = authored(app, proposal)
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    with connect(artifacts.path) as db, transaction(db):
        if artifact == "source":
            source = artifacts.proposal(definition["source"]["proposal_id"], 1)
            source["proposal"] = changed
            db.execute(
                "UPDATE proposals SET document=? WHERE id=?",
                (encode(source), source["proposal_id"]),
            )
        else:
            altered = copy.deepcopy(definition)
            if artifact == "module":
                altered["module_ref"] = "missing-module"
            elif artifact == "hash":
                altered["behavior_hash"] = "sha256:" + "f" * 64
            else:
                altered["construction_context_ref"] = "missing-context"
            db.execute(
                "UPDATE blobs SET document=? WHERE id=?",
                (encode(altered), definition["definition_id"]),
            )
    result = app.execute(
        "definition_verify",
        {"definition_id": definition["definition_id"], "profile_id": "bounded"},
    )
    assert result["request_status"] != "completed", result
    assert not artifacts.find("verification_evidence")


def test_all_authoring_tool_boundaries(trusted_setup, proposal):
    root, ctx, policy, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    found = app.execute("models_list", {})
    assert found["request_status"] == "completed"
    assert any(
        m["model_kind"] == "request_flow" and m["authoring_supported"]
        for m in found["result"]["models"]
    )
    p = app.execute("definition_propose", {"proposal": proposal})["result"]
    original = app.execute(
        "definition_get", {"proposal_id": p["proposal_id"], "proposal_revision": 1}
    )
    assert original["result"] == p
    admitted = app.execute(
        "definition_validate", {"proposal_id": p["proposal_id"], "proposal_revision": 1}
    )
    assert admitted["outcome"] == "admitted"
    definition = admitted["result"]["definition"]
    assert (
        app.execute("definition_get", {"definition_id": definition["definition_id"]})[
            "result"
        ]["definition"]
        == definition
    )
    proof = app.execute(
        "definition_verify",
        {"definition_id": definition["definition_id"], "profile_id": "bounded"},
    )
    assert proof["result"]["verification_status"] == "verified"
    assert {g["gap_id"] for g in app.execute("gaps_list", {})["result"]["gaps"]} == {
        "GAP-001",
        "GAP-002",
        "GAP-003",
        "GAP-004",
        "GAP-005",
    }
    assert not list((root / "systems").glob("*.sqlite"))
    for result in [found, original, admitted, proof]:
        validate_output(result)


def test_frozen_validation_and_stale_proposal_edit(trusted_setup, proposal):
    root, ctx, _, _ = trusted_setup
    app = Application(root, ctx, "local-delegation")
    first = app.execute("definition_propose", {"proposal": proposal})["result"]
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    args = {
        "proposal": changed,
        "base_proposal_id": first["proposal_id"],
        "expected_proposal_revision": 1,
    }
    assert app.execute("definition_propose", args)["result"]["proposal_revision"] == 2
    assert app.execute("definition_propose", args)["outcome"] == "conflict"
    old = app.execute(
        "definition_validate",
        {"proposal_id": first["proposal_id"], "proposal_revision": 1},
    )["result"]["definition"]
    new = app.execute(
        "definition_validate",
        {"proposal_id": first["proposal_id"], "proposal_revision": 2},
    )["result"]["definition"]
    assert old["behavior_hash"] != new["behavior_hash"]
    assert old["source"]["proposal_revision"] == 1


def test_bad_source_and_missing_authority_are_structured(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    assert (
        app.execute("definition_validate", {"proposal_id": "missing"})["outcome"]
        == "invalid_input"
    )
    proposal["models"][0]["emits"] = []
    assert (
        app.execute("definition_propose", {"proposal": proposal})["outcome"]
        == "invalid_input"
    )
    policy_document.update(version=2, operations=[])
    artifacts.install_policy(policy_document)
    assert app.execute("models_list", {})["outcome"] == "unauthorized"
