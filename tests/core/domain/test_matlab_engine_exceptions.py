from core.domain.exceptions import (
    MatlabEngineDisabledError,
    MatlabEngineError,
    MatlabEngineSessionError,
    MatlabEngineStartupError,
    MatlabEngineTimeoutError,
    MatlabEngineUnavailableError,
)


def test_matlab_engine_disabled_error_has_stable_reason_code() -> None:
    error = MatlabEngineDisabledError(reason_code="matlab_engine_disabled")

    assert isinstance(error, MatlabEngineError)
    assert error.reason_code == "matlab_engine_disabled"
    assert str(error) == "matlab_engine_disabled"


def test_matlab_engine_reason_code_matrix_is_stable() -> None:
    cases = [
        (MatlabEngineTimeoutError, "startup_timeout_reaped"),
        (MatlabEngineStartupError, "startup_reaper_failed"),
        (MatlabEngineStartupError, "startup_connect_failed"),
        (MatlabEngineStartupError, "startup_pid_attestation_failed"),
        (MatlabEngineSessionError, "health_probe_failed"),
        (MatlabEngineTimeoutError, "health_probe_timeout_reaped"),
        (MatlabEngineStartupError, "health_probe_reaper_failed"),
        (MatlabEngineUnavailableError, "owned_startup_unsupported_platform"),
        (MatlabEngineDisabledError, "matlab_engine_disabled"),
    ]

    for error_type, reason_code in cases:
        error = error_type(reason_code=reason_code)
        assert error.reason_code == reason_code
        assert error.diagnostic_metadata == {}
