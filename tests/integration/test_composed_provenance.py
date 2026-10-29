from behavior import BehaviorModule

from behavior_mcp.authoring import reconstruct
from behavior_mcp.server import Application
from tests.fixtures.runtime import authored, composed_proposal


def test_imported_wire_has_no_receipts_but_original_provenance_survives(
    trusted_setup, proposal
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    source = composed_proposal(proposal)
    manifest = authored(app, source)
    imported = BehaviorModule.from_wire_json(
        artifacts.get(manifest["module_ref"])["wire_json"]
    )
    assert imported.model_receipts == []
    assert imported.behavior_version == manifest["behavior_hash"]
    loaded = Application(root, ctx, "local-delegation").execute(
        "definition_get", {"definition_id": manifest["definition_id"]}
    )["result"]["definition"]
    assert loaded == manifest
    assert len(reconstruct(artifacts, manifest["definition_id"])[1].model_receipts) == 2
    for model in loaded["models"]:
        assert (
            artifacts.get(model["receipt_ref"])["model"] == model["canonical_document"]
        )
    canonical = next(
        m["canonical_document"]
        for m in manifest["models"]
        if m["model_kind"] == "request_flow"
    )
    assert (
        app.execute("definition_propose", {"proposal": canonical})["outcome"]
        == "invalid_input"
    )
    assert {g["gap_id"] for g in app.execute("gaps_list", {})["result"]["gaps"]} == {
        "GAP-001",
        "GAP-002",
        "GAP-003",
        "GAP-004",
        "GAP-005",
    }
