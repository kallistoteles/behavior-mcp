"""Finite exact-version dispatch over installed trusted authoring implementations."""

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, cast

from behavior import BehaviorModule

from . import authoring as legacy
from .adapter_versions import v2_0_0, v2_1_0, v2_2_0, v2_3_0
from .schemas import JSON, OperationError, resource, validate

# Only accepted immutable checkpoints are entered here. Never import a client string.
HANDLERS: dict[str, Any] = {
    "2.0.0": v2_0_0,
    "2.1.0": v2_1_0,
    "2.2.0": v2_2_0,
    "2.3.0": v2_3_0,
}


def handler(proposal: JSON) -> Any:
    if (
        proposal.get("format") == "behavior-mcp.authoring.v1"
        and proposal.get("adapter_profile") == "scalar-models.v1"
    ):
        return legacy
    if (
        proposal.get("format") == "behavior-mcp.authoring.v2"
        and proposal.get("adapter_profile") == "structured-models.v2"
    ):
        selected = HANDLERS.get(proposal.get("adapter_version", ""))
        if selected is not None:
            return selected
    raise OperationError(
        "unsupported",
        "ADAPTER_UNAVAILABLE",
        "The exact authoring implementation is unavailable",
    )


def release_identity(proposal: JSON | None = None) -> JSON:
    if proposal is None or handler(proposal) is legacy:
        return legacy.release_identity()
    return dict(
        legacy.release_identity(),
        adapter_profile="structured-models.v2",
        adapter_version=proposal["adapter_version"],
    )


def validate_proposal(proposal: JSON) -> None:
    # Preserve v1's closed-input error contract for malformed/non-authoring documents.
    # Exact unknown v2 implementations remain an explicit unsupported capability.
    if proposal.get("format") != "behavior-mcp.authoring.v2":
        validate("authoring", proposal)
    selected = handler(proposal)
    validate(
        "authoring"
        if selected is legacy
        else "authoring-v2-" + proposal["adapter_version"],
        proposal,
    )
    if selected is not legacy:
        from .source_bounds import check_source_operands

        check_source_operands(proposal)


def construction_context(proposal: JSON) -> JSON:
    selected = handler(proposal)
    if selected is legacy:
        return legacy.construction_context(proposal)
    version = proposal["adapter_version"]
    files = {
        name: "bytes-sha256:"
        + hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in selected.CLOSURE
    }
    schema_name = "authoring-v2-" + version + ".schema.json"
    files["contracts/" + schema_name] = (
        "bytes-sha256:" + hashlib.sha256(resource(schema_name).read_bytes()).hexdigest()
    )
    return {
        "adapter_profile": "structured-models.v2",
        "adapter_version": version,
        "adapter_code_identity": "bytes-sha256:"
        + hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "adapter_files": files,
        "release": release_identity(proposal),
        "fixed_entities": [{"name": "Actor", "fields": {"name": {"type": "string"}}}],
        "trusted_context": {
            "actor": "trusted_host",
            "worker": "trusted_host",
            "now": "utc-unix-milliseconds.v1",
        },
        "composition_order": [m["model_id"] for m in proposal["models"]],
        "action_order": [a["name"] for a in proposal["actions"]],
        "policy_order": [p["id"] for p in proposal["safety"]],
    }


def build(proposal: JSON) -> BehaviorModule:
    validate_proposal(proposal)
    return cast(BehaviorModule, handler(proposal).build(proposal))


capabilities = legacy.capabilities
historical_module = legacy.historical_module


def gaps() -> list[JSON]:
    return [
        *legacy.gaps(),
        {
            "gap_id": "GAP-005",
            "capability": "public symbolic literal equality construction",
            "status": "unsupported_literal_left_equality",
            "evidence_refs": [
                "SEMANTIC_GAPS.md",
                "specs/002-remaining-behavior-models/evidence/tdd/T010.json",
            ],
        },
    ]


