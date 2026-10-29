"""Real pinned-toolchain certification, export and fresh unverified-bundle checking."""

import base64
import json

from tests.fixtures.expanded import setup
from tests.fixtures.runtime import authored


def certify(app, definition):
    result = app.execute(
        "definition_safety_certify",
        {"definition_id": definition["definition_id"], "profile_id": "safety-default"},
    )
    assert result["outcome"] == "safety_certified", result
    report = result["result"]
    assert report["assessment_outcome"] == "Certified under assumptions"
    assert report["scope"] == "OrdinaryTransitions"
    assert report["initial_validity"] == "Unestablished"
    assert report["certificate_ref"] is not None
    return result


def bundle_for(app, definition):
    inspected = app.execute(
        "definition_get", {"definition_id": definition["definition_id"]}
    )
    assert inspected["request_status"] == "completed", inspected
    evidence = next(
        e
        for e in inspected["result"]["evidence"]
        if e["kind"] == "safety_assessment_evidence"
    )
    ref = evidence["document"]["bundle_ref"]
    data = bytearray()
    offset = 0
    while True:
        response = app.execute(
            "definition_get",
            {
                "definition_id": definition["definition_id"],
                "evidence_ref": ref,
                "offset": offset,
                "limit": 65536,
            },
        )
        assert response["request_status"] == "completed", response
        chunk = response["result"]
        data.extend(base64.b64decode(chunk["data"]))
        offset = len(data)
        if offset == chunk["total_bytes"]:
            break
    return json.loads(data)


def test_real_certification_and_fresh_import(tmp_path):
    app, proposal, _ = setup(tmp_path, "lifecycle")
    definition = authored(app, proposal)
    first = certify(app, definition)
    bundle = bundle_for(app, definition)
    checked = app.execute(
        "definition_safety_verify_evidence",
        {
            "definition_id": definition["definition_id"],
            "profile_id": "safety-default",
            "bundle": bundle,
        },
    )
    assert checked["outcome"] == "safety_certified", checked
    assert checked["result"]["policy_set_hash"] == first["result"]["policy_set_hash"]
    assert checked["result"]["certificate_ref"]
    bundle["behavior_hash"] = "sha256:" + "1" * 64
    bad = app.execute(
        "definition_safety_verify_evidence",
        {
            "definition_id": definition["definition_id"],
            "profile_id": "safety-default",
            "bundle": bundle,
        },
    )
    assert bad["outcome"] != "safety_certified", bad


def test_missing_tools_are_not_an_assessment(tmp_path, monkeypatch):
    app, proposal, _ = setup(tmp_path, "lifecycle")
    definition = authored(app, proposal)
    monkeypatch.setenv("BEHAVIOR_SAFETY_TOOLCHAIN", "/missing")
    result = app.execute(
        "definition_safety_certify",
        {"definition_id": definition["definition_id"], "profile_id": "safety-default"},
    )
    assert result["request_status"] == "failed", result
    assert result["error"]["operation_may_have_committed"] is False


def test_matching_behavior_does_not_accept_foreign_policy_evidence(tmp_path):
    import copy

    from tests.fixtures.expanded import retained_lifecycle

    app, _, original, proposal, _ = retained_lifecycle(tmp_path)
    bundle = bundle_for(app, original)
    changed = copy.deepcopy(proposal)
    next(p for p in changed["safety"] if p["id"] == "parent_control")["writers"][
        "phase"
    ].append({"action": "remove_parent"})
    candidate = authored(app, changed)
    assert candidate["behavior_hash"] == original["behavior_hash"]
    assert candidate["policy_set_hash"] != original["policy_set_hash"]
    response = app.execute(
        "definition_safety_verify_evidence",
        {
            "definition_id": candidate["definition_id"],
            "profile_id": "safety-default",
            "bundle": bundle,
        },
    )
    assert response["outcome"] != "safety_certified", response
    assert response["result"].get("certificate_ref") is None
