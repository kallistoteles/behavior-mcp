"""Immutable structured-models.v2 release 2.0.0; all semantics remain public Behavior."""

from enum import Enum
from typing import Any

from behavior import (
    Approval,
    BehaviorModule,
    Id,
    RequestFlow,
    StateMachine,
    entity,
    field,
    nominal,
    project,
    read,
)

from ..schemas import JSON, OperationError, validate
from .fragments_2_0_0 import Fragments


def build(proposal: JSON) -> BehaviorModule:
    validate("authoring-v2-2.0.0", proposal)
    count = 0
    pending: list[Any] = [proposal]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            count += "op" in node
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    if count > 4096:
        raise OperationError(
            "invalid_input", "EXPRESSION_LIMIT", "Expression node limit exceeded"
        )
    declarations = proposal["declarations"]
    names = [
        "Actor",
        *[
            s["name"]
            for kind in ("entities", "enums", "nominals")
            for s in declarations[kind]
        ],
    ]
    if len(names) != len(set(names)):
        raise OperationError(
            "invalid_input", "AMBIGUOUS_DECLARATION", "Declarations must be unique"
        )
    models: dict[str, Any] = {}
    enums: dict[str, Any] = {
        s["name"]: Enum(s["name"], [(c["name"], c["value"]) for c in s["cases"]])
        for s in declarations["enums"]
    }
    nominals = {
        s["name"]: nominal(s["name"], int, ops=set(s["operations"]))
        for s in declarations["nominals"]
    }
    actor = entity(type("Actor", (), {"name": field(str)}))
    entities: dict[str, Any] = {"Actor": actor}
    fragments = Fragments(entities, enums, nominals, models)
    unresolved = list(declarations["entities"])
    model_specs = list(proposal["models"])
    ordered_models: list[str] = []
    if len({s["model_id"] for s in model_specs}) != len(model_specs):
        raise OperationError(
            "invalid_input", "AMBIGUOUS_MODEL", "Model IDs must be unique"
        )
    while unresolved or model_specs:
        progress = False
        for spec in unresolved[:]:
            try:
                fields = {
                    name: field(fragments.type(d)) for name, d in spec["fields"].items()
                }
            except KeyError:
                continue
            entities[spec["name"]] = entity(type(spec["name"], (), fields))
            unresolved.remove(spec)
            progress = True
        for spec in model_specs[:]:
            try:
                model: Any
                kind = spec["model_kind"]
                if kind == "request_flow":
                    model = RequestFlow(
                        spec["model_id"],
                        actor=actor,
                        status=enums[spec["status_enum"]],
                        payload={
                            n: fragments.type(t) for n, t in spec["payload"].items()
                        },
                    )
                elif kind == "state_machine":
                    model = StateMachine(
                        spec["model_id"],
                        subject=fragments.entity(spec["subject"]),
                        state_field=spec["state_field"],
                        subject_param="subject",
                        entry_states=spec["entry_states"],
                    )
                elif kind == "approval":
                    open_when, eligible = approval_conditions(fragments, spec)
                    model = Approval(
                        spec["model_id"],
                        subject=fragments.entity(spec["subject"]),
                        actor=actor,
                        approve_threshold=spec["approve_threshold"],
                        reject_threshold=spec.get("reject_threshold"),
                        payload={
                            n: fragments.type(t) for n, t in spec["payload"].items()
                        },
                        open_when=open_when,
                        eligible=eligible,
                    )
                else:
                    raise OperationError(
                        "unsupported",
                        "DRAFT_FAMILY_UNAVAILABLE",
                        "This family is not implemented in this draft",
                    )
            except KeyError:
                continue
            models[spec["model_id"]] = model
            ordered_models.append(spec["model_id"])
            model_specs.remove(spec)
            progress = True
        if not progress:
            raise OperationError(
                "unsupported",
                "AUTHORING_REFERENCE_UNRESOLVED",
                "Unresolved or cyclic authoring references",
            )
    for spec in proposal["models"]:
        model = models[spec["model_id"]]
        if spec["model_kind"] == "request_flow":
            for creation in spec["creations"]:
                names = ["request_id", *sorted(creation["inputs"]), "actor"]
                model.create(
                    creation["id"],
                    to=creation["to"],
                    inputs={
                        n: fragments.type(t) for n, t in creation["inputs"].items()
                    },
                    context={"actor": Id[actor]},
                    values=fragments.values(names, creation["values"]),
                    requires=[
                        fragments.callback(names, r) for r in creation["requires"]
                    ],
                )
        if spec["model_kind"] == "approval":
            for choice, decision in spec["decisions"].items():
                names = ["decision_id", *sorted(decision["inputs"]), "subject", "actor"]

                def acting_actor(*values: Any) -> Any:
                    return values[-1]

                getattr(model, choice)(
                    actor=acting_actor,
                    inputs={
                        n: fragments.type(t) for n, t in decision["inputs"].items()
                    },
                    context={"actor": Id[actor]},
                    values=fragments.values(names, decision["values"]),
                    requires=[
                        fragments.callback(names, r) for r in decision["requires"]
                    ],
                )
            continue
        for transition in spec["transitions"]:
            # The public StateMachine signature orders state, inputs, related state.
            names = [
                "subject"
                if spec["model_kind"] == "state_machine"
                else spec["model_id"],
                *sorted(transition["inputs"]),
            ]
            state = {}
            if "parent" in transition:
                state["parent"] = fragments.entity(transition["parent"])
                names.append("parent")
            model.transition(
                transition["id"],
                from_=transition["from"],
                to=transition["to"],
                inputs={n: fragments.type(t) for n, t in transition["inputs"].items()},
                state=state,
                requires=[fragments.callback(names, r) for r in transition["requires"]],
                effects=fragments.effects(names, transition["assignments"]),
            )
    actions = [fragments.lifecycle(s) for s in proposal["actions"]]
    reads = []
    for spec in proposal["models"]:
        if spec["model_kind"] == "approval":
            reads.append(
                approval_read(
                    models[spec["model_id"]],
                    fragments.entity(spec["subject"]),
                    spec["model_id"],
                )
            )
    if proposal["safety"]:
        raise OperationError(
            "unsupported",
            "DRAFT_SAFETY_UNAVAILABLE",
            "Safety authoring is not yet implemented",
        )
    return BehaviorModule(
        entities=list(entities.values()),
        enums=list(enums.values()),
        nominals=list(nominals.values()),
        models=[models[s["model_id"]] for s in proposal["models"]],
        actions=actions,
        reads=reads,
    )


