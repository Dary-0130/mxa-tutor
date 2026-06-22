"""MATLAB Engine substrate adapter."""

from adapters.matlab_engine.owned_startup import (
    DEFAULT_CLEANUP_GRACE_S as OWNED_DEFAULT_CLEANUP_GRACE_S,
)
from adapters.matlab_engine.owned_startup import (
    DEFAULT_POLL_INTERVAL_S as OWNED_DEFAULT_POLL_INTERVAL_S,
)
from adapters.matlab_engine.owned_startup import (
    DEFAULT_STARTUP_TIMEOUT_S,
    HEALTH_PROBE_TIMEOUT_S,
    OwnedMatlabEngineRuntime,
    SessionBackedMatlabEngineProvider,
    start_owned_bounded,
)
from adapters.matlab_engine.runtime import (
    MatlabEngineOwnership,
    MatlabEngineSession,
    MatlabEngineState,
    MatlabSimulationResult,
    MatlabSimulinkCapability,
)

__all__ = [
    "DEFAULT_STARTUP_TIMEOUT_S",
    "HEALTH_PROBE_TIMEOUT_S",
    "MatlabEngineOwnership",
    "MatlabEngineSession",
    "MatlabEngineState",
    "MatlabSimulationResult",
    "MatlabSimulinkCapability",
    "OWNED_DEFAULT_CLEANUP_GRACE_S",
    "OWNED_DEFAULT_POLL_INTERVAL_S",
    "OwnedMatlabEngineRuntime",
    "SessionBackedMatlabEngineProvider",
    "start_owned_bounded",
]
