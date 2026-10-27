"""Bounded data adapters. Public Behavior constructors own typing and lowering."""

import copy
import hashlib
import json
import uuid
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from behavior import BehaviorModule, Id, RequestFlow, StateMachine, entity, field, set_

from .schemas import JSON, OperationError, load_schema, validate

if TYPE_CHECKING:
    from .artifacts import ArtifactStore


ADAPTER_VERSION = "1"


def release_identity() -> JSON:
    return {
        "behavior_version": "0.14.0",
        "behavior_commit": "1cba9e16ff73f927ae08e70a7bc74a6ca52355e4",
        "core_version": "0.15.0",
        "core_commit": "6b93898a9375113f7a8946f23ab5535319b6f5d6",
        "verifier_version": "0.10.0",
        "adapter_profile": "scalar-models.v1",
        "adapter_version": ADAPTER_VERSION,
    }


def construction_context(proposal: JSON) -> JSON:
    return {
        "adapter_profile": "scalar-models.v1",
        "adapter_version": ADAPTER_VERSION,
        "adapter_code_identity": "bytes-sha256:"
        + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "release": release_identity(),
        "fixed_entities": [{"name": "Actor", "fields": {"name": {"type": "string"}}}],
        "trusted_context": {"actor": {"entity": "Actor", "source": "trusted_host"}},
        "composition_order": [m["model_id"] for m in proposal["models"]],
    }


def _initializer(creation: JSON) -> Callable[..., JSON]:
    names = ["request_id", *sorted(creation["inputs"]), "actor"]
    sources = copy.deepcopy(creation["initializer"])

    def initialize(*symbols: Any) -> JSON:
        supplied = dict(zip(names, symbols, strict=True))
        result: JSON = {}
        for target, source in sources.items():
            if source["source"] == "literal":
                result[target] = source["value"]
            elif source["source"] == "host_actor":
                result[target] = supplied["actor"]
            else:
                result[target] = supplied[source["name"]]
        return result

    return initialize


def _transfers(transition: JSON) -> list[Callable[..., None]]:
    names = sorted(transition["inputs"])
    assignments = copy.deepcopy(transition["assignments"])

    def transfer(subject: Any, *symbols: Any) -> None:
        supplied = dict(zip(names, symbols, strict=True))
        for assignment in assignments:
            set_(
                getattr(subject, assignment["target_field"]),
                supplied[assignment["input"]],
            )

    return [transfer] if assignments else []


def build(proposal: JSON) -> BehaviorModule:
    validate("authoring", proposal)
    enum_specs = proposal["declarations"]["enums"]
    entity_specs = proposal["declarations"]["entities"]
    names = (
        [spec["name"] for spec in enum_specs]
        + [spec["name"] for spec in entity_specs]
        + ["Actor"]
    )
    if len(names) != len(set(names)):
        raise OperationError(
            "invalid_input",
            "AMBIGUOUS_DECLARATION",
            "Declaration names must be unambiguous in this adapter",
        )
    try:
        enums: dict[str, Any] = {
            spec["name"]: Enum(
                spec["name"], [(case["name"], case["value"]) for case in spec["cases"]]
            )
            for spec in enum_specs
        }
    except (TypeError, ValueError):
        raise OperationError(
            "model_invalid",
            "ENUM_DECLARATION_INVALID",
            "Public enum construction refused the declaration",
        ) from None
    actor = entity(type("Actor", (), {"name": field(str)}))
    entities = [actor]
    types_by_name = {"Actor": actor}
    try:
        for spec in entity_specs:
            fields = {
                name: field(
                    str
                    if descriptor.get("type") == "string"
                    else enums[descriptor["enum"]]
                )
                for name, descriptor in spec["fields"].items()
            }
            declared = entity(type(spec["name"], (), fields))
            entities.append(declared)
            types_by_name[spec["name"]] = declared
        models: list[Any] = [None] * len(proposal["models"])
        # Public generated request_entity handles are available before composing the module.
        # Keep every model/declaration in the final input; Core diagnoses duplicate ownership.
        for index, spec in enumerate(proposal["models"]):
            if spec["model_kind"] != "request_flow":
                continue
            flow = RequestFlow(
                spec["model_id"],
                actor=actor,
                status=enums[spec["status_enum"]],
                payload={n: str for n in spec["payload"]},
            )
            for creation in spec["creations"]:
                flow.create(
                    creation["id"],
                    to=creation["to"],
                    inputs={n: str for n in creation["inputs"]},
                    context={"actor": Id[actor]},
                    values=_initializer(creation),
                )
            models[index] = flow
            types_by_name[flow.request_entity.__name__] = flow.request_entity
        for index, spec in enumerate(proposal["models"]):
            if spec["model_kind"] == "state_machine":
                models[index] = StateMachine(
                    spec["model_id"],
                    subject=types_by_name[spec["subject_entity"]],
                    state_field=spec["state_field"],
                    subject_param=spec["subject_param"],
                    entry_states=spec["entry_states"],
                )
            for transition in spec["transitions"]:
                models[index].transition(
                    transition["id"],
                    from_=transition["from"],
                    to=transition["to"],
                    inputs={n: str for n in transition["inputs"]},
                    effects=_transfers(transition),
                )
        return BehaviorModule(
            entities=entities, enums=list(enums.values()), models=models
        )
    except KeyError:
        raise OperationError(
            "model_invalid",
            "UNRESOLVED_AUTHORING_REFERENCE",
            "An authoring reference cannot be resolved through the supported adapter",
        ) from None


