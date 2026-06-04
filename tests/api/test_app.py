"""FastAPI app 工厂测试。"""

import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_settings
from app.config import AppSettings


def test_create_app_returns_fastapi_instance() -> None:
    from api.main import create_app

    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "mxa-tutor"
    assert app.version == "0.0.1"


def test_create_app_description_uses_em_dash() -> None:
    from api.main import create_app

    with Path("pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    expected = pyproject["project"]["description"]

    app = create_app()

    assert app.description == expected
    assert "\u2014" in app.description


def test_module_level_app_exists() -> None:
    from api.main import app

    assert app.title == "mxa-tutor"


def test_app_has_health_route() -> None:
    from api.main import create_app

    app = create_app()
    health_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/health" and "GET" in getattr(route, "methods", set())
    ]

    assert health_routes


def test_get_settings_returns_app_settings() -> None:
    assert isinstance(get_settings(), AppSettings)


def test_get_settings_is_lru_cached() -> None:
    first = get_settings()
    second = get_settings()

    assert first is second


def test_lifespan_startup_runs_without_exception() -> None:
    from api.main import create_app

    app = create_app()

    with TestClient(app):
        pass


def test_lifespan_fails_when_deepseek_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from api.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(Exception) as exc_info, TestClient(create_app()):
        pass

    assert "deepseek_api_key" in _flatten_exception_text(exc_info.value).lower()


def test_openapi_schema_includes_health() -> None:
    from api.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]
    assert "HealthResponse" in schema["components"]["schemas"]


def _flatten_exception_text(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        parts.append(str(current))
        current = current.__cause__ or current.__context__
    nested = getattr(exc, "exceptions", ())
    for sub_exc in nested:
        if isinstance(sub_exc, BaseException):
            parts.append(_flatten_exception_text(sub_exc))
        else:
            parts.append(str(sub_exc))
    return " ".join(parts)
