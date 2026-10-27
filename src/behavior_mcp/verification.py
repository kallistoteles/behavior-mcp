"""Bounded public verification workers; no host proof engine or generated code."""

import json
import os
import signal
import subprocess
import sys
import threading

from behavior import BehaviorModule, Profile, verify

from .authoring import release_identity
from .limits import DEFAULT_PROFILES, HostLimits
from .schemas import JSON, OperationError

PROFILES = DEFAULT_PROFILES
WORKERS = threading.BoundedSemaphore(2)


def project_attestation(
    module: BehaviorModule,
    profile_id: str,
    attestation: JSON,
    *,
    expected_profile: JSON | None = None,
) -> JSON:
    report = attestation["data"]
    if expected_profile is not None and any(
        report.get("profile", {}).get(k) != v for k, v in expected_profile.items()
    ):
        raise OperationError(
            "infrastructure",
            "ATTESTATION_PROFILE_MISMATCH",
            "Public report differs from requested host profile parameters",
        )
    if (
        report != json.loads(attestation["json"])
        or report.get("result") != attestation["result"]
        or report.get("hash") != attestation["hash"]
        or report.get("behavior_version") != module.behavior_version
    ):
        raise OperationError(
            "infrastructure",
            "ATTESTATION_MISMATCH",
            "Public attestation fields do not agree",
        )
    if (
        report.get("verifier_version") != "0.10.0"
        or report.get("solver_version") != "z3 4.16.0"
    ):
        raise OperationError(
            "unsupported",
            "VERIFIER_IDENTITY_MISMATCH",
            "Attestation does not use the declared verifier and solver",
        )
    status = report["result"]
    if status not in {"verified", "not_verified"}:
        raise OperationError(
            "unsupported",
            "VERIFICATION_RESULT_UNSUPPORTED",
            "Public verification result is unsupported",
        )
    checks = report["checks"]
    if status != "verified" and any(c.get("outcome") == "inconclusive" for c in checks):
        status = "inconclusive"
    return {
        "kind": "verification",
        "verification_status": status,
        "upstream_result": report["result"],
        "profile_id": profile_id,
        "semantic_profile": {
            "wire_ir": json.loads(module.to_wire_json())["ir_version"]
        },
        "checks": checks,
        "obligations": report.get("obligations", []),
        "assumptions": report.get("assumptions", []),
        "report_identity": attestation["hash"],
        "report": report,
        "release": release_identity(),
    }


def verify_module(
    module: BehaviorModule,
    profile_id: str,
    *,
    worker_command: list[str] | None = None,
    timeout: float | None = None,
    limits: HostLimits | None = None,
    workers: threading.BoundedSemaphore | None = None,
) -> JSON:
    if profile_id not in PROFILES:
        raise OperationError(
            "unsupported",
            "VERIFICATION_PROFILE_UNSUPPORTED",
            "Verification profile is not host-enabled",
        )
    profile = (limits or HostLimits()).profile(profile_id)
    pool = workers or WORKERS
    if not pool.acquire(timeout=1):
        raise OperationError(
            "infrastructure",
            "VERIFICATION_CAPACITY",
            "Verification worker capacity is exhausted",
            retryable=True,
        )
    global_acquired = False
    try:
        if workers is not None:
            global_acquired = WORKERS.acquire(timeout=1)
            if not global_acquired:
                raise OperationError(
                    "infrastructure",
                    "VERIFICATION_CAPACITY",
                    "Verification worker capacity is exhausted",
                    retryable=True,
                )
        command = worker_command or [
            sys.executable,
            "-m",
            "behavior_mcp.verification",
            "--worker",
        ]
        with subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        ) as process:
            try:
                output, _ = process.communicate(
                    json.dumps({"wire": module.to_wire_json(), "profile": profile}),
                    timeout=timeout
                    if timeout is not None
                    else profile["wall_clock_guard_ms"] / 1000 + 5,
                )
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise OperationError(
                    "infrastructure",
                    "VERIFICATION_TIMEOUT",
                    "Verification worker deadline expired",
                    retryable=True,
                ) from None
            if process.returncode != 0:
                raise OperationError(
                    "infrastructure",
                    "VERIFICATION_WORKER_FAILED",
                    "Public verification worker failed; no attestation exists",
                    retryable=True,
                )
        try:
            return project_attestation(
                module, profile_id, json.loads(output), expected_profile=profile
            )
        except (ValueError, KeyError, TypeError):
            raise OperationError(
                "infrastructure",
                "INVALID_VERIFIER_REPORT",
                "Public verification worker returned no usable report",
            ) from None
    finally:
        if global_acquired:
            WORKERS.release()
        pool.release()


def main() -> None:
    request = json.load(sys.stdin)
    module = BehaviorModule.from_wire_json(request["wire"])
    result = verify(module, Profile(**request["profile"]))
    print(
        json.dumps(
            {
                "result": result.result,
                "hash": result.hash,
                "data": result.data,
                "json": result.json,
            }
        )
    )


if __name__ == "__main__":
    main()
