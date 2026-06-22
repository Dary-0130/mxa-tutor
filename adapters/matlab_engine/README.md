# MATLAB Engine adapter

Synchronous substrate wrapper for MATLAB Engine for Python.

- `MatlabEngineSession.start_owned(...)` starts a MATLAB process owned by the wrapper.
- `MatlabEngineSession.connect_shared(name)` connects only to an explicitly named shared session.
- `run_simulation(..., timeout_s, cancel_event)` uses Engine `FutureResult` polling and cancellation.

This adapter is not wired into FastAPI routes or lifespan in TASK-512 b2-0. Async service code should
bridge it with one `asyncio.to_thread(...)` call in the service layer.
