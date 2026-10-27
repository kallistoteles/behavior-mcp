"""Independently authored oracle: only the pinned public Behavior API."""

from enum import Enum

from behavior import BehaviorModule, Id, RequestFlow, StateMachine, entity, field, set_


def reference_module(transition="finish", compose=False):
    class Status(Enum):
        OPEN = "Open"
        DONE = "Done"

    @entity
    class Actor:
        name = field(str)

    flow = RequestFlow(
        "record", actor=Actor, status=Status, payload={"label": str, "outcome": str}
    )
    flow.create(
        "new",
        to=Status.OPEN,
        inputs={"label": str},
        context={"actor": Id[Actor]},
        values=lambda request_id, label, actor: {
            "requester": actor,
            "label": label,
            "outcome": "",
        },
    )
    flow.transition(
        transition,
        from_={Status.OPEN},
        to=Status.DONE,
        inputs={"outcome": str},
        effects=[lambda record, outcome: set_(record.outcome, outcome)],
    )
    models = [flow]
    entities = [Actor]
    if compose:

        @entity
        class Auxiliary:
            status = field(Status)

        machine = StateMachine(
            "auxiliary",
            subject=Auxiliary,
            state_field="status",
            entry_states={Status.OPEN},
        )
        machine.transition("finish", from_={Status.OPEN}, to=Status.DONE)
        models.append(machine)
        entities.append(Auxiliary)
    return BehaviorModule(entities=entities, enums=[Status], models=models)


SEED = [{"entity": "Actor", "value": {"id": "actor-1", "name": "local"}}]
