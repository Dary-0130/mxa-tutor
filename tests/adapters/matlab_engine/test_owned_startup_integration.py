"""Real owned-startup MATLAB Engine checks.

Set ``MXA_RUN_MATLAB_ENGINE=1`` to opt in. These tests are intentionally
Windows-only because TASK-513 owned process-tree recovery uses ``matlab.exe
-wait`` and ``taskkill /T``.
"""

from __future__ import annotations

import os
import sys

import pytest

RUN_ENGINE = os.getenv("MXA_RUN_MATLAB_ENGINE") == "1"
if not RUN_ENGINE:
    pytest.skip("Set MXA_RUN_MATLAB_ENGINE=1 to run.", allow_module_level=True)

if sys.platform != "win32":
    pytest.skip("TASK-513 owned startup is Windows-only.", allow_module_level=True)

from adapters.matlab_engine.owned_startup import (  # noqa: E402
    start_owned_bounded,
)
from adapters.matlab_engine.runtime import MatlabEngineState  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_owned_startup_connect_probe_close_reaps_process_tree() -> None:
    runtime = start_owned_bounded()
    root_pid = runtime.startup_proc.pid
    matlab_pid = runtime.session.matlab_process_id
    try:
        assert matlab_pid is not None
        assert runtime.provider.health_probe() is None
    finally:
        if runtime.session.state != MatlabEngineState.CLOSED:
            runtime.session.close()
        if not runtime.wait_tree_gone():
            assert runtime.terminate_tree()
        runtime.cleanup_log_file()

    assert runtime.wait_tree_gone()
    assert root_pid > 0
