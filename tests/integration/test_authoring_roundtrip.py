import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from behavior_mcp.artifacts import ArtifactStore, encode
from behavior_mcp.authoring import admit_proposal, reconstruct
from behavior_mcp.schemas import OperationError
from behavior_mcp.server import Application
from tests.fixtures.runtime import authored


def test_two_exact_roundtrips_and_frozen_source_while_head_changes(
    trusted_setup, proposal, monkeypatch
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    definition = authored(app, proposal)
    first = reconstruct(ArtifactStore(root), definition["definition_id"])
    second = reconstruct(ArtifactStore(root), definition["definition_id"])
    assert first[0] == second[0] == definition
    assert first[1].behavior_version == second[1].behavior_version
    assert [r.to_dict() for r in first[1].model_receipts] == [
        r.to_dict() for r in second[1].model_receipts
    ]
    from behavior_mcp import authoring

    original = authoring.build
    reached = threading.Event()
    proceed = threading.Event()

    def paused(data):
        reached.set()
        assert proceed.wait(10)
        return original(data)

    monkeypatch.setattr(authoring, "build", paused)
    source = definition["source"]
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(admit_proposal, artifacts, source["proposal_id"], 1)
        assert reached.wait(10)
        updated = artifacts.propose(
            changed,
            base_proposal_id=source["proposal_id"],
            expected_proposal_revision=1,
        )
        assert updated["proposal_revision"] == 2
        proceed.set()
        assert pending.result() == definition
    assert artifacts.proposal(source["proposal_id"], 1)["proposal"] == proposal


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_kind", "state_machine"),
        ("model_semantic_version", 3),
        ("lowerer_version", 2),
    ],
)
def test_manifest_model_identity_metadata_must_match_authoritative_receipt(
    trusted_setup, proposal, field, value
):
    root, ctx, _, artifacts = trusted_setup
    d = authored(Application(root, ctx, "local-delegation"), proposal)
    tampered = copy.deepcopy(d)
    tampered["models"][0][field] = value
    from behavior_mcp.storage import connect, transaction

    with connect(artifacts.path) as db, transaction(db):
        db.execute(
            "UPDATE blobs SET document=? WHERE id=?",
            (encode(tampered), d["definition_id"]),
        )
    with pytest.raises(OperationError):
        reconstruct(artifacts, d["definition_id"])
