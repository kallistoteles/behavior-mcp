from itertools import count

import pytest
from behavior import CommitRefused, Store, run_conformance

from behavior_mcp.sqlite_backend import SQLiteBackend
from tests.fixtures.public_models import SEED, reference_module


def test_all_public_backend_conformance_cases(tmp_path):
    ids = count()
    report = run_conformance(
        lambda: SQLiteBackend(tmp_path / f"case-{next(ids)}.sqlite")
    )
    assert len(report.cases) == 45
    assert report.ok, report.failed()
    assert any(
        name == "creation_lost_ack_recovery" and ok for name, ok, _ in report.cases
    )
    assert not hasattr(
        SQLiteBackend, "keys_by_field_at"
    )  # Core's supported index fallback.


def test_public_core_can_acknowledge_already_with_publication_disabled(tmp_path):
    model = reference_module()
    backend = SQLiteBackend(tmp_path / "guarded.sqlite")
    store = Store.create(backend, model, Store.genesis_for(model, SEED))
    original = store.current_history().as_dict()
    evaluated = store.evaluate(
        model,
        "record__new",
        bindings={},
        input={"request_id": "r1", "label": "Example"},
        context={"actor": "actor-1"},
        commit_time="2026-10-26T00:00:00Z",
    )
    guarded = Store.open(SQLiteBackend(backend.path, allow_publication=False))
    with pytest.raises(CommitRefused) as error:
        guarded.commit(model, evaluated.bundle)
    assert error.value.code == "BACKEND_ERROR"
    assert store.current_history().as_dict() == original
    committed = store.commit(model, evaluated.bundle)
    acknowledged = guarded.commit(model, evaluated.bundle)
    assert acknowledged.already and acknowledged.record_id == committed.record_id
    assert store.current_history().as_dict()["position"] == 1
