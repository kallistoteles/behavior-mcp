import copy
from pathlib import Path

import behavior
import pytest

from behavior_mcp.dependencies import (
    DependencyError,
    audit_imports,
    check_dependencies,
    verify_versions,
)


def test_installed_release_and_public_interfaces():
    check_dependencies()


@pytest.mark.parametrize(
    "path,bad",
    [
        ("binding.python", "0.13.0"),
        ("core.version", "0.14.0"),
        ("core.commit", "0" * 40),
        ("verifier", "0.9.0"),
    ],
)
def test_substituted_identities_fail(path, bad):
    versions = copy.deepcopy(behavior.versions())
    keys = path.split(".")
    target = versions
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = bad
    with pytest.raises(DependencyError):
        verify_versions(versions)


@pytest.mark.parametrize(
    "source",
    [
        "from behavior import _engine",
        "import behavior._engine",
        "from behavior.models._internal import lower",
        "from behavior import unknown_private_surface",
    ],
)
def test_private_or_undeclared_interfaces_rejected(tmp_path, source):
    p = tmp_path / "consumer.py"
    p.write_text(source)
    with pytest.raises(DependencyError):
        audit_imports(tmp_path)


def test_public_imports_allowed(tmp_path):
    (tmp_path / "consumer.py").write_text(
        "from behavior import Store, RequestFlow, StateMachine\n"
    )
    audit_imports(tmp_path)


def test_modified_release_files_rejected(monkeypatch):
    import importlib.metadata

    dist = importlib.metadata.distribution("behavior")
    module = Path(str(dist.locate_file("behavior/__init__.py")))
    original_read = Path.read_bytes

    def changed_read(path):
        data = original_read(path)
        return data + b"\n# altered distribution\n" if path == module else data

    # Inject a read fault; never mutate an installed file or uv's shared package cache.
    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(DependencyError, match="Released Behavior file changed"):
        check_dependencies()


def test_source_graph_has_no_checkout_override():
    root = Path(__file__).resolve().parents[2]
    audit_imports(root / "src")
    graph = (root / "uv.lock").read_text()
    assert 'editable = "."' in graph
    assert "github.com/kallistoteles/behavior-ir/releases/download/v0.14.0/" in graph
    assert "794d2dd5ddf8613c52f524a1b4b74c0246d86a5ea52414424ab89ef104e86513" in graph
    assert "/home/" not in graph
    assert "git = " not in graph


def test_public_fixtures_admit_and_compose():
    from tests.fixtures.public_models import reference_module

    first = reference_module()
    composed = reference_module(compose=True)
    assert len(first.model_receipts) == 1
    assert len(composed.model_receipts) == 2
    assert (
        first.model_receipts[0].model_hash
        == next(
            r for r in composed.model_receipts if r.model_kind == "request_flow"
        ).model_hash
    )
    assert first.behavior_version != composed.behavior_version


def test_installed_resources_outside_checkout(tmp_path):
    import subprocess
    import sys

    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "from behavior_mcp.schemas import load_schema; from behavior_mcp.dependencies import check_dependencies; check_dependencies(); assert load_schema('result')['$id']=='urn:behavior-mcp:result:v1'",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr


def test_embedded_server_refuses_a_different_core_release(tmp_path, monkeypatch):
    from behavior_mcp.policy import TrustedContext
    from behavior_mcp.server import Application

    unsupported = copy.deepcopy(behavior.versions())
    unsupported["core"]["version"] = "0.14.0"
    monkeypatch.setattr(behavior, "versions", lambda: unsupported)
    with pytest.raises(DependencyError):
        Application(
            tmp_path,
            TrustedContext(
                "agent-session",
                "workspace-1",
                "actor-1",
                lambda: "2026-10-26T00:00:00Z",
            ),
            "local-delegation",
        )
