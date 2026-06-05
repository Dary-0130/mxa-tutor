"""健康检查端点测试。"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.schemas.health import HealthResponse


def test_get_health_returns_200_with_exact_body() -> None:
    from api.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.0.1",
        "app_name": "mxa-tutor",
    }


def test_health_response_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        HealthResponse(
            status="ok",
            version="0.0.1",
            app_name="mxa-tutor",
            extra="x",
        )


def test_health_response_schema_in_openapi() -> None:
    from api.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    schema = response.json()
    response_schema = schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema["$ref"] == "#/components/schemas/HealthResponse"


def test_404_for_unknown_path() -> None:
    from api.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/nonexistent")

    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": "请求的资源不存在"}
    assert "detail" not in response.text
