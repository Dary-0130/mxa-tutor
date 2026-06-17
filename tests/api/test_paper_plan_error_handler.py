from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError


def test_paper_plan_generation_error_returns_502() -> None:
    response = _trigger(PaperPlanGenerationError("missing_binding_not_found"))

    assert response.status_code == 502
    assert response.json() == {
        "error": "paper_plan_generation_failed",
        "message": "建模计划生成失败,请刷新重试",
    }


def test_user_supply_paper_not_found_returns_400() -> None:
    response = _trigger(PaperUserSupplyError("paper_not_found"))

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def test_user_supply_prompt_not_found_returns_400() -> None:
    response = _trigger(PaperUserSupplyError("prompt_id_not_found"))

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def test_user_supply_prompt_duplicated_returns_400() -> None:
    response = _trigger(PaperUserSupplyError("prompt_id_duplicated"))

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def test_user_supply_parameter_name_mismatch_returns_400() -> None:
    response = _trigger(PaperUserSupplyError("parameter_name_mismatch"))

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def test_user_supply_already_filled_returns_400() -> None:
    response = _trigger(PaperUserSupplyError("prompt_already_filled"))

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def _trigger(exc: Exception) -> object:
    get_settings.cache_clear()
    app = FastAPI()
    register_error_handlers(app, get_settings())

    async def raise_error() -> None:
        raise exc

    app.add_api_route("/_trigger", raise_error, methods=["GET"])
    with TestClient(app) as client:
        return client.get("/_trigger")