def capabilities(module: BehaviorModule) -> list[JSON]:
    # Inspection of admitted public output; no semantic reconstruction or guessed action names.
    return [
        {"name": a["name"], "params": a["params"]}
        for a in json.loads(module.to_wire_json())["actions"]
    ]


def admit_proposal(artifacts: "ArtifactStore", proposal_id: str, revision: int) -> JSON:
    snapshot = artifacts.proposal(proposal_id, revision)
    context = snapshot["construction_context"]
    if context != construction_context(snapshot["proposal"]):
        raise OperationError(
            "unsupported",
            "ADAPTER_CONTEXT_MISMATCH",
            "Stored authoring context is unavailable under this exact adapter",
        )
    module = build(snapshot["proposal"])
    models = []
    for receipt in module.model_receipts:
        receipt_ref = artifacts.put("lowering_receipt", receipt.to_dict())
        models.append(
            {
                "model_kind": receipt.model_kind,
                "model_semantic_version": receipt.model_semantic_version,
                "lowerer_version": receipt.lowerer_version,
                "model_hash": receipt.model_hash,
                "canonical_document": receipt.model,
                "receipt_ref": receipt_ref,
            }
        )
    manifest = {
        "kind": "definition",
        "definition_id": "definition-" + uuid.uuid4().hex,
        "source": {"proposal_id": proposal_id, "proposal_revision": revision},
        "parent_definition_id": snapshot["parent_definition_id"],
        "behavior_hash": module.behavior_version,
        "schema_hash": module.schema_hash,
        "models": models,
        "module_ref": artifacts.put("module", {"wire_json": module.to_wire_json()}),
        "construction_context_ref": artifacts.put("construction_context", context),
        "release": release_identity(),
    }
    return artifacts.publish_definition(manifest)


def discovery() -> list[JSON]:
    import inspect

    from behavior import Approval, WorkQueue

    classes = {
        "request_flow": RequestFlow,
        "state_machine": StateMachine,
        "approval": Approval,
        "work_queue": WorkQueue,
    }
    schema = load_schema("authoring")
    return [
        {
            "model_kind": kind,
            "description": inspect.getdoc(classes[kind]),
            "upstream_available": True,
            "authoring_supported": kind in {"request_flow", "state_machine"},
            "schema_origin": "behavior-mcp bounded adapter; not an upstream generic schema",
            "authoring_schema": schema
            if kind in {"request_flow", "state_machine"}
            else None,
            "adapter_profile": "scalar-models.v1",
            "adapter_version": ADAPTER_VERSION,
            "provenance": "https://github.com/kallistoteles/behavior-ir/tree/v0.14.0/models",
            "limits": [
                "string fields",
                "explicit typed transfers",
                "no arbitrary expressions",
                "no command emission",
                "no cross-system references",
            ],
        }
        for kind in ("request_flow", "state_machine", "approval", "work_queue")
    ]


def gaps() -> list[JSON]:
    return [
        {
            "gap_id": f"GAP-{i:03}",
            "capability": capability,
            "status": (
                "unsupported_canonical_only",
                "bounded_host_schema_only",
                "managed_external_provenance",
                "unsupported_schema_migration",
            )[i - 1],
            "evidence_refs": [
                "SEMANTIC_GAPS.md",
                "specs/001-agent-native-systems/evidence/public_api_results.json",
            ],
        }
        for i, capability in enumerate(
            [
                "canonical-only reconstruction",
                "generic model configuration schemas",
                "Wire import lowering provenance",
                "governed Python prepared migration",
            ],
            1,
        )
    ]


