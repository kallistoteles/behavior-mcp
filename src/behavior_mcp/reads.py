"""Public Core reads; journal orchestration is separate from domain publication."""

from typing import Any, cast

from behavior import BehaviorModule, ReadExecution, StateRef, Store

from .schemas import JSON


def execute_read(
    store: Store, module: BehaviorModule, intent: JSON, context: JSON, at: StateRef
) -> ReadExecution:
    return cast(
        ReadExecution, store.read_intent(module, intent, context=context, at=at)
    )


class Reads:
    def __init__(self, manager: Any) -> None:
        self.manager = manager

    def invoke(self, args: JSON, subject: JSON) -> JSON:
        import json
        import sys

        from .adapters import historical_module, reads
        from .proof_worker import run_bounded
        from .runtime_context import bind_context
        from .schemas import OperationError, failure

        m = self.manager
        sid = args["system_id"]
        opid = args["operation_id"]
        m.policy.authorize(m.context, "capability_read", sid)
        m.policy.authorize_capability(args["capability_id"], read=True)
        m.bound(sid, opid, "read", args)
        operation = m.operation(sid, opid)
        if operation is None:
            definition, module, snapshot = m.active(sid)
            active = m.metadata(sid, "active")
            if args["expected_activation_revision"] != active["activation_revision"]:
                raise OperationError(
                    "conflict",
                    "DEPLOYMENT_MOVED",
                    "Requested activation revision is stale",
                )
            capability = next(
                (r for r in reads(module) if r["name"] == args["capability_id"]), None
            )
            if capability is None:
                raise OperationError(
                    "invalid_input",
                    "CAPABILITY_UNKNOWN",
                    "Declared read is unavailable",
                )
            context, provenance = bind_context(
                m.policy, m.context, snapshot["proposal"], capability, args
            )
            store = Store.open(m.backend(sid, allow_publication=False))
            operation = {
                "operation_id": opid,
                "kind": "read",
                "status": "pending",
                "request": args,
                "definition_id": definition["definition_id"],
                "activation_revision": active["activation_revision"],
                "source_history": store.current_history().as_dict(),
                "source_state": store.current().as_dict(),
                "trusted_context": context,
                "context_provenance": provenance,
                "receipt": None,
            }
            m.bind(sid, opid, "read", args)
            m.save_operation(sid, operation)
            m.fault("after_read_pending")
        definition, module = historical_module(m.artifacts, operation["definition_id"])
        subject.update(m.subject(sid, definition, operation["source_history"], opid))
        if "response_envelope" in operation:
            return dict(operation["response_envelope"])
        try:
            output = run_bounded(
                [sys.executable, "-m", "behavior_mcp.reads"],
                {
                    "path": str(m.artifacts.system_path(sid)),
                    "wire_json": module.to_wire_json(),
                    "intent": {
                        "capability": args["capability_id"],
                        "targets": args["bindings"],
                        "input": args["input"],
                    },
                    "context": operation["trusted_context"],
                    "at": operation["source_state"],
                },
                timeout=m.limits.read_timeout_seconds,
                output_limit=m.limits.read_output_bytes,
            )
            data = json.loads(output)
            record = data["record"]
            if (
                json.loads(data["record_json"]) != record
                or data.get("replayed") is not True
            ):
                raise OperationError(
                    "infrastructure",
                    "READ_REPLAY_FAILED",
                    "Public read evidence failed replay",
                )
            if (
                record["record_id"] != data["response"]["record_id"]
                or record["result"] != data["response"]["result"]
            ):
                raise OperationError(
                    "infrastructure",
                    "EVIDENCE_MISMATCH",
                    "Public read response differs from its record",
                )
            record_ref = m.artifacts.put(
                "core_read_record",
                {
                    "system_id": sid,
                    "definition_id": definition["definition_id"],
                    **data,
                },
            )
            result = {
                "kind": "read",
                "system_id": sid,
                "definition_id": definition["definition_id"],
                "behavior_hash": definition["behavior_hash"],
                "schema_hash": definition["schema_hash"],
                "activation_revision": operation["activation_revision"],
                "operation_id": opid,
                "capability_id": args["capability_id"],
                "history_anchor": operation["source_history"],
                "state_ref": operation["source_state"],
                "trusted_context_ref": m.artifacts.put(
                    "read_context",
                    {
                        "system_id": sid,
                        "context": operation["trusted_context"],
                        "provenance": operation["context_provenance"],
                    },
                ),
                "read_record_ref": record_ref,
                "response": data["response"],
                "release": definition["release"],
            }
            envelope = cast(JSON, m.response("read", "read", subject, result, "read"))
            operation.update(
                status="completed"
                if data["response"]["result"] == "VALUE"
                else "refused",
                read_record_ref=record_ref,
            )
        except Exception as error:
            envelope = failure("read", subject, error)
            operation.update(status="failed")
        operation["response_envelope"] = envelope
        m.save_operation(sid, operation)
        m.fault("after_read_completed")
        return envelope


def main() -> None:
    import json
    import sys
    from pathlib import Path

    from .sqlite_backend import SQLiteBackend

    request = json.load(sys.stdin)
    module = BehaviorModule.from_wire_json(request["wire_json"])
    store = Store.open(SQLiteBackend(Path(request["path"]), allow_publication=False))
    execution = execute_read(
        store, module, request["intent"], request["context"], StateRef.of(request["at"])
    )
    print(
        json.dumps(
            {
                "response": execution.response.as_dict(),
                "record": execution.record.as_dict(),
                "record_json": execution.record.to_json(),
                "replayed": store.replay_read(module, execution.record).matches,
            }
        )
    )


if __name__ == "__main__":
    main()