def approval_read(model: Any, subject_type: Any, model_id: str) -> Any:
    def status(subject: Any) -> Any:
        return project(
            subject,
            lambda s: [
                model.approve_count(s),
                model.reject_count(s),
                model.approved(s),
                model.rejected(s),
                model.pending(s),
            ],
        )

    status.__name__ = "mcp_" + model_id + "_status"
    status.__annotations__ = {"subject": subject_type}
    return read(status)


def approval_conditions(fragments: Fragments, spec: JSON) -> tuple[Any, Any]:
    layouts = [
        ["decision_id", *sorted(d["inputs"]), "actor"]
        for d in spec["decisions"].values()
    ]
    # A shared model condition can name only positional bindings common to both
    # public decision signatures; no capability or missing parameter is guessed.
    positions = {
        name: index
        for index, name in enumerate(layouts[0])
        if all(index < len(layout) and layout[index] == name for layout in layouts)
    }

    def scope(subject: Any, others: tuple[Any, ...]) -> JSON:
        bindings = {
            name: others[index]
            for name, index in positions.items()
            if index < len(others)
        }
        bindings.update(subject=subject, actor=others[-1])
        return bindings

    def open_when(subject: Any, *others: Any) -> Any:
        return fragments.expression(spec["open_when"], scope(subject, others))

    def eligible(subject: Any, actor: Any, *others: Any) -> Any:
        return fragments.expression(
            spec["eligible"], dict(scope(subject, others), actor=actor)
        )

    return open_when, eligible


VERSION = "2.0.0"
KINDS = ("request_flow", "state_machine", "approval")
CLOSURE = ("adapter_versions/v2_0_0.py", "adapter_versions/fragments_2_0_0.py")
