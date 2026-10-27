"""Phase 0 public-release feasibility probe; not the server or a durability test."""

import copy
import hashlib
import json
import platform
from enum import Enum
from pathlib import Path

from behavior import (
    BehaviorModule,
    Id,
    InMemoryBackend,
    RequestFlow,
    StateMachine,
    Store,
    entity,
    field,
    set_,
    versions,
)

PROPOSAL = {
    "flow_id": "record",
    "states": {"OPEN": "Open", "DONE": "Done"},
    "create_to": "Open",
    "transition_id": "finish",
    "from": ["Open"],
    "to": "Done",
}


def build(data, compose=False):
    if set(data) != set(PROPOSAL):
        raise ValueError("unsupported authoring fields")
    status_type = Enum("Status", data["states"])

    @entity
    class Actor:
        name = field(str)

    flow = RequestFlow(
        data["flow_id"],
        actor=Actor,
        status=status_type,
        payload={"label": str, "outcome": str},
    )
    flow.create(
        "new",
        to=data["create_to"],
        inputs={"label": str},
        context={"actor": Id[Actor]},
        values=lambda request_id, label, actor: {
            "requester": actor,
            "label": label,
            "outcome": "",
        },
    )
    flow.transition(
        data["transition_id"],
        from_=data["from"],
        to=data["to"],
        inputs={"outcome": str},
        effects=[lambda record, outcome: set_(record.outcome, outcome)],
    )
    entities, models = [Actor], [flow]
    if compose:

        @entity
        class Auxiliary:
            status = field(status_type)

        machine = StateMachine(
            "auxiliary",
            subject=Auxiliary,
            state_field="status",
            entry_states={status_type.OPEN},
        )
        machine.transition("finish", from_={status_type.OPEN}, to=status_type.DONE)
        entities.append(Auxiliary)
        models.append(machine)
    return BehaviorModule(entities=entities, enums=[status_type], models=models)


def identities(module):
    receipt = next(r for r in module.model_receipts if r.model_kind == "request_flow")
    return {
        "model": receipt.model_hash,
        "behavior": module.behavior_version,
        "schema": module.schema_hash,
    }


def main():
    module = build(json.loads(json.dumps(PROPOSAL)))
    seed = [{"entity": "Actor", "value": {"id": "a1", "name": "local"}}]
    genesis = Store.genesis_for(module, seed)
    store = Store.create(InMemoryBackend(), module, genesis)
    independent = Store.create(InMemoryBackend(), module, genesis)
    same_genesis_store_ids_equal = store.store_id == independent.store_id
    creation = store.evaluate(
        module,
        "record__new",
        bindings={},
        input={"request_id": "r1", "label": "Example"},
        context={"actor": "a1"},
        commit_time="2026-10-26T00:00:00Z",
    )
    created = store.commit(module, creation.bundle)
    before = store.current()
    missing = store.evaluate(
        module,
        "record__new",
        bindings={},
        input={"request_id": "r2"},
        context={"actor": "a1"},
        commit_time="2026-10-26T00:00:00Z",
    )
    unchanged = store.current() == before
    completion = store.evaluate(
        module,
        "record__finish",
        bindings={"record": "r1"},
        input={"outcome": "Complete"},
        commit_time="2026-10-26T00:00:01Z",
    )
    completed = store.commit(module, completion.bundle)
    repeated = store.evaluate(
        module,
        "record__finish",
        bindings={"record": "r1"},
        input={"outcome": "Again"},
        commit_time="2026-10-26T00:00:02Z",
    )
    rebuilt = build(json.loads(json.dumps(PROPOSAL)))
    revised_data = copy.deepcopy(PROPOSAL)
    revised_data["transition_id"] = "complete"
    revised = build(revised_data)
    composed = build(PROPOSAL, compose=True)
    imported = BehaviorModule.from_wire_json(module.to_wire_json())
    try:
        build({**PROPOSAL, "custom_guard": "unsupported"})
        unsupported = False
    except ValueError:
        unsupported = True
    snapshot = store.export_seed_at(revised, store.current_history())
    result = {
        "purpose": "public API feasibility only; in-memory, no host implementation",
        "python": platform.python_version(),
        "probe_byte_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": versions(),
        "identities": identities(module),
        "canonical_document": module.model_receipts[0].model,
        "runtime_actions": json.loads(module.to_wire_json())["actions"],
        "observations": {
            "creation": creation.decision.result,
            "missing_input": missing.decision.result,
            "missing_input_head_unchanged": unchanged,
            "completion": completion.decision.result,
            "repeated_completion": repeated.decision.result,
            "repeated_completion_has_bundle": repeated.bundle is not None,
            "record": store.load("Record", "r1"),
            "commit_records": [created.record_id, completed.record_id],
            "retained_input_identity_equal": identities(module) == identities(rebuilt),
            "revision_model_changed": identities(module)["model"]
            != identities(revised)["model"],
            "revision_behavior_changed": module.behavior_version
            != revised.behavior_version,
            "revision_schema_equal": module.schema_hash == revised.schema_hash,
            "composition_receipts": len(composed.model_receipts),
            "composition_first_model_equal": identities(module)["model"]
            == identities(composed)["model"],
            "composition_behavior_changed": module.behavior_version
            != composed.behavior_version,
            "wire_behavior_equal": imported.behavior_version == module.behavior_version,
            "wire_schema_equal": imported.schema_hash == module.schema_hash,
            "wire_import_receipts": len(imported.model_receipts),
            "same_genesis_store_ids_equal": same_genesis_store_ids_equal,
            "independent_store_position": independent.current().position,
            "same_schema_snapshot_format": snapshot["format"],
            "unsupported_extension_rejected": unsupported,
        },
        "not_established": [
            "physical durability",
            "MCP implementation",
            "trusted host authorization",
            "formal verification",
            "arbitrary canonical-only re-authoring",
            "schema migration",
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
