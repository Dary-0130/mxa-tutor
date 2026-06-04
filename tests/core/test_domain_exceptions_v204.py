import pytest

from core.domain.exceptions import (
    ChatSessionNotFoundError,
    MxaError,
    ProjectError,
    StoreError,
)


def test_chat_session_not_found_error_inherits_from_project_error() -> None:
    error = ChatSessionNotFoundError("session missing")

    assert isinstance(error, ProjectError)
    assert isinstance(error, MxaError)


def test_store_error_inherits_from_mxa_error() -> None:
    error = StoreError("sqlite_operation_failed")

    assert isinstance(error, MxaError)
    assert not isinstance(error, ProjectError)
    assert str(error) == "sqlite_operation_failed"


def test_store_error_does_not_accept_keyword_error_code() -> None:
    with pytest.raises(TypeError):
        StoreError(error_code="sqlite_operation_failed")
