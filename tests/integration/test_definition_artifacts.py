import copy

import pytest

from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.authoring import admit_proposal
from behavior_mcp.schemas import OperationError


def test_proposal_revisions_and_immutable_manifest(tmp_path, proposal):
    store = ArtifactStore(tmp_path)
    first = store.propose(proposal)
    manifest = admit_proposal(store, first["proposal_id"], 1)
    fork = store.propose(proposal, parent_definition_id=manifest["definition_id"])
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    edit = store.propose(
        changed, base_proposal_id=fork["proposal_id"], expected_proposal_revision=1
    )
    assert edit["proposal_id"] == fork["proposal_id"] and edit["proposal_revision"] == 2
    assert edit["parent_definition_id"] == manifest["definition_id"]
    with pytest.raises(OperationError):
        store.propose(
            changed, base_proposal_id=fork["proposal_id"], expected_proposal_revision=1
        )
    with pytest.raises(OperationError):
        store.propose(
            changed,
            base_proposal_id=fork["proposal_id"],
            expected_proposal_revision=2,
            parent_definition_id="other",
        )
    reopened = ArtifactStore(tmp_path)
    assert reopened.proposal(fork["proposal_id"]) == edit
    assert reopened.proposal(fork["proposal_id"], 1) == fork
    assert admit_proposal(reopened, first["proposal_id"], 1) == manifest
    assert reopened.definition(manifest["definition_id"]) == manifest
    assert manifest["source"] == {
        "proposal_id": first["proposal_id"],
        "proposal_revision": 1,
    }
    assert (
        reopened.get(manifest["models"][0]["receipt_ref"])["model_hash"]
        == manifest["models"][0]["model_hash"]
    )


def test_metadata_never_changes_semantic_identity(tmp_path, proposal):
    store = ArtifactStore(tmp_path)
    first = store.propose(proposal)
    m1 = admit_proposal(store, first["proposal_id"], 1)
    proposal["metadata"] = {"title": "Another display label"}
    second = store.propose(proposal)
    m2 = admit_proposal(store, second["proposal_id"], 1)
    assert m1["behavior_hash"] == m2["behavior_hash"]
    assert "metadata" not in second["proposal"]
    assert second["metadata"] == {"title": "Another display label"}
