"""Planning-only probe of the exact released, top-level Behavior Safety APIs."""

from __future__ import annotations

import argparse
import json
import tempfile
from enum import Enum
from pathlib import Path

from behavior import (
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
    action,
    and_,
    any_,
    certify_safety,
    create,
    entity,
    field,
    load_safety_bundle,
    not_,
    remove,
    requires,
    select,
    set_,
    validate_safety_snapshot,
    verify_safety_evidence,
    versions,
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


def build(*, missing_guard=False, safety=True):
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


def run(*, certify=False):
    model = build()
    analysis = model.safety_analysis.to_dict()
    stripped = build(safety=False)
    unsupported = build(missing_guard=True).safety_analysis.to_dict()
    store = Store.create(InMemoryBackend(), model, Store.genesis_for(model, []))
    anchor = store.current_history()
    valid = validate_safety_snapshot(store, model, at=anchor)
    invalid_seed = [
        {"entity": "Parent", "value": {"id": "p1", "phase": "Stopped"}},
        {"entity": "Child", "value": {"id": "c1", "phase": "Active", "owner": "p1"}},
    ]
    invalid_store = Store.create(
        InMemoryBackend(), model, Store.genesis_for(model, invalid_seed)
    )
    invalid = validate_safety_snapshot(
        invalid_store, model, at=invalid_store.current_history()
    )
    machine = StateMachine(
        "parent", subject=Parent, state_field="phase", entry_states=[ParentPhase.OPEN]
    )
    machine.transition("stop", from_=[ParentPhase.OPEN], to=ParentPhase.STOPPED)
    generated = BehaviorModule(
        entities=[Parent],
        enums=[ParentPhase],
        models=[machine],
        safety=[
            FieldOwnership(
                id="control",
                entity=Parent,
                writers={"phase": [GeneratedAction("parent", "stop")]},
            )
        ],
    )
    output = {
        "versions": versions(),
        "analysis": analysis,
        "behavior_hash_without_safety": stripped.behavior_version,
        "behavior_hash_with_safety": model.behavior_version,
        "safety_changes_wire_identity": stripped.behavior_version
        != model.behavior_version,
        "model_receipt_count": len(model.model_receipts),
        "valid_snapshot": valid.to_dict(),
        "valid_matches_anchor": valid.matches_anchor(model, anchor),
        "invalid_snapshot": invalid.to_dict(),
        "invalid_matches_anchor": invalid.matches_anchor(
            model, invalid_store.current_history()
        ),
        "missing_guard_analysis": unsupported,
        "generated_action_analysis": generated.safety_analysis.to_dict(),
    }
    try:
        validate_safety_snapshot({}, model)
    except TypeError as exc:
        output["detached_snapshot_error"] = str(exc)
    with tempfile.TemporaryDirectory(
        prefix="behavior-mcp-safety-planning-"
    ) as directory:
        try:
            absent = certify_safety(
                model, output=Path(directory) / "absent", toolchain="/missing"
            )
            output["wrong_toolchain_assessment"] = absent.to_dict()
        except Exception as exc:
            output["wrong_toolchain_error"] = {
                "type": type(exc).__name__,
                "detail": str(exc),
            }
        if certify:
            assessed = certify_safety(model, output=Path(directory) / "proof")
            output["certification"] = assessed.to_dict()
            output["certificate"] = (
                assessed.certificate.to_dict() if assessed.certificate else None
            )
            bundle_path = Path(directory) / "proof" / "bundle.json"
            imported = load_safety_bundle(bundle_path)
            checked = verify_safety_evidence(
                model, imported, output=Path(directory) / "rechecked"
            )
            output["fresh_checking"] = checked.to_dict()
            output["fresh_checking_has_certificate"] = checked.certificate is not None
            output["bundle_bytes"] = bundle_path.stat().st_size
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--certify", action="store_true")
    args = parser.parse_args()
    result = run(certify=args.certify)
    evidence = Path(__file__).with_name("safety_public_api_results.json")
    evidence.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(evidence),
                "analysis_status": result["analysis"]["status"],
                "same_behavior_hash": not result["safety_changes_wire_identity"],
                "missing_guard_status": result["missing_guard_analysis"]["status"],
                "state_valid": result["valid_snapshot"]["status"],
                "state_invalid": result["invalid_snapshot"]["status"],
                "certification": result.get("certification", {}).get("outcome"),
            },
            indent=2,
        )
    )
