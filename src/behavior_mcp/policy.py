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


@dataclass(frozen=True)
class Delegation:
    _encoded: str

    @staticmethod
    def from_document(document: JSON, issuer_id: str) -> "Delegation":
        validate("host-policy", document)
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

    def check_candidate(
        self,
        proposal: JSON,
        module: BehaviorModule,
        *,
        existing: bool,
        exceptions: list[str] | None = None,
    ) -> None:
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
