"""Planning evidence; probes only the pinned released public Behavior interfaces."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from behavior import (
    Approval,
    BehaviorModule,
    Id,
    InMemoryBackend,
    Store,
    WorkQueue,
    entity,
    field,
    nominal,
    project,
    read,
    versions,
)


@entity
class Actor:
    name = field(str)


@entity
class Subject:
    label = field(str)


def compact_module(module):
    wire = json.loads(module.to_wire_json())
    return {
        "ir_version": wire["ir_version"],
        "behavior_hash": module.behavior_version,
        "schema_hash": module.schema_hash,
        "entities": [
            {
                "name": e["name"],
                "fields": [{"name": f["name"], "type": f["type"]} for f in e["fields"]],
            }
            for e in wire["entities"]
        ],
        "actions": [
            {"name": a["name"], "params": a["params"]} for a in wire["actions"]
        ],
        "reads": [
            {"name": r["name"], "params": r["params"]} for r in wire.get("reads", [])
        ],
        "derived": [
            {"name": d["name"], "kind": d["kind"], "params": d["params"]}
            for d in wire.get("derived", [])
        ],
        "receipts": [
            {
                "kind": r.model_kind,
                "model_hash": r.model_hash,
                "model_semantic_version": r.model_semantic_version,
                "lowerer_version": r.lowerer_version,
                "canonical_model": r.model,
            }
            for r in module.model_receipts
        ],
    }


def attempt(store, module, action, *, bindings=None, inputs=None, context=None):
    evaluation = store.evaluate(
        module,
        action,
        bindings=bindings or {},
        input=inputs or {},
        context=context or {},
        commit_time="2026-10-28T00:00:00Z",
    )
    outcome = {
        "decision": evaluation.decision.result,
        "reasons": evaluation.decision.reasons,
    }
    if evaluation.bundle is not None:
        result = store.commit(module, evaluation.bundle)
        outcome.update(
            already=result.already, history_position=result.result_state.position
        )
    return outcome


def approval_probe():
    approval = Approval(
        "approval",
        subject=Subject,
        actor=Actor,
        approve_threshold=2,
        reject_threshold=1,
    )
    approval.approve(
        actor=lambda decision_id, subject, actor: actor, context={"actor": Id[Actor]}
    )
    approval.reject(
        actor=lambda decision_id, subject, actor: actor, context={"actor": Id[Actor]}
    )

    @read
    def approval_status(subject: Subject):
        return project(
            subject,
            lambda s: [
                approval.approve_count(s),
                approval.reject_count(s),
                approval.approved(s),
                approval.rejected(s),
                approval.pending(s),
            ],
        )

    module = BehaviorModule(
        entities=[Actor, Subject], models=[approval], reads=[approval_status]
    )
    store = Store.create(
        InMemoryBackend(),
        module,
        Store.genesis_for(
            module,
            [
                {"entity": "Actor", "value": {"id": "actor-1", "name": "one"}},
                {"entity": "Actor", "value": {"id": "actor-2", "name": "two"}},
                {"entity": "Subject", "value": {"id": "subject-1", "label": "Example"}},
            ],
        ),
    )
    declared_intent = store.read_intent(
        module,
        {
            "capability": "approval_status",
            "targets": {"subject": "subject-1"},
            "input": {},
        },
        context={},
    )
    before = store.read(module, approval_status, bindings={"subject": "subject-1"})
    results = [
        attempt(
            store,
            module,
            "approval__approve",
            bindings={"subject": "subject-1"},
            inputs={"decision_id": "d1"},
            context={"actor": "actor-1"},
        )
    ]
    results.append(
        attempt(
            store,
            module,
            "approval__reject",
            bindings={"subject": "subject-1"},
            inputs={"decision_id": "duplicate"},
            context={"actor": "actor-1"},
        )
    )
    middle = store.read(module, approval_status, bindings={"subject": "subject-1"})
    results.append(
        attempt(
            store,
            module,
            "approval__approve",
            bindings={"subject": "subject-1"},
            inputs={"decision_id": "d2"},
            context={"actor": "actor-2"},
        )
    )
    after = store.read(module, approval_status, bindings={"subject": "subject-1"})
    return {
        "module": compact_module(module),
        "declared_read_intent": declared_intent.response.as_dict(),
        "read_before": before.response.as_dict(),
        "operations": results,
        "read_middle": middle.response.as_dict(),
        "read_after": after.response.as_dict(),
        "read_replay": store.replay_read(module, after.record).matches,
        "wire_reimport_receipt_count": len(
            BehaviorModule.from_wire_json(module.to_wire_json()).model_receipts
        ),
    }


def queue_probe():
    time = nominal("Time", int, ops={"order"})
    queue = WorkQueue(
        "queue", worker=Actor, time=time, max_attempts=2, payload={"label": str}
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

    def queue_terminal(work):
        return project(work, lambda w: [queue.terminal(w)])

    queue_terminal.__annotations__ = {"work": queue.work_entity}
    terminal_read = read(queue_terminal)
    module = BehaviorModule(entities=[Actor], models=[queue], reads=[terminal_read])
    store = Store.create(
        InMemoryBackend(),
        module,
        Store.genesis_for(
            module, [{"entity": "Actor", "value": {"id": "actor-1", "name": "one"}}]
        ),
    )
    outcomes = [
        attempt(
            store,
            module,
            queue.action_name("enqueue"),
            inputs={"id": "work-1", "available_at": 10, "label": "Example"},
        )
    ]
    ready = store.read(module, queue.read_name("ready"), context={"now": 10})
    outcomes.append(
        attempt(
            store,
            module,
            queue.action_name("claim"),
            bindings={"queue": "work-1"},
            inputs={"expected_generation": 0},
            context={"now": 10, "lease_until": 20, "worker": "actor-1"},
        )
    )
    expired_before = store.read(module, queue.read_name("expired"), context={"now": 19})
    expired_at = store.read(module, queue.read_name("expired"), context={"now": 20})
    outcomes.append(
        attempt(
            store,
            module,
            queue.action_name("complete"),
            bindings={"queue": "work-1"},
            inputs={"generation": 1},
            context={"now": 20, "worker": "actor-1"},
        )
    )
    outcomes.append(
        attempt(
            store,
            module,
            queue.action_name("recover"),
            bindings={"queue": "work-1"},
            context={"now": 20, "available_at": 20},
        )
    )
    return {
        "module": compact_module(module),
        "operations": outcomes,
        "ready": ready.response.as_dict(),
        "expired_before": expired_before.response.as_dict(),
        "expired_at": expired_at.response.as_dict(),
        "read_replay": store.replay_read(module, expired_at.record).matches,
        "wire_reimport_receipt_count": len(
            BehaviorModule.from_wire_json(module.to_wire_json()).model_receipts
        ),
    }


if __name__ == "__main__":
    output = {
        "release": versions(),
        "approval": approval_probe(),
        "work_queue": queue_probe(),
        "public_store_interfaces": {
            name: str(inspect.signature(getattr(Store, name)))
            for name in ("read", "read_intent", "evaluate", "commit")
        },
    }
    destination = Path(__file__).with_name("operational_models_results.json")
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(
        json.dumps(
            {
                "evidence": str(destination),
                "approval_operations": output["approval"]["operations"],
                "queue_operations": output["work_queue"]["operations"],
                "approval_reads": output["approval"]["read_after"],
                "queue_expiry_before_at": [
                    output["work_queue"]["expired_before"],
                    output["work_queue"]["expired_at"],
                ],
            },
            indent=2,
        )
    )
