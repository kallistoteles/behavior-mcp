"""Catalog availability is an exact installed-version claim, separate from authority."""

from behavior_mcp.adapters import discovery, gaps
from behavior_mcp.schemas import load_schema


def test_exact_six_family_support_matrix():
    expected = {
        "request_flow": {"1", "2.0.0", "2.1.0", "2.2.0", "2.3.0"},
        "state_machine": {"1", "2.0.0", "2.1.0", "2.2.0", "2.3.0"},
        "approval": {"2.0.0", "2.1.0", "2.2.0", "2.3.0"},
        "work_queue": {"2.1.0", "2.2.0", "2.3.0"},
        "field_ownership": {"2.2.0", "2.3.0"},
        "lifecycle_dependency": {"2.3.0"},
    }
    catalog = discovery()
    assert {row["model_kind"] for row in catalog} == set(expected)
    for row in catalog:
        assert {v["adapter_version"] for v in row["adapter_versions"]} == expected[
            row["model_kind"]
        ]
        assert row["authoring_supported"] is True
        for version in row["adapter_versions"]:
            load_schema(version["schema_resource"].removesuffix(".schema.json"))
        assert row["category"] == (
            "safety"
            if row["model_kind"] in {"field_ownership", "lifecycle_dependency"}
            else "operational"
        )


def test_all_retained_and_new_gaps_are_visible():
    assert {"GAP-001", "GAP-002", "GAP-003", "GAP-004", "GAP-005"} <= {
        row["gap_id"] for row in gaps()
    }


def test_catalog_distinguishes_pinned_proof_readiness_from_authoring(monkeypatch):
    from behavior_mcp.dependencies import check_proof_dependencies

    check_proof_dependencies()
    catalog = discovery()
    for row in catalog:
        for version in row["adapter_versions"]:
            assert version["certification_ready"] is (row["category"] == "safety")
    monkeypatch.setenv("BEHAVIOR_SAFETY_TOOLCHAIN", "/unavailable")
    missing = discovery()
    assert all(row["authoring_supported"] for row in missing)
    assert not any(
        v["certification_ready"] for row in missing for v in row["adapter_versions"]
    )
