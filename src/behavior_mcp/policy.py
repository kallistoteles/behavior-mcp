"""Host authority is immutable configuration, never agent model content."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from behavior import BehaviorModule

from .schemas import JSON, OperationError, validate


@dataclass(frozen=True)
class TrustedContext:
    principal_id: str
    workspace_id: str
    actor_id: str
    clock: Callable[[], str]
    semantic_clock: Callable[[], int] | None = None

    def snapshot(self) -> JSON:
        now = self.semantic_clock() if self.semantic_clock is not None else None
        if type(now) is not int or not 0 <= now <= 9007199254740991:
            raise OperationError(
                "infrastructure",
                "TRUSTED_TIME_INVALID",
                "Trusted semantic time is unavailable or invalid",
            )
        return {
            "now": now,
            "audit_time": self.clock(),
            "profile": "utc-unix-milliseconds.v1",
            "actor": self.actor_id,
            "worker": self.actor_id,
        }


@dataclass(frozen=True)
class Delegation:
    _encoded: str

    @staticmethod
    def from_document(document: JSON, issuer_id: str) -> "Delegation":
        expanded = document.get("format") == "behavior-mcp.host-policy.v2"
        validate("host-policy-v2" if expanded else "host-policy", document)
        if expanded:
            from .policy_v2 import validate_policy

            validate_policy(document)
        if document["issuer_id"] != issuer_id:
            raise OperationError(
                "unauthorized",
                "ISSUER_MISMATCH",
                "Issuer differs from trusted administration",
            )
        return Delegation(json.dumps(document, sort_keys=True, separators=(",", ":")))

    @property
    def document(self) -> JSON:
        return dict(json.loads(self._encoded))

    def authorize(
        self, context: TrustedContext, operation: str, system_id: str | None = None
    ) -> None:
        p = self.document
        if (
            context.principal_id != p["principal_id"]
            or context.workspace_id != p["workspace_id"]
            or operation not in p["operations"]
        ):
            raise OperationError(
                "unauthorized",
                "OPERATION_DENIED",
                "Operation is outside trusted delegation",
            )
        scope = p["system_scope"]
        if (
            system_id is not None
            and scope["kind"] == "ids"
            and system_id not in scope["system_ids"]
        ):
            raise OperationError(
                "unauthorized", "SYSTEM_DENIED", "System is outside trusted delegation"
            )

    def authorize_capability(self, capability: str, *, read: bool = False) -> None:
        document = self.document
        allowed = (
            document["runtime_reads" if read else "runtime_actions"]
            if document["format"] == "behavior-mcp.host-policy.v2"
            else ([] if read else document["construction"]["allowed_capability_names"])
        )
        if capability not in allowed:
            raise OperationError(
                "unauthorized",
                "CAPABILITY_DENIED",
                "Capability is outside current runtime authority",
            )

    def check_candidate(
        self,
        proposal: JSON,
        module: BehaviorModule,
        *,
        existing: bool,
        exceptions: list[str] | None = None,
    ) -> None:
        if self.document["format"] == "behavior-mcp.host-policy.v2":
            from .policy_v2 import check_candidate, select_grant

            if proposal["format"] == "behavior-mcp.authoring.v1":
                grant = select_grant(self.document, proposal)
                legacy = {
                    k: v
                    for k, v in self.document.items()
                    if k not in {"allowed_adapters", "runtime_actions", "runtime_reads"}
                }
                legacy.update(
                    format="behavior-mcp.host-policy.v1",
                    construction=grant["construction"],
                    effects=grant["effects"],
                    state=grant["state"],
                )
                Delegation(json.dumps(legacy)).check_candidate(
                    proposal, module, existing=existing, exceptions=exceptions
                )
            else:
                check_candidate(
                    self.document,
                    proposal,
                    module,
                    existing=existing,
                    exceptions=exceptions or [],
                )
            return
        from .authoring import capabilities, release_identity

        p = self.document
        waived = set(exceptions or [])
        if not waived <= {
            "adapter_version",
            "model_kind",
            "model_id",
            "capability_set",
            "typed_effect",
            "state_change",
        }:
            raise OperationError(
                "unauthorized", "INVALID_EXCEPTION", "Unsupported candidate exception"
            )

        def require(condition: bool, code: str, exception: str | None = None) -> None:
            if not condition and (exception is None or exception not in waived):
                raise OperationError(
                    "unauthorized",
                    code,
                    "Candidate exceeds the trusted activation bounds",
                )

        construction = p["construction"]
        effects = p["effects"]
        state = p["state"]
        release = release_identity()
        require(
            all(
                construction[k] == release[k]
                for k in (
                    "adapter_profile",
                    "behavior_version",
                    "core_version",
                    "core_commit",
                    "verifier_version",
                )
            ),
            "RELEASE_DENIED",
        )
        require(
            construction["adapter_version"] == release["adapter_version"],
            "ADAPTER_DENIED",
            "adapter_version",
        )
        wire = json.loads(module.to_wire_json())
        require(not wire.get("commands"), "EXTERNAL_COMMANDS_UNSUPPORTED")
        require(
            all(
                c["name"] in construction["allowed_capability_names"]
                for c in capabilities(module)
            ),
            "CAPABILITIES_DENIED",
            "capability_set",
        )
        enums = {e["name"]: e["cases"] for e in proposal["declarations"]["enums"]}
        entities = {e["name"]: e for e in proposal["declarations"]["entities"]}
        for model in proposal["models"]:
            require(
                model["model_kind"] in construction["allowed_model_kinds"],
                "MODEL_KIND_DENIED",
                "model_kind",
            )
            require(
                model["model_id"] in construction["allowed_model_ids"],
                "MODEL_ID_DENIED",
                "model_id",
            )
            if model["model_kind"] == "request_flow":
                statuses = [case["value"] for case in enums[model["status_enum"]]]
            elif model["model_kind"] == "state_machine":
                descriptor = entities[model["subject_entity"]]["fields"][
                    model["state_field"]
                ]
                if "enum" not in descriptor:
                    raise OperationError(
                        "unsupported",
                        "STATUS_COVERAGE_UNKNOWN",
                        "Status coverage is unavailable",
                    )
                statuses = [case["value"] for case in enums[descriptor["enum"]]]
            else:
                raise OperationError(
                    "unsupported",
                    "CANDIDATE_COVERAGE_UNKNOWN",
                    "Candidate coverage is unavailable",
                )
            require(
                all(v in state["allowed_status_values"] for v in statuses),
                "STATUS_DENIED",
                "state_change",
            )
            for creation in model.get("creations", []):
                require(
                    state["allow_new_records"], "CREATION_EFFECT_DENIED", "state_change"
                )
                for target, source in creation["initializer"].items():
                    form = {
                        "literal": "literal_initializer",
                        "input": "input_initializer",
                        "host_actor": "trusted_actor_initializer",
                    }[source["source"]]
                    require(
                        form in effects["allowed_forms"]
                        and target in effects["initializer_fields"],
                        "INITIALIZER_DENIED",
                        "typed_effect",
                    )
            for transition in model["transitions"]:
                require(
                    state["allow_existing_record_changes"],
                    "STATE_CHANGE_DENIED",
                    "state_change",
                )
                for source in transition["from"]:
                    require(
                        {"from": source, "to": transition["to"]}
                        in state["allowed_status_edges"],
                        "STATUS_EDGE_DENIED",
                        "state_change",
                    )
                for assignment in transition["assignments"]:
                    require(
                        "input_to_field_assignment" in effects["allowed_forms"]
                        and assignment["target_field"] in effects["assignment_fields"],
                        "ASSIGNMENT_DENIED",
                        "typed_effect",
                    )
