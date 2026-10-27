import pytest
from behavior import Store, replay_data

from behavior_mcp.sqlite_backend import SQLiteBackend
from tests.fixtures.public_models import SEED, reference_module


@pytest.mark.parametrize(
    "phase,expected", [("create_before_commit", False), ("create_after_commit", True)]
)
def test_creation_crash_is_atomic(tmp_path, subprocess_python, phase, expected):
    path = tmp_path / "system.sqlite"
    script = """import os,sys
from behavior import Store
from behavior_mcp.sqlite_backend import SQLiteBackend
from tests.fixtures.public_models import reference_module,SEED
m=reference_module()
b=SQLiteBackend(__import__('pathlib').Path(sys.argv[1]),fault=lambda stage:os._exit(73) if stage==sys.argv[2] else None)
Store.create(b,m,Store.genesis_for(m,SEED))
"""
    run = subprocess_python(script, path, phase)
    assert run.returncode == 73
    b = SQLiteBackend(path)
    assert (b.genesis() is not None) == expected
    if expected:
        assert Store.open(b).current().position == 0


@pytest.mark.parametrize(
    "phase,position", [("commit_before_commit", 0), ("commit_after_commit", 1)]
)
def test_transition_crash_is_atomic(tmp_path, subprocess_python, phase, position):
    path = tmp_path / "system.sqlite"
    m = reference_module()
    Store.create(SQLiteBackend(path), m, Store.genesis_for(m, SEED))
    script = """import os,sys
from behavior import Store
from behavior_mcp.sqlite_backend import SQLiteBackend
from tests.fixtures.public_models import reference_module
m=reference_module();b=SQLiteBackend(__import__('pathlib').Path(sys.argv[1]),fault=lambda stage:os._exit(74) if stage==sys.argv[2] else None);s=Store.open(b)
e=s.evaluate(m,'record__new',bindings={},input={'request_id':'r1','label':'Example'},context={'actor':'actor-1'},commit_time='2026-10-26T00:00:00Z');s.commit(m,e.bundle)
"""
    assert subprocess_python(script, path, phase).returncode == 74
    store = Store.open(SQLiteBackend(path))
    assert store.current().position == position
    assert replay_data(store).ok
    assert len(list(store.history())) == position
