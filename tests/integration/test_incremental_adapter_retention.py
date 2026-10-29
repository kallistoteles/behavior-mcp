"""Reopen saved checkpoint workspaces; never regenerate them using a newer adapter."""

import hashlib
import json
import shutil
from pathlib import Path

from behavior_mcp.adapters import reconstruct
from behavior_mcp.artifacts import ArtifactStore
from behavior_mcp.server import Application

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/adapter_versions"


def test_every_published_checkpoint_retains_real_workspace(tmp_path, context):
    from behavior_mcp.adapters import HANDLERS

    for version in HANDLERS:
        fixture = FIXTURES / ("v" + version.replace(".", "_"))
        manifest = json.loads((fixture / "manifest.json").read_text())
        root = tmp_path / version
        shutil.copytree(fixture / "workspace", root)
        store = ArtifactStore(root)
        definition, module, snapshot = reconstruct(store, manifest["definition_id"])
        assert definition["release"]["adapter_version"] == version
        assert definition["behavior_hash"] == manifest["behavior_hash"]
        assert snapshot["construction_context"] == manifest["construction_context"]
        for relative, digest in manifest["closure"].items():
            from behavior_mcp import adapters

            package = Path(adapters.__file__).parent
            path = package / relative
            if relative.startswith("contracts/"):
                from behavior_mcp.schemas import resource

                path = resource(Path(relative).name)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        app = Application(root, context, manifest["policy_id"])
        for tool in ("capabilities_list", "system_recover", "system_inspect"):
            result = app.execute(tool, {"system_id": manifest["system_id"]})
            assert result["request_status"] == "completed", result
