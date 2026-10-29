"""Draft bounded symbolic construction; the public Behavior API owns all meaning."""

from collections.abc import Callable
from enum import Enum
from typing import Any

from behavior import (
    Id,
    Input,
    Ref,
    action,
    and_,
    any_,
    create,
    not_,
    or_,
    remove,
    requires,
    select,
    set_,
)

from .schemas import JSON, OperationError


class Fragments:
    def __init__(
        self,
        entities: dict[str, Any],
        enums: dict[str, Any],
        nominals: dict[str, Any],
        models: dict[str, Any],
    ) -> None:
        self.entities, self.enums, self.nominals, self.models = (
            entities,
            enums,
            nominals,
            models,
        )

    def entity(self, ref: Any) -> Any:
        if isinstance(ref, str):
            return self.entities[ref]
        model = self.models[ref["model_id"]]
        return getattr(
            model,
            {
                "request": "request_entity",
                "decision": "decision_entity",
                "work": "work_entity",
            }[ref["output"]],
        )

    def type(self, descriptor: JSON) -> Any:
        kind = descriptor["kind"]
        if kind in ("string", "int", "bool"):
            return {"string": str, "int": int, "bool": bool}[kind]
        if kind == "enum":
            return self.enums[descriptor["name"]]
        if kind == "nominal":
            return self.nominals[descriptor["name"]]
        if kind in ("id", "ref"):
            return (Id if kind == "id" else Ref)[self.entity(descriptor["entity"])]
        raise OperationError(
            "invalid_input", "TYPE_UNSUPPORTED", "Unknown typed descriptor"
        )

    def expression(self, node: JSON, scope: JSON) -> Any:
        op = node["op"]
        if op == "literal":
            return node["value"]
        if op == "enum":
            return self.enums[node["enum"]][node["case"]]
        if op == "param":
            return scope[node["name"]]
        if op == "field":
            return getattr(self.expression(node["value"], scope), node["name"])
        if op == "eq":
            left = self.expression(node["left"], scope)
            if isinstance(left, (bool, int, str, Enum)):
                raise OperationError(
                    "unsupported",
                    "LITERAL_EQUALITY_UNSUPPORTED",
                    "The public profile requires a symbolic left operand; Python equality cannot define Behavior semantics",
                )
            return left == self.expression(node["right"], scope)
        if op in ("and", "or"):
            return (and_ if op == "and" else or_)(
                *[self.expression(n, scope) for n in node["args"]]
            )
        if op == "not":
            return not_(self.expression(node["value"], scope))
        if op == "in":
            return self.expression(node["value"], scope).in_(
                [self.expression(n, scope) for n in node["members"]]
            )
        if op == "any":
            return any_(
                select(self.entity(node["entity"])),
                lambda value: self.expression(
                    node["where"], dict(scope, **{node["bind"]: value})
                ),
            )
        if op == "derived":
            if node["function"] not in (
                "approve_count",
                "reject_count",
                "approved",
                "rejected",
                "pending",
                "terminal",
            ):
                raise OperationError(
                    "unsupported", "DERIVED_UNSUPPORTED", "Unknown derived handle"
                )
            return getattr(self.models[node["model_id"]], node["function"])(
                self.expression(node["subject"], scope)
            )
        raise OperationError(
            "invalid_input", "EXPRESSION_UNSUPPORTED", "Unknown expression node"
        )

    def callback(self, names: list[str], node: JSON) -> Callable[..., Any]:
        def trace(*values: Any) -> Any:
            return self.expression(node, dict(zip(names, values, strict=True)))

        return trace

    def values(self, names: list[str], nodes: JSON) -> Callable[..., JSON]:
        def trace(*values: Any) -> JSON:
            scope = dict(zip(names, values, strict=True))
            return {name: self.expression(node, scope) for name, node in nodes.items()}

        return trace

    def effects(
        self, names: list[str], transfers: list[JSON]
    ) -> list[Callable[..., None]]:
        def trace(*values: Any) -> None:
            scope = dict(zip(names, values, strict=True))
            for item in transfers:
                set_(
                    self.expression(item["target"], scope),
                    self.expression(item["value"], scope),
                )

        return [trace] if transfers else []

    def lifecycle(self, spec: JSON) -> Any:
        entity_type = self.entity(spec["entity"])
        parent_type = self.entity(spec["parent"]) if "parent" in spec else None

        def execute(scope: JSON) -> None:
            for root in spec["requires"]:
                requires(self.expression(root, scope))
            if spec["kind"] == "create_entity":
                create(
                    entity_type,
                    id=scope["new_id"],
                    **{
                        name: self.expression(value, scope)
                        for name, value in spec["values"].items()
                    },
                )
            elif spec["kind"] == "set_field":
                set_(
                    getattr(scope["subject"], spec["field"]),
                    self.expression(spec["value"], scope),
                )
            elif spec["kind"] == "remove_entity":
                remove(scope["subject"])
            else:
                raise OperationError(
                    "unsupported",
                    "ACTION_FACTORY_UNSUPPORTED",
                    "Unknown action factory",
                )

        invoke: Any
        if spec["kind"] == "create_entity":
            if parent_type is None:

                def create_plain(*, new_id: Any) -> None:
                    execute({"new_id": new_id})

                create_plain.__annotations__ = {"new_id": Input[Id[entity_type]]}
                invoke = create_plain
            else:

                def create_related(parent: Any, *, new_id: Any) -> None:
                    execute({"parent": parent, "new_id": new_id})

                create_related.__annotations__ = {
                    "parent": parent_type,
                    "new_id": Input[Id[entity_type]],
                }
                invoke = create_related
        elif parent_type is None:

            def change_plain(subject: Any) -> None:
                execute({"subject": subject})

            change_plain.__annotations__ = {"subject": entity_type}
            invoke = change_plain
        else:

            def change_related(subject: Any, parent: Any) -> None:
                execute({"subject": subject, "parent": parent})

            change_related.__annotations__ = {
                "subject": entity_type,
                "parent": parent_type,
            }
            invoke = change_related
        invoke.__name__ = spec["name"]
        return action(invoke)
