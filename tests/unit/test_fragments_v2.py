"""Typed fragments trace through public constructors, with no executable input."""

import importlib
import importlib.util
import json
from pathlib import Path

import pytest
from behavior import InMemoryBackend, Store

from behavior_mcp.schemas import OperationError

CONTRACTS = (
    Path(__file__).resolve().parents[2]
    / "specs/002-remaining-behavior-models/contracts"
)


def draft():
    assert importlib.util.find_spec("behavior_mcp.authoring_v2"), (
        "Typed v2 builder is absent"
    )
    return importlib.import_module("behavior_mcp.authoring_v2")


def base():
    doc = json.loads((CONTRACTS / "examples/approval.json").read_text())
    doc["models"] = []
    return doc


def test_fixed_create_factory_uses_core():
    m = draft().build(base())
    store = Store.create(InMemoryBackend(), m, Store.genesis_for(m, []))
    e = store.evaluate(
        m,
        "new_subject",
        bindings={},
        input={"new_id": "s1"},
        context={},
        commit_time="2026-10-28T00:00:00Z",
    )
    assert e.decision.result == "ALLOW"
    store.commit(m, e.bundle)
    assert store.current().position == 1


@pytest.mark.parametrize(
    "bad", [{"op": "python", "source": "1+1"}, {"op": "param", "name": "missing"}]
)
def test_unknown_or_unbound_fragments_refuse(bad):
    doc = base()
    doc["actions"][0]["requires"] = [bad]
    with pytest.raises((OperationError, KeyError)):
        draft().build(doc)


def test_literal_equality_is_never_evaluated_by_python():
    doc = base()
    doc["actions"][0]["requires"] = [
        {
            "op": "eq",
            "left": {"op": "literal", "value": True},
            "right": {"op": "literal", "value": 1},
        }
    ]
    with pytest.raises(OperationError) as error:
        draft().build(doc)
    assert error.value.category == "unsupported"


def test_every_descriptor_and_explicit_enum_order():
    import json

    doc = base()
    doc["declarations"] = {
        "enums": [
            {
                "name": "Phase",
                "cases": [
                    {"name": "Z", "value": "last"},
                    {"name": "A", "value": "first"},
                ],
            }
        ],
        "nominals": [{"name": "Time", "base": "int", "operations": ["order"]}],
        "entities": [
            {"name": "Target", "fields": {"label": {"kind": "string"}}},
            {
                "name": "Subject",
                "fields": {
                    "label": {"kind": "string"},
                    "count": {"kind": "int"},
                    "enabled": {"kind": "bool"},
                    "phase": {"kind": "enum", "name": "Phase"},
                    "at": {"kind": "nominal", "name": "Time"},
                    "target_id": {"kind": "id", "entity": "Target"},
                    "target_ref": {"kind": "ref", "entity": "Target"},
                },
            },
        ],
    }
    doc["actions"] = []
    m = draft().build(doc)
    wire = json.loads(m.to_wire_json())
    subject = next(e for e in wire["entities"] if e["name"] == "Subject")
    assert {f["name"] for f in subject["fields"]} == {
        "label",
        "count",
        "enabled",
        "phase",
        "at",
        "target_id",
        "target_ref",
    }
    assert m.schema_hash


def test_all_lifecycle_factories_and_symbolic_guard_nodes():
    doc = json.loads((CONTRACTS / "examples/lifecycle.json").read_text())
    doc["safety"] = []
    m = draft().build(doc)
    store = Store.create(InMemoryBackend(), m, Store.genesis_for(m, []))
    wire = json.loads(m.to_wire_json())
    actions = {a["name"]: a for a in wire["actions"]}
    for spec in doc["actions"]:
        assert spec["name"] in actions
    # Guards include eq, and, not, any, in, field, enum, param. Public tracing
    # preserves each explicit root; the adapter does not recognize proof patterns.
    assert len(actions["stop_parent"]["preconditions"]) == 1
    assert len(actions["activate_child"]["preconditions"]) == 2
    for name, bindings, inputs, expected in [
        ("new_parent", {}, {"new_id": "p1"}, "ALLOW"),
        ("new_child", {"parent": "p1"}, {"new_id": "c1"}, "ALLOW"),
        ("stop_parent", {"subject": "p1"}, {}, "DENY"),
        ("finish_child", {"subject": "c1"}, {}, "ALLOW"),
        ("stop_parent", {"subject": "p1"}, {}, "ALLOW"),
        ("activate_child", {"subject": "c1", "parent": "p1"}, {}, "DENY"),
        ("remove_parent", {"subject": "p1"}, {}, "DENY"),
        ("remove_child", {"subject": "c1"}, {}, "ALLOW"),
        ("remove_parent", {"subject": "p1"}, {}, "ALLOW"),
    ]:
        evaluation = store.evaluate(
            m,
            name,
            bindings=bindings,
            input=inputs,
            context={},
            commit_time="2026-10-28T00:00:00Z",
        )
        assert evaluation.decision.result == expected, (name, evaluation.decision)
        if evaluation.bundle is not None:
            store.commit(m, evaluation.bundle)


def test_cyclic_declaration_is_explicitly_unsupported():
    doc = base()
    doc["actions"] = []
    doc["declarations"]["entities"] = [
        {"name": "Left", "fields": {"other": {"kind": "ref", "entity": "Right"}}},
        {"name": "Right", "fields": {"other": {"kind": "ref", "entity": "Left"}}},
    ]
    with pytest.raises(OperationError) as error:
        draft().build(doc)
    assert error.value.category == "unsupported"


@pytest.mark.parametrize(
    "left",
    [
        {"op": "param", "name": "subject"},
        {"op": "field", "value": {"op": "param", "name": "actor"}, "name": "node"},
        {
            "op": "field",
            "value": {
                "op": "field",
                "value": {"op": "param", "name": "subject"},
                "name": "id",
            },
            "name": "args",
        },
    ],
)
def test_python_objects_never_define_structured_equality(left):
    from behavior_mcp.adapters import build

    doc = json.loads((CONTRACTS / "examples/approval.json").read_text())
    doc["models"][0]["eligible"] = {"op": "eq", "left": left, "right": left}
    with pytest.raises(OperationError) as error:
        build(doc)
    assert error.value.category == "unsupported"
