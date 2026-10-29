"""Workspace-scoped immutable artifacts and trusted host policy versions."""

import hashlib
import json
import re
from pathlib import Path

from .schemas import JSON, OperationError
from .storage import connect, file_lock, transaction


def encode(value: JSON) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "host.sqlite"
        with connect(self.path) as db, transaction(db):
            db.execute(
                "CREATE TABLE IF NOT EXISTS blobs (id TEXT PRIMARY KEY, kind TEXT NOT NULL, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS policies (id TEXT, version INTEGER, document TEXT NOT NULL, PRIMARY KEY(id,version))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations (operation_id TEXT PRIMARY KEY, system_id TEXT UNIQUE NOT NULL, request TEXT NOT NULL, principal TEXT NOT NULL)"
            )

    def put(self, kind: str, value: JSON, *, identity: str | None = None) -> str:
        document = encode(value)
        identity = (
            identity
            or "bytes-sha256:"
            + hashlib.sha256((kind + "\n" + document).encode()).hexdigest()
        )
        with connect(self.path) as db, transaction(db):
            prior = db.execute(
                "SELECT kind,document FROM blobs WHERE id=?", (identity,)
            ).fetchone()
            if prior and (prior["kind"] != kind or prior["document"] != document):
                raise OperationError(
                    "conflict", "IMMUTABLE_ARTIFACT", "Artifact cannot be overwritten"
                )
            db.execute(
                "INSERT OR IGNORE INTO blobs VALUES (?,?,?)", (identity, kind, document)
            )
        return identity

    def get(self, identity: str) -> JSON:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT kind,document FROM blobs WHERE id=?", (identity,)
            ).fetchone()
        if row is None:
            raise OperationError(
                "invalid_input",
                "ARTIFACT_NOT_FOUND",
                "Artifact is unavailable in this workspace",
            )
        if identity.startswith("bytes-sha256:"):
            actual = (
                "bytes-sha256:"
                + hashlib.sha256(
                    (row["kind"] + "\n" + row["document"]).encode()
                ).hexdigest()
            )
            if actual != identity:
                raise OperationError(
                    "infrastructure",
                    "ARTIFACT_BYTES_CHANGED",
                    "Stored artifact bytes differ from their physical identity",
                )
        return dict(json.loads(row["document"]))

    def install_policy(self, document: JSON) -> None:
        with (
            file_lock(self.root / "policy.lock"),
            connect(self.path) as db,
            transaction(db),
        ):
            prior = db.execute(
                "SELECT document FROM policies WHERE id=? AND version=?",
                (document["policy_id"], document["version"]),
            ).fetchone()
            text = encode(document)
            if prior and prior["document"] != text:
                raise OperationError(
                    "conflict",
                    "IMMUTABLE_POLICY",
                    "Policy version cannot be overwritten",
                )
            latest = db.execute(
                "SELECT MAX(version) FROM policies WHERE id=?", (document["policy_id"],)
            ).fetchone()[0]
            if latest is not None and document["version"] < latest:
                raise OperationError(
                    "conflict", "STALE_POLICY", "Cannot install an older policy version"
                )
            db.execute(
                "INSERT OR IGNORE INTO policies VALUES (?,?,?)",
                (document["policy_id"], document["version"], text),
            )

    def policy(self, policy_id: str, version: int | None = None) -> JSON:
        with connect(self.path) as db:
            if version is None:
                row = db.execute(
                    "SELECT document FROM policies WHERE id=? ORDER BY version DESC LIMIT 1",
                    (policy_id,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT document FROM policies WHERE id=? AND version=?",
                    (policy_id, version),
                ).fetchone()
        if row is None:
            raise OperationError(
                "unauthorized", "POLICY_MISSING", "Trusted policy is unavailable"
            )
        return dict(json.loads(row["document"]))

    def propose(
        self,
        proposal: JSON,
        *,
        base_proposal_id: str | None = None,
        expected_proposal_revision: int | None = None,
        parent_definition_id: str | None = None,
    ) -> JSON:
        import copy
        import uuid

        from .adapters import construction_context, validate_proposal

        validate_proposal(proposal)
        if (base_proposal_id is None) != (expected_proposal_revision is None):
            raise OperationError(
                "invalid_input",
                "BASE_REVISION_REQUIRED",
                "Base proposal and expected revision are required together",
            )
        if parent_definition_id is not None:
            self.definition(parent_definition_id)
        original = copy.deepcopy(proposal)
        metadata = original.pop("metadata", {})
        with connect(self.path) as db, transaction(db):
            self._proposal_tables(db)
            if base_proposal_id is None:
                proposal_id = "proposal-" + uuid.uuid4().hex
                revision = 1
            else:
                proposal_id = base_proposal_id
                row = db.execute(
                    "SELECT revision,document FROM proposals WHERE id=? ORDER BY revision DESC LIMIT 1",
                    (proposal_id,),
                ).fetchone()
                if row is None or row["revision"] != expected_proposal_revision:
                    raise OperationError(
                        "conflict",
                        "PROPOSAL_HEAD_MOVED",
                        "Proposal revision is stale or unavailable",
                    )
                prior = json.loads(row["document"])
                if (
                    parent_definition_id is not None
                    and parent_definition_id != prior["parent_definition_id"]
                ):
                    raise OperationError(
                        "conflict",
                        "PROPOSAL_PARENT_CHANGED",
                        "A changed parent requires a new proposal",
                    )
                parent_definition_id = prior["parent_definition_id"]
                revision = row["revision"] + 1
            snapshot = {
                "kind": "proposal",
                "proposal_id": proposal_id,
                "proposal_revision": revision,
                "parent_definition_id": parent_definition_id,
                "proposal": original,
                "construction_context": construction_context(original),
                "metadata": metadata,
            }
            db.execute(
                "INSERT INTO proposals VALUES (?,?,?)",
                (proposal_id, revision, encode(snapshot)),
            )
        return snapshot

    @staticmethod
    def _proposal_tables(db: object) -> None:
        # The connection is supplied only by connect(); this annotation is refined below.
        import sqlite3

        assert isinstance(db, sqlite3.Connection)
        db.execute(
            "CREATE TABLE IF NOT EXISTS proposals (id TEXT, revision INTEGER, document TEXT NOT NULL, PRIMARY KEY(id,revision))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS definitions (proposal_id TEXT, revision INTEGER, definition_id TEXT UNIQUE NOT NULL, PRIMARY KEY(proposal_id,revision))"
        )

    def proposal(self, proposal_id: str, revision: int | None = None) -> JSON:
        with connect(self.path) as db:
            self._proposal_tables(db)
            row = db.execute(
                "SELECT document FROM proposals WHERE id=? "
                + (
                    "ORDER BY revision DESC LIMIT 1"
                    if revision is None
                    else "AND revision=?"
                ),
                (proposal_id,) if revision is None else (proposal_id, revision),
            ).fetchone()
        if row is None:
            raise OperationError(
                "invalid_input",
                "PROPOSAL_NOT_FOUND",
                "Proposal revision is unavailable in this workspace",
            )
        return dict(json.loads(row["document"]))

    def publish_definition(self, manifest: JSON) -> JSON:
        source = manifest["source"]
        with connect(self.path) as db, transaction(db):
            self._proposal_tables(db)
            prior = db.execute(
                "SELECT definition_id FROM definitions WHERE proposal_id=? AND revision=?",
                (source["proposal_id"], source["proposal_revision"]),
            ).fetchone()
            if prior:
                row = db.execute(
                    "SELECT document FROM blobs WHERE id=?", (prior["definition_id"],)
                ).fetchone()
                existing = dict(json.loads(row["document"]))
                candidate = dict(manifest, definition_id=existing["definition_id"])
                if candidate != existing:
                    raise OperationError(
                        "conflict",
                        "RECONSTRUCTION_MISMATCH",
                        "Authoritative reconstruction differs from stored definition",
                    )
                return existing
            db.execute(
                "INSERT INTO blobs VALUES (?,?,?)",
                (manifest["definition_id"], "definition", encode(manifest)),
            )
            db.execute(
                "INSERT INTO definitions VALUES (?,?,?)",
                (
                    source["proposal_id"],
                    source["proposal_revision"],
                    manifest["definition_id"],
                ),
            )
        return manifest

    def definition(self, definition_id: str) -> JSON:
        definition = self.get(definition_id)
        if definition.get("kind") != "definition":
            raise OperationError(
                "invalid_input",
                "DEFINITION_REQUIRED",
                "An admitted definition is required",
            )
        return definition

    def inspect_definition(self, definition_id: str, workspace_id: str) -> JSON:
        from .adapters import historical_module
        from .schemas import validate_verification

        definition, _ = historical_module(self, definition_id)
        source = self.proposal(
            definition["source"]["proposal_id"],
            definition["source"]["proposal_revision"],
        )
        context = self.get(definition["construction_context_ref"])
        if source["construction_context"] != context:
            raise OperationError(
                "infrastructure",
                "EVIDENCE_MISMATCH",
                "Retained source and construction context differ",
            )
        linked = [
            (definition["module_ref"], "module"),
            (definition["construction_context_ref"], "construction_context"),
        ]
        linked.extend(
            (m["receipt_ref"], "lowering_receipt") for m in definition["models"]
        )
        if definition.get("inventory_ref"):
            linked.append((definition["inventory_ref"], "capability_inventory"))
        if definition.get("safety_analysis_ref"):
            linked.append((definition["safety_analysis_ref"], "safety_analysis"))
        artifacts = [
            {"artifact_ref": ref, "kind": kind, "document": self.get(ref)}
            for ref, kind in linked
        ]
        evidence = []
        for kind in (
            "validation_evidence",
            "verification_evidence",
            "safety_assessment_evidence",
        ):
            for ref, document in self.find(kind):
                subject = document["subject"]
                # System-specific deployment evidence is not exposed through a shared definition.
                if (
                    subject.get("definition_id") != definition_id
                    or subject.get("workspace_id") != workspace_id
                    or "system_id" in subject
                ):
                    continue
                if any(
                    subject.get(k) != definition[k]
                    for k in ("behavior_hash", "schema_hash", "release")
                ):
                    raise OperationError(
                        "infrastructure",
                        "EVIDENCE_MISMATCH",
                        "Stored evidence differs from its retained definition",
                    )
                if kind == "verification_evidence":
                    validate_verification(document["report"], subject)
                evidence.append(
                    {"artifact_ref": ref, "kind": kind, "document": document}
                )
        return {
            "kind": "definition_inspection",
            "definition": definition,
            "source": source,
            "artifacts": artifacts,
            "evidence": evidence,
        }

    def bind_operation(
        self,
        operation_id: str,
        system_id: str,
        principal: str,
        kind: str,
        request: JSON,
        *,
        create_capacity: int | None = None,
    ) -> None:
        with connect(self.path) as db, transaction(db):
            db.execute(
                "CREATE TABLE IF NOT EXISTS operation_bindings (id TEXT PRIMARY KEY,system_id TEXT,principal TEXT,kind TEXT,request TEXT)"
            )
            prior = db.execute(
                "SELECT * FROM operation_bindings WHERE id=?", (operation_id,)
            ).fetchone()
            candidate = (system_id, principal, kind, encode(request))
            if prior:
                if (
                    tuple(
                        prior[k] for k in ("system_id", "principal", "kind", "request")
                    )
                    != candidate
                ):
                    raise OperationError(
                        "conflict",
                        "OPERATION_REUSE",
                        "OperationId is already bound to a different request or scope",
                    )
                return
            if create_capacity is not None:
                count = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
                if count >= create_capacity:
                    raise OperationError(
                        "unauthorized",
                        "SYSTEM_CAPACITY",
                        "System creation exceeds trusted capacity",
                    )
                db.execute(
                    "INSERT INTO reservations VALUES (?,?,?,?)",
                    (operation_id, system_id, encode(request), principal),
                )
            db.execute(
                "INSERT INTO operation_bindings VALUES (?,?,?,?,?)",
                (operation_id, *candidate),
            )

    def operation_binding(self, operation_id: str) -> JSON | None:
        with connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS operation_bindings (id TEXT PRIMARY KEY,system_id TEXT,principal TEXT,kind TEXT,request TEXT)"
            )
            row = db.execute(
                "SELECT * FROM operation_bindings WHERE id=?", (operation_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["request"] = json.loads(result["request"])
        return result

    def system_ids(self) -> list[str]:
        with connect(self.path) as db:
            return [
                row["system_id"]
                for row in db.execute(
                    "SELECT system_id FROM reservations ORDER BY system_id"
                )
            ]

    def system_path(self, system_id: str) -> Path:
        # Never interpolate a caller identifier into a path without resolving its host reservation.
        with connect(self.path) as db:
            row = db.execute(
                "SELECT system_id FROM reservations WHERE system_id=?", (system_id,)
            ).fetchone()
        if row is None:
            raise OperationError(
                "invalid_input",
                "SYSTEM_NOT_FOUND",
                "System is unavailable in this workspace",
            )
        if not re.fullmatch(r"system-[0-9a-f]{32}", row["system_id"]):
            raise OperationError(
                "infrastructure",
                "INVALID_SYSTEM_CATALOG",
                "Host system catalog is inconsistent",
            )
        return self.root / "systems" / (str(row["system_id"]) + ".sqlite")

    def find(self, kind: str) -> list[tuple[str, JSON]]:
        with connect(self.path) as db:
            rows = db.execute(
                "SELECT id,document FROM blobs WHERE kind=? ORDER BY id", (kind,)
            ).fetchall()
        return [(row["id"], self.get(row["id"])) for row in rows]

    def approvals(self) -> list[JSON]:
        with connect(self.path) as db:
            rows = db.execute("SELECT document FROM approvals ORDER BY id").fetchall()
        return [dict(json.loads(row["document"])) for row in rows]
