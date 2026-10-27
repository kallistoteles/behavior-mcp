import pytest
from behavior import CommitRefused

from behavior_mcp.schemas import OperationError, failure, redact


def test_credentials_redacted():
    assert redact(
        {
            "password": "private",
            "nested": {"api_token": "private"},
            "message": "token=private",
        }
    ) == {
        "password": "[REDACTED]",
        "nested": {"api_token": "[REDACTED]"},
        "message": "token=[REDACTED]",
    }


@pytest.mark.parametrize(
    "category",
    [
        "invalid_input",
        "model_invalid",
        "semantic_refusal",
        "unauthorized",
        "conflict",
        "unsupported",
        "infrastructure",
    ],
)
def test_known_failure_categories(category):
    result = failure(
        "read", {"workspace_id": "w"}, OperationError(category, "test", "safe")
    )
    assert result["error"]["category"] == category
    assert result["request_status"] == (
        "failed" if category == "infrastructure" else "refused"
    )


def test_backend_error_is_not_a_semantic_denial():
    result = failure(
        "commit",
        {"workspace_id": "w", "system_id": "s", "operation_id": "o"},
        CommitRefused("BACKEND_ERROR", "unsafe-secret"),
    )
    assert result["request_status"] == "unknown"
    assert result["error"]["operation_may_have_committed"] is True
    assert "unsafe-secret" not in str(result)


def test_unexpected_publication_failure_preserves_uncertainty():
    result = failure(
        "activation",
        {"workspace_id": "w", "system_id": "s", "operation_id": "o"},
        OSError("lost acknowledgment; token=private"),
    )
    assert result["request_status"] == "unknown"
    assert result["error"]["operation_may_have_committed"] is True
    assert "private" not in str(result)


def test_verification_worker_timeout_has_timeout_outcome():
    result = failure(
        "verification",
        {"workspace_id": "w"},
        OperationError("infrastructure", "VERIFICATION_TIMEOUT", "deadline"),
    )
    assert result["outcome"] == "timeout"
    assert result["request_status"] == "failed"


def test_read_backend_failure_does_not_claim_a_domain_commit():
    result = failure(
        "read",
        {"workspace_id": "w", "system_id": "s"},
        CommitRefused("BACKEND_ERROR", "unsafe-secret"),
    )
    assert result["request_status"] == "failed"
    assert result["error"]["operation_may_have_committed"] is False
