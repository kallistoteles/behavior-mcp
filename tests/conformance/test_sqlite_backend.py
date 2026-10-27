from itertools import count

from behavior import run_conformance

from behavior_mcp.sqlite_backend import SQLiteBackend


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
