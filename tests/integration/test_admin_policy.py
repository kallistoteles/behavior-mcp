import copy

import pytest

from behavior_mcp.admin import AdminAuthority, install_approval, install_policy
from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.schemas import OperationError
from behavior_mcp.server import Application
from tests.fixtures.runtime import authored, create_active


def test_policy_installation_binds_independent_issuer_and_workspace(
    tmp_path, policy_document
):
    authority = AdminAuthority(
        "local-operator", "workspace-1", tmp_path, ("agent-session",)
    )
    install_policy(tmp_path, policy_document, authority)
    assert ArtifactStore(tmp_path).policy("local-delegation") == policy_document
    forged = copy.deepcopy(policy_document)
    forged.update(version=2, issuer_id="claimed-admin")
    with pytest.raises(OperationError):
        install_policy(tmp_path, forged, authority)
    with pytest.raises(OperationError):
        install_policy(tmp_path / "other", policy_document, authority)
    changed = copy.deepcopy(policy_document)
    changed["effects"]["allow_external_commands"] = True
    with pytest.raises(OperationError):
        install_policy(tmp_path, changed, authority)


def test_exact_approval_is_not_runtime_permission_or_general_waiver(
    trusted_setup, proposal, policy_document
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, _ = create_active(app, proposal)
    changed = copy.deepcopy(proposal)
    changed["models"][0]["transitions"][0]["id"] = "complete"
    d2 = authored(app, changed)
    policy_document["version"] = 2
    policy_document["construction"]["allowed_capability_names"] = [
        "record__new",
        "record__finish",
    ]
    artifacts.install_policy(policy_document)
    head = app.execute("system_inspect", {"system_id": sid})["result"]["history_anchor"]
    request = {
        "system_id": sid,
        "definition_id": d2["definition_id"],
        "operation_id": "approved-activation",
        "expected_activation_revision": 1,
        "expected_history": head,
    }
    assert app.execute("definition_activate", request)["outcome"] == "unauthorized"
    approval = {
        "format": "behavior-mcp.activation-approval.v1",
        "approval_id": "approval-1",
        "issuer_id": "local-operator",
        "grantee_principal_id": ctx.principal_id,
        "workspace_id": ctx.workspace_id,
        "system_id": sid,
        "definition_id": d2["definition_id"],
        "behavior_hash": d2["behavior_hash"],
        "schema_hash": d2["schema_hash"],
        "policy_id": "local-delegation",
        "policy_version": 2,
        "expected_activation_revision": 1,
        "history_anchor": head,
        "exceptions": ["capability_set"],
    }
    authority = AdminAuthority(
        "local-operator", "workspace-1", root, ("agent-session",)
    )
    install_approval(root, approval, authority)
    assert app.execute("definition_activate", request)["outcome"] == "activated"
    evaluation = app.execute(
        "transition_evaluate",
        {
            "system_id": sid,
            "capability_id": "record__complete",
            "bindings": {"record": "r1"},
            "input": {"outcome": "x"},
            "expected_activation_revision": 2,
            "operation_id": "not-authorized",
        },
    )
    assert evaluation["outcome"] == "unauthorized"
    forged = dict(approval, approval_id="forged", exceptions=["schema_migration"])
    with pytest.raises(OperationError):
        install_approval(root, forged, authority)


def test_missing_required_proof_fails_closed(
    trusted_setup, proposal, policy_document, semantic_profile_id
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, c, a = create_active(app, proposal)
    policy_document.update(
        version=2,
        required_verification=[
            {
                "profile_id": "default",
                "semantic_profile_id": semantic_profile_id,
                "required_check_ids": ["missing-check"],
                "required_obligation_ids": [],
                "permitted_assumption_ids": [],
            }
        ],
    )
    artifacts.install_policy(policy_document)
    request = {
        "system_id": sid,
        "definition_id": d["definition_id"],
        "operation_id": "required-proof",
        "expected_activation_revision": 1,
        "expected_history": a["result"]["receipt"]["history_anchor"],
    }
    result = app.execute("definition_activate", request)
    assert result["outcome"] in {"unauthorized", "unsupported"}
    assert (
        app.execute("system_inspect", {"system_id": sid})["result"]["active"][
            "activation_revision"
        ]
        == 1
    )


def test_required_proof_accepts_actual_proven_check(
    trusted_setup, proposal, policy_document, semantic_profile_id
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, a = create_active(app, proposal)
    result = app.execute(
        "definition_verify",
        {"definition_id": d["definition_id"], "profile_id": "bounded"},
    )
    assert result["outcome"] == "verification_verified", result
    check = next(c for c in result["result"]["checks"] if c["outcome"] == "proven")
    policy_document.update(
        version=2,
        required_verification=[
            {
                "profile_id": "bounded",
                "semantic_profile_id": semantic_profile_id,
                "required_check_ids": [check["key"]],
                "required_obligation_ids": [],
                "permitted_assumption_ids": [],
            }
        ],
    )
    artifacts.install_policy(policy_document)
    activated = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": d["definition_id"],
            "operation_id": "proof-required",
            "expected_activation_revision": 1,
            "expected_history": a["result"]["receipt"]["history_anchor"],
        },
    )
    assert activated["outcome"] == "activated", activated
    assert activated["result"]["receipt"]["verification_evidence_refs"] == [
        result["evidence"][0]["report_ref"]
    ]


def test_overall_verified_cannot_satisfy_an_inconclusive_required_check(
    trusted_setup, proposal, policy_document, semantic_profile_id
):
    root, ctx, _, artifacts = trusted_setup
    app = Application(root, ctx, "local-delegation")
    sid, d, _, a = create_active(app, proposal)
    result = app.execute(
        "definition_verify",
        {"definition_id": d["definition_id"], "profile_id": "bounded"},
    )
    reference = result["evidence"][0]["report_ref"]
    evidence = artifacts.get(reference)
    check = next(c for c in evidence["report"]["checks"] if c["outcome"] == "proven")
    key = check["key"]
    # Adversarial synthetic coverage fixture. This is not genuine replacement proof evidence.
    check["outcome"] = "inconclusive"
    for item in evidence["report"]["report"]["checks"]:
        if item["key"] == key:
            item["outcome"] = "inconclusive"
    from behavior_mcp.storage import connect, transaction

    with connect(artifacts.path) as db, transaction(db):
        db.execute("DELETE FROM blobs WHERE id=?", (reference,))
    artifacts.put("verification_evidence", evidence)
    policy_document.update(
        version=2,
        required_verification=[
            {
                "profile_id": "bounded",
                "semantic_profile_id": semantic_profile_id,
                "required_check_ids": [key],
                "required_obligation_ids": [],
                "permitted_assumption_ids": [],
            }
        ],
    )
    artifacts.install_policy(policy_document)
    activated = app.execute(
        "definition_activate",
        {
            "system_id": sid,
            "definition_id": d["definition_id"],
            "operation_id": "inconclusive-check",
            "expected_activation_revision": 1,
            "expected_history": a["result"]["receipt"]["history_anchor"],
        },
    )
    assert activated["outcome"] == "unauthorized", activated
