import pytest

from behavior_mcp.authoring import build
from behavior_mcp.policy import Delegation
from behavior_mcp.schemas import OperationError


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("construction", "allowed_model_kinds", ["state_machine"]),
        ("construction", "allowed_model_ids", ["other"]),
        ("construction", "allowed_capability_names", ["record__new"]),
        ("construction", "adapter_version", "2"),
        ("effects", "allowed_forms", []),
        ("effects", "initializer_fields", []),
        ("effects", "assignment_fields", []),
        ("state", "allowed_status_values", ["Open"]),
        ("state", "allowed_status_edges", []),
        ("state", "allow_new_records", False),
        ("state", "allow_existing_record_changes", False),
    ],
)
def test_workspace_access_does_not_waive_candidate_bounds(
    policy_document, proposal, group, key, value
):
    policy_document[group][key] = value
    policy = Delegation.from_document(policy_document, "local-operator")
    with pytest.raises(OperationError):
        policy.check_candidate(proposal, build(proposal), existing=True)


def test_exact_named_exception_only(policy_document, proposal):
    policy_document["construction"]["allowed_capability_names"] = ["record__new"]
    p = Delegation.from_document(policy_document, "local-operator")
    p.check_candidate(
        proposal, build(proposal), existing=True, exceptions=["capability_set"]
    )
    with pytest.raises(OperationError):
        p.check_candidate(
            proposal, build(proposal), existing=True, exceptions=["model_id"]
        )
