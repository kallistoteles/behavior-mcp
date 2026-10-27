import json
import sys

import pytest
from behavior import Profile, verify

from behavior_mcp.authoring import build
from behavior_mcp.schemas import OperationError
from behavior_mcp.verification import project_attestation, verify_module


def test_exact_public_attestation_projection(proposal):
    module = build(proposal)
    report = verify_module(module, "bounded")
    assert report["upstream_result"] == report["report"]["result"]
    assert report["report_identity"] == report["report"]["hash"]
    assert report["checks"] == report["report"]["checks"]
    assert report["report"]["behavior_version"] == module.behavior_version
    assert report["semantic_profile"] == {
        "wire_ir": json.loads(module.to_wire_json())["ir_version"]
    }
    assert report["report"]["solver_version"] == "z3 4.16.0"
    assert report["verification_status"] == "verified"


def test_unknown_profile_and_missing_solver_fail_without_fabricated_proof(proposal):
    module = build(proposal)
    with pytest.raises(OperationError):
        verify_module(module, "invented")
    with pytest.raises(OperationError) as failure:
        verify_module(
            module,
            "bounded",
            worker_command=[sys.executable, "-c", "import sys; sys.exit(2)"],
        )
    assert failure.value.category == "infrastructure"


def test_worker_timeout_is_distinct(proposal):
    with pytest.raises(OperationError) as error:
        verify_module(
            build(proposal),
            "bounded",
            worker_command=[sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.1,
        )
    assert error.value.code == "VERIFICATION_TIMEOUT"


def test_inconclusive_report_cannot_be_projected_as_verified(proposal):
    module = build(proposal)
    actual = verify(module, Profile(rlimit=1, wall_clock_guard_ms=5000))
    projected = project_attestation(
        module,
        "bounded",
        {
            "result": actual.result,
            "hash": actual.hash,
            "data": actual.data,
            "json": actual.json,
        },
    )
    assert projected["upstream_result"] == actual.result
    assert projected["verification_status"] != "verified"
    bad = {
        "result": "verified",
        "hash": actual.hash,
        "data": actual.data,
        "json": actual.json,
    }
    with pytest.raises(OperationError):
        project_attestation(module, "bounded", bad)
