"""Planning-only composition checks using public released model constructors."""

import json
from enum import Enum
from pathlib import Path

from behavior import (
    Approval,
    BehaviorModule,
    FieldOwnership,
    GeneratedAction,
    Id,
    RequestFlow,
    StateMachine,
    WorkQueue,
    entity,
    field,
    nominal,
    versions,
)


@entity
class Actor:
    name = field(str)


class Phase(Enum):
    OPEN = "Open"
    DONE = "Done"


@entity
class Auxiliary:
    phase = field(Phase)


def probe():
    flow = RequestFlow("records", actor=Actor, status=Phase, payload={"label": str})
    flow.create(
        "start",
        to=Phase.OPEN,
        inputs={"label": str},
        context={"actor": Id[Actor]},
        values=lambda request_id, label, actor: {"label": label, "requester": actor},
    )
    flow.transition("finish", from_=[Phase.OPEN], to=Phase.DONE)
    approval = Approval(
        "review", subject=flow.request_entity, actor=Actor, approve_threshold=1
    )
    approval.approve(
        actor=lambda decision_id, subject, actor: actor, context={"actor": Id[Actor]}
    )
    approval.reject(
        actor=lambda decision_id, subject, actor: actor, context={"actor": Id[Actor]}
    )
    combined = BehaviorModule(entities=[Actor], enums=[Phase], models=[approval, flow])
    queue = WorkQueue(
        "jobs", worker=Actor, time=nominal("Time", int, ops={"order"}), max_attempts=3
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
    machine = StateMachine(
        "auxiliary", subject=Auxiliary, state_field="phase", entry_states=[Phase.OPEN]
    )
    machine.transition("finish", from_=[Phase.OPEN], to=Phase.DONE)
    controlled = BehaviorModule(
        entities=[Actor, Auxiliary],
        enums=[Phase],
        models=[queue, machine],
        safety=[
            FieldOwnership(
                id="auxiliary_control",
                entity=Auxiliary,
                writers={"phase": [GeneratedAction("auxiliary", "finish")]},
            )
        ],
    )
    return {
        "versions": versions(),
        "approval_request_flow": {
            "behavior_hash": combined.behavior_version,
            "models": [r.model_kind for r in combined.model_receipts],
        },
        "work_queue_state_machine_field_ownership": {
            "behavior_hash": controlled.behavior_version,
            "models": [r.model_kind for r in controlled.model_receipts],
            "safety": controlled.safety_analysis.to_dict(),
        },
    }


if __name__ == "__main__":
    result = probe()
    path = Path(__file__).with_name("composition_results.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(path),
                "approval_request_flow": result["approval_request_flow"]["models"],
                "queue_state_machine": result[
                    "work_queue_state_machine_field_ownership"
                ]["models"],
            }
        )
    )
