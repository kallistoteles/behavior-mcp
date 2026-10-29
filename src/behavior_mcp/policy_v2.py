"""Finite host grant matching over explicit data and admitted public inventories.

This module never evaluates Behavior expressions or establishes logical implication.
"""

import json
from typing import Any

from behavior import BehaviorModule

from .schemas import JSON, OperationError

EXCEPTIONS = {
    "model_kind",
    "model_id",
    "capability_set",
    "typed_effect",
    "state_change",
    "condition_scope",
    "safety_scope",
    "model_parameters",
}


def key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def same(left: Any, right: Any) -> bool:
    return key(left) == key(right)


def member(value: Any, values: list[Any]) -> bool:
    return any(same(value, item) for item in values)


def invalid(message: str) -> None:
    raise OperationError("invalid_input", "HOST_POLICY_INVALID", message)


def validate_policy(document: JSON) -> None:
    from .adapters import HANDLERS

    seen: set[str] = set()
    for grant in document["allowed_adapters"]:
        selector = key([grant["adapter_profile"], grant["adapter_version"]])
        if selector in seen:
            invalid("Duplicate adapter grant")
        seen.add(selector)
        if grant["adapter_profile"] == "scalar-models.v1":
            if grant["adapter_version"] != "1":
                invalid("Unavailable legacy implementation")
            continue
        if grant["adapter_version"] not in HANDLERS:
            raise OperationError(
                "unsupported",
                "ADAPTER_UNAVAILABLE",
                "Delegation names an unavailable exact implementation",
            )
        keyed = {
            "model_parameter_bounds": ("model_id",),
            "field_ownership_bounds": ("id",),
            "allowed_field_refs": ("entity",),
            "state_fields": ("entity", "field"),
            "proposed_time_bounds": ("capability_id", "parameter"),
            "required_guard_roots": ("capability",),
            "required_model_conditions": ("model_id", "slot", "capability_id"),
        }
        for field, fields in keyed.items():
            values = [key([item[f] for f in fields]) for item in grant[field]]
            if len(values) != len(set(values)):
                invalid("Duplicate keyed grant bound")
        for row in grant["model_parameter_bounds"]:
            if (
                row["model_kind"] == "work_queue"
                and row["max_attempts_min"] > row["max_attempts_max"]
            ):
                invalid("Invalid attempts range")
        for row in grant["proposed_time_bounds"]:
            if row["minimum"] > row["maximum"]:
                invalid("Invalid proposed time range")


def select_grant(document: JSON, proposal: JSON) -> JSON:
    from .adapters import release_identity

    release = release_identity(proposal)
    found = [
        g
        for g in document["allowed_adapters"]
        if g["adapter_profile"] == release["adapter_profile"]
        and g["adapter_version"] == release["adapter_version"]
    ]
    if len(found) != 1:
        raise OperationError(
            "unauthorized", "ADAPTER_DENIED", "Exact adapter is outside delegation"
        )
    grant = found[0]
    if grant["adapter_profile"] == "scalar-models.v1":
        # The explicit legacy branch retains its original construction grammar.
        # Its unchanged checker establishes the fields defined by that contract.
        return dict(grant)
    if any(grant.get(k) != v for k, v in release.items()):
        raise OperationError(
            "unauthorized", "RELEASE_DENIED", "Release differs from trusted grant"
        )
    return dict(grant)