def reconstruct(
    artifacts: "ArtifactStore", definition_id: str
) -> tuple[JSON, BehaviorModule, JSON]:
    manifest = artifacts.definition(definition_id)
    try:
        source = manifest["source"]
        snapshot = artifacts.proposal(
            source["proposal_id"], source["proposal_revision"]
        )
        context = artifacts.get(manifest["construction_context_ref"])
        if (
            context != snapshot["construction_context"]
            or context != construction_context(snapshot["proposal"])
            or manifest["release"] != release_identity()
        ):
            raise OperationError(
                "unsupported",
                "RECONSTRUCTION_CONTEXT_UNAVAILABLE",
                "Exact retained authoring context is unavailable",
            )
        module = build(snapshot["proposal"])
        imported = BehaviorModule.from_wire_json(
            artifacts.get(manifest["module_ref"])["wire_json"]
        )
        if any(
            m.behavior_version != manifest["behavior_hash"]
            or m.schema_hash != manifest["schema_hash"]
            for m in (module, imported)
        ):
            raise OperationError(
                "infrastructure",
                "RECONSTRUCTION_IDENTITY_MISMATCH",
                "Stored and rebuilt public identities disagree",
            )
        receipts = {r.model_hash: r.to_dict() for r in module.model_receipts}
        if len(receipts) != len(manifest["models"]):
            raise OperationError(
                "infrastructure",
                "RECONSTRUCTION_RECEIPT_MISMATCH",
                "Stored receipt membership differs",
            )
        for model in manifest["models"]:
            actual = receipts.get(model["model_hash"])
            if (
                actual is None
                or any(
                    model[k] != actual[k]
                    for k in (
                        "model_kind",
                        "model_semantic_version",
                        "lowerer_version",
                        "model_hash",
                    )
                )
                or actual != artifacts.get(model["receipt_ref"])
                or actual["model"] != model["canonical_document"]
            ):
                raise OperationError(
                    "infrastructure",
                    "RECONSTRUCTION_RECEIPT_MISMATCH",
                    "Stored lowering provenance differs from public reconstruction",
                )
        return manifest, module, snapshot
    except OperationError as error:
        if error.category == "invalid_input":
            raise OperationError(
                "infrastructure",
                "HISTORICAL_ARTIFACT_UNAVAILABLE",
                "Required retained artifact is unavailable",
            ) from None
        raise


def historical_module(
    artifacts: "ArtifactStore", definition_id: str
) -> tuple[JSON, BehaviorModule]:
    """Admit retained Wire through Core; retain rather than reconstruct model provenance."""
    manifest = artifacts.definition(definition_id)
    try:
        actual_release = release_identity()
        if any(
            manifest["release"][k] != actual_release[k]
            for k in (
                "behavior_version",
                "behavior_commit",
                "core_version",
                "core_commit",
                "verifier_version",
            )
        ):
            raise OperationError(
                "unsupported",
                "HISTORICAL_RELEASE_UNAVAILABLE",
                "Exact historical Behavior/Core release is unavailable",
            )
        artifacts.proposal(
            manifest["source"]["proposal_id"], manifest["source"]["proposal_revision"]
        )
        artifacts.get(manifest["construction_context_ref"])
        module = BehaviorModule.from_wire_json(
            artifacts.get(manifest["module_ref"])["wire_json"]
        )
        if (
            module.behavior_version != manifest["behavior_hash"]
            or module.schema_hash != manifest["schema_hash"]
        ):
            raise OperationError(
                "infrastructure",
                "HISTORICAL_IDENTITY_MISMATCH",
                "Public Wire admission differs from retained identities",
            )
        for model in manifest["models"]:
            receipt = artifacts.get(model["receipt_ref"])
            if (
                any(
                    receipt[k] != model[k]
                    for k in (
                        "model_kind",
                        "model_semantic_version",
                        "lowerer_version",
                        "model_hash",
                    )
                )
                or receipt["model"] != model["canonical_document"]
            ):
                raise OperationError(
                    "infrastructure",
                    "HISTORICAL_PROVENANCE_MISMATCH",
                    "Retained lowering provenance is inconsistent",
                )
        return manifest, module
    except OperationError as error:
        if error.category == "invalid_input":
            raise OperationError(
                "infrastructure",
                "HISTORICAL_ARTIFACT_UNAVAILABLE",
                "Original historical artifacts are unavailable",
            ) from None
        raise
