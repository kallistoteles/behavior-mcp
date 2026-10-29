"""Bind public parameter roles to trusted context and explicit operational grants."""

from .policy import Delegation, TrustedContext
from .schemas import JSON, OperationError


def bind_context(
    policy: Delegation,
    trusted: TrustedContext,
    proposal: JSON,
    capability: JSON,
    args: JSON,
) -> tuple[JSON, JSON]:
    from .policy_v2 import select_grant

    roles = {
        role: {p["name"] for p in capability["params"] if p["role"] == role}
        for role in ("state", "input", "context")
    }
    for name, role in (("bindings", "state"), ("input", "input")):
        if set(args[name]) - roles[role] or set(args[name]) & {
            "actor",
            "worker",
            "now",
        }:
            raise OperationError(
                "invalid_input",
                "PARAMETER_ROLE_INVALID",
                "Request includes an unknown or trusted parameter",
            )
    proposals = args.get("context_proposals", {})
    permitted = roles["context"] & {"lease_until", "available_at"}
    if set(proposals) - permitted:
        raise OperationError(
            "invalid_input",
            "CONTEXT_PROPOSAL_INVALID",
            "Proposed context is not declared by this capability",
        )
    time_values = {n: v for n, v in args["input"].items() if n == "available_at"}
    time_values.update(proposals)
    snapshot: JSON = (
        trusted.snapshot()
        if "now" in roles["context"] or time_values
        else {
            "audit_time": trusted.clock(),
            "actor": trusted.actor_id,
            "worker": trusted.actor_id,
        }
    )
    context = {n: snapshot[n] for n in roles["context"] & {"actor", "worker", "now"}}
    context.update(proposals)
    if time_values:
        grant = select_grant(policy.document, proposal)
        for name, value in time_values.items():
            rows = [
                r
                for r in grant["proposed_time_bounds"]
                if r["capability_id"] == capability["name"] and r["parameter"] == name
            ]
            if (
                type(value) is not int
                or not 0 <= value <= 9007199254740991
                or len(rows) != 1
                or not rows[0]["minimum"] <= value <= rows[0]["maximum"]
                or value - snapshot["now"] > rows[0]["max_future_offset_ms"]
            ):
                raise OperationError(
                    "unauthorized",
                    "TIME_PROPOSAL_DENIED",
                    "Proposed time is outside trusted delegation",
                )
    return context, snapshot
