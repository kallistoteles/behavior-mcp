"""Release provenance and declared public-interface checks shared by startup and gates."""

import ast
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any

import behavior


class DependencyError(RuntimeError):
    """The installed graph does not match the reviewed public release."""


def release_manifest() -> dict[str, Any]:
    return dict(json.loads(files("behavior_mcp").joinpath("release.json").read_text()))


def verify_versions(info: dict[str, Any]) -> None:
    if (
        info.get("binding", {}).get("python") != "0.14.0"
        or info.get("core", {}).get("version") != "0.15.0"
        or info.get("core", {}).get("commit")
        != "6b93898a9375113f7a8946f23ab5535319b6f5d6"
        or info.get("engine") != "0.15.0"
        or info.get("verifier") != "0.10.0"
    ):
        raise DependencyError(
            "Behavior binding/Core/verifier differs from the declared release"
        )


def audit_imports(root: Path) -> None:
    allowed = set(release_manifest()["public_names"])
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("behavior."):
                        raise DependencyError(
                            f"Use declared top-level Behavior interfaces: {path.name}"
                        )
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("behavior.") or (
                    node.module == "behavior"
                    and any(a.name not in allowed for a in node.names)
                ):
                    raise DependencyError(f"Undeclared Behavior interface: {path.name}")


def check_dependencies() -> None:
    verify_versions(behavior.versions())
    dist = importlib.metadata.distribution("behavior")
    manifest = release_manifest()
    direct = json.loads(dist.read_text("direct_url.json") or "{}")
    expected_url = (
        "https://github.com/kallistoteles/behavior-ir/releases/download/v0.14.0/"
        "behavior-0.14.0-cp313-abi3-manylinux_2_28_x86_64.whl"
    )
    if dist.version != "0.14.0" or direct.get("url") != expected_url:
        raise DependencyError("Behavior must originate from the pinned released wheel")
    origin = Path(behavior.__file__).resolve()
    if origin != Path(str(dist.locate_file("behavior/__init__.py"))).resolve():
        raise DependencyError(
            "Behavior import origin differs from installed distribution"
        )
    for name, expected in manifest["files"].items():
        path = Path(str(dist.locate_file(name)))
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise DependencyError(f"Released Behavior file changed: {name}")
    for name in ("mcp", "mcp-types"):
        if importlib.metadata.version(name) != "2.3.0":
            raise DependencyError(f"{name} differs from the declared release")
    audit_imports(Path(__file__).parent)


def check_proof_dependencies() -> dict[str, str]:
    """Require the released proof package only when certification is requested."""
    expected = release_manifest()["proof_toolchain"]
    if any(
        k in os.environ for k in ("BEHAVIOR_LEAN_BINARY", "BEHAVIOR_LEANCHECKER_BINARY")
    ):
        raise DependencyError("Proof binary overrides are forbidden")
    path = os.environ.get("BEHAVIOR_SAFETY_TOOLCHAIN")
    derivation = os.environ.get("BEHAVIOR_SAFETY_TOOLCHAIN_DRV")
    if path is None or path != expected["outPath"] or derivation != expected["drvPath"]:
        raise DependencyError("Proof package differs from the declared release")
    try:
        version = subprocess.run(
            [str(Path(path) / "bin/lean"), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise DependencyError("Declared proof tooling is unavailable") from error
    if (
        re.search(
            r"\bversion " + re.escape(expected["version"]) + r"(?:[ ,)]|$)", version
        )
        is None
    ):
        raise DependencyError("Lean version differs from the declared release")
    if not (Path(path) / "bin/leanchecker").is_file():
        raise DependencyError("Declared proof checker is unavailable")
    return dict(expected)


if __name__ == "__main__":
    check_dependencies()
    print("Released dependency identities and public API boundary: PASS")
