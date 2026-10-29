"""Host orchestration of public Safety evidence, without model or proof semantics."""

import base64
import json
import os
import shutil
import sys
import tempfile
from itertools import islice
from pathlib import Path
from typing import Any, cast

from behavior import Store, validate_safety_snapshot

from .adapters import reconstruct
from .artifacts import encode
from .dependencies import check_proof_dependencies
from .policy import Delegation
from .proof_worker import PROOF_WORKERS, run_bounded
from .schemas import JSON, OperationError, completed
from .storage import file_lock


def cleanup_staging(root: Path) -> None:
    staging = root / ".proof-staging"
    if not staging.is_dir() or staging.is_symlink():
        return
    for directory in islice(staging.iterdir(), 64):
        marker = directory / "owner.json"
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or not directory.name.startswith("job-")
            or not marker.is_file()
            or marker.stat().st_size > 4096
        ):
            continue
        try:
            owner = json.loads(marker.read_text())
            if (
                owner.get("format") != "behavior-mcp.proof-job.v1"
                or type(owner.get("pid")) is not int
                or owner["pid"] <= 0
            ):
                continue
            try:
                os.kill(owner["pid"], 0)
            except ProcessLookupError:
                shutil.rmtree(directory)
        except (OSError, ValueError):
            continue


def artifact_subject(workspace_id: str, definition: JSON) -> JSON:
    return {
        "workspace_id": workspace_id,
        **{
            k: definition[k]
            for k in (
                "definition_id",
                "behavior_hash",
                "schema_hash",
                "policy_set_hash",
                "release",
            )
        },
    }


class Safety:
    def __init__(self, app: Any) -> None:
        self.app = app

    def policy(self) -> Delegation:
        doc = self.app.artifacts.policy(self.app.policy_id)
        return Delegation.from_document(doc, doc["issuer_id"])

    def run(self, name: str, args: JSON, subject: JSON) -> JSON:
        app = self.app
        with file_lock(app.workspace / "policy.lock", shared=True):
            captured_policy = self.policy()
            captured_policy.authorize(app.context, name)
            definition, module, snapshot = reconstruct(
                app.artifacts, args["definition_id"]
            )
            if not definition.get("safety_analysis_ref"):
                raise OperationError(
                    "unsupported",
                    "SAFETY_POLICIES_REQUIRED",
                    "This definition has no Safety policies",
                )
            subject.update(artifact_subject(app.context.workspace_id, definition))
            context = app.artifacts.get(definition["construction_context_ref"])
            imported_ref = None
            if name == "definition_safety_verify_evidence":
                imported_ref = app.artifacts.put(
                    "unverified_safety_bundle",
                    {"subject": dict(subject), "bundle": args["bundle"]},
                )
        check_proof_dependencies()
        if not PROOF_WORKERS.acquire(blocking=False):
            raise OperationError(
                "infrastructure",
                "PROOF_CAPACITY",
                "Proof worker capacity is occupied",
                retryable=True,
            )
        try:
            staging = app.workspace / ".proof-staging"
            staging.mkdir(mode=0o700, exist_ok=True)
            if staging.is_symlink():
                raise OperationError(
                    "infrastructure",
                    "PROOF_STAGING_INVALID",
                    "Owned proof staging is unavailable",
                )
            with tempfile.TemporaryDirectory(prefix="job-", dir=staging) as temporary:
                directory = Path(temporary)
                (directory / "owner.json").write_text(
                    json.dumps(
                        {"format": "behavior-mcp.proof-job.v1", "pid": os.getpid()}
                    )
                )
                request = {
                    "kind": "check" if imported_ref else "certify",
                    "proposal": snapshot["proposal"],
                    "construction_context": context,
                    "behavior_hash": definition["behavior_hash"],
                    "schema_hash": definition["schema_hash"],
                    "policy_set_hash": definition["policy_set_hash"],
                    "output": str(directory / "public-output"),
                    "bundle_limit": app.limits.proof_bundle_bytes,
                }
                if imported_ref:
                    request["bundle"] = args["bundle"]
                output = run_bounded(
                    [sys.executable, "-m", "behavior_mcp.proof_worker", "--safety"],
                    request,
                    timeout=app.limits.proof_timeout_seconds,
                    address_space_bytes=8 * 1024**3,
                )
                public = json.loads(output)
                analysis = app.artifacts.get(definition["safety_analysis_ref"])
                validate_assessment(public, definition, analysis)
                if (
                    public["bundle"] is not None
                    and len(encode(public["bundle"]).encode())
                    > app.limits.proof_bundle_bytes
                ):
                    raise OperationError(
                        "infrastructure",
                        "PROOF_BUNDLE_LIMIT",
                        "Complete public bundle exceeds the host byte limit",
                    )
            # Pure compilation holds neither policy nor system writer locks. Disclosure
            # and artifact publication receive a fresh current-policy authorization.
            with file_lock(app.workspace / "policy.lock", shared=True):
                current_policy = self.policy()
                current_policy.authorize(app.context, name)
                report = public["assessment"]
                report_ref = app.artifacts.put("safety_assessment", report)
                certificate_ref = (
                    app.artifacts.put("safety_certificate", public["certificate"])
                    if public["certificate"] is not None
                    else None
                )
                bundle_ref = (
                    app.artifacts.put("safety_bundle", public["bundle"])
                    if public["bundle"] is not None
                    else None
                )
                projection = {
                    "kind": "safety_assessment",
                    **{
                        k: definition[k]
                        for k in (
                            "definition_id",
                            "behavior_hash",
                            "schema_hash",
                            "policy_set_hash",
                            "release",
                        )
                    },
                    "profile_id": args["profile_id"],
                    "analysis_version": report["analysis_version"],
                    "checker_version": report["checker_version"],
                    "assessment_outcome": report["outcome"],
                    "assumptions": report["assumptions"],
                    "obligations": report["obligations"],
                    "assessment_ref": report_ref,
                    "certificate_ref": certificate_ref,
                    **{
                        k: report[k]
                        for k in (
                            "scope",
                            "initial_validity",
                            "exclusions",
                            "external_obligations",
                            "dependency_identity",
                        )
                    },
                }
                ref = app.artifacts.put(
                    "safety_assessment_evidence",
                    {
                        "subject": dict(subject),
                        "report": projection,
                        "release": definition["release"],
                        "bundle_ref": bundle_ref,
                        "import_ref": imported_ref,
                        "authorization": {
                            "principal_id": app.context.principal_id,
                            "operation": name,
                            "original_policy": {
                                "policy_id": captured_policy.document["policy_id"],
                                "policy_version": captured_policy.document["version"],
                            },
                            "current_policy": {
                                "policy_id": current_policy.document["policy_id"],
                                "policy_version": current_policy.document["version"],
                            },
                            "audit_time": app.context.clock(),
                        },
                    },
                )
                evidence = [
                    {
                        "evidence_id": ref,
                        "kind": "safety_checking"
                        if imported_ref
                        else "safety_certification",
                        "report_ref": ref,
                        "subject": dict(subject),
                        "release": definition["release"],
                    }
                ]
                outcome = {
                    "Certified under assumptions": "safety_certified",
                    "Inconclusive": "safety_inconclusive",
                    "Unsupported": "safety_unsupported",
                    "Failed": "safety_failed",
                }[report["outcome"]]
                return completed(
                    "safety_checking" if imported_ref else "safety_certification",
                    outcome,
                    subject,
                    projection,
                    evidence,
                )
        finally:
            PROOF_WORKERS.release()


