from typing import cast

import pytest

from adapters.matlab_engine.owned_startup import SessionBackedMatlabEngineProvider
from adapters.matlab_engine.runtime import MatlabEngineSession
from core.domain.exceptions import MatlabEngineSessionError, MatlabEngineStartupError
from core.interfaces.matlab_engine_provider import MatlabEngineProvider


def test_matlab_engine_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        MatlabEngineProvider()


class _StubMatlabEngineProvider(MatlabEngineProvider):
    def health_probe(self) -> None:
        return None


def test_matlab_engine_provider_stub_works() -> None:
    provider = _StubMatlabEngineProvider()

    assert provider.health_probe() is None


class _FakeSession:
    def __init__(self, result: bool | BaseException) -> None:
        self.result = result
        self.calls = 0

    def health_probe(self) -> bool:
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_session_backed_provider_true_returns_none() -> None:
    session = _FakeSession(True)
    provider = SessionBackedMatlabEngineProvider(cast(MatlabEngineSession, session))

    assert provider.health_probe() is None
    assert session.calls == 1


def test_session_backed_provider_false_raises_typed_reason() -> None:
    session = _FakeSession(False)
    provider = SessionBackedMatlabEngineProvider(cast(MatlabEngineSession, session))

    with pytest.raises(MatlabEngineSessionError) as exc_info:
        provider.health_probe()

    assert exc_info.value.reason_code == "health_probe_failed"


def test_session_backed_provider_propagates_typed_error() -> None:
    error = MatlabEngineStartupError(reason_code="startup_connect_failed")
    session = _FakeSession(error)
    provider = SessionBackedMatlabEngineProvider(cast(MatlabEngineSession, session))

    with pytest.raises(MatlabEngineStartupError) as exc_info:
        provider.health_probe()

    assert exc_info.value is error
