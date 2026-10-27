"""Independent deployment/state boundaries and explicit host-coordinated activation."""

import base64
import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from behavior import BehaviorModule, Store

from .artifacts import ArtifactStore, encode
from .authoring import capabilities, reconstruct, release_identity
from .limits import HostLimits
from .policy import Delegation, TrustedContext
from .schemas import JSON, OperationError, completed
from .sqlite_backend import SQLiteBackend
from .storage import connect, file_lock, transaction


class SystemManager:
    def __init__(
        self,
        root: Path,
        context: TrustedContext,
        artifacts: ArtifactStore,
        policy: Delegation,
        fault: Callable[[str], None] | None = None,
        limits: HostLimits | None = None,
    ) -> None:
        self.root = root
        self.context = context
        self.artifacts = artifacts
        self.policy = policy
        self.fault = fault or (lambda _: None)
        self.limits = limits or HostLimits()
        self.recovery_publication_attempted = False
        self.recovery_operation_id: str | None = None

    def backend(
        self, system_id: str, *, operation: JSON | None = None
    ) -> SQLiteBackend:
        path = self.artifacts.system_path(system_id)
        if not path.is_file():
            raise OperationError(
                "infrastructure",
                "SYSTEM_STORAGE_MISSING",
                "Original system storage is unavailable",
            )
        with connect(path) as db:
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        if (
            not {
                "core_meta",
                "core_versions",
                "core_records",
                "core_removed",
                "core_edges",
                "host_operations",
                "system_meta",
                "activations",
            }
            <= tables
        ):
            raise OperationError(
                "infrastructure",
                "SYSTEM_STORAGE_INVALID",
                "Original system database schema is unavailable; no empty reinitialization is permitted",
            )
        return SQLiteBackend(path, fault=self.fault, operation=operation)

    def metadata(self, system_id: str, key: str) -> JSON | None:
        path = self.artifacts.system_path(system_id)
        if not path.is_file():
            raise OperationError(
                "infrastructure",
                "SYSTEM_STORAGE_MISSING",
                "Original system storage is unavailable",
            )
        with connect(path) as db:
            row = db.execute(
                "SELECT document FROM system_meta WHERE key=?", (key,)
            ).fetchone()
        return dict(json.loads(row["document"])) if row else None

    @staticmethod
    def _write_meta(db: Any, key: str, value: JSON) -> None:
        db.execute(
            "INSERT OR REPLACE INTO system_meta VALUES (?,?)", (key, encode(value))
        )

    def operation(self, system_id: str, operation_id: str) -> JSON | None:
        with connect(self.artifacts.system_path(system_id)) as db:
            row = db.execute(
                "SELECT document FROM host_operations WHERE id=?", (operation_id,)
            ).fetchone()
        return dict(json.loads(row["document"])) if row else None

    def save_operation(self, system_id: str, operation: JSON) -> None:
        with connect(self.artifacts.system_path(system_id)) as db, transaction(db):
            db.execute(
                "INSERT OR REPLACE INTO host_operations VALUES (?,?)",
                (operation["operation_id"], encode(operation)),
            )

    def bind(self, system_id: str, operation_id: str, kind: str, request: JSON) -> None:
        self.artifacts.bind_operation(
            operation_id, system_id, self.context.principal_id, kind, request
        )

    def bound(
        self,
        system_id: str,
        operation_id: str,
        kind: str | None = None,
        request: JSON | None = None,
    ) -> JSON | None:
        binding = self.artifacts.operation_binding(operation_id)
        if binding and (
            binding["system_id"] != system_id
            or binding["principal"] != self.context.principal_id
            or (kind is not None and binding["kind"] != kind)
            or (request is not None and binding["request"] != request)
        ):
            raise OperationError(
                "conflict",
                "OPERATION_REUSE",
                "OperationId belongs to another request or scope",
            )
        return binding

    def unresolved(self, system_id: str) -> list[JSON]:
        with connect(self.artifacts.system_path(system_id)) as db:
            rows = db.execute(
                "SELECT document FROM host_operations ORDER BY id"
            ).fetchall()
        return [
            op
            for row in rows
            if (op := json.loads(row["document"]))["status"]
            in {"committing", "unknown"}
        ]

    def ensure_resolved(self, system_id: str, operation_id: str | None = None) -> None:
        if any(op["operation_id"] != operation_id for op in self.unresolved(system_id)):
            raise OperationError(
                "conflict",
                "SYSTEM_RECOVERY_REQUIRED",
                "Resolve the original uncertain operation before another mutation",
            )

    @staticmethod
    def activation_ref(active: JSON | None) -> JSON | None:
        return (
            {
                k: active[k]
                for k in (
                    "activation_id",
                    "activation_revision",
                    "definition_id",
                    "behavior_hash",
                )
            }
            if active
            else None
        )

    def subject(
        self,
        system_id: str,
        definition: JSON,
        history: JSON,
        operation_id: str | None = None,
    ) -> JSON:
        subject = {
            "workspace_id": self.context.workspace_id,
            "system_id": system_id,
            "definition_id": definition["definition_id"],
            "behavior_hash": definition["behavior_hash"],
            "schema_hash": definition["schema_hash"],
            "release": definition["release"],
            "history_anchor": history,
        }
        if operation_id is not None:
            subject["operation_id"] = operation_id
        return subject

    def response(
        self,
        stage: str,
        outcome: str,
        subject: JSON,
        result: JSON,
        evidence_kind: str | None = None,
        evidence_report: JSON | None = None,
    ) -> JSON:
        evidence = []
        if evidence_kind:
            ref = self.artifacts.put(
                evidence_kind + "_evidence",
                {
                    "subject": subject,
                    "report": evidence_report
                    if evidence_report is not None
                    else result,
                    "release": release_identity(),
                },
            )
            evidence = [
                {
                    "evidence_id": ref,
                    "kind": evidence_kind,
                    "report_ref": ref,
                    "subject": subject,
                    "release": release_identity(),
                }
            ]
        return completed(stage, outcome, subject, result, evidence)

    def route(self, name: str, args: JSON, subject: JSON) -> JSON:
        if name == "systems_create":
            return self.create(args, subject)
        if name == "systems_list":
            self.policy.authorize(self.context, name)
            systems = []
            for sid in self.artifacts.system_ids():
                try:
                    self.policy.authorize(self.context, "system_inspect", sid)
                except OperationError:
                    continue
                try:
                    with file_lock(self.root / "locks" / (sid + ".lock")):
                        view = self.inspect(sid)
                except OperationError as error:
                    if (
                        error.code != "SYSTEM_CREATING"
                        and error.category != "infrastructure"
                    ):
                        raise
                    view = {
                        "system_id": sid,
                        "lifecycle": "creating"
                        if error.code == "SYSTEM_CREATING"
                        else "recovery_required",
                        "active": None,
                    }
                except (sqlite3.Error, OSError):
                    view = {
                        "system_id": sid,
                        "lifecycle": "recovery_required",
                        "active": None,
                    }
                systems.append(
                    {k: view[k] for k in ("system_id", "lifecycle", "active")}
                )
            page, cursor = self.page(
                systems,
                args,
                {"kind": "systems", "workspace_id": self.context.workspace_id},
            )
            return self.response(
                "discovery",
                "listed",
                subject,
                {"kind": "systems", "systems": page, "next_cursor": cursor},
            )
        sid = args["system_id"]
        subject["system_id"] = sid
        # Resolve scope before touching a backend; activation/commit retries may disclose only
        # an existing original outcome under current operation_get authority.
        if name not in {"definition_activate", "transition_commit"}:
            self.policy.authorize(self.context, name, sid)
        else:
            binding = self.artifacts.operation_binding(args["operation_id"])
            try:
                self.policy.authorize(self.context, name, sid)
            except OperationError:
                if binding is None:
                    raise
                self.policy.authorize(self.context, "operation_get", sid)
            if binding:
                self.bound(sid, args["operation_id"])
        path = self.artifacts.system_path(sid)
        if not path.exists():
            raise OperationError(
                "infrastructure",
                "SYSTEM_STORAGE_MISSING",
                "Reserved system storage is unavailable; restore original storage instead of recreating history",
            )
        if name == "system_recover" and self.metadata(sid, "descriptor") is None:
            return self.recover_creation(sid, args, subject)
        with file_lock(self.root / "locks" / (sid + ".lock")):
            if name == "system_inspect":
                return self.response("read", "read", subject, self.inspect(sid))
            if name == "definition_activate":
                return self.activate(args, subject)
            if name == "capabilities_list":
                definition, module, _ = self.active(sid)
                history = Store.open(self.backend(sid)).current_history().as_dict()
                subject.update(self.subject(sid, definition, history))
                return self.response(
                    "discovery",
                    "listed",
                    subject,
                    {
                        "kind": "capabilities",
                        "system_id": sid,
                        "definition_id": definition["definition_id"],
                        "behavior_hash": definition["behavior_hash"],
                        "schema_hash": definition["schema_hash"],
                        "capabilities": capabilities(module),
                        "release": definition["release"],
                    },
                )
            if name == "state_read":
                return self.read(args, subject)
            from .operations import Operations

            operations = Operations(self)
            if name == "transition_evaluate":
                return operations.evaluate(args, subject)
            if name == "transition_commit":
                return operations.commit(args, subject)
            if name == "operation_get":
                return operations.get(args, subject)
            if name == "system_recover":
                return operations.recover(args, subject)
        raise OperationError("unsupported", "TOOL_UNSUPPORTED", "Tool is not supported")

    def inspect(self, sid: str) -> JSON:
        descriptor = self.metadata(sid, "descriptor")
        if descriptor is None:
            raise OperationError(
                "conflict", "SYSTEM_CREATING", "System creation requires recovery"
            )
        active = self.metadata(sid, "active")
        history = Store.open(self.backend(sid)).current_history().as_dict()
        permitted = []
        for operation in self.policy.document["operations"]:
            try:
                self.policy.authorize(self.context, operation, sid)
            except OperationError:
                continue
            permitted.append(operation)
        return {
            "kind": "system",
            "system_id": sid,
            "lifecycle": "recovery_required"
            if self.unresolved(sid)
            else "active"
            if active
            else "inactive",
            "initializing_definition_id": descriptor["definition_id"],
            "active": self.activation_ref(active),
            "history_anchor": history,
            "permitted_operations": permitted,
        }

    def active(self, sid: str) -> tuple[JSON, BehaviorModule, JSON]:
        active = self.metadata(sid, "active")
        if active is None:
            raise OperationError(
                "semantic_refusal",
                "SYSTEM_INACTIVE",
                "Runtime requires separate authorized activation",
            )
        return reconstruct(self.artifacts, active["definition_id"])

    def create(self, args: JSON, subject: JSON) -> JSON:
        operation_id = args["operation_id"]
        subject["operation_id"] = operation_id
        prior = self.artifacts.operation_binding(operation_id)
        if prior:
            sid = prior["system_id"]
            subject["system_id"] = sid
            self.policy.authorize(self.context, "operation_get", sid)
            self.bound(sid, operation_id, "system_creation", args)
        else:
            self.policy.authorize(self.context, "systems_create")
            sid = "system-" + uuid.uuid4().hex
        if prior and not self.artifacts.system_path(sid).exists():
            raise OperationError(
                "infrastructure",
                "SYSTEM_STORAGE_MISSING",
                "Original system storage is unavailable; creation cannot be replayed into an empty backend",
            )
        p = self.policy.document
        prepared_backend = None
        definition, module, snapshot = reconstruct(
            self.artifacts, args["definition_id"]
        )
        if not prior:
            if not p["system_creation"]["allowed"]:
                raise OperationError(
                    "unauthorized",
                    "CREATION_DENIED",
                    "System creation is not delegated",
                )
            self.policy.check_candidate(snapshot["proposal"], module, existing=False)
            if len(self.artifacts.system_ids()) >= p["system_creation"]["max_systems"]:
                raise OperationError(
                    "unauthorized",
                    "SYSTEM_CAPACITY",
                    "System creation exceeds trusted capacity",
                )
            # This identifier was allocated by the host above, never supplied by a caller.
            # Make the empty backend durable before publishing its catalog reservation.
            # An interrupted preparation is an unreferenced empty file, not a system.
            prepared_backend = SQLiteBackend(
                self.root / "systems" / (sid + ".sqlite"), fault=self.fault
            )
            self.artifacts.bind_operation(
                operation_id,
                sid,
                self.context.principal_id,
                "system_creation",
                args,
                create_capacity=p["system_creation"]["max_systems"],
            )
        subject["system_id"] = sid
        with file_lock(self.root / "locks" / (sid + ".lock")):
            backend = self.backend(sid) if prior else prepared_backend
            assert backend is not None
            operation = self.operation(sid, operation_id)
            if operation and operation["status"] == "committed":
                subject.update(
                    self.subject(
                        sid,
                        definition,
                        operation["receipt"]["history_anchor"],
                        operation_id,
                    )
                )
                return self.response(
                    "system_creation",
                    "already_created",
                    subject,
                    operation["result"],
                    "validation",
                )
            already_published = backend.genesis() is not None
            context_id = "creation-context:" + operation_id
            try:
                creation_context = self.artifacts.get(context_id)
            except OperationError as error:
                if error.code != "ARTIFACT_NOT_FOUND" or already_published:
                    raise OperationError(
                        "infrastructure",
                        "CREATION_CONTEXT_UNAVAILABLE",
                        "Original creation context is unavailable",
                    ) from None
                creation_context = None
            if not already_published:
                self.policy.authorize(self.context, "systems_create")
                if (
                    not p["system_creation"]["allowed"]
                    or len(self.artifacts.system_ids())
                    > p["system_creation"]["max_systems"]
                ):
                    raise OperationError(
                        "unauthorized",
                        "CREATION_DENIED",
                        "Current delegation does not permit fresh initialization",
                    )
                self.policy.check_candidate(
                    snapshot["proposal"], module, existing=False
                )
                actor = p["system_creation"]["bootstrap_actor"]
                if actor["id"] != self.context.actor_id:
                    raise OperationError(
                        "unauthorized",
                        "ACTOR_CONTEXT_MISMATCH",
                        "Trusted bootstrap actor differs from launcher context",
                    )
                seed = [
                    {
                        "entity": actor["entity"],
                        "value": {"id": actor["id"], "name": actor["name"]},
                    }
                ]
                if creation_context is not None and creation_context["seed"] != seed:
                    raise OperationError(
                        "conflict",
                        "CREATION_CONTEXT_CHANGED",
                        "Original bootstrap seed is no longer delegated",
                    )
                if creation_context is None:
                    genesis = Store.genesis_for(
                        module,
                        seed,
                        policy={
                            "format": "behavior.evidence_policy.v1",
                            "require": "none",
                        },
                    )
                    creation_context = {
                        "principal_id": self.context.principal_id,
                        "workspace_id": self.context.workspace_id,
                        "system_id": sid,
                        "definition_id": definition["definition_id"],
                        "genesis": genesis,
                        "seed": seed,
                        "policy": {
                            "policy_id": p["policy_id"],
                            "policy_version": p["version"],
                        },
                    }
                    self.artifacts.put(
                        "creation_context", creation_context, identity=context_id
                    )
            if (
                creation_context is None
                or creation_context["system_id"] != sid
                or creation_context["definition_id"] != definition["definition_id"]
            ):
                raise OperationError(
                    "infrastructure",
                    "CREATION_CONTEXT_MISMATCH",
                    "Original creation scope is inconsistent",
                )
            store = Store.create(backend, module, creation_context["genesis"])
            history = store.history_at(0).as_dict()
            receipt = {
                "operation_id": operation_id,
                "system_id": sid,
                "definition_id": definition["definition_id"],
                "store_id": store.store_id,
                "history_anchor": history,
            }
            result = {
                "kind": "system_creation",
                "lifecycle": "inactive",
                "receipt": receipt,
                "release": definition["release"],
            }
            descriptor = {
                "system_id": sid,
                "workspace_id": self.context.workspace_id,
                "definition_id": definition["definition_id"],
                "operation_id": operation_id,
                "label": args.get("label"),
            }
            with connect(backend.path) as db, transaction(db):
                if self.metadata(sid, "descriptor") is None:
                    self._write_meta(db, "descriptor", descriptor)
                record = {
                    "operation_id": operation_id,
                    "kind": "system_creation",
                    "status": "committed",
                    "creation_context_ref": context_id,
                    "publication_policy": creation_context["policy"]
                    if already_published
                    else {"policy_id": p["policy_id"], "policy_version": p["version"]},
                    "principal": self.context.principal_id,
                    "request": args,
                    "receipt": receipt,
                    "result": result,
                }
                db.execute(
                    "INSERT OR REPLACE INTO host_operations VALUES (?,?)",
                    (operation_id, encode(record)),
                )
            subject.update(self.subject(sid, definition, history, operation_id))
            return self.response(
                "system_creation",
                "already_created" if already_published else "created",
                subject,
                result,
                "validation",
            )

    def recover_creation(self, sid: str, args: JSON, subject: JSON) -> JSON:
        with connect(self.artifacts.path) as db:
            row = db.execute(
                "SELECT operation_id,request FROM reservations WHERE system_id=?",
                (sid,),
            ).fetchone()
        if row is None:
            raise OperationError(
                "invalid_input", "SYSTEM_NOT_FOUND", "System reservation is unavailable"
            )
        self.recovery_publication_attempted = True
        self.recovery_operation_id = row["operation_id"]
        self.create(json.loads(row["request"]), subject)
        return self.route(
            "system_recover",
            {"system_id": sid, "operation_id": row["operation_id"]},
            subject,
        )

    def _approval(self, sid: str, definition: JSON, args: JSON) -> JSON | None:
        p = self.policy.document
        expected = {
            "grantee_principal_id": self.context.principal_id,
            "workspace_id": self.context.workspace_id,
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "behavior_hash": definition["behavior_hash"],
            "schema_hash": definition["schema_hash"],
            "policy_id": p["policy_id"],
            "policy_version": p["version"],
            "expected_activation_revision": args["expected_activation_revision"],
            "history_anchor": args["expected_history"],
        }
        return next(
            (
                a
                for a in self.artifacts.approvals()
                if all(a[k] == v for k, v in expected.items())
            ),
            None,
        )

    def required_evidence(self, definition: JSON) -> list[str]:
        refs = []
        for requirement in self.policy.document["required_verification"]:
            matched = None
            for ref, evidence in self.artifacts.find("verification_evidence"):
                subject = evidence["subject"]
                report = evidence["report"]
                if any(
                    subject.get(k) != definition[k]
                    for k in (
                        "definition_id",
                        "behavior_hash",
                        "schema_hash",
                        "release",
                    )
                ):
                    continue
                raw = report["report"]
                if (
                    report["profile_id"] != requirement["profile_id"]
                    or report["verification_status"] != "verified"
                    or report["upstream_result"] != "verified"
                    or raw.get("result") != "verified"
                    or raw.get("hash") != report["report_identity"]
                    or raw.get("behavior_version") != definition["behavior_hash"]
                    or report["release"] != definition["release"]
                ):
                    continue
                if (
                    "wire_ir:" + report["semantic_profile"]["wire_ir"]
                    != requirement["semantic_profile_id"]
                ):
                    continue
                if (
                    report["checks"] != raw["checks"]
                    or report["obligations"] != raw.get("obligations", [])
                    or report["assumptions"] != raw.get("assumptions", [])
                ):
                    continue
                check_ids = {
                    c["key"] for c in raw["checks"] if c.get("outcome") == "proven"
                }
                obligation_ids = {o["id"] for o in report["obligations"] if "id" in o}
                assumption_ids = {
                    a if isinstance(a, str) else a.get("id")
                    for a in report["assumptions"]
                }
                if (
                    not set(requirement["required_check_ids"]) <= check_ids
                    or not set(requirement["required_obligation_ids"]) <= obligation_ids
                    or not assumption_ids
                    <= set(requirement["permitted_assumption_ids"])
                ):
                    continue
                matched = ref
                break
            if matched is None:
                raise OperationError(
                    "unauthorized",
                    "VERIFICATION_REQUIRED",
                    "Required exact public proof evidence is missing or unestablished",
                )
            refs.append(matched)
        return refs

    def activate(self, args: JSON, subject: JSON) -> JSON:
        sid = args["system_id"]
        opid = args["operation_id"]
        subject["operation_id"] = opid
        binding = self.bound(sid, opid, "activation", args)
        prior = self.operation(sid, opid) if binding else None
        if prior and prior["status"] == "committed":
            self.policy.authorize(self.context, "operation_get", sid)
            receipt = prior["receipt"]
            definition = self.artifacts.definition(receipt["definition_id"])
            subject.update(
                self.subject(sid, definition, receipt["history_anchor"], opid)
            )
            return self.response(
                "activation",
                "already_activated",
                subject,
                {
                    "kind": "activation",
                    "receipt": receipt,
                    "observed_current_deployment": self.activation_ref(
                        self.metadata(sid, "active")
                    ),
                },
                "activation",
            )
        self.policy.authorize(self.context, "definition_activate", sid)
        self.ensure_resolved(sid, opid)
        definition, module, snapshot = reconstruct(
            self.artifacts, args["definition_id"]
        )
        store = Store.open(self.backend(sid))
        history = store.current_history().as_dict()
        previous = self.metadata(sid, "active")
        revision = previous["activation_revision"] if previous else 0
        if (
            args["expected_activation_revision"] != revision
            or args["expected_history"] != history
        ):
            raise OperationError(
                "conflict",
                "DEPLOYMENT_MOVED",
                "Activation revision or Core history moved",
            )
        if definition["schema_hash"] != store.schema_at().hash:
            raise OperationError(
                "unsupported",
                "SCHEMA_MIGRATION_UNSUPPORTED",
                "Schema-changing activation requires an unsupported migration boundary",
            )
        approval = self._approval(sid, definition, args)
        self.policy.check_candidate(
            snapshot["proposal"],
            module,
            existing=True,
            exceptions=approval["exceptions"] if approval else [],
        )
        verification_refs = self.required_evidence(definition)
        store.export_seed_at(module, history)
        self.bind(sid, opid, "activation", args)
        subject.update(self.subject(sid, definition, history, opid))
        p = self.policy.document
        authorization_ref = self.artifacts.put(
            "activation_authorization",
            {
                "principal_id": self.context.principal_id,
                "workspace_id": self.context.workspace_id,
                "system_id": sid,
                "definition_id": definition["definition_id"],
                "behavior_hash": definition["behavior_hash"],
                "policy_id": p["policy_id"],
                "policy_version": p["version"],
                "approval_id": approval["approval_id"] if approval else None,
                "history_anchor": history,
            },
        )
        validation_ref = self.artifacts.put(
            "validation_evidence",
            {
                "subject": subject,
                "report": {
                    "admitted": True,
                    "module_ref": definition["module_ref"],
                    "receipt_refs": [m["receipt_ref"] for m in definition["models"]],
                },
                "release": definition["release"],
            },
        )
        request_ref = self.artifacts.put(
            "activation_request",
            {
                "request": args,
                "principal_id": self.context.principal_id,
                "workspace_id": self.context.workspace_id,
                "system_id": sid,
            },
        )
        receipt = {
            "activation_id": "activation-" + uuid.uuid4().hex,
            "operation_id": opid,
            "workspace_id": self.context.workspace_id,
            "system_id": sid,
            "definition_id": definition["definition_id"],
            "behavior_hash": definition["behavior_hash"],
            "schema_hash": definition["schema_hash"],
            "previous_activation_revision": revision,
            "activation_revision": revision + 1,
            "policy": {"policy_id": p["policy_id"], "policy_version": p["version"]},
            "authorization_ref": authorization_ref,
            "history_anchor": history,
            "validation_evidence_refs": [validation_ref],
            "verification_evidence_refs": verification_refs,
            "release": definition["release"],
            "request_binding_ref": request_ref,
        }
        result = {
            "kind": "activation",
            "receipt": receipt,
            "observed_current_deployment": self.activation_ref(receipt),
        }
        with connect(self.artifacts.system_path(sid)) as db, transaction(db):
            self._write_meta(db, "active", receipt)
            db.execute(
                "INSERT INTO activations VALUES (?,?)", (revision + 1, encode(receipt))
            )
            db.execute(
                "INSERT INTO host_operations VALUES (?,?)",
                (
                    opid,
                    encode(
                        {
                            "operation_id": opid,
                            "kind": "activation",
                            "status": "committed",
                            "principal": self.context.principal_id,
                            "request": args,
                            "receipt": receipt,
                            "result": result,
                        }
                    ),
                ),
            )
            self.fault("activation_before_commit")
        self.fault("activation_after_commit")
        return self.response("activation", "activated", subject, result, "activation")

    def page(
        self, items: list[JSON], args: JSON, scope: JSON
    ) -> tuple[list[JSON], str | None]:
        # This fingerprints host query bytes, never Behavior meaning or caller authority.
        query_bytes_sha256 = hashlib.sha256(encode(scope).encode()).hexdigest()
        offset = 0
        if args.get("cursor"):
            try:
                cursor = json.loads(base64.urlsafe_b64decode(args["cursor"]))
                if (
                    cursor["query_bytes_sha256"] != query_bytes_sha256
                    or type(cursor["offset"]) is not int
                    or cursor["offset"] < 0
                ):
                    raise ValueError("scope")
                offset = cursor["offset"]
            except (ValueError, KeyError, TypeError):
                raise OperationError(
                    "invalid_input",
                    "CURSOR_INVALID",
                    "Read cursor does not match the authorized query",
                ) from None
        limit = args.get("limit", self.limits.page_default)
        if limit > self.limits.page_max:
            raise OperationError(
                "invalid_input",
                "PAGE_LIMIT_EXCEEDED",
                "Read page exceeds trusted host limit",
            )
        page = items[offset : offset + limit]
        next_cursor = (
            base64.urlsafe_b64encode(
                encode(
                    {"query_bytes_sha256": query_bytes_sha256, "offset": offset + limit}
                ).encode()
            ).decode()
            if offset + limit < len(items)
            else None
        )
        return page, next_cursor

    def read(self, args: JSON, subject: JSON) -> JSON:
        sid = args["system_id"]
        definition, module, _ = self.active(sid)
        store = Store.open(self.backend(sid))
        history = args.get("history") or store.current_history().as_dict()
        if args.get("history") is not None:
            if history["position"] == 0:
                descriptor = self.metadata(sid, "descriptor")
                if descriptor is None:
                    raise OperationError(
                        "infrastructure",
                        "HISTORICAL_BINDING_MISSING",
                        "Initial definition is unavailable",
                    )
                historical_definition_id = descriptor["definition_id"]
            else:
                with connect(self.artifacts.system_path(sid)) as db:
                    rows = db.execute("SELECT document FROM host_operations").fetchall()
                operation_records = [json.loads(row["document"]) for row in rows]
                historical = next(
                    (
                        op
                        for op in operation_records
                        if op["kind"] == "transition"
                        and op["status"] == "committed"
                        and op["receipt"]["record_id"] == history["record"]
                    ),
                    None,
                )
                if historical is None:
                    raise OperationError(
                        "infrastructure",
                        "HISTORICAL_BINDING_MISSING",
                        "Original committed definition binding is unavailable",
                    )
                historical_definition_id = historical["definition_id"]
            from .authoring import historical_module

            definition, module = historical_module(
                self.artifacts, historical_definition_id
            )
        # export_seed_at validates the complete snapshot and exact supplied Core anchor.
        store.export_seed_at(module, history)
        state = store.state_at(history["position"])
        wire = json.loads(module.to_wire_json())
        entities = (
            [args["entity"]]
            if args.get("entity")
            else [e["name"] for e in wire["entities"]]
        )
        records: list[JSON] = []
        for entity in sorted(entities):
            keys = (
                [{"entity": entity, "id": args["record_id"]}]
                if args.get("record_id")
                else self.backend(sid).keys_at(entity, history["position"])
            )
            records.extend(store.load(entity, key["id"], at=state) for key in keys)
        scope = {
            "kind": "state",
            "system_id": sid,
            "history": history,
            "entity": args.get("entity"),
            "record_id": args.get("record_id"),
        }
        page, cursor = self.page(records, args, scope)
        subject.update(self.subject(sid, definition, history))
        return self.response(
            "read",
            "read",
            subject,
            {
                "kind": "state_page",
                "system_id": sid,
                "read_definition_id": definition["definition_id"],
                "behavior_hash": definition["behavior_hash"],
                "schema_hash": definition["schema_hash"],
                "history_anchor": history,
                "records": page,
                "next_cursor": cursor,
                "release": definition["release"],
            },
        )

    def replay(self, system_id: str) -> JSON:
        """Caller holds the coordinated system boundary; Core checks historical meaning."""
        from dataclasses import asdict

        from behavior import replay_behavior, replay_data

        from .authoring import historical_module

        self.policy.authorize(self.context, "system_recover", system_id)
        descriptor = self.metadata(system_id, "descriptor")
        if descriptor is None:
            raise OperationError(
                "infrastructure",
                "SYSTEM_DESCRIPTOR_MISSING",
                "System descriptor is unavailable",
            )
        with connect(self.artifacts.system_path(system_id)) as db:
            rows = db.execute(
                "SELECT document FROM activations ORDER BY revision"
            ).fetchall()
        activations = [json.loads(row["document"]) for row in rows]
        ids = list(
            dict.fromkeys(
                [
                    descriptor["definition_id"],
                    *[a["definition_id"] for a in activations],
                ]
            )
        )
        definitions = []
        modules = {}
        for identity in ids:
            definition, module = historical_module(self.artifacts, identity)
            definitions.append(
                {
                    "definition_id": identity,
                    "behavior_hash": definition["behavior_hash"],
                    "schema_hash": definition["schema_hash"],
                    "model_hashes": [m["model_hash"] for m in definition["models"]],
                    "source": definition["source"],
                    "release": definition["release"],
                }
            )
            modules[module.behavior_version] = module
        for activation in activations:
            self.artifacts.policy(
                activation["policy"]["policy_id"],
                activation["policy"]["policy_version"],
            )
            self.artifacts.get(activation["authorization_ref"])
            self.artifacts.get(activation["request_binding_ref"])
            for ref in (
                activation["validation_evidence_refs"]
                + activation["verification_evidence_refs"]
            ):
                self.artifacts.get(ref)
        store = Store.open(self.backend(system_id))
        data = replay_data(store)
        behavior = replay_behavior(store, list(modules.values()))
        if not data.ok or not behavior.ok:
            raise OperationError(
                "infrastructure",
                "HISTORICAL_REPLAY_FAILED",
                "Core replay did not establish historical equivalence",
            )
        return {
            "data": asdict(data),
            "behavior": asdict(behavior),
            "definitions": definitions,
            "release": release_identity(),
            "model_provenance": "retained original lowering receipts; Wire replay validates admitted Core behavior identities",
        }