def validate_assessment(public: JSON, definition: JSON, analysis: JSON) -> None:
    report = public["assessment"]
    certificate = public["certificate"]
    if (
        any(
            report.get(k) != definition[k] for k in ("behavior_hash", "policy_set_hash")
        )
        or report.get("inventory") != analysis["inventory"]
        or report.get("policies") != analysis["policies"]
    ):
        raise OperationError(
            "infrastructure",
            "SAFETY_SUBJECT_MISMATCH",
            "Public assessment differs from the exact definition or complete policies",
        )
    certified = report["outcome"] == "Certified under assumptions"
    if certified != (certificate is not None) or (
        certified
        and any(
            certificate.get(k) != report.get(k)
            for k in (
                "behavior_hash",
                "policy_set_hash",
                "inventory",
                "policies",
                "evidence_hash",
                "outcome",
                "dependency_identity",
            )
        )
    ):
        raise OperationError(
            "infrastructure",
            "SAFETY_CERTIFICATE_MISMATCH",
            "Public assessment and certificate disagree",
        )


def evidence_chunk(
    artifacts: Any, definition: JSON, workspace_id: str, args: JSON
) -> JSON:
    allowed = {definition.get("safety_analysis_ref")}
    for _, doc in artifacts.find("safety_assessment_evidence"):
        if (
            doc["subject"].get("definition_id") == definition["definition_id"]
            and doc["subject"].get("workspace_id") == workspace_id
            and "system_id" not in doc["subject"]
        ):
            allowed.update(
                [
                    doc["report"]["assessment_ref"],
                    doc["report"]["certificate_ref"],
                    doc.get("bundle_ref"),
                ]
            )
    ref = args["evidence_ref"]
    if ref not in allowed or ref is None:
        raise OperationError(
            "unauthorized",
            "EVIDENCE_SCOPE_DENIED",
            "Evidence is not an artifact-only member of this exact definition",
        )
    data = encode(artifacts.get(ref)).encode()
    return {
        "kind": "evidence_chunk",
        "definition_id": definition["definition_id"],
        "evidence_ref": ref,
        "offset": args["offset"],
        "limit": args["limit"],
        "total_bytes": len(data),
        "encoding": "base64",
        "data": base64.b64encode(
            data[args["offset"] : args["offset"] + args["limit"]]
        ).decode(),
    }


