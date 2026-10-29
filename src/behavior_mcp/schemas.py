"""Closed host syntax, evidence projections and distinct operation failures."""

import copy
import importlib.metadata
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from behavior import BehaviorError, CommitRefused, ModelBuildError, StateConflict
from jsonschema import Draft202012Validator

JSON = dict[str, Any]


class OperationError(Exception):
    def __init__(
        self,
        category: str,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        uncertain: bool = False,
        result: JSON | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.code = code
        self.retryable = retryable
        self.uncertain = uncertain
        self.result = result or {}


def resource(name: str) -> Path:
    base = Path(
        str(
            importlib.metadata.distribution("behavior-mcp").locate_file(
                "behavior_mcp/contracts"
            )
        )
    )
    if Path(name).name != name:
        raise ValueError("Only packaged resources may be loaded")
    return base / name


_SCHEMA_NAMES = (
    "activation-approval",
    "activation-approval-v2",
    "authoring",
    "authoring-v2",
    "authoring-v2-2.0.0",
    "authoring-v2-2.1.0",
    "authoring-v2-2.2.0",
    "authoring-v2-2.3.0",
    "expanded-result",
    "host-policy",
    "host-policy-v2",
    "result",
    "tool-additions",
    "tool-request",
)


@lru_cache(maxsize=32)
def _schema(name: str) -> JSON:
    if name not in _SCHEMA_NAMES:
        raise ValueError("Unknown schema")
    document: JSON = json.loads(resource(name + ".schema.json").read_text())

    def check(value: Any) -> None:
        if isinstance(value, dict):
            if "$ref" in value and not value["$ref"].startswith("#/"):
                raise ValueError("Remote schema references are forbidden")
            for v in value.values():
                check(v)
        elif isinstance(value, list):
            for v in value:
                check(v)

    check(document)
    return document


def load_schema(name: str) -> JSON:
    return copy.deepcopy(_schema(name))


def audit_schemas() -> tuple[str, ...]:
    """Meta-validate every fixed packaged contract in the shared quality gate.

    Runtime validates untrusted data against these trusted constants. Repeating
    the schema-as-data audit in every crash/read/proof worker adds no input
    validation and can exhaust the installed acceptance deadline.
    """
    for name in _SCHEMA_NAMES:
        Draft202012Validator.check_schema(_schema(name))
    return _SCHEMA_NAMES


def prune_schema(document: JSON) -> JSON:
    """Keep the complete transitive closure of local definitions in a host schema."""
    root = copy.deepcopy(document)
    definitions = root.pop("$defs", {})

    def references(value: Any) -> set[str]:
        if isinstance(value, list):
            return set().union(*(references(v) for v in value))
        if not isinstance(value, dict):
            return set()
        result = set()
        if "$ref" in value:
            ref = value["$ref"]
            if not ref.startswith("#/$defs/"):
                raise ValueError("Only fixed local contract references are supported")
            result.add(ref.split("/")[2])
        return result.union(*(references(v) for v in value.values()))

    pending = references(root)
    retained = set()
    while pending:
        name = pending.pop()
        if name in retained:
            continue
        retained.add(name)
        pending.update(references(definitions[name]) - retained)
    if retained:
        root["$defs"] = {k: v for k, v in definitions.items() if k in retained}
    return root


@lru_cache(maxsize=32)
def _stage_result_schema(stage: str) -> JSON:
    variants = []
    for name in ("result", "expanded-result"):
        schema = load_schema(name)
        if not Draft202012Validator(schema["properties"]["stage"]).is_valid(stage):
            continue
        schema["$id"] += ":stage:" + stage
        schema["properties"]["stage"] = {"const": stage}
        conditions = []
        for condition in schema["allOf"]:
            predicate = condition.get("if", {}).get("properties", {}).get("stage")
            if predicate is not None and not Draft202012Validator(predicate).is_valid(
                stage
            ):
                continue
            choices = condition.get("then", {}).get("oneOf")
            if choices and all("stage" in v.get("properties", {}) for v in choices):
                selected = [
                    v
                    for v in choices
                    if Draft202012Validator(v["properties"]["stage"]).is_valid(stage)
                ]
                if selected:
                    condition["then"]["oneOf"] = selected
                else:
                    condition["then"] = False
            conditions.append(condition)
        schema["allOf"] = conditions
        variants.append(prune_schema(schema))
    if not variants:
        raise ValueError("Unknown fixed tool stage")
    return {"type": "object", "anyOf": variants}


def stage_result_schema(stage: str) -> JSON:
    """Advertise the unchanged versioned contracts restricted to a fixed tool stage."""
    return copy.deepcopy(_stage_result_schema(stage))


def validate(name: str, value: Any) -> None:
    errors = list(Draft202012Validator(_schema(name)).iter_errors(value))
    if errors:
        # Do not echo untrusted input values or schema-validator reprs.
        raise OperationError(
            "invalid_input",
            "SCHEMA_INVALID",
            "Input does not match the declared schema",
        )


def validate_input(name: str, arguments: JSON) -> None:
    if (
        name
        in {
            "capability_read",
            "definition_safety_certify",
            "definition_safety_verify_evidence",
            "state_validate_safety",
        }
        or (name == "transition_evaluate" and "context_proposals" in arguments)
        or (name == "definition_get" and "evidence_ref" in arguments)
    ):
        validate("tool-additions", {"name": name, "arguments": arguments})
    else:
        validate("tool-request", {"name": name, "arguments": arguments})
    if name == "definition_propose":
        from .adapters import validate_proposal

        validate_proposal(arguments["proposal"])


def validate_output(value: JSON, *, expanded: bool | None = None) -> None:
    if expanded is None:
        # These are server-created subjects and retained snapshots, never a fallback on failure.
        result = value["result"]
        expanded = (
            value["stage"]
            in {"safety_certification", "safety_checking", "safety_state_validation"}
            or value["subject"].get("release", {}).get("adapter_profile")
            == "structured-models.v2"
            or result.get("proposal", {}).get("format") == "behavior-mcp.authoring.v2"
            or (
                result.get("kind") == "models"
                and any("category" in m for m in result["models"])
            )
            or "policy_set_hash" in (result.get("observed_current_deployment") or {})
            or any(
                "policy_set_hash" in (item.get("active") or {})
                for item in result.get("systems", [])
            )
        )
    try:
        validate("expanded-result" if expanded else "result", value)
    except OperationError:
        raise OperationError(
            "infrastructure",
            "RESULT_SCHEMA_INVALID",
            "Server output does not match the declared result schema",
        ) from None
    subject = value["subject"]
    result = value["result"]

    def check(obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        for key in (
            "workspace_id",
            "system_id",
            "operation_id",
            "definition_id",
            "behavior_hash",
            "schema_hash",
            "policy_set_hash",
            "history_anchor",
            "release",
        ):
            if key in obj and key in subject and obj[key] != subject[key]:
                raise OperationError(
                    "infrastructure",
                    "EVIDENCE_MISMATCH",
                    "Result differs from its authoritative subject",
                )
        # A later deployment and historical source/artifact identities are intentionally distinct.
        for key in ("receipt", "definition"):
            if key in obj:
                check(obj[key])

    check(result)
    for evidence in value["evidence"]:
        check(evidence["subject"])
        if "release" in subject and evidence["release"] != subject["release"]:
            raise OperationError(
                "infrastructure", "EVIDENCE_MISMATCH", "Evidence release differs"
            )
    if result.get("kind") == "verification":
        validate_verification(result, subject)
    if result.get("kind") == "proposal":
        for key in ("proposal_id", "proposal_revision"):
            if result[key] != subject.get(key):
                raise OperationError(
                    "infrastructure", "EVIDENCE_MISMATCH", "Proposal source differs"
                )
    if result.get("kind") == "validation":
        source = result["definition"]["source"]
        if any(
            source[k] != subject.get(k) for k in ("proposal_id", "proposal_revision")
        ):
            raise OperationError(
                "infrastructure", "EVIDENCE_MISMATCH", "Validation source differs"
            )


def validate_verification(report: JSON, subject: JSON) -> None:
    """Bind a projection to the retained public report, never infer proof from shape."""
    raw = report["report"]
    if (
        raw.get("behavior_version") != subject["behavior_hash"]
        or raw.get("hash") != report["report_identity"]
        or raw.get("result") != report["upstream_result"]
        or report["release"] != subject["release"]
        or any(
            report[key] != raw.get(key, [])
            for key in ("checks", "obligations", "assumptions")
        )
        or (
            report["verification_status"] == "verified"
            and raw.get("result") != "verified"
        )
    ):
        raise OperationError(
            "infrastructure",
            "EVIDENCE_MISMATCH",
            "Verification differs from its exact public subject or report",
        )


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if re.search(r"password|secret|credential|private.?key|token", k, re.I)
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(
            r"(?i)(token|password|secret|credential)=([^\s,;]+)",
            r"\1=[REDACTED]",
            value,
        )
    return value


def completed(
    stage: str,
    outcome: str,
    subject: JSON,
    result: JSON,
    evidence: list[JSON] | None = None,
) -> JSON:
    envelope = {
        "format": "behavior-mcp.result.v1",
        "request_status": "completed",
        "stage": stage,
        "outcome": outcome,
        "subject": subject,
        "result": result,
        "evidence": evidence or [],
        "error": None,
    }
    validate_output(envelope)
    return envelope


def failure(
    stage: str, subject: JSON, error: Exception, *, mutation_attempted: bool = False
) -> JSON:
    if isinstance(error, OperationError):
        e = error
    elif isinstance(error, StateConflict):
        e = OperationError(
            "conflict",
            "STATE_CONFLICT",
            "Core state moved; evaluate a new operation",
            retryable=True,
        )
    elif isinstance(error, CommitRefused):
        e = OperationError(
            "infrastructure" if error.code == "BACKEND_ERROR" else "semantic_refusal",
            error.code,
            "Core backend outcome is uncertain"
            if error.code == "BACKEND_ERROR"
            else "Core refused the operation",
            uncertain=error.code == "BACKEND_ERROR"
            and stage in {"system_creation", "activation", "commit", "recovery"}
            and "system_id" in subject
            and "operation_id" in subject,
            retryable=error.code == "BACKEND_ERROR",
            result={"diagnostics": [{"code": error.code}]},
        )
    elif isinstance(error, ModelBuildError):
        e = OperationError(
            "model_invalid",
            "MODEL_INVALID",
            "Public model authoring refused the definition",
            result={"diagnostics": redact(error.errors)},
        )
    elif isinstance(error, BehaviorError):
        e = OperationError(
            "model_invalid",
            "BEHAVIOR_INVALID",
            "Public Behavior interface refused the definition",
        )
    else:
        e = OperationError(
            "infrastructure",
            "INFRASTRUCTURE_FAILURE",
            "Operation could not be completed",
            retryable=True,
        )
    uncertain = e.uncertain or (
        e.category == "infrastructure"
        and (stage in {"system_creation", "activation", "commit"} or mutation_attempted)
        and "system_id" in subject
        and "operation_id" in subject
    )
    status = (
        "unknown"
        if uncertain
        else "failed"
        if e.category == "infrastructure"
        else "refused"
    )
    outcome = (
        "outcome_unknown"
        if uncertain
        else "timeout"
        if status == "failed" and e.code.endswith("TIMEOUT")
        else "infrastructure_failure"
        if status == "failed"
        else e.category
    )
    envelope = {
        "format": "behavior-mcp.result.v1",
        "request_status": status,
        "stage": stage,
        "outcome": outcome,
        "subject": subject,
        "result": redact(e.result),
        "evidence": [],
        "error": {
            "category": e.category,
            "code": e.code,
            "message": redact(str(e)),
            "retryable": e.retryable,
            "operation_may_have_committed": uncertain,
        },
    }
    validate_output(envelope)
    return envelope


if __name__ == "__main__":
    print(f"Packaged contract meta-validation: {len(audit_schemas())} PASS")