def reads(module: BehaviorModule) -> list[JSON]:
    return [
        {"name": r["name"], "params": r["params"]}
        for r in json.loads(module.to_wire_json()).get("reads", [])
    ]


def inventory(
    module: BehaviorModule, *, expanded: bool, proposal: JSON | None = None
) -> list[JSON]:
    if not expanded:
        return capabilities(module)
    factories = {a["name"] for a in (proposal or {}).get("actions", [])}
    wrappers = {
        "mcp_" + s["model_id"] + suffix
        for s in (proposal or {}).get("models", [])
        for suffix in ("_status", "_terminal")
    }
    return [
        dict(
            item,
            kind=kind,
            provenance="host_lifecycle_factory"
            if item["name"] in factories
            else "host_read_wrapper"
            if item["name"] in wrappers
            else "authoritative_model",
        )
        for kind, items in (("action", capabilities(module)), ("read", reads(module)))
        for item in items
    ]


def admit_proposal(artifacts: Any, proposal_id: str, revision: int) -> JSON:
    snapshot = artifacts.proposal(proposal_id, revision)
    proposal = snapshot["proposal"]
    if handler(proposal) is legacy:
        return legacy.admit_proposal(artifacts, proposal_id, revision)
    context = construction_context(proposal)
    if context != snapshot["construction_context"]:
        raise OperationError(
            "unsupported",
            "ADAPTER_CONTEXT_MISMATCH",
            "Exact retained authoring context is unavailable",
        )
    module = build(proposal)
    models = []
    for receipt in module.model_receipts:
        models.append(
            {
                "model_kind": receipt.model_kind,
                "model_semantic_version": receipt.model_semantic_version,
                "lowerer_version": receipt.lowerer_version,
                "model_hash": receipt.model_hash,
                "canonical_document": receipt.model,
                "receipt_ref": artifacts.put("lowering_receipt", receipt.to_dict()),
            }
        )
    analysis = (
        cast(Any, module.safety_analysis).to_dict() if proposal["safety"] else None
    )
    manifest = {
        "kind": "definition",
        "format": "behavior-mcp.definition.v2",
        "definition_id": "definition-" + uuid.uuid4().hex,
        "source": {"proposal_id": proposal_id, "proposal_revision": revision},
        "parent_definition_id": snapshot["parent_definition_id"],
        "behavior_hash": module.behavior_version,
        "schema_hash": module.schema_hash,
        "models": models,
        "inventory_ref": artifacts.put(
            "capability_inventory",
            {"actions": capabilities(module), "reads": reads(module)},
        ),
        "module_ref": artifacts.put("module", {"wire_json": module.to_wire_json()}),
        "construction_context_ref": artifacts.put("construction_context", context),
        "release": release_identity(proposal),
        "policy_set_hash": analysis["policy_set_hash"] if analysis else None,
        "safety_analysis_ref": artifacts.put("safety_analysis", analysis)
        if analysis
        else None,
    }
    return cast(JSON, artifacts.publish_definition(manifest))


