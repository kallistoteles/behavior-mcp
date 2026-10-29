"""Every queue operation is compared with an independent public Core consumer."""

import json

import pytest
from behavior import BehaviorModule, InMemoryBackend, Store

from behavior_mcp.server import Application
from tests.fixtures.expanded import setup
from tests.fixtures.runtime import create_active


def request(app, sid, capability, operation, *, inputs=None, proposals=None, work="w1"):
    capabilities = app.execute("capabilities_list", {"system_id": sid})["result"][
        "capabilities"
    ]
    action = next(c for c in capabilities if c["name"] == "jobs__" + capability)
    bindings = {p["name"]: work for p in action["params"] if p["role"] == "state"}
    return {
        "system_id": sid,
        "capability_id": action["name"],
        "operation_id": operation,
        "bindings": bindings,
        "input": inputs or {},
        "context_proposals": proposals or {},
        "expected_activation_revision": 1,
    }


def run(
    app,
    sid,
    capability,
    operation,
    *,
    inputs=None,
    proposals=None,
    work="w1",
    expected="ALLOW",
):
    args = request(
        app, sid, capability, operation, inputs=inputs, proposals=proposals, work=work
    )
    result = app.execute("transition_evaluate", args)
    assert result["outcome"] == (
        "evaluation_allowed" if expected == "ALLOW" else "semantic_refusal"
    ), result
    if expected == "ALLOW":
        committed = app.execute(
            "transition_commit",
            {
                "system_id": sid,
                "operation_id": operation,
                "evaluation_token": result["result"]["evaluation_token"],
            },
        )
        assert committed["outcome"] == "committed", committed
    return args, result


@pytest.mark.parametrize(
    "operation",
    ["claim", "renew", "complete", "retry", "fail", "recover", "exhaust", "cancel"],
)
def test_every_queue_operation_against_public_reference(tmp_path, operation):
    now = [10]
    app, proposal, policy = setup(tmp_path, "work-queue", clock=lambda: now[0])
    if operation == "exhaust":
        proposal["models"][0]["max_attempts"] = 1
    sid, definition, _, _ = create_active(app, proposal)
    # The oracle is independently constructed from the public model; it does not
    # consume the adapter's source, Wire, decisions or generated expectations.
    from behavior import WorkQueue, nominal

    from tests.fixtures.remaining_models import Actor

    time = nominal("Time", int, ops={"order"})
    queue = WorkQueue(
        "jobs",
        worker=Actor,
        time=time,
        max_attempts=proposal["models"][0]["max_attempts"],
        payload={"label": str},
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
    module = BehaviorModule(entities=[Actor], nominals=[time], models=[queue])
    store = Store.create(
        InMemoryBackend(),
        module,
        Store.genesis_for(
            module, [{"entity": "Actor", "value": {"id": "actor-1", "name": "local"}}]
        ),
    )
    sequence = [("enqueue", {"id": "w1", "available_at": 0, "label": "Example"}, {})]
    if operation not in ("claim", "cancel"):
        sequence.append(("claim", {"expected_generation": 0}, {"lease_until": 20}))
    parameters = {
        "claim": ({"expected_generation": 0}, {"lease_until": 20}),
        "renew": ({"generation": 1}, {"lease_until": 30}),
        "complete": ({"generation": 1}, {}),
        "retry": ({"generation": 1}, {"available_at": 10}),
        "fail": ({"generation": 1}, {}),
        "recover": ({}, {"available_at": 20}),
        "exhaust": ({}, {}),
        "cancel": ({}, {}),
    }
    sequence.append((operation, *parameters[operation]))
    for index, (name, inputs, proposals) in enumerate(sequence):
        if name in ("recover", "exhaust"):
            now[0] = 20
        args, result = run(
            app, sid, name, f"op-{index}", inputs=inputs, proposals=proposals
        )
        signature = next(
            a
            for a in json.loads(module.to_wire_json())["actions"]
            if a["name"] == args["capability_id"]
        )
        context = {
            p["name"]: ({"now": now[0], "worker": "actor-1", **proposals}[p["name"]])
            for p in signature["params"]
            if p["role"] == "context"
        }
        e = store.evaluate(
            module,
            args["capability_id"],
            bindings=args["bindings"],
            input=inputs,
            context=context,
            commit_time=app.context.clock(),
        )
        assert e.decision.result == "ALLOW", e.decision
        store.commit(module, e.bundle)
    reopened = Application(tmp_path, app.context, app.policy_id)
    assert (
        reopened.execute("system_recover", {"system_id": sid})["request_status"]
        == "completed"
    )


def test_queue_expiry_stale_generation_and_contention(tmp_path):
    from tests.fixtures.expanded import active

    now = [10]
    app, sid, _, _, _ = active(tmp_path, "work-queue", clock=lambda: now[0])
    run(
        app,
        sid,
        "enqueue",
        "enqueue",
        inputs={"id": "w1", "available_at": 0, "label": "Example"},
    )
    first = request(
        app,
        sid,
        "claim",
        "first",
        inputs={"expected_generation": 0},
        proposals={"lease_until": 20},
    )
    second = dict(first, operation_id="second")
    a = app.execute("transition_evaluate", first)
    b = app.execute("transition_evaluate", second)
    assert a["outcome"] == b["outcome"] == "evaluation_allowed"
    committed = app.execute(
        "transition_commit",
        {
            "system_id": sid,
            "operation_id": "first",
            "evaluation_token": a["result"]["evaluation_token"],
        },
    )
    assert committed["outcome"] == "committed", committed
    # The identical Core transition can be acknowledged for another host operation
    # without creating a second history event.
    duplicate = app.execute(
        "transition_commit",
        {
            "system_id": sid,
            "operation_id": "second",
            "evaluation_token": b["result"]["evaluation_token"],
        },
    )
    assert duplicate["outcome"] == "already_committed", duplicate
    run(app, sid, "complete", "stale", inputs={"generation": 0}, expected="DENY")
    run(
        app,
        sid,
        "claim",
        "competing",
        inputs={"expected_generation": 1},
        proposals={"lease_until": 20},
        expected="DENY",
    )
    now[0] = 19
    run(
        app,
        sid,
        "recover",
        "not-expired",
        proposals={"available_at": 19},
        expected="DENY",
    )
    now[0] = 20
    run(app, sid, "complete", "at-expiry", inputs={"generation": 1}, expected="DENY")
    run(app, sid, "recover", "expired", proposals={"available_at": 20})
    run(
        app,
        sid,
        "claim",
        "reclaim",
        inputs={"expected_generation": 1},
        proposals={"lease_until": 30},
    )
    run(app, sid, "complete", "complete", inputs={"generation": 2})
    run(
        app,
        sid,
        "claim",
        "terminal",
        inputs={"expected_generation": 2},
        proposals={"lease_until": 30},
        expected="DENY",
    )
