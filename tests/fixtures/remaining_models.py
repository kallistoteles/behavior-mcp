"""Independent public model builders and manually stated semantic expectations.

No MCP adapter or stored adapter output participates in these reference modules.
"""

from enum import Enum

from behavior import (
    Approval,
    BehaviorModule,
    FieldOwnership,
    GeneratedAction,
    Id,
    InMemoryBackend,
    Input,
    LifecycleDependency,
    Ref,
    StateMachine,
    Store,
    WorkQueue,
    action,
    and_,
    any_,
    create,
    entity,
    field,
    nominal,
    not_,
    project,
    read,
    remove,
    requires,
    select,
    set_,
)


@entity
class Actor:
    name = field(str)


@entity
class Subject:
    label = field(str)


ACTORS = [
    {"entity": "Actor", "value": {"id": "actor-1", "name": "one"}},
    {"entity": "Actor", "value": {"id": "actor-2", "name": "two"}},
]
# Expectations are consumer requirements, not adapter-derived truth tables.
APPROVAL_EXPECTATIONS = {
    "first_approve": "ALLOW",
    "duplicate_actor": "DENY",
    "second_actor": "ALLOW",
    "pending_before_threshold": True,
    "approved_after_threshold": True,
    "closed_subject": "DENY",
    "ineligible_actor": "DENY",
    "bad_threshold": "model_invalid",
}
QUEUE_EXPECTATIONS = {
    "enqueue": "ALLOW",
    "claim": "ALLOW",
    "renew": "ALLOW",
    "complete": "ALLOW",
    "retry": "ALLOW",
    "fail": "ALLOW",
    "recover": "ALLOW",
    "exhaust": "ALLOW",
    "cancel": "ALLOW",
    "stale_generation": "DENY",
    "second_claim": "DENY",
    "complete_at_expiry": "DENY",
    "recover_before_expiry": "DENY",
    "recover_at_expiry": "ALLOW",
    "terminal_claim": "DENY",
}
SAFETY_EXPECTATIONS = {
    "missing_stop_guard": "Unsupported",
    "guarded_parent_child": "Lowered",
    "active_child_stops_parent": "DENY",
    "terminal_child_stops_parent": "ALLOW",
    "reparent": "Unsupported",
    "computed_state": "Unsupported",
}


def approval_module(*, open_when=None, eligible=None, threshold=2):
    model = Approval(
        "review",
        subject=Subject,
        actor=Actor,
        approve_threshold=threshold,
        reject_threshold=1,
        open_when=open_when,
        eligible=eligible,
    )
    for register in (model.approve, model.reject):
        register(
            actor=lambda decision_id, subject, actor: actor,
            context={"actor": Id[Actor]},
        )

    @read
    def mcp_review_status(subject: Subject):
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

    return BehaviorModule(
        entities=[Actor, Subject], models=[model], reads=[mcp_review_status]
    )


def queue_module():
    time = nominal("Time", int, ops={"order"})
    queue = WorkQueue(
        "jobs", worker=Actor, time=time, max_attempts=2, payload={"label": str}
    )
    queue.enqueue(authorized=lambda **_: True)
    queue.claim(eligible=lambda work, **_: True)
    queue.renew()
    queue.complete()
    queue.retry()
    queue.fail()
    queue.recover(authorized=lambda work, **_: True)
    queue.exhaust(authorized=lambda work, **_: True)
    queue.cancel(authorized=lambda work, **_: True)
    return BehaviorModule(entities=[Actor], nominals=[time], models=[queue])


def ownership_module():
    class Phase(Enum):
        OPEN = "Open"
        STOPPED = "Stopped"

    @entity
    class Parent:
        phase = field(Phase)

    model = StateMachine(
        "parent", subject=Parent, state_field="phase", entry_states=[Phase.OPEN]
    )
    model.transition("stop", from_=[Phase.OPEN], to=Phase.STOPPED)
    return BehaviorModule(
        entities=[Parent],
        enums=[Phase],
        models=[model],
        safety=[
            FieldOwnership(
                id="control",
                entity=Parent,
                writers={"phase": [GeneratedAction("parent", "stop")]},
            )
        ],
    )


def reference_store(module, seed=()):
    return Store.create(
        InMemoryBackend(), module, Store.genesis_for(module, [*ACTORS, *seed])
    )


class ParentPhase(Enum):
    OPEN = "Open"
    STOPPED = "Stopped"


class ChildPhase(Enum):
    ACTIVE = "Active"
    TERMINAL = "Terminal"


@entity
class Parent:
    phase = field(ParentPhase)


@entity
class Child:
    phase = field(ChildPhase)
    owner = field(Ref[Parent])


@action
def stop(parent: Parent):
    requires(
        not_(
            any_(
                select(Child),
                lambda child: and_(
                    child.owner == parent.id,
                    not_(child.phase.in_([ChildPhase.TERMINAL])),
                ),
            )
        )
    )
    set_(parent.phase, ParentPhase.STOPPED)


@action
def stop_missing_guard(parent: Parent):
    set_(parent.phase, ParentPhase.STOPPED)


@action
def activate(child: Child, parent: Parent):
    requires(child.owner == parent.id)
    requires(not_(parent.phase.in_([ParentPhase.STOPPED])))
    set_(child.phase, ChildPhase.ACTIVE)


@action
def finish(child: Child):
    set_(child.phase, ChildPhase.TERMINAL)


@action
def create_parent(*, new_id: Input[Id[Parent]]):
    create(Parent, id=new_id, phase=ParentPhase.OPEN)


@action
def create_child(parent: Parent, *, new_id: Input[Id[Child]]):
    requires(not_(parent.phase.in_([ParentPhase.STOPPED])))
    create(Child, id=new_id, phase=ChildPhase.ACTIVE, owner=parent.id)


@action
def remove_parent(parent: Parent):
    remove(parent)


@action
def remove_child(child: Child):
    remove(child)


def lifecycle_module(*, missing_guard=False, safety=True):
    parent_stop = stop_missing_guard if missing_guard else stop
    policies = [
        FieldOwnership(
            id="parents",
            entity=Parent,
            writers={"phase": [parent_stop]},
            creators=[create_parent],
            removers=[remove_parent],
        ),
        FieldOwnership(
            id="children",
            entity=Child,
            writers={"phase": [activate, finish], "owner": []},
            creators=[create_child],
            removers=[remove_child],
        ),
        LifecycleDependency(
            id="relationship",
            parent=Parent,
            child=Child,
            owner_field="owner",
            parent_state="phase",
            child_state="phase",
            prohibited=[ParentPhase.STOPPED],
            terminal=[ChildPhase.TERMINAL],
            ownership=["parents", "children"],
        ),
    ]
    return BehaviorModule(
        entities=[Parent, Child],
        enums=[ParentPhase, ChildPhase],
        actions=[
            parent_stop,
            activate,
            finish,
            create_parent,
            create_child,
            remove_parent,
            remove_child,
        ],
        safety=policies if safety else [],
    )
