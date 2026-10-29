"""Every family retains editable source, authoritative identity and explicit ancestry."""

import copy

import pytest

from behavior_mcp.adapters import reconstruct
from behavior_mcp.server import Application
from tests.fixtures.expanded import setup
from tests.fixtures.runtime import authored


@pytest.mark.parametrize(
    "family", ["approval", "work-queue", "field-ownership", "lifecycle"]
)
def test_all_family_roundtrips_and_metadata_revisions(tmp_path, family):
    app, proposal, _ = setup(tmp_path, family)
    definition = authored(app, proposal)
    reopened = Application(tmp_path, app.context, app.policy_id)
    rebuilt, module, snapshot = reconstruct(
        reopened.artifacts, definition["definition_id"]
    )
    assert rebuilt == definition
    again = reopened.execute("definition_validate", definition["source"])
    assert again["result"]["definition"] == definition, again
    changed = copy.deepcopy(proposal)
    changed["metadata"] = {"title": "Revised display title"}
    saved = reopened.execute(
        "definition_propose",
        {
            "proposal": changed,
            "base_proposal_id": snapshot["proposal_id"],
            "expected_proposal_revision": snapshot["proposal_revision"],
        },
    )
    assert saved["result"]["proposal_revision"] == snapshot["proposal_revision"] + 1, (
        saved
    )
    next_definition = authored(reopened, changed)
    assert next_definition["definition_id"] != definition["definition_id"]
    assert next_definition["behavior_hash"] == definition["behavior_hash"]
    assert next_definition["schema_hash"] == definition["schema_hash"]
    assert next_definition["release"] == definition["release"]
    stale = reopened.execute(
        "definition_propose",
        {
            "proposal": proposal,
            "base_proposal_id": snapshot["proposal_id"],
            "expected_proposal_revision": snapshot["proposal_revision"],
        },
    )
    assert stale["outcome"] == "conflict", stale


@pytest.mark.parametrize(
    "family", ["approval", "work-queue", "field-ownership", "lifecycle"]
)
def test_semantic_revision_preserves_previous_artifacts(tmp_path, family):
    app, proposal, _ = setup(tmp_path, family)
    original = authored(app, proposal)
    changed = copy.deepcopy(proposal)
    if family == "approval":
        changed["models"][0]["approve_threshold"] = 1
    elif family == "work-queue":
        changed["models"][0]["max_attempts"] = 4
    elif family == "field-ownership":
        changed["safety"][0]["writers"]["phase"].append({"action": "remove_parent"})
    else:
        changed["safety"][-1]["terminal"].append("Active")
    candidate = authored(Application(tmp_path, app.context, app.policy_id), changed)
    assert candidate["definition_id"] != original["definition_id"]
    assert candidate["schema_hash"] == original["schema_hash"]
    assert (candidate["behavior_hash"], candidate["policy_set_hash"]) != (
        original["behavior_hash"],
        original["policy_set_hash"],
    )
    retained, _, snapshot = reconstruct(app.artifacts, original["definition_id"])
    assert retained == original and snapshot["proposal"] == proposal
