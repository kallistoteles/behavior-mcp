"""Operational support bounds for structured authoring receivers.

Resolve only the profile's lexical State/query bindings. Never evaluate an
expression, inspect private SDK attributes, infer types or lower an alternative
meaning. Core still admits and type-checks every supported expression.
"""

from typing import Any

from .schemas import JSON, OperationError


def check_source_operands(proposal: JSON) -> None:
    def unsupported(code: str, message: str) -> None:
        raise OperationError("unsupported", code, message)

    def walk(value: Any, entities: set[str]) -> None:
        if isinstance(value, list):
            for child in value:
                walk(child, entities)
        elif isinstance(value, dict):
            op = value.get("op")
            if op == "any":
                walk(value["where"], entities | {value["bind"]})
                return
            if op == "field":
                receiver = value["value"]
                if (
                    receiver.get("op") != "param"
                    or receiver.get("name") not in entities
                ):
                    unsupported(
                        "FIELD_RECEIVER_UNSUPPORTED",
                        "Field projection requires an explicit State or query entity binding; scalar and reference attributes are not public entity projections",
                    )
            if op == "eq":
                left = value["left"]
                if left["op"] in {"literal", "enum"}:
                    unsupported(
                        "LITERAL_EQUALITY_UNSUPPORTED",
                        "A symbolic left operand is required; Python equality cannot define Behavior semantics",
                    )
                if left["op"] == "param" and left["name"] in entities:
                    unsupported(
                        "ENTITY_EQUALITY_UNSUPPORTED",
                        "Compare explicit entity id projections; Python entity-object identity cannot define Behavior semantics",
                    )
            for child in value.values():
                walk(child, entities)

    for action in proposal["actions"]:
        bound = {"parent"} if "parent" in action else set()
        if action["kind"] != "create_entity":
            bound.add("subject")
        walk(action, bound)
    for model in proposal["models"]:
        kind = model["model_kind"]
        if kind == "approval":
            walk(model["open_when"], {"subject"})
            walk(model["eligible"], {"subject"})
            walk(model["decisions"], {"subject"})
        elif kind == "work_queue":
            for name, configuration in model["capabilities"].items():
                walk(configuration, set() if name == "enqueue" else {"work"})
        else:
            for creation in model.get("creations", []):
                walk(creation, set())
            for transition in model["transitions"]:
                bound = {"subject" if kind == "state_machine" else model["model_id"]}
                if "parent" in transition:
                    bound.add("parent")
                walk(transition, bound)
