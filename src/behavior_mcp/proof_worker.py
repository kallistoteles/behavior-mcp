"""Bounded fixed-command workers for public reads and Safety evidence.

Command arguments are constructed only by trusted host code. They are not MCP input.
"""

import json
import os
import subprocess
import sys
import threading

from .schemas import JSON, OperationError
from .verification import bounded_worker_output

PROOF_WORKERS = threading.BoundedSemaphore(1)


def run_bounded(
    command: list[str],
    request: JSON,
    *,
    timeout: float = 120,
    output_limit: int = 8 * 1024 * 1024,
    address_space_bytes: int = 4 * 1024**3,
    cancellation: threading.Event | None = None,
) -> bytes:
    if (
        type(address_space_bytes) is not int
        or not 1 <= address_space_bytes <= 8 * 1024**3
    ):
        raise ValueError("Trusted worker address-space ceiling is invalid")
    encoded = json.dumps(request, separators=(",", ":")).encode()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "behavior_mcp.proof_worker",
            "--exec",
            json.dumps(command),
            str(address_space_bytes),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        raw = bounded_worker_output(
            process,
            encoded,
            timeout,
            stdout_limit=output_limit,
            cancellation=cancellation,
        )
        if process.returncode != 0:
            raise OperationError(
                "infrastructure",
                "WORKER_FAILED",
                "Public worker failed",
                retryable=True,
            )
        return raw
    except OperationError as error:
        if error.code.endswith("_LIMIT"):
            raise OperationError(
                "infrastructure",
                "WORKER_OUTPUT_LIMIT",
                "Worker output exceeded the host limit",
            ) from None
        raise
    finally:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def _limits(address_space_bytes: int) -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_AS, (address_space_bytes, address_space_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))


def main() -> None:
    if sys.argv[1:] == ["--safety"]:
        safety_job()
        return
    if len(sys.argv) == 4 and sys.argv[1] == "--exec":
        command: list[str] = json.loads(sys.argv[2])
        _limits(int(sys.argv[3]))
        os.execvpe(command[0], command, dict(os.environ))
    raise SystemExit("A trusted worker command is required")


def safety_job() -> None:
    from pathlib import Path

    from behavior import certify_safety, load_safety_bundle, verify_safety_evidence

    from .adapters import build, construction_context
    from .dependencies import check_dependencies, check_proof_dependencies

    check_dependencies()
    tooling = check_proof_dependencies()
    request = json.load(sys.stdin)
    if construction_context(request["proposal"]) != request["construction_context"]:
        raise ValueError("Authoring context differs")
    module = build(request["proposal"])
    analysis = module.safety_analysis
    if (
        analysis is None
        or module.behavior_version != request["behavior_hash"]
        or module.schema_hash != request["schema_hash"]
        or analysis.to_dict()["policy_set_hash"] != request["policy_set_hash"]
    ):
        raise ValueError("Safety subject differs")
    output = Path(request["output"])
    if request["kind"] == "certify":
        assessment = certify_safety(module, output=output, toolchain=tooling["outPath"])
    elif request["kind"] == "check":
        assessment = verify_safety_evidence(
            module,
            load_safety_bundle(request["bundle"]),
            output=output,
            toolchain=tooling["outPath"],
        )
    else:
        raise ValueError("Unknown fixed proof operation")
    bundle_path = output / "bundle.json"
    if bundle_path.exists() and bundle_path.stat().st_size > request["bundle_limit"]:
        raise ValueError("Complete public bundle exceeds host limit")
    result = {
        "assessment": assessment.to_dict(),
        "certificate": assessment.certificate.to_dict()
        if assessment.certificate
        else None,
        "bundle": json.loads(bundle_path.read_text()) if bundle_path.exists() else None,
    }
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
