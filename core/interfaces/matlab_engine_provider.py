from abc import ABC, abstractmethod


class MatlabEngineProvider(ABC):
    """Service-facing health check on the app-managed MATLAB Engine session.

    Session ownership, PID, and lifecycle controls stay in the composition root
    and concrete adapter. Async callers must bridge blocking calls with
    ``asyncio.to_thread``.
    """

    @abstractmethod
    def health_probe(self) -> None:
        """Raise a typed MATLAB Engine error when the session is unhealthy."""
        ...
