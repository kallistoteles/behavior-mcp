import copy
import importlib.metadata
import json
from pathlib import Path

import pytest

from behavior_mcp.schemas import (
    OperationError,
    load_schema,
    validate_input,
    validate_output,
)


def fixtures():
    p = Path(
        str(
            importlib.metadata.distribution("behavior-mcp").locate_file(
                "behavior_mcp/contracts/example-results.json"
            )
        )
    )
    return json.loads(p.read_text())


@pytest.mark.parametrize(
    "name",
    ["authoring", "tool-request", "host-policy", "activation-approval", "result"],
)
def test_installed_schema_resources(name):
    assert load_schema(name)["$schema"].endswith("2020-12/schema")


@pytest.mark.parametrize(
    "name", ["verified", "activated", "already_activated_after_newer_activation"]
)
def test_complete_synthetic_results(name):
    validate_output(fixtures()["valid"][name])


@pytest.mark.parametrize(
    "name",
    [
        "empty_verified",
        "empty_activation",
        "verified_from_inconclusive",
        "completed_with_error",
    ],
)
def test_invalid_synthetic_claims(name):
    with pytest.raises(OperationError):
        validate_output(fixtures()["invalid"][name])


def test_exact_revision_and_closed_inputs(proposal):
    validate_input("definition_propose", {"proposal": proposal})
    validate_input(
        "definition_propose",
        {
            "proposal": proposal,
            "base_proposal_id": "p",
            "expected_proposal_revision": 1,
        },
    )
    validate_input("definition_validate", {"proposal_id": "p", "proposal_revision": 1})
    for name, args in [
        ("definition_validate", {"proposal_id": "p"}),
        ("definition_propose", {"proposal": proposal, "base_proposal_id": "p"}),
        ("definition_get", {"definition_id": "d", "proposal_revision": 1}),
        ("models_list", {"actor": "admin"}),
    ]:
        with pytest.raises(OperationError):
            validate_input(name, args)


def test_runtime_projection_must_match_original_receipt():
    value = copy.deepcopy(fixtures()["valid"]["activated"])
    value["result"]["receipt"]["system_id"] = "other-system"
    with pytest.raises(OperationError):
        validate_output(value)


def test_invalid_server_output_is_an_infrastructure_error():
    with pytest.raises(OperationError) as error:
        validate_output(fixtures()["invalid"]["empty_verified"])
    assert error.value.category == "infrastructure"


@pytest.mark.parametrize(
    "target", ["behavior", "report_identity", "coverage", "evidence"]
)
def test_verification_projection_binds_exact_public_subject_and_evidence(target):
    value = copy.deepcopy(fixtures()["valid"]["verified"])
    if target == "behavior":
        value["result"]["report"]["behavior_version"] = "sha256:" + "f" * 64
    elif target == "report_identity":
        value["result"]["report_identity"] = "sha256:" + "f" * 64
    elif target == "coverage":
        value["result"]["report"]["checks"] = []
    else:
        value["evidence"][0]["subject"]["behavior_hash"] = "sha256:" + "f" * 64
    with pytest.raises(OperationError) as error:
        validate_output(value)
    assert error.value.category == "infrastructure"