def reconstruct(
    artifacts: Any, definition_id: str
) -> tuple[JSON, BehaviorModule, JSON]:
    manifest = artifacts.definition(definition_id)
    if manifest["release"]["adapter_profile"] == "scalar-models.v1":
        return legacy.reconstruct(artifacts, definition_id)
    source = manifest["source"]
    snapshot = artifacts.proposal(source["proposal_id"], source["proposal_revision"])
    context = construction_context(snapshot["proposal"])
    if (
        context != snapshot["construction_context"]
        or context != artifacts.get(manifest["construction_context_ref"])
        or manifest["release"] != context["release"]
    ):
        raise OperationError(
            "unsupported",
            "RECONSTRUCTION_CONTEXT_UNAVAILABLE",
            "Exact retained authoring context is unavailable",
        )
    module = build(snapshot["proposal"])
    historical_module(artifacts, definition_id)
    if (
        module.behavior_version != manifest["behavior_hash"]
        or module.schema_hash != manifest["schema_hash"]
    ):
        raise OperationError(
            "infrastructure",
            "RECONSTRUCTION_IDENTITY_MISMATCH",
            "Reconstructed identities differ",
        )
    receipts = [r.to_dict() for r in module.model_receipts]
    if receipts != [artifacts.get(m["receipt_ref"]) for m in manifest["models"]]:
        raise OperationError(
            "infrastructure",
            "RECONSTRUCTION_RECEIPT_MISMATCH",
            "Reconstructed provenance differs",
        )
    actual = (
        cast(Any, module.safety_analysis).to_dict()
        if snapshot["proposal"]["safety"]
        else None
    )
    if (actual is None) != (manifest["safety_analysis_ref"] is None) or (
        actual is not None
        and (
            actual != artifacts.get(manifest["safety_analysis_ref"])
            or actual["policy_set_hash"] != manifest["policy_set_hash"]
        )
    ):
        raise OperationError(
            "infrastructure",
            "SAFETY_IDENTITY_MISMATCH",
            "Reconstructed Safety provenance differs",
        )
    return manifest, module, snapshot


def discovery() -> list[JSON]:
    import inspect

    from behavior import (
        Approval,
        FieldOwnership,
        LifecycleDependency,
        RequestFlow,
        StateMachine,
        WorkQueue,
    )

    from .dependencies import DependencyError, check_proof_dependencies
    from .schemas import load_schema

    try:
        check_proof_dependencies()
        proof_ready = True
    except DependencyError:
        proof_ready = False
    families = {
        "request_flow": RequestFlow,
        "state_machine": StateMachine,
        "approval": Approval,
        "work_queue": WorkQueue,
        "field_ownership": FieldOwnership,
        "lifecycle_dependency": LifecycleDependency,
    }
    result = []
    for kind, model in families.items():
        versions: list[JSON] = []
        if kind in ("request_flow", "state_machine"):
            versions.append(
                {
                    "adapter_profile": "scalar-models.v1",
                    "adapter_version": "1",
                    "schema_resource": "authoring.schema.json",
                    "authoring_supported": True,
                    "certification_ready": False,
                }
            )
        for version, implementation in HANDLERS.items():
            if kind in implementation.KINDS:
                versions.append(
                    {
                        "adapter_profile": "structured-models.v2",
                        "adapter_version": version,
                        "schema_resource": "authoring-v2-" + version + ".schema.json",
                        "authoring_supported": True,
                        "certification_ready": proof_ready
                        and kind in ("field_ownership", "lifecycle_dependency"),
                    }
                )
        selected = (
            versions[-1]
            if versions
            else {"adapter_profile": "scalar-models.v1", "adapter_version": "1"}
        )
        result.append(
            {
                "model_kind": kind,
                "category": "safety"
                if kind in ("field_ownership", "lifecycle_dependency")
                else "operational",
                "description": inspect.getdoc(model) or kind,
                "upstream_available": True,
                "authoring_supported": bool(versions),
                "schema_origin": "behavior-mcp bounded adapter; not an upstream generic schema",
                "authoring_schema": load_schema(
                    selected["schema_resource"].removesuffix(".schema.json")
                )
                if versions
                else None,
                "adapter_profile": selected["adapter_profile"],
                "adapter_version": selected["adapter_version"],
                "adapter_versions": versions,
                "provenance": "https://github.com/kallistoteles/behavior-ir/tree/v0.14.0/models",
                "limits": [
                    "bounded typed input",
                    "no command emission",
                    "no cross-system references",
                    "Safety analysis alone is uncertified",
                    "field projection requires an explicit State/query entity binding",
                    "entity comparisons require explicit id projections",
                    "literal-left equality is unsupported (GAP-005)",
                ],
            }
        )
    return result


def ecosystem_release() -> JSON:
    return {
        k: v
        for k, v in legacy.release_identity().items()
        if not k.startswith("adapter_")
    }
