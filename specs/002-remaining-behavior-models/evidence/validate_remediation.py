"""Validate design remediation without importing or changing the server implementation."""

import copy
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

FEATURE = Path(__file__).resolve().parents[1]
ROOT = FEATURE.parents[1]
CONTRACTS = FEATURE / "contracts"


def validate():
    required = [
        "adapter-versions.md",
        "host-policy-v2.schema.json",
        "activation-approval-v2.schema.json",
        "expanded-result.schema.json",
    ]
    missing = [name for name in required if not (CONTRACTS / name).is_file()]
    assert not missing, f"Missing promised design contracts: {missing}"
    schemas = {}
    for path in CONTRACTS.glob("*.schema.json"):
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
    policy = Draft202012Validator(schemas["host-policy-v2.schema.json"])
    approval = Draft202012Validator(schemas["activation-approval-v2.schema.json"])
    result = Draft202012Validator(schemas["expanded-result.schema.json"])

    def fixture(name):
        return json.loads((CONTRACTS / "examples" / name).read_text())

    policies = [
        fixture("host-policy-v2.json"),
        fixture("host-policy-v2-work-queue.json"),
        fixture("host-policy-v2-safety.json"),
    ]
    for document in policies:
        policy.validate(document)
    approval.validate(fixture("activation-approval-v2.json"))
    outputs = fixture("expanded-results.json")
    for document in outputs:
        result.validate(document)
    invalid = []
    bad = copy.deepcopy(policies[0])
    bad["allow_self_approval"] = True
    invalid.append((policy, bad))
    bad = copy.deepcopy(policies[0])
    bad["allowed_adapters"][0]["adapter_version"] = "latest"
    invalid.append((policy, bad))
    bad = copy.deepcopy(policies[0])
    bad["allowed_adapters"][0]["allow_external_commands"] = True
    invalid.append((policy, bad))
    bad = fixture("activation-approval-v2.json")
    del bad["policy_set_hash"]
    invalid.append((approval, bad))
    bad = fixture("activation-approval-v2.json")
    bad["exceptions"] = ["required_safety"]
    invalid.append((approval, bad))
    certificate = next(
        d for d in outputs if d["result"].get("kind") == "safety_assessment"
    )
    bad = copy.deepcopy(certificate)
    bad["result"]["assessment_outcome"] = "Unsupported"
    bad["outcome"] = "safety_unsupported"
    invalid.append((result, bad))
    bad = copy.deepcopy(certificate)
    bad["result"]["certificate_ref"] = None
    invalid.append((result, bad))
    read = next(d for d in outputs if d["result"].get("kind") == "read")
    bad = copy.deepcopy(read)
    bad["error"] = {
        "category": "infrastructure",
        "code": "READ_FAILED",
        "message": "failed",
        "retryable": True,
        "operation_may_have_committed": True,
    }
    bad["request_status"] = "unknown"
    bad["outcome"] = "outcome_unknown"
    invalid.append((result, bad))
    bad = copy.deepcopy(read)
    bad["result"]["claimed_authorization"] = True
    invalid.append((result, bad))
    for validator, document in invalid:
        assert not validator.is_valid(document), (
            "Contract admitted an adversarial fixture"
        )
    proposals = {
        name: fixture(name + ".json")
        for name in ("approval", "work-queue", "field-ownership", "lifecycle")
    }
    versions = {
        "approval": "2.0.0",
        "work-queue": "2.1.0",
        "field-ownership": "2.2.0",
        "lifecycle": "2.3.0",
    }
    for name, document in proposals.items():
        version = versions[name]
        assert document["adapter_version"] == version
        validator = Draft202012Validator(schemas[f"authoring-v2-{version}.schema.json"])
        validator.validate(document)
    old = Draft202012Validator(schemas["authoring-v2-2.0.0.schema.json"])
    bad = copy.deepcopy(proposals["work-queue"])
    bad["adapter_version"] = "2.0.0"
    assert not old.is_valid(bad), "Old implementation advertised a later model"
    tasks = (FEATURE / "tasks.md").read_text()
    assert len(re.findall(r"^- \[[ Xx]\] T\d{3}", tasks, re.M)) == 100
    for token in (
        "test_incremental_adapter_retention.py",
        "v2_0_0.py",
        "v2_1_0.py",
        "v2_2_0.py",
        "v2_3_0.py",
    ):
        assert token in tasks, token
    assert "US6 audits already delivered interfaces" in tasks
    assert (
        hashlib.sha256(
            (ROOT / "src/behavior_mcp/authoring.py").read_bytes()
        ).hexdigest()
        == "32289a08c99625eb489f67ac0c50bcf8f5692cd80e12a2660ce5837c19533b7c"
    )
    return {
        "schemas": len(schemas),
        "policy_fixtures": len(policies),
        "result_fixtures": len(outputs),
        "negative_cases": len(invalid) + 1,
        "versioned_proposals": len(proposals),
        "tasks": 100,
        "legacy_adapter_preserved": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
