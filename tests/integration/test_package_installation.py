"""Exercise a built release and its source rebuild with the declared locked graph."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_built_distribution_outside_checkout(tmp_path):
    commands = []

    def run(command, *, cwd=ROOT, env=None, timeout=900):
        result = subprocess.run(
            command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
        commands.append(
            {
                "command": list(map(str, command)),
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        assert result.returncode == 0, result.stdout + "\n" + result.stderr
        return result

    out = tmp_path / "dist"
    run(
        [
            "uv",
            "build",
            "--no-build-isolation",
            "--python",
            sys.executable,
            "--out-dir",
            str(out),
        ]
    )
    wheel = next(out.glob("*.whl"))
    source = next(out.glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "behavior_mcp/contracts/result.schema.json" in names
        assert "behavior_mcp/release.json" in names
        assert not any(
            n.endswith(".pyc") or "/__pycache__/" in n or n.startswith("behavior/")
            for n in names
        )
        for name in [
            "authoring",
            "tool-request",
            "host-policy",
            "activation-approval",
            "result",
        ]:
            assert (
                archive.read(f"behavior_mcp/contracts/{name}.schema.json")
                == (
                    ROOT
                    / f"specs/001-agent-native-systems/contracts/{name}.schema.json"
                ).read_bytes()
            )
        # Every historical translation closure and its exact public schema ships in the wheel.
        from tests.fixtures.expanded import ROOT as fixture_root

        for checkpoint in (fixture_root / "tests/fixtures/adapter_versions").glob(
            "*/manifest.json"
        ):
            manifest = json.loads(checkpoint.read_text())
            for relative, digest in manifest["closure"].items():
                content = archive.read("behavior_mcp/" + relative)
                assert hashlib.sha256(content).hexdigest() == digest
        for schema in (ROOT / "specs/002-remaining-behavior-models/contracts").glob(
            "*.schema.json"
        ):
            assert (
                archive.read("behavior_mcp/contracts/" + schema.name)
                == schema.read_bytes()
            )
    clean = tmp_path / "installed"
    environment = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(clean))
    environment.pop("PYTHONPATH", None)
    run(["uv", "sync", "--locked", "--no-install-project"], env=environment)
    python = clean / "bin/python"
    run(
        ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
        env=environment,
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    probe = """import json,sys
from pathlib import Path
import behavior_mcp
from behavior_mcp.dependencies import check_dependencies
from behavior_mcp.schemas import load_schema
assert Path(behavior_mcp.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
check_dependencies()
assert load_schema('result')['$id']=='urn:behavior-mcp:result:v1'
print(json.dumps({'installed_origin':str(Path(behavior_mcp.__file__).resolve()),'schemas':'validated','released_dependency_bytes':'validated'}))
"""
    run([str(python), "-c", probe, str(clean)], cwd=outside, env=environment)
    for executable in ["behavior-mcp", "behavior-mcp-admin"]:
        run([str(clean / "bin" / executable), "--help"], cwd=outside, env=environment)
    extracted = tmp_path / "source"
    extracted.mkdir()
    with tarfile.open(source) as archive:
        archive.extractall(extracted, filter="data")
    source_root = next(extracted.iterdir())
    for relative in [
        "specs/002-remaining-behavior-models/evidence/validate_remediation.py",
        "specs/002-remaining-behavior-models/tasks.md",
        "specs/002-remaining-behavior-models/quickstart.md",
    ]:
        assert (source_root / relative).read_bytes() == (ROOT / relative).read_bytes()

    for fixture in (ROOT / "tests/fixtures").glob("**/manifest.json"):
        relative = fixture.relative_to(ROOT)
        assert (source_root / relative).read_bytes() == fixture.read_bytes()
        manifest = json.loads(fixture.read_text())
        for name, digest in manifest.get("workspace_files", {}).items():
            content = (source_root / relative.parent / "workspace" / name).read_bytes()
            assert hashlib.sha256(content).hexdigest() == digest

    rebuilt = tmp_path / "rebuilt"
    run(
        [
            "uv",
            "build",
            "--no-build-isolation",
            "--python",
            str(python),
            "--wheel",
            str(source_root),
            "--out-dir",
            str(rebuilt),
        ],
        cwd=outside,
        env=environment,
    )
    rebuilt_wheel = next(rebuilt.glob("*.whl"))
    assert wheel.read_bytes() == rebuilt_wheel.read_bytes(), (
        "Source-distribution rebuild must reproduce the wheel bytes"
    )
    # The repository path supplies only independent test fixtures. src/ is not on sys.path;
    # the installed-origin assertion above and every worker use the clean wheel environment.
    environment["PYTHONPATH"] = str(ROOT)
    tested = run(
        [
            str(python),
            "-m",
            "pytest",
            "-q",
            "--import-mode=importlib",
            "-p",
            "no:cacheprovider",
            str(ROOT / "tests"),
            "--ignore=" + str(ROOT / "tests/integration/test_package_installation.py"),
        ],
        cwd=outside,
        env=environment,
    )
    assert " skipped" not in tested.stdout
    passed = re.search(r"(\d+) passed", tested.stdout)
    assert passed is not None
    evidence = {
        "scope": "reproducible source/wheel and clean installed consumer environment",
        "wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_rebuild_identical": True,
        "installed_tests_passed": int(passed[1]),
        "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "flake_lock_sha256": hashlib.sha256(
            (ROOT / "flake.lock").read_bytes()
        ).hexdigest(),
        "commands": commands,
    }
    import shutil

    artifacts = ROOT / "dist"
    artifacts.mkdir(exist_ok=True)
    shutil.copy2(wheel, artifacts / wheel.name)
    shutil.copy2(source, artifacts / source.name)
    evidence["wheel_artifact"] = "dist/" + wheel.name
    evidence["source_artifact"] = "dist/" + source.name
    p = ROOT / "specs/002-remaining-behavior-models/evidence/package.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(evidence, indent=2) + "\n")
