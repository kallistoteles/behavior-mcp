"""Evaluate, commit and recover original Core bundles under trusted system scope."""

import json
import uuid
from typing import TYPE_CHECKING

from behavior import CommitRefused, StateConflict, Store, replay_data

from .adapters import historical_module, reconstruct
from .schemas import JSON, OperationError, failure

if TYPE_CHECKING:
    from .systems import SystemManager


class Operations:
    def __init__(self, manager: "SystemManager") -> None:
        self.manager = manager

    def evaluate(self, args: JSON, subject: JSON) -> JSON:
        m = self.manager
        sid = args["system_id"]
        opid = args["operation_id"]
        subject["operation_id"] = opid
        m.policy.authorize(m.context, "transition_evaluate", sid)
        m.bound(sid, opid, "transition", args)
        previous = m.operation(sid, opid)
        if previous is not None:
            if "refusal" in previous:
                return dict(previous["refusal"])
            if "evaluation" not in previous:
                raise OperationError(
                    "conflict",
                    "OPERATION_FINISHED",
                    "Operation has no reusable evaluation",
                )
            subject.update(previous["evaluation_subject"])
            return m.response(
                "evaluation",
                "evaluation_allowed",
                subject,
                previous["evaluation"],
                "transition",
            )
        m.ensure_resolved(sid, opid)
        definition, module, snapshot = m.active(sid)
        active = m.metadata(sid, "active")
        if (
            active is None
            or args["expected_activation_revision"] != active["activation_revision"]
        ):
            raise OperationError(
                "conflict", "DEPLOYMENT_MOVED", "Requested activation revision is stale"
            )
        m.policy.authorize_capability(args["capability_id"])
        store = Store.open(m.backend(sid))
        history = store.current_history().as_dict()
        subject.update(m.subject(sid, definition, history, opid))
        context: JSON = {}
        actions = json.loads(module.to_wire_json())["actions"]
        action = next((a for a in actions if a["name"] == args["capability_id"]), None)
        if action and any(
            p["role"] == "context" and p["name"] == "actor" for p in action["params"]
        ):
            context["actor"] = m.context.actor_id
        audit_time = (
            m.context.clock()
            if definition["release"]["adapter_profile"] != "structured-models.v2"
            else ""
        )
        provenance = None
        if definition["release"]["adapter_profile"] == "structured-models.v2":
            from .runtime_context import bind_context

            if action is None:
                raise OperationError(
                    "invalid_input", "CAPABILITY_UNKNOWN", "Capability is not declared"
                )
            context, provenance = bind_context(
                m.policy, m.context, snapshot["proposal"], action, args
            )
            audit_time = provenance["audit_time"]
        evaluated = store.evaluate(
            module,
            args["capability_id"],
            bindings=args["bindings"],
            input=args["input"],
            context=context,
            commit_time=audit_time,
        )
        decision = {
            "result": evaluated.decision.result,
            "reasons": evaluated.decision.reasons,
        }
        m.bind(sid, opid, "transition", args)
        operation = {
            "operation_id": opid,
            "kind": "transition",
            "status": "evaluated" if evaluated.bundle is not None else "refused",
            "principal": m.context.principal_id,
            "request": args,
            "definition_id": definition["definition_id"],
            "behavior_hash": definition["behavior_hash"],
            "schema_hash": definition["schema_hash"],
            "source_history": history,
            "bundle": evaluated.bundle,
            "decision_record_json": evaluated.decision.record_json,
            "trusted_context": context,
            "activation_revision": active["activation_revision"],
            "policy": {
                "policy_id": m.policy.document["policy_id"],
                "policy_version": m.policy.document["version"],
            },
            "receipt": None,
        }
        if provenance is not None:
            operation["context_provenance"] = provenance
        if evaluated.bundle is None:
            refusal = failure(
                "evaluation",
                subject,
                OperationError(
                    "semantic_refusal",
                    "CORE_" + evaluated.decision.result,
                    "Core refused the requested transition",
                    result={"core_decision": decision, "operation_id": opid},
                ),
            )
            operation["refusal"] = refusal
            m.save_operation(sid, operation)
            return refusal
        result = {
            "kind": "evaluation",
            "operation_id": opid,
            "evaluation_token": "evaluation-" + uuid.uuid4().hex,
            "decision": decision,
            "source_history": history,
            "trusted_context": context
            or {"source": "trusted_host", "explicit_context": {}},
            "release": definition["release"],
        }
        operation.update(evaluation=result, evaluation_subject=dict(subject))
        m.save_operation(sid, operation)
        return m.response(
            "evaluation", "evaluation_allowed", subject, result, "transition"
        )

    def authorize_commit(
        self, sid: str, operation: JSON, *, recovery: bool = False
    ) -> JSON:
        """Check current authority for a potentially fresh publication, not historical truth."""
        m = self.manager
        opid = operation["operation_id"]
        m.policy.authorize(m.context, "transition_commit", sid)
        if operation["status"] == "refused" or (
            operation["status"] == "not_committed"
            and not (recovery and operation.get("reconciliation_ref"))
        ):
            raise OperationError(
                "conflict",
                "OPERATION_FINISHED",
                "Original operation is definitively not committed; evaluate a new operation",
            )
        m.ensure_resolved(sid, opid)
        active = m.metadata(sid, "active")
        if (
            active is None
            or active["activation_revision"] != operation["activation_revision"]
            or active["definition_id"] != operation["definition_id"]
        ):
            raise OperationError(
                "conflict",
                "DEPLOYMENT_MOVED",
                "Deployment differs from the original evaluation",
            )
        m.policy.authorize_capability(operation["request"]["capability_id"])
        if (
            operation["trusted_context"].get("actor", m.context.actor_id)
            != m.context.actor_id
            or operation["trusted_context"].get("worker", m.context.actor_id)
            != m.context.actor_id
        ):
            raise OperationError(
                "conflict",
                "TRUSTED_CONTEXT_CHANGED",
                "Trusted actor differs from the original evaluation",
            )
        if (
            not recovery
            and operation["policy"]["policy_version"] != m.policy.document["version"]
        ):
            raise OperationError(
                "conflict",
                "POLICY_MOVED",
                "Policy changed since evaluation; establish the original outcome before re-evaluation",
            )
        assert active is not None
        return active

    def commit(self, args: JSON, subject: JSON, *, recovery: bool = False) -> JSON:
        m = self.manager
        sid = args["system_id"]
        opid = args["operation_id"]
        subject["operation_id"] = opid
        m.bound(sid, opid, "transition")
        operation = m.operation(sid, opid)
        if (
            operation is None
            or operation.get("evaluation", {}).get("evaluation_token")
            != args["evaluation_token"]
        ):
            raise OperationError(
                "invalid_input",
                "EVALUATION_NOT_FOUND",
                "Evaluation token is unavailable for this exact operation",
            )
        if operation["principal"] != m.context.principal_id:
            raise OperationError(
                "unauthorized",
                "OPERATION_OWNER_DENIED",
                "Operation belongs to another trusted principal",
            )
        if operation["status"] == "committed":
            definition = m.artifacts.definition(operation["definition_id"])
            m.policy.authorize(m.context, "operation_get", sid)
            subject.update(
                m.subject(sid, definition, operation["receipt"]["history_anchor"], opid)
            )
            return m.response(
                "commit",
                "already_committed",
                subject,
                {
                    "kind": "transition_commit",
                    "receipt": operation["receipt"],
                    "already": True,
                    "release": definition["release"],
                },
                "transition",
            )
        active = self.authorize_commit(sid, operation, recovery=recovery)
        definition, module, _ = reconstruct(m.artifacts, operation["definition_id"])
        authorization = {
            "principal_id": m.context.principal_id,
            "workspace_id": m.context.workspace_id,
            "system_id": sid,
            "operation_id": opid,
            "definition_id": definition["definition_id"],
            "behavior_hash": definition["behavior_hash"],
            "policy_id": m.policy.document["policy_id"],
            "policy_version": m.policy.document["version"],
            "activation_revision": active["activation_revision"],
            "source_history": operation["source_history"],
        }
        authorization_ref = m.artifacts.put("execution_authorization", authorization)
        operation.setdefault("commit_authorization_refs", []).append(authorization_ref)
        operation["commit_authorization"] = authorization
        operation.update(status="committing", commit_request=args)
        m.save_operation(sid, operation)
        subject.update(m.subject(sid, definition, operation["source_history"], opid))
        store = Store.open(m.backend(sid, operation=operation))
        if recovery:
            m.recovery_publication_attempted = True
            m.recovery_operation_id = opid
        try:
            committed = store.commit(module, operation["bundle"])
        except StateConflict:
            operation["status"] = "not_committed"
            m.save_operation(sid, operation)
            raise
        except CommitRefused as error:
            current = m.operation(sid, opid)
            if current is None or current["status"] != "committed":
                operation["status"] = (
                    "unknown" if error.code == "BACKEND_ERROR" else "refused"
                )
                m.save_operation(sid, operation)
            raise
        current = m.operation(sid, opid)
        if current is None or current["status"] != "committed":
            # Core may recognize the original commit without invoking the backend again.
            # Only Core's acknowledged result supplies this recovered receipt.
            history = store.history_at(committed.result_state.position).as_dict()
            receipt = {
                "operation_id": opid,
                "record_id": committed.record_id,
                "result_state": committed.result_state.as_dict(),
                "definition_id": definition["definition_id"],
                "behavior_hash": definition["behavior_hash"],
                "history_anchor": history,
            }
            operation.update(status="committed", receipt=receipt)
            m.save_operation(sid, operation)
        else:
            receipt = current["receipt"]
        subject.update(m.subject(sid, definition, receipt["history_anchor"], opid))
        return m.response(
            "commit",
            "already_committed" if committed.already else "committed",
            subject,
            {
                "kind": "transition_commit",
                "receipt": receipt,
                "already": committed.already,
                "release": definition["release"],
            },
            "transition",
        )

    def report(self, sid: str, opid: str) -> JSON:
        m = self.manager
        m.policy.authorize(m.context, "operation_get", sid)
        binding = m.bound(sid, opid)
        if binding is None:
            raise OperationError(
                "invalid_input",
                "OPERATION_NOT_FOUND",
                "Operation is unavailable in this scope",
            )
        operation = m.operation(sid, opid)
        status = operation["status"] if operation else "not_committed"
        if operation is None and binding["kind"] == "system_creation":
            # Core creation and the host completion receipt have different publication
            # boundaries. Observe the original backend; inspection never completes creation.
            if m.backend(sid).genesis() is not None:
                status = "unknown"
        report = {
            "kind": "operation_report",
            "operation_id": opid,
            "operation_kind": binding["kind"],
            "status": status,
            "operation_may_have_committed": status in {"committing", "unknown"},
            "receipt": operation.get("receipt")
            if operation and status == "committed"
            else None,
            "observed_current_deployment": m.activation_ref(m.metadata(sid, "active")),
        }
        if binding["kind"] == "read":
            report["read_record_ref"] = (
                operation.get("read_record_ref") if operation else None
            )
        return report

    def report_subject(self, sid: str, operation: JSON, opid: str) -> JSON:
        receipt = operation.get("receipt") or {}
        definition_id = operation.get("definition_id") or receipt.get("definition_id")
        history = receipt.get("history_anchor") or operation.get("source_history")
        if definition_id and history:
            return self.manager.subject(
                sid,
                self.manager.artifacts.definition(definition_id),
                dict(history),
                opid,
            )
        return {}

    def get(self, args: JSON, subject: JSON) -> JSON:
        subject["operation_id"] = args["operation_id"]
        result = self.report(args["system_id"], args["operation_id"])
        operation = self.manager.operation(args["system_id"], args["operation_id"])
        if operation:
            subject.update(
                self.report_subject(args["system_id"], operation, args["operation_id"])
            )
        return self.manager.response("recovery", "operation_status", subject, result)

    def reconcile_transition(self, sid: str, opid: str) -> JSON:
        """Reconcile under the writer boundary without allowing domain publication.

        An unchanged exact Core history establishes nonpublication. If it moved, another
        OperationId may have committed the same transition. Ask Core about the original
        bundle using a backend whose publication callbacks always refuse. Only Core's
        already acknowledgment or StateConflict settles that case; other results fail
        closed. No bundle fields or semantic hashes are interpreted here.
        """
        m = self.manager
        m.policy.authorize(m.context, "operation_get", sid)
        m.bound(sid, opid, "transition")
        operation = m.operation(sid, opid)
        if operation is None:
            raise OperationError(
                "infrastructure",
                "OPERATION_RECORD_MISSING",
                "Original operation record is unavailable",
            )
        if operation["status"] not in {"committing", "unknown"}:
            return operation
        if operation.get("receipt") is not None:
            raise OperationError(
                "infrastructure",
                "OPERATION_RECEIPT_INCONSISTENT",
                "Operation status and publication receipt disagree",
            )
        observed = Store.open(m.backend(sid)).current_history().as_dict()
        outcome = "not_committed"
        basis = "original exact Core history unchanged; no atomic publication receipt"
        if observed != operation["source_history"]:
            from .adapters import historical_module

            definition, module = historical_module(
                m.artifacts, operation["definition_id"]
            )
            probe = Store.open(m.backend(sid, allow_publication=False))
            try:
                acknowledged = probe.commit(module, operation["bundle"])
            except StateConflict:
                basis = "Core StateConflict with domain publication disabled"
            except CommitRefused:
                raise OperationError(
                    "infrastructure",
                    "RECONCILIATION_INCONCLUSIVE",
                    "Core did not establish the original outcome; domain publication was disabled",
                    uncertain=True,
                    retryable=True,
                ) from None
            else:
                if not acknowledged.already:
                    raise OperationError(
                        "infrastructure",
                        "RECONCILIATION_INCONCLUSIVE",
                        "Core did not acknowledge an existing publication",
                        uncertain=True,
                    )
                history = probe.history_at(acknowledged.result_state.position).as_dict()
                operation["receipt"] = {
                    "operation_id": opid,
                    "record_id": acknowledged.record_id,
                    "result_state": acknowledged.result_state.as_dict(),
                    "definition_id": definition["definition_id"],
                    "behavior_hash": definition["behavior_hash"],
                    "history_anchor": history,
                }
                outcome = "committed"
                basis = "Core already acknowledgment with domain publication disabled"
        ref = m.artifacts.put(
            "operation_reconciliation",
            {
                "principal_id": m.context.principal_id,
                "workspace_id": m.context.workspace_id,
                "system_id": sid,
                "operation_id": opid,
                "outcome": outcome,
                "basis": basis,
                "history_anchor": observed,
                "policy": {
                    "policy_id": m.policy.document["policy_id"],
                    "policy_version": m.policy.document["version"],
                },
            },
        )
        operation.update(status=outcome, reconciliation_ref=ref)
        m.save_operation(sid, operation)
        return operation

    def recover(self, args: JSON, subject: JSON) -> JSON:
        m = self.manager
        sid = args["system_id"]
        m.policy.authorize(m.context, "system_recover", sid)
        m.policy.authorize(m.context, "operation_get", sid)
        if "operation_id" in args:
            opid = args["operation_id"]
            subject["operation_id"] = opid
            binding = m.bound(sid, opid)
            if binding is None:
                raise OperationError(
                    "invalid_input",
                    "OPERATION_NOT_FOUND",
                    "Original operation is unavailable",
                )
            operation = m.operation(sid, opid)
            if operation:
                subject.update(self.report_subject(sid, operation, opid))
            if (
                operation
                and operation["status"] in {"committing", "unknown"}
                and binding["kind"] == "transition"
            ):
                operation = self.reconcile_transition(sid, opid)
                if operation["status"] == "not_committed":
                    try:
                        self.authorize_commit(sid, operation, recovery=True)
                    except OperationError as error:
                        if error.category not in {"unauthorized", "conflict"}:
                            raise
                        # Original nonpublication is established even when a fresh retry
                        # is outside current authority or deployment conditions.
                    else:
                        history = Store.open(m.backend(sid)).current_history().as_dict()
                        if history == operation["source_history"]:
                            self.commit(
                                operation["commit_request"],
                                dict(subject),
                                recovery=True,
                            )
            elif operation is None and binding["kind"] == "activation":
                # No request receipt in the atomic publication transaction establishes no
                # publication. Any fresh publication still requires current activation grants.
                m.recovery_publication_attempted = True
                m.recovery_operation_id = opid
                m.activate(binding["request"], dict(subject))
            result = self.report(sid, opid)
            if result.get("receipt") and "history_anchor" in subject:
                subject["history_anchor"] = result["receipt"]["history_anchor"]
            outcome = (
                "recovered"
                if result["status"] in {"committed", "not_committed", "refused"}
                else "operation_status"
            )
            return m.response("recovery", outcome, subject, result, "recovery")
        recovered = []
        for operation in m.unresolved(sid):
            response = self.recover(
                {"system_id": sid, "operation_id": operation["operation_id"]},
                {"workspace_id": m.context.workspace_id, "system_id": sid},
            )
            recovered.append(response["result"])
        descriptor = m.metadata(sid, "descriptor")
        active = m.metadata(sid, "active")
        if descriptor is None:
            raise OperationError(
                "conflict",
                "SYSTEM_CREATING",
                "Incomplete system creation requires its original reservation",
            )
        definition, _ = historical_module(m.artifacts, descriptor["definition_id"])
        if active is not None:
            definition, _ = historical_module(m.artifacts, active["definition_id"])
        store = Store.open(m.backend(sid))
        if not replay_data(store).ok:
            raise OperationError(
                "infrastructure",
                "REPLAY_FAILED",
                "Core data replay did not establish valid history",
            )
        result = {
            "kind": "system_recovery",
            "system_id": sid,
            "lifecycle": "active" if active else "inactive",
            "recovered_operations": recovered,
            "active": m.activation_ref(active),
            "history_anchor": store.current_history().as_dict(),
            "release": definition["release"],
        }
        subject.update(m.subject(sid, definition, result["history_anchor"]))
        replay = m.replay(sid)
        return m.response(
            "recovery",
            "system_recovered",
            subject,
            result,
            "recovery",
            evidence_report={"result": result, "replay": replay},
        )
