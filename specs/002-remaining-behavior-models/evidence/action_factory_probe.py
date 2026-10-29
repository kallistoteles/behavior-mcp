"""Planning-only proof that fixed typed lifecycle factories need no generated source."""

import json
from enum import Enum
from pathlib import Path

from behavior import (
    BehaviorModule,
    Id,
    InMemoryBackend,
    Input,
    Store,
    action,
    create,
    entity,
    field,
    set_,
    versions,
)


class Phase(Enum):
    OPEN = "Open"
    DONE = "Done"


@entity
class Record:
    phase = field(Phase)


def creation_factory(entity_type, name, values):
    def record(*, new_id: Input[Id[entity_type]]):
        create(entity_type, id=new_id, **values)

    record.__name__ = name
    return action(record)


def assignment_factory(entity_type, name, field_name, value):
    def record(subject: entity_type):
        set_(getattr(subject, field_name), value)

    record.__name__ = name
    return action(record)


def probe():
    create_record = creation_factory(Record, "new_record", {"phase": Phase.OPEN})
    finish_record = assignment_factory(Record, "finish_record", "phase", Phase.DONE)
    module = BehaviorModule(
        entities=[Record], enums=[Phase], actions=[create_record, finish_record]
    )
    store = Store.create(InMemoryBackend(), module, Store.genesis_for(module, []))
    outcomes = []
    for name, bindings, supplied in (
        ("new_record", {}, {"new_id": "r1"}),
        ("finish_record", {"subject": "r1"}, {}),
    ):
        evaluated = store.evaluate(
            module,
            name,
            bindings=bindings,
            input=supplied,
            commit_time="2026-10-28T00:00:00Z",
        )
        assert evaluated.bundle is not None
        store.commit(module, evaluated.bundle)
        outcomes.append(evaluated.decision.result)
    return {
        "versions": versions(),
        "behavior_hash": module.behavior_version,
        "schema_hash": module.schema_hash,
        "actions": [a["name"] for a in json.loads(module.to_wire_json())["actions"]],
        "outcomes": outcomes,
        "history_position": store.current_history().position,
        "client_executable_code": False,
        "generated_source": False,
    }


if __name__ == "__main__":
    result = probe()
    path = Path(__file__).with_name("action_factory_results.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
