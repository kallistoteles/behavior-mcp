import pytest

from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.schemas import OperationError
from behavior_mcp.storage import connect, file_lock, transaction


def test_verified_sqlite_settings_and_rollback(tmp_path):
    with connect(tmp_path / "deep" / "store.sqlite") as db:
        assert db.execute("pragma journal_mode").fetchone()[0] == "delete"
        assert db.execute("pragma synchronous").fetchone()[0] == 3
        assert db.execute("pragma foreign_keys").fetchone()[0] == 1
        db.execute("create table items (v integer)")
        with pytest.raises(RuntimeError):
            with transaction(db):
                db.execute("insert into items values (1)")
                raise RuntimeError("abort")
        assert db.execute("select count(*) from items").fetchone()[0] == 0


def test_workspace_lock_is_exclusive_across_processes(tmp_path, subprocess_python):
    path = tmp_path / "owner.lock"
    with file_lock(path, blocking=False):
        result = subprocess_python(
            'from behavior_mcp.storage import file_lock; import sys\nwith file_lock(__import__("pathlib").Path(sys.argv[1]),blocking=False): pass',
            path,
        )
        assert result.returncode != 0
    with file_lock(path, blocking=False):
        pass


def test_immutable_blobs_and_policies_survive_reopen(tmp_path, policy_document):
    store = ArtifactStore(tmp_path)
    key = store.put("fixture", {"value": 1})
    store.install_policy(policy_document)
    assert ArtifactStore(tmp_path).get(key) == {"value": 1}
    assert ArtifactStore(tmp_path).policy("local-delegation") == policy_document
    with pytest.raises(OperationError):
        store.put("fixture", {"value": 2}, identity=key)
    changed = dict(policy_document, principal_id="impostor")
    with pytest.raises(OperationError):
        store.install_policy(changed)
