"""Deterministic consumer fixtures; no AI service or note client."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs/001-agent-native-systems/contracts"


@pytest.fixture
def proposal():
    return json.loads((CONTRACTS / "example-proposal.json").read_text())


@pytest.fixture
def policy_document():
    return json.loads((CONTRACTS / "example-host-policy.json").read_text())


@pytest.fixture
def fixed_clock():
    return lambda: "2026-10-26T00:00:00Z"


@pytest.fixture
def context(fixed_clock):
    from behavior_mcp.policy import TrustedContext

    return TrustedContext("agent-session", "workspace-1", "actor-1", fixed_clock)


@pytest.fixture
def trusted_setup(tmp_path, policy_document, context):
    from behavior_mcp.artifacts import ArtifactStore
    from behavior_mcp.policy import Delegation

    artifacts = ArtifactStore(tmp_path)
    policy = Delegation.from_document(copy.deepcopy(policy_document), "local-operator")
    artifacts.install_policy(policy.document)
    return tmp_path, context, policy, artifacts


@pytest.fixture
def subprocess_python():
    def run(source, *args, timeout=30):
        return subprocess.run(
            [sys.executable, "-c", source, *map(str, args)],
            env=dict(os.environ),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return run


@pytest.fixture
def semantic_profile_id():
    from tests.fixtures.public_models import reference_module

    return "wire_ir:" + json.loads(reference_module().to_wire_json())["ir_version"]


def pytest_sessionfinish(session, exitstatus):
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None and reporter.stats.get("skipped"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
