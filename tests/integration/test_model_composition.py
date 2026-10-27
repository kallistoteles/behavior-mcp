import pytest
from behavior import ModelBuildError

from behavior_mcp.authoring import build
from tests.fixtures.public_models import reference_module
from tests.fixtures.runtime import composed_proposal


def test_two_models_match_independent_public_composition(proposal):
    first = build(proposal)
    composed = build(composed_proposal(proposal))
    expected = reference_module(compose=True)
    assert composed.behavior_version == expected.behavior_version
    assert composed.schema_hash == expected.schema_hash
    assert len(composed.model_receipts) == 2
    original = next(
        r for r in composed.model_receipts if r.model_kind == "request_flow"
    )
    assert original.model_hash == first.model_receipts[0].model_hash
    assert composed.behavior_version != first.behavior_version
    reordered = composed_proposal(proposal)
    reordered["models"].reverse()
    assert build(reordered).behavior_version == composed.behavior_version


def test_public_models_refuse_conflicting_field_ownership(proposal):
    source = composed_proposal(proposal)
    source["models"][1]["subject_entity"] = "Record"
    source["models"][1]["subject_param"] = "record"
    with pytest.raises(ModelBuildError) as error:
        build(source)
    assert "CONFLICTING_OWNERSHIP" in [e["code"] for e in error.value.errors]
