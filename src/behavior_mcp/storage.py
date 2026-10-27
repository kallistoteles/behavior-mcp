"""Local host storage and coordination; no domain transition semantics."""

import fcntl
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def durable_directory(path: Path) -> None:
    if not path.exists():
        durable_directory(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
        sync_directory(path.parent)
    sync_directory(path)


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    durable_directory(path.parent)
    new = not path.exists()
    db = sqlite3.connect(path, isolation_level=None, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        if db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
            raise RuntimeError("DELETE journaling required")
        db.execute("PRAGMA synchronous=EXTRA")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=2000")
        if (
            db.execute("PRAGMA synchronous").fetchone()[0] != 3
            or db.execute("PRAGMA foreign_keys").fetchone()[0] != 1
        ):
            raise RuntimeError("Durability settings not established")
        if new:
            os.chmod(path, 0o600)
            sync_directory(path.parent)
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


@contextmanager
def file_lock(
    path: Path, *, shared: bool = False, blocking: bool = True
) -> Iterator[None]:
    durable_directory(path.parent)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(
            fd,
            (fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            | (0 if blocking else fcntl.LOCK_NB),
        )
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