def acquire_validation(
    manager: Any, sid: str, definition: JSON, module: Any, history: JSON
) -> tuple[JSON, str, bool]:
    store = Store.open(manager.backend(sid, allow_publication=False))
    record = validate_safety_snapshot(store, module, at=history)
    report = record.to_dict()
    if any(
        report.get(k) != v
        for k, v in {
            "behavior_hash": definition["behavior_hash"],
            "policy_set_hash": definition["policy_set_hash"],
            "schema": definition["schema_hash"],
            "history": history,
        }.items()
    ):
        raise OperationError(
            "infrastructure",
            "SAFETY_STATE_SUBJECT_MISMATCH",
            "Public state validation differs from its exact subject",
        )
    subject = manager.subject(sid, definition, history)
    ref = manager.artifacts.put(
        "safety_state_validation_evidence",
        {"subject": subject, "report": report, "release": definition["release"]},
    )
    return report, ref, record.matches_anchor(module, history)


def state_validation(manager: Any, args: JSON, subject: JSON) -> JSON:
    sid = args["system_id"]
    manager.policy.authorize(manager.context, "definition_get")
    definition, module, _ = reconstruct(manager.artifacts, args["definition_id"])
    if not definition.get("safety_analysis_ref"):
        raise OperationError(
            "unsupported",
            "SAFETY_POLICIES_REQUIRED",
            "This definition has no Safety policies",
        )
    history = (
        Store.open(manager.backend(sid, allow_publication=False))
        .current_history()
        .as_dict()
    )
    if args["expected_history"] != history:
        raise OperationError(
            "conflict",
            "HISTORY_MOVED",
            "Current Core history differs from the expected anchor",
        )
    subject.update(manager.subject(sid, definition, history))
    report, ref, _ = acquire_validation(manager, sid, definition, module, history)
    result = {
        "kind": "safety_state_validation",
        "system_id": sid,
        **{
            k: definition[k]
            for k in (
                "definition_id",
                "behavior_hash",
                "schema_hash",
                "policy_set_hash",
                "release",
            )
        },
        "validation_status": report["status"],
        "history_anchor": history,
        "validation_ref": ref,
        "report": report,
    }
    return cast(
        JSON,
        manager.response(
            "safety_state_validation",
            "safety_state_"
            + {
                "Valid": "valid",
                "Invalid": "invalid",
                "Unestablished": "unestablished",
            }[report["status"]],
            subject,
            result,
            "safety_state_validation",
        ),
    )


def required_safety(
    manager: Any, definition: JSON, module: Any, proposal: JSON
) -> list[str]:
    from .policy_v2 import select_grant

    if (
        manager.policy.document["format"] != "behavior-mcp.host-policy.v2"
        or proposal["format"] != "behavior-mcp.authoring.v2"
    ):
        return []
    requirements = select_grant(manager.policy.document, proposal)["required_safety"]
    if not requirements:
        return []
    refs = []
    analysis = (
        manager.artifacts.get(definition["safety_analysis_ref"])
        if definition.get("safety_analysis_ref")
        else None
    )
    for requirement in requirements:
        matched = None
        if analysis is not None and set(requirement["required_policy_ids"]) <= {
            p["id"] for p in proposal["safety"]
        }:
            for ref, document in manager.artifacts.find("safety_assessment_evidence"):
                subject = document["subject"]
                projection = document["report"]
                if (
                    subject.get("workspace_id") != manager.context.workspace_id
                    or any(
                        subject.get(k) != definition[k]
                        for k in (
                            "definition_id",
                            "behavior_hash",
                            "schema_hash",
                            "policy_set_hash",
                            "release",
                        )
                    )
                    or "system_id" in subject
                ):
                    continue
                if (
                    projection["certificate_ref"] is None
                    or projection["assessment_outcome"] != "Certified under assumptions"
                ):
                    continue
                raw = manager.artifacts.get(projection["assessment_ref"])
                certificate = manager.artifacts.get(projection["certificate_ref"])
                validate_assessment(
                    {"assessment": raw, "certificate": certificate},
                    definition,
                    analysis,
                )
                if (
                    any(
                        raw.get(k) != requirement[k]
                        for k in (
                            "analysis_version",
                            "checker_version",
                            "dependency_identity",
                        )
                    )
                    or projection["profile_id"] != requirement["profile_id"]
                ):
                    continue
                if any(
                    raw["obligations"].get(k) != "Passed"
                    for k in requirement["required_obligations"]
                ) or not set(raw["assumptions"]) <= set(
                    requirement["permitted_assumptions"]
                ):
                    continue
                external = {o["id"]: o["status"] for o in raw["external_obligations"]}
                if external != {
                    "initial_validity": "Unestablished",
                    "approved_modules": "Host obligation",
                    "migration_safety": "Excluded",
                }:
                    continue
                matched = ref
                break
        if matched is None:
            raise OperationError(
                "unauthorized",
                "SAFETY_EVIDENCE_REQUIRED",
                "Required complete current-subject Safety evidence is not established",
            )
        refs.append(matched)
    return refs
