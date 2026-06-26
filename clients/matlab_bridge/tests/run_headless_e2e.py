"""Run the MATLAB bridge headless E2E against a real FastAPI app."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import uvicorn


class FakeEmbedder:
    def __init__(
        self,
        model_name: str = "fake-model",
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        _ = model_name, device, normalize

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def dimension(self) -> int:
        return 2


class FakeTextProvider:
    def __init__(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def chat(
        self,
        messages: list[object],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ):
        from core.interfaces.llm_provider import LLMResponse

        _ = json_mode, timeout, max_tokens
        text = "\n".join(message.content for message in messages)
        request_id = _extract_request_id(text)
        diagnostic_kind = _extract_diagnostic_kind(text)
        if diagnostic_kind == "auto_captured_error":
            supporting_signal = "Undefined function or variable Kp_ctrl"
            caveat = "这里只基于自动采集的报错文本,没有运行仿真。"
        else:
            supporting_signal = "Error in [REDACTED_PATH] at line 1"
            caveat = "这里只基于粘贴的报错文本,没有运行仿真。"
        payload = {
            "protocol_version": "0.3-b1",
            "request_id": request_id,
            "status": "completed",
            "mode": "llm_error_explanation",
            "meaning": "这段报错表示 MATLAB 正在报告某个脚本位置相关的运行错误。",
            "likely_causes": [
                {
                    "cause": "错误可能与报错中提到的位置或调用链有关。",
                    "is_inference": True,
                    "confidence": "low",
                    "supporting_signals": [supporting_signal],
                }
            ],
            "next_steps": [{"action": "先运行 `which` 查看相关名称解析,再检查初始化脚本。"}],
            "caveats": [caveat],
        }
        return LLMResponse(
            text=json.dumps(payload, ensure_ascii=False),
            prompt_tokens=1,
            completion_tokens=1,
            model="fake",
            latency_ms=1,
        )

    def capability(self):
        from core.interfaces.llm_provider import ModelCapability

        return ModelCapability(model_name="fake")


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    mltbx_path = args.mltbx.resolve()
    if not mltbx_path.exists():
        raise FileNotFoundError(mltbx_path)

    port = _free_port()
    tmp_dir = Path(tempfile.mkdtemp(prefix="mxa-task510-e2e-"))
    os.environ.update(
        {
            "DEEPSEEK_API_KEY": "fake-for-e2e",
            "APP_ENV": "test",
            "MATLAB_BRIDGE_ENABLED": "true",
            "MATLAB_BRIDGE_AUTH_SIGNING_KEY": "test-bridge-signing-key-32-bytes-ok",
            "DB_PATH": str(tmp_dir / "mxa.db"),
            "UPLOAD_DIR": str(tmp_dir / "uploads"),
        }
    )

    import api.main as api_main
    from adapters.storage._connection import open_connection
    from adapters.storage.schema import init_schema
    from adapters.storage.sqlite_bridge_run_state_store import (
        BridgeRunStateScope,
        SqliteBridgeRunStateStore,
    )
    from api.dependencies import get_matlab_bridge_auth_service, get_settings
    from core.domain.bridge_auth import RUN_STATE_WRITE_CAPABILITY

    get_settings.cache_clear()
    get_matlab_bridge_auth_service.cache_clear()
    api_main.SentenceTransformerEmbedder = FakeEmbedder
    api_main.DeepSeekTextProvider = FakeTextProvider
    app = api_main.create_app()
    session_id = "11111111-1111-4111-8111-111111111111"
    auth_service = get_matlab_bridge_auth_service()
    asyncio.run(
        _prepare_run_state_session(
            tmp_dir / "mxa.db",
            auth_service,
            session_id,
            open_connection,
            init_schema,
            BridgeRunStateScope,
            SqliteBridgeRunStateStore,
        )
    )
    valid_token = auth_service.issue_token(
        user_id="user-alpha",
        project_id="project-alpha",
        session_id=session_id,
    ).access_token
    verified_context = auth_service.verify_token(
        valid_token,
        required_capability=RUN_STATE_WRITE_CAPABILITY,
    )
    if verified_context.session_id != session_id:
        raise AssertionError("Python verifier returned the wrong session scope")
    revoked_token = auth_service.issue_token(
        user_id="user-alpha",
        project_id="project-alpha",
        session_id=session_id,
    ).access_token
    auth_service.revoke_token(revoked_token)
    bridge_counter = {"diagnostic": 0, "explanation": 0, "run_state": 0}

    @app.middleware("http")
    async def count_bridge_requests(request, call_next):
        if request.url.path == "/api/v1/bridge/diagnostic":
            bridge_counter["diagnostic"] += 1
        if request.url.path == "/api/v1/bridge/explanation":
            bridge_counter["explanation"] += 1
        if request.url.path == "/api/v1/bridge/run-state":
            bridge_counter["run_state"] += 1
        return await call_next(request)

    servers = [
        _start_server(app, "127.0.0.1", port, lifespan="on"),
        _start_server(app, "::1", port, lifespan="off"),
    ]
    try:
        _wait_for_server("127.0.0.1", port)
        _wait_for_server("::1", port)
        try:
            _run_matlab_e2e(
                repo_root,
                mltbx_path,
                port,
                valid_token,
                revoked_token,
                session_id,
            )
        except subprocess.CalledProcessError:
            print(f"bridge_requests_seen={bridge_counter}")
            raise
        if bridge_counter != {"diagnostic": 1, "explanation": 2, "run_state": 4}:
            raise AssertionError(f"unexpected bridge request counts: {bridge_counter}")
    finally:
        for server, _ in servers:
            server.should_exit = True
        for _, thread in servers:
            thread.join(timeout=15)
    print(
        "run_state_token_verified_by_python=true "
        f"session_id={verified_context.session_id} "
        f"capabilities={sorted(verified_context.capabilities)}"
    )
    print(
        "TASK-514 bridge E2E passed: " f"mltbx={mltbx_path} size={mltbx_path.stat().st_size} bytes"
    )
    return 0


def _parse_args() -> argparse.Namespace:
    default_mltbx = Path(__file__).resolve().parents[1] / "dist" / "mxa-matlab-bridge-0.1.0.mltbx"
    parser = argparse.ArgumentParser()
    parser.add_argument("--mltbx", type=Path, default=default_mltbx)
    return parser.parse_args()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(
    app, host: str, port: int, *, lifespan: str
) -> tuple[uvicorn.Server, threading.Thread]:
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            lifespan=lifespan,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def _wait_for_server(host: str, port: int) -> None:
    url = f"http://[{host}]:{port}/health" if ":" in host else f"http://{host}:{port}/health"
    deadline = time.time() + 45
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"server did not become healthy: {last_error}")


def _run_matlab_e2e(
    repo_root: Path,
    mltbx_path: Path,
    port: int,
    valid_token: str,
    revoked_token: str,
    session_id: str,
) -> None:
    matlab_code = (
        f"cd('{_matlab_quote(repo_root)}'); "
        "addpath('clients/matlab_bridge/tests'); "
        f"headless_bridge_e2e('{_matlab_quote(mltbx_path)}', "
        f"'http://localhost:{port}', "
        f"'{_matlab_quote(valid_token)}', "
        f"'{_matlab_quote(revoked_token)}', "
        f"'{_matlab_quote(session_id)}');"
    )
    subprocess.run(["matlab", "-batch", matlab_code], cwd=repo_root, check=True)


async def _prepare_run_state_session(
    db_path: Path,
    auth_service,
    session_id: str,
    open_connection_fn,
    init_schema_fn,
    scope_cls,
    store_cls,
) -> None:
    created_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
    async with open_connection_fn(str(db_path)) as conn:
        await init_schema_fn(conn)
        await conn.execute(
            """
            INSERT INTO project_status_record(
                project_id, name, status, created_at, updated_at
            ) VALUES ('project-alpha', 'demo.zip', 'parsing', ?, ?)
            ON CONFLICT(project_id) DO NOTHING
            """,
            (created_at, created_at),
        )
        await conn.commit()
    store = store_cls(str(db_path))
    await store.establish_session(
        scope_cls(
            user_id="user-alpha",
            project_id="project-alpha",
            session_id=session_id,
            process_generation=auth_service.process_generation,
        )
    )


def _matlab_quote(value: object) -> str:
    return str(value).replace("'", "''").replace("\\", "/")


def _extract_request_id(text: str) -> str:
    match = re.search(
        r"request_id:\s*([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        text,
    )
    if match is None:
        raise RuntimeError("request_id missing from bridge prompt")
    return match.group(1)


def _extract_diagnostic_kind(text: str) -> str:
    match = re.search(r"diagnostic_kind:\s*([A-Za-z0-9_]+)", text)
    if match is None:
        raise RuntimeError("diagnostic_kind missing from bridge prompt")
    return match.group(1)


if __name__ == "__main__":
    sys.exit(main())
