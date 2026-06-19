from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from tests.api.test_paper_tuning import (
    FakeBundleStore,
    FakeTuningService,
    _create_app,
    _record,
)


@pytest.mark.parametrize(
    ("exc", "status_code", "machine_code"),
    [
        (LLMAuthError("auth"), 503, "llm_auth"),
        (LLMQuotaError("quota"), 503, "llm_quota"),
        (LLMRateLimitError("rate"), 429, "llm_rate_limit"),
        (LLMServerError("server"), 502, "llm_server"),
        (LLMTimeoutError("timeout"), 504, "llm_timeout"),
    ],
)
def test_tuning_route_llm_error_subclasses_use_existing_handlers(
    exc: Exception,
    status_code: int,
    machine_code: str,
) -> None:
    app = _create_app(FakeBundleStore(_record()), FakeTuningService(exc))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/tuning-suggest",
            json={"user_scenario": "Need damping"},
        )

    assert response.status_code == status_code
    assert response.json()["error"] == machine_code
