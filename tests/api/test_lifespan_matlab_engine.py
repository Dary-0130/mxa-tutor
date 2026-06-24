from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from api.dependencies import get_matlab_engine_provider, get_settings
from core.domain.exceptions import (
    MatlabEngineBusyError,
    MatlabEngineDisabledError,
    MatlabEngineSessionError,
    MatlabEngineTimeoutError,
)

TEST_BRIDGE_SIGNING_KEY = "test-bridge-signing-key-32-bytes-ok"


def test_flag_off_create_app_does_not_import_concrete_adapter() -> None:
    code = textwrap.dedent(
        """
        import os
        import sys

        os.environ["DEEPSEEK_API_KEY"] = "fake-for-test"
        os.environ.pop("MATLAB_ENGINE_ENABLED", None)
        os.environ["MATLAB_BRIDGE_ENABLED"] = "false"
        os.environ["APP_ENV"] = "production"

        from api.main import create_app

        create_app()
        assert "adapters.matlab_engine" not in sys.modules
        assert "adapters.matlab_engine.owned_startup" not in sys.modules
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("app_env", "bridge_enabled", "engine_enabled", "valid"),
    [
        ("production", "false", "false", True),
        ("development", "true", "false", True),
        ("test", "true", "false", True),
        ("production", "true", "false", False),
        ("development", "false", "true", False),
        ("test", "false", "true", False),
        ("production", "true", "true", False),
        ("development", "true", "true", True),
        ("test", "true", "true", True),
    ],
)
def test_create_app_matlab_engine_truth_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str,
    bridge_enabled: str,
    engine_enabled: str,
    valid: bool,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", bridge_enabled)
    monkeypatch.setenv("MATLAB_ENGINE_ENABLED", engine_enabled)
    if bridge_enabled == "true":
        monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "mxa.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()

    if valid:
        assert isinstance(api_main.create_app(), FastAPI)
    else:
        with pytest.raises((RuntimeError, ValidationError)):
            api_main.create_app()


def test_lifespan_starts_engine_once_and_clears_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    runtime = _FakeRuntime()
    _enable_engine_env(monkeypatch, tmp_path)
    monkeypatch.setattr(api_main, "_start_owned_matlab_engine_runtime", runtime.start)

    app = api_main.create_app()
    with TestClient(app):
        assert app.state.matlab_engine_provider is runtime.provider

    assert runtime.start_calls == 1
    assert runtime.provider.calls == 1
    assert runtime.session.close_calls == 1
    assert runtime.terminate_calls == 0
    assert runtime.cleanup_calls == 1
    assert not hasattr(app.state, "matlab_engine_provider")


def test_health_probe_timeout_reaps_and_skips_concurrent_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    runtime = _FakeRuntime(provider_delay_s=0.05)
    _enable_engine_env(monkeypatch, tmp_path)
    monkeypatch.setattr(api_main, "_start_owned_matlab_engine_runtime", runtime.start)
    monkeypatch.setattr(api_main, "_matlab_engine_health_probe_timeout_s", lambda: 0.001)

    app = api_main.create_app()
    with pytest.raises(MatlabEngineTimeoutError) as exc_info, TestClient(app):
        pass

    assert exc_info.value.reason_code == "health_probe_timeout_reaped"
    assert runtime.terminate_calls == 1
    assert runtime.session.close_calls == 0
    assert runtime.cleanup_calls == 1
    assert not hasattr(app.state, "matlab_engine_provider")


def test_health_probe_typed_failure_closes_once_and_cleans_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    runtime = _FakeRuntime(
        provider_error=MatlabEngineSessionError(reason_code="health_probe_failed")
    )
    _enable_engine_env(monkeypatch, tmp_path)
    monkeypatch.setattr(api_main, "_start_owned_matlab_engine_runtime", runtime.start)

    app = api_main.create_app()
    with pytest.raises(MatlabEngineSessionError), TestClient(app):
        pass

    assert runtime.session.close_calls == 1
    assert runtime.terminate_calls == 0
    assert runtime.cleanup_calls == 1
    assert not hasattr(app.state, "matlab_engine_provider")


def test_shutdown_close_timeout_reaps_and_cleans_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    runtime = _FakeRuntime(close_delay_s=0.05, cleanup_grace_s=0.001)
    _enable_engine_env(monkeypatch, tmp_path)
    monkeypatch.setattr(api_main, "_start_owned_matlab_engine_runtime", runtime.start)

    app = api_main.create_app()
    with TestClient(app):
        assert app.state.matlab_engine_provider is runtime.provider

    assert runtime.session.close_calls == 1
    assert runtime.terminate_calls == 1
    assert runtime.cleanup_calls == 1
    assert not hasattr(app.state, "matlab_engine_provider")


def test_shutdown_busy_close_reaps_without_propagating(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    runtime = _FakeRuntime(close_error=MatlabEngineBusyError(reason_code="busy"))
    _enable_engine_env(monkeypatch, tmp_path)
    monkeypatch.setattr(api_main, "_start_owned_matlab_engine_runtime", runtime.start)

    app = api_main.create_app()
    with TestClient(app):
        pass

    assert runtime.session.close_calls == 1
    assert runtime.terminate_calls == 1
    assert runtime.cleanup_calls == 1


def test_shutdown_close_success_still_reaps_when_tree_remains(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    runtime = _FakeRuntime(wait_tree_gone=False)
    _enable_engine_env(monkeypatch, tmp_path)
    monkeypatch.setattr(api_main, "_start_owned_matlab_engine_runtime", runtime.start)

    app = api_main.create_app()
    with TestClient(app):
        pass

    assert runtime.session.close_calls == 1
    assert runtime.wait_tree_calls == 1
    assert runtime.terminate_calls == 1


def test_get_matlab_engine_provider_disabled_when_unwired() -> None:
    app = FastAPI()
    request = cast(Request, type("RequestLike", (), {"app": app})())

    with pytest.raises(MatlabEngineDisabledError) as exc_info:
        get_matlab_engine_provider(request)

    assert exc_info.value.reason_code == "matlab_engine_disabled"


def _enable_engine_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("MATLAB_ENGINE_ENABLED", "true")
    monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "mxa.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()


def _assert_not_event_loop_thread() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise AssertionError("blocking MATLAB Engine call ran on the event loop")


class _FakeProvider:
    def __init__(
        self,
        *,
        delay_s: float = 0.0,
        error: BaseException | None = None,
    ) -> None:
        self.delay_s = delay_s
        self.error = error
        self.calls = 0

    def health_probe(self) -> None:
        _assert_not_event_loop_thread()
        self.calls += 1
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error


class _FakeSession:
    def __init__(
        self,
        *,
        close_delay_s: float = 0.0,
        close_error: BaseException | None = None,
    ) -> None:
        self.close_delay_s = close_delay_s
        self.close_error = close_error
        self.close_calls = 0

    def close(self) -> None:
        _assert_not_event_loop_thread()
        self.close_calls += 1
        if self.close_delay_s > 0:
            time.sleep(self.close_delay_s)
        if self.close_error is not None:
            raise self.close_error


class _FakeRuntime:
    def __init__(
        self,
        *,
        provider_delay_s: float = 0.0,
        provider_error: BaseException | None = None,
        close_delay_s: float = 0.0,
        close_error: BaseException | None = None,
        cleanup_grace_s: float = 0.1,
        wait_tree_gone: bool = True,
    ) -> None:
        self.provider = _FakeProvider(delay_s=provider_delay_s, error=provider_error)
        self.session = _FakeSession(close_delay_s=close_delay_s, close_error=close_error)
        self.cleanup_grace_s = cleanup_grace_s
        self.wait_tree_gone_result = wait_tree_gone
        self.start_calls = 0
        self.terminate_calls = 0
        self.cleanup_calls = 0
        self.wait_tree_calls = 0
        self.is_tree_terminated = False

    def start(self) -> _FakeRuntime:
        _assert_not_event_loop_thread()
        self.start_calls += 1
        return self

    def terminate_tree(self) -> bool:
        _assert_not_event_loop_thread()
        self.terminate_calls += 1
        self.is_tree_terminated = True
        return True

    def wait_tree_gone(self, timeout_s: float) -> bool:
        _assert_not_event_loop_thread()
        assert timeout_s == self.cleanup_grace_s
        self.wait_tree_calls += 1
        return self.wait_tree_gone_result

    def cleanup_log_file(self) -> None:
        _assert_not_event_loop_thread()
        self.cleanup_calls += 1
