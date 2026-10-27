"""Durable implementation of the pinned public Core Backend storage callbacks.

Documents and identities originate in Core. SQL indexes implement as-of lookup only.
"""

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

from .artifacts import encode
from .schemas import JSON
from .storage import connect, transaction


class SQLiteBackend:
    def __init__(
        self,
        path: Path,
        *,
        fault: Callable[[str], None] | None = None,
        operation: JSON | None = None,
    ) -> None:
        self.path = path
        self.fault = fault or (lambda _: None)
        self.operation = operation
        with connect(path) as db, transaction(db):
            db.execute(
                "CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS core_versions (entity TEXT, id TEXT, revision INTEGER, created_at INTEGER, document TEXT NOT NULL, PRIMARY KEY(entity,id,revision))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS core_records (position INTEGER PRIMARY KEY, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS core_removed (entity TEXT, id TEXT, position INTEGER, PRIMARY KEY(entity,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS core_edges (target_entity TEXT,target_id TEXT,source_entity TEXT,source_id TEXT,field TEXT,added INTEGER,dropped INTEGER)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS host_operations (id TEXT PRIMARY KEY, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS system_meta (key TEXT PRIMARY KEY, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS activations (revision INTEGER PRIMARY KEY, document TEXT NOT NULL)"
            )

    @staticmethod
    def _meta(db: sqlite3.Connection, key: str) -> JSON | None:
        row = db.execute(
            "SELECT document FROM core_meta WHERE key=?", (key,)
        ).fetchone()
        return dict(json.loads(row["document"])) if row else None

    def genesis(self) -> JSON | None:
        with connect(self.path) as db:
            return self._meta(db, "genesis")

    def head(self) -> JSON | None:
        with connect(self.path) as db:
            return self._meta(db, "head")

    @staticmethod
    def _versions(db: sqlite3.Connection, versions: list[JSON]) -> None:
        for v in versions:
            db.execute(
                "INSERT INTO core_versions VALUES (?,?,?,?,?)",
                (v["entity"], v["id"], v["revision"], v["created_at"], encode(v)),
            )

    @staticmethod
    def _references(db: sqlite3.Connection, changes: list[JSON], position: int) -> None:
        for change in changes:
            key = (
                change["target"]["entity"],
                change["target"]["id"],
                change["source"]["entity"],
                change["source"]["id"],
                change["field"],
            )
            if change["op"] == "add":
                db.execute(
                    "INSERT INTO core_edges VALUES (?,?,?,?,?,?,NULL)", (*key, position)
                )
            else:
                db.execute(
                    "UPDATE core_edges SET dropped=? WHERE rowid=(SELECT rowid FROM core_edges WHERE target_entity=? AND target_id=? AND source_entity=? AND source_id=? AND field=? AND dropped IS NULL LIMIT 1)",
                    (position, *key),
                )

    def create(
        self, genesis: JSON, head: JSON, seed: list[JSON], seed_refs: list[JSON]
    ) -> None:
        # Keyed storage products ignore enumeration order, as the public callback contract permits.
        product = {
            "genesis": genesis,
            "head": head,
            "seed": sorted(seed, key=lambda v: (v["entity"], v["id"], v["revision"])),
            "references": sorted(seed_refs, key=encode),
        }
        with connect(self.path) as db, transaction(db):
            existing = self._meta(db, "creation")
            if existing is not None:
                if existing != product:
                    raise ValueError("Conflicting original Store creation")
                return
            if self._meta(db, "genesis") is not None:
                raise ValueError("Incomplete original creation product")
            self._versions(db, seed)
            self._references(db, seed_refs, 0)
            for k, v in [("genesis", genesis), ("head", head), ("creation", product)]:
                db.execute("INSERT INTO core_meta VALUES (?,?)", (k, encode(v)))
            self.fault("create_before_commit")
        self.fault("create_after_commit")

    def version_at(self, key: JSON, position: int) -> JSON | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT document FROM core_versions WHERE entity=? AND id=? AND created_at<=? ORDER BY created_at DESC LIMIT 1",
                (key["entity"], key["id"], position),
            ).fetchone()
        return dict(json.loads(row["document"])) if row else None

    def version(self, key: JSON, revision: int) -> JSON | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT document FROM core_versions WHERE entity=? AND id=? AND revision=?",
                (key["entity"], key["id"], revision),
            ).fetchone()
        return dict(json.loads(row["document"])) if row else None

    def removed_at(self, key: JSON) -> int | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT position FROM core_removed WHERE entity=? AND id=?",
                (key["entity"], key["id"]),
            ).fetchone()
        return int(row["position"]) if row else None

    def incoming_at(self, target: JSON, position: int) -> list[JSON]:
        with connect(self.path) as db:
            rows = db.execute(
                "SELECT source_entity AS entity,source_id AS id,field FROM core_edges WHERE target_entity=? AND target_id=? AND added<=? AND (dropped IS NULL OR dropped>?) ORDER BY source_entity,source_id,field",
                (target["entity"], target["id"], position, position),
            ).fetchall()
        return [dict(row) for row in rows]

    def keys_at(self, entity_type: str, position: int) -> list[JSON]:
        with connect(self.path) as db:
            rows = db.execute(
                "SELECT DISTINCT v.entity,v.id FROM core_versions v LEFT JOIN core_removed r ON r.entity=v.entity AND r.id=v.id WHERE v.entity=? AND v.created_at<=? AND (r.position IS NULL OR r.position>?) ORDER BY v.id",
                (entity_type, position, position),
            ).fetchall()
        return [dict(row) for row in rows]

    def record(self, position: int) -> JSON | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT document FROM core_records WHERE position=?", (position,)
            ).fetchone()
        return dict(json.loads(row["document"])) if row else None

    def commit(
        self,
        expected: str,
        versions: list[JSON],
        removals: list[JSON],
        ref_changes: list[JSON],
        record: JSON,
        head: JSON,
    ) -> str:
        with connect(self.path) as db, transaction(db):
            prior = self._meta(db, "head")
            if prior is None or prior["last_record"] != expected:
                return "head_moved"
            position = head["state_ref"]["position"]
            self._versions(db, versions)
            for key in removals:
                db.execute(
                    "INSERT OR IGNORE INTO core_removed VALUES (?,?,?)",
                    (key["entity"], key["id"], position),
                )
            self._references(db, ref_changes, position)
            db.execute(
                "INSERT INTO core_records VALUES (?,?)", (position, encode(record))
            )
            db.execute(
                "UPDATE core_meta SET document=? WHERE key=?", (encode(head), "head")
            )
            if self.operation is not None:
                operation = dict(self.operation)
                source = operation["source_history"]
                receipt = {
                    "operation_id": operation["operation_id"],
                    "record_id": head["last_record"],
                    "result_state": head["state_ref"],
                    "definition_id": operation["definition_id"],
                    "behavior_hash": operation["behavior_hash"],
                    "history_anchor": {
                        "format": "behavior.history_ref.v1",
                        "store": source["store"],
                        "state": head["state_ref"]["state"],
                        "position": position,
                        "record": head["last_record"],
                    },
                }
                operation.update(status="committed", receipt=receipt)
                db.execute(
                    "INSERT OR REPLACE INTO host_operations VALUES (?,?)",
                    (operation["operation_id"], encode(operation)),
                )
            self.fault("commit_before_commit")
        self.fault("commit_after_commit")
        return "applied"
