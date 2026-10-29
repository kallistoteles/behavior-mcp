"""Unverified proof premises and subject claims cannot establish a certificate."""

import copy

import pytest
from behavior import load_safety_bundle

from tests.fixtures.expanded import retained_lifecycle
from tests.integration.test_safety_evidence import bundle_for


@pytest.mark.parametrize("tampering", ["subject", "merge_trace"])
def test_tampered_bundle_is_rejected_or_freshly_reestablished(tmp_path, tampering):
    app, _, definition, _, _ = retained_lifecycle(tmp_path)
    original = bundle_for(app, definition)
    bundle = copy.deepcopy(original)
    if tampering == "subject":
        bundle["evidence"]["behavior_hash"] = "sha256:" + "0" * 64
    else:
        branch = next(n for n in bundle["witness"]["nodes"] if n["kind"] == "branch")
        branch["choices"][0] = not branch["choices"][0]
    # This deliberately remains structurally loadable unverified evidence. The
    # checking boundary, rather than an unknown top-level key, must handle it.
    load_safety_bundle(bundle)
    result = app.execute(
        "definition_safety_verify_evidence",
        {
            "definition_id": definition["definition_id"],
            "profile_id": "safety-default",
            "bundle": bundle,
        },
    )
    if result["outcome"] == "safety_certified":
        # The public checker may discard supplied claims and re-prove the exact
        # expected module. Only its freshly established original premises count.
        raw = app.artifacts.get(result["result"]["assessment_ref"])
        assert raw["behavior_hash"] == definition["behavior_hash"]
        assert raw["proof"]["witness"] == original["evidence"]["proof"]["witness"]
        assert result["result"]["certificate_ref"]
    else:
        assert result["result"].get("certificate_ref") is None, result
        assert (
            result.get("error") is None
            or result["error"]["operation_may_have_committed"] is False
        )