def check_candidate(
    document: JSON,
    proposal: JSON,
    module: BehaviorModule,
    *,
    existing: bool,
    exceptions: list[str],
) -> None:
    from .adapters import capabilities, reads

    waived = set(exceptions)
    if not waived <= EXCEPTIONS:
        raise OperationError(
            "unauthorized", "INVALID_EXCEPTION", "Unsupported v2 candidate exception"
        )

    def require(condition: bool, code: str, exception: str | None = None) -> None:
        if not condition and (exception is None or exception not in waived):
            raise OperationError(
                "unauthorized", code, "Candidate exceeds trusted activation bounds"
            )

    grant = select_grant(document, proposal)
    wire = json.loads(module.to_wire_json())
    require(not wire.get("commands"), "EXTERNAL_COMMANDS_UNSUPPORTED")
    require(
        all(a["name"] in grant["allowed_action_names"] for a in capabilities(module))
        and all(r["name"] in grant["allowed_read_names"] for r in reads(module)),
        "CAPABILITIES_DENIED",
        "capability_set",
    )
    for kind in ("entity", "enum", "nominal"):
        require(
            all(
                member(d, grant[f"allowed_{kind}_declarations"])
                for d in proposal["declarations"][
                    "entities" if kind == "entity" else kind + "s"
                ]
            ),
            "DECLARATION_DENIED",
        )
    roots: dict[str, list[JSON]] = {}
    model_conditions: dict[str, Any] = {}
    receipts = {
        r.model.get(
            "approval_id", r.model.get("queue_id", r.model.get("model_id"))
        ): r.model
        for r in module.model_receipts
    }

    def expression(node: Any, scope: JSON) -> Any:
        if not isinstance(node, dict) or "op" not in node:
            return None
        op = node["op"]
        require(
            op in grant["allowed_condition_ops"],
            "CONDITION_OP_DENIED",
            "condition_scope",
        )
        if op == "param":
            return scope.get(node["name"])
        if op == "field":
            ref = expression(node["value"], scope)
            require(
                any(
                    same(row["entity"], ref) and node["name"] in row["fields"]
                    for row in grant["allowed_field_refs"]
                ),
                "FIELD_SCOPE_DENIED",
                "condition_scope",
            )
        elif op == "any":
            require(
                member(node["entity"], grant["allowed_query_entities"]),
                "QUERY_SCOPE_DENIED",
                "condition_scope",
            )
            expression(node["where"], dict(scope, **{node["bind"]: node["entity"]}))
            return None
        elif op == "derived":
            require(
                member(
                    {"model_id": node["model_id"], "function": node["function"]},
                    grant["allowed_derived_functions"],
                ),
                "DERIVED_SCOPE_DENIED",
                "condition_scope",
            )
        for value in node.values():
            if isinstance(value, dict):
                expression(value, scope)
            elif isinstance(value, list):
                for item in value:
                    expression(item, scope)
        return None

    def fragments(value: Any, scope: JSON) -> None:
        if isinstance(value, dict):
            if "op" in value:
                expression(value, scope)
            else:
                for child in value.values():
                    fragments(child, scope)
        elif isinstance(value, list):
            for child in value:
                fragments(child, scope)

    def state(ref: Any, field: str, values: list[str], edges: list[JSON]) -> None:
        rows = [
            r
            for r in grant["state_fields"]
            if same(r["entity"], ref) and r["field"] == field
        ]
        require(
            len(rows) == 1
            and all(v in rows[0]["values"] for v in values)
            and all(member(e, rows[0]["edges"]) for e in edges),
            "STATE_SCOPE_DENIED",
            "state_change",
        )

    for spec in proposal["models"]:
        kind, mid = spec["model_kind"], spec["model_id"]
        require(kind in grant["allowed_model_kinds"], "MODEL_KIND_DENIED", "model_kind")
        require(mid in grant["allowed_model_ids"], "MODEL_ID_DENIED", "model_id")
        scope = {"subject": spec.get("subject"), "actor": "Actor", "worker": "Actor"}
        if kind in ("approval", "work_queue"):
            bounds = [
                r
                for r in grant["model_parameter_bounds"]
                if r["model_id"] == mid and r["model_kind"] == kind
            ]
            require(len(bounds) == 1, "MODEL_PARAMETERS_DENIED", "model_parameters")
            if len(bounds) == 1:
                bound = bounds[0]
                require(
                    same(spec["payload"], bound["payload"]),
                    "PAYLOAD_DENIED",
                    "model_parameters",
                )
                if kind == "approval":
                    normalized = receipts.get(mid)
                    require(normalized is not None, "NORMALIZED_PARAMETERS_UNAVAILABLE")
                    assert normalized is not None
                    require(
                        normalized["approve_threshold"] in bound["approve_thresholds"]
                        and normalized["reject_threshold"]
                        in bound["reject_thresholds"],
                        "THRESHOLD_DENIED",
                        "model_parameters",
                    )
                else:
                    require(
                        spec["time"] == bound["time_nominal"]
                        and bound["max_attempts_min"]
                        <= spec["max_attempts"]
                        <= bound["max_attempts_max"],
                        "QUEUE_PARAMETERS_DENIED",
                        "model_parameters",
                    )
            require(
                grant["allow_new_records"], "CREATION_EFFECT_DENIED", "state_change"
            )
            if kind == "approval":
                for slot in ("open_when", "eligible"):
                    model_conditions[key([mid, slot, None])] = spec[slot]
                for name, decision in spec["decisions"].items():
                    roots[key({"model_id": mid, "local_action_id": name})] = decision[
                        "requires"
                    ]
            else:
                require(
                    grant["allow_existing_record_changes"],
                    "STATE_CHANGE_DENIED",
                    "state_change",
                )
                scope["work"] = {"model_id": mid, "output": "work"}
                for name, cap in spec["capabilities"].items():
                    roots[key({"model_id": mid, "local_action_id": name})] = cap[
                        "requires"
                    ]
                    if "authorization" in cap:
                        model_conditions[key([mid, "authorization", name])] = cap[
                            "authorization"
                        ]
        else:
            ref = spec.get("subject", {"model_id": mid, "output": "request"})
            field = spec.get("state_field", "status")
            scope["subject"] = ref
            scope[mid] = ref
            for transition in spec["transitions"]:
                require(
                    grant["allow_existing_record_changes"],
                    "STATE_CHANGE_DENIED",
                    "state_change",
                )
                state(
                    ref,
                    field,
                    [*transition["from"], transition["to"]],
                    [{"from": v, "to": transition["to"]} for v in transition["from"]],
                )
                roots[key({"model_id": mid, "local_action_id": transition["id"]})] = (
                    transition["requires"]
                )
            for creation in spec.get("creations", []):
                require(
                    grant["allow_new_records"], "CREATION_EFFECT_DENIED", "state_change"
                )
                state(ref, field, [creation["to"]], [])
                roots[key({"model_id": mid, "local_action_id": creation["id"]})] = (
                    creation["requires"]
                )
        fragments(spec, scope)
    enums = {
        e["name"]: {c["name"]: c["value"] for c in e["cases"]}
        for e in proposal["declarations"]["enums"]
    }
    for action in proposal["actions"]:
        require(
            member(action, grant["allowed_action_descriptors"]),
            "ACTION_DESCRIPTOR_DENIED",
            "typed_effect",
        )
        permission = {
            "create_entity": "allow_new_records",
            "set_field": "allow_existing_record_changes",
            "remove_entity": "allow_remove_records",
        }[action["kind"]]
        require(grant[permission], "STATE_CHANGE_DENIED", "state_change")
        if action["kind"] == "set_field":
            state(
                action["entity"],
                action["field"],
                [enums[action["value"]["enum"]][action["value"]["case"]]],
                [],
            )
        roots[key({"action": action["name"]})] = action["requires"]
        fragments(action, {"subject": action["entity"], "parent": action.get("parent")})
    for row in grant["required_guard_roots"]:
        require(
            all(member(r, roots.get(key(row["capability"]), [])) for r in row["roots"]),
            "REQUIRED_GUARD_MISSING",
            "condition_scope",
        )
    for row in grant["required_model_conditions"]:
        require(
            same(
                model_conditions.get(
                    key([row["model_id"], row["slot"], row["capability_id"]])
                ),
                row["expression"],
            ),
            "MODEL_CONDITION_DENIED",
            "condition_scope",
        )
    require(
        all(
            pid in [s["id"] for s in proposal["safety"]]
            for pid in grant["required_policy_ids"]
        ),
        "REQUIRED_POLICY_MISSING",
        "safety_scope",
    )
    for policy in proposal["safety"]:
        if policy["policy_kind"] == "lifecycle_dependency":
            require(
                member(policy, grant["allowed_lifecycle_dependencies"]),
                "LIFECYCLE_SCOPE_DENIED",
                "safety_scope",
            )
            continue
        bounds = [
            b
            for b in grant["field_ownership_bounds"]
            if b["id"] == policy["id"] and same(b["entity"], policy["entity"])
        ]
        require(len(bounds) == 1, "OWNERSHIP_SCOPE_DENIED", "safety_scope")
        if len(bounds) != 1:
            continue
        bound = bounds[0]
        require(
            set(bound["required_protected_fields"]) <= set(policy["writers"]),
            "PROTECTED_FIELD_MISSING",
            "safety_scope",
        )
        for name, selectors in policy["writers"].items():
            require(
                name in bound["writers"]
                and all(member(s, bound["writers"][name]) for s in selectors),
                "WRITER_SCOPE_DENIED",
                "safety_scope",
            )
        for name in ("creators", "removers"):
            require(
                all(member(s, bound[name]) for s in policy[name]),
                "LIFECYCLE_SELECTOR_DENIED",
                "safety_scope",
            )
