"""Research-only reproduction of retained adapter byte-identity coupling.

Run from repository root with .venv/bin/python -B <this file>. No production
files are modified. The temporary changed source path is never imported.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from behavior_mcp import authoring
from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.policy import Delegation, TrustedContext
from behavior_mcp.server import Application

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "specs/001-agent-native-systems/contracts"


def main():
    proposal = json.loads((CONTRACTS / "example-proposal.json").read_text())
    policy_document = json.loads((CONTRACTS / "example-host-policy.json").read_text())
    context = TrustedContext(
        "agent-session", "workspace-1", "actor-1", lambda: "2026-10-26T00:00:00Z"
    )
    original_path = authoring.__file__
    source = Path(original_path).read_bytes()
    results = {
        "adapter_sha256": hashlib.sha256(source).hexdigest(),
        "released_behavior": authoring.release_identity(),
    }
    with tempfile.TemporaryDirectory(
        prefix="behavior-mcp-compatibility-probe-"
    ) as temporary:
        temporary_path = Path(temporary)
        root = temporary_path / "workspace"
        root.mkdir()
        artifacts = ArtifactStore(root)
        delegation = Delegation.from_document(policy_document, "local-operator")
        artifacts.install_policy(delegation.document)
        app = Application(root, context, "local-delegation")
        saved = app.execute("definition_propose", {"proposal": proposal})["result"]
        validated = app.execute(
            "definition_validate",
            {"proposal_id": saved["proposal_id"], "proposal_revision": 1},
        )
        assert validated["outcome"] == "admitted", validated
        definition = validated["result"]["definition"]
        created = app.execute(
            "systems_create",
            {"definition_id": definition["definition_id"], "operation_id": "create"},
        )
        assert created["outcome"] == "created", created
        receipt = created["result"]["receipt"]
        system_id = receipt["system_id"]
        activated = app.execute(
            "definition_activate",
            {
                "system_id": system_id,
                "definition_id": definition["definition_id"],
                "expected_activation_revision": 0,
                "expected_history": receipt["history_anchor"],
                "operation_id": "activate",
            },
        )
        assert activated["outcome"] == "activated", activated
        candidate_path = temporary_path / "authoring-with-extra-newline.py"
        candidate_path.write_bytes(source + b"\n")
        before = authoring.construction_context(proposal)
        try:
            authoring.__file__ = str(candidate_path)
            after = authoring.construction_context(proposal)
            assert before["adapter_code_identity"] != after["adapter_code_identity"]
            probes = {
                "read_retained_definition": (
                    "definition_get",
                    {"definition_id": definition["definition_id"]},
                ),
                "revalidate_retained_source": (
                    "definition_validate",
                    {"proposal_id": saved["proposal_id"], "proposal_revision": 1},
                ),
                "discover_active_capabilities": (
                    "capabilities_list",
                    {"system_id": system_id},
                ),
                "recover_active_system": ("system_recover", {"system_id": system_id}),
            }
            results["with_only_source_byte_identity_changed"] = {}
            for label, (name, arguments) in probes.items():
                response = app.execute(name, arguments)
                results["with_only_source_byte_identity_changed"][label] = {
                    "request_status": response["request_status"],
                    "outcome": response["outcome"],
                    "error_code": response["error"]["code"]
                    if response["error"]
                    else None,
                }
        finally:
            authoring.__file__ = original_path
        restored = app.execute("capabilities_list", {"system_id": system_id})
        assert restored["request_status"] == "completed", restored
        results["restoring_original_context_restores_runtime"] = True
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
