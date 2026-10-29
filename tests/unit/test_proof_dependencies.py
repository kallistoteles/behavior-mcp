"""Proof tools are exact optional dependencies; ordinary execution is unaffected."""

import json
import os
from pathlib import Path

import pytest

from behavior_mcp import dependencies

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = json.loads(
    (
        ROOT / "specs/002-remaining-behavior-models/evidence/proof_toolchain.json"
    ).read_text()
)["profiles"]["x86_64-linux"]


def readiness():
    check = getattr(dependencies, "check_proof_dependencies", None)
    assert callable(check), "Missing exact proof toolchain readiness boundary"
    return check()


def test_exact_proof_lock_and_runtime(monkeypatch):
    lock = json.loads((ROOT / "flake.lock").read_text())
    root = lock["nodes"][lock["root"]]["inputs"]
    assert "behavior-proof" in root, "Proof input is absent from declared Nix graph"
    node = lock["nodes"][root["behavior-proof"]]["locked"]
    assert node["rev"] == "1cba9e16ff73f927ae08e70a7bc74a6ca52355e4"
    monkeypatch.setenv("BEHAVIOR_SAFETY_TOOLCHAIN", EXPECTED["outPath"])
    monkeypatch.setenv("BEHAVIOR_SAFETY_TOOLCHAIN_DRV", EXPECTED["drvPath"])
    assert readiness()["version"] == "4.30.0"


@pytest.mark.parametrize("key", ["BEHAVIOR_LEAN_BINARY", "BEHAVIOR_LEANCHECKER_BINARY"])
def test_binary_overrides_forbidden(monkeypatch, key):
    monkeypatch.setenv(key, "/bin/true")
    with pytest.raises(dependencies.DependencyError):
        readiness()


@pytest.mark.parametrize("path", ["/missing", "/nix/store/incorrect-lean4-4.29.1"])
def test_wrong_or_missing_proof_tools(monkeypatch, path):
    monkeypatch.setenv("BEHAVIOR_SAFETY_TOOLCHAIN", path)
    with pytest.raises(dependencies.DependencyError):
        readiness()


def test_ordinary_runtime_without_proof(monkeypatch):
    for key in os.environ:
        if key.startswith("BEHAVIOR_SAFETY_"):
            monkeypatch.delenv(key)
    dependencies.check_dependencies()
