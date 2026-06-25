from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from loguru import logger

from core.domain.bridge_auth import RUN_STATE_EXPLAIN_CAPABILITY, RUN_STATE_WRITE_CAPABILITY
from features.matlab_bridge.bridge_auth_service import (
    BridgeAuthForbiddenError,
    BridgeAuthRevocationStoreUnavailableError,
    BridgeAuthService,
    BridgeAuthServiceConfig,
    BridgeAuthTokenError,
    InMemoryBridgeRevocationStore,
)

SIGNING_KEY = "test-bridge-signing-key-32-bytes-ok"
KEY_ID = "test-key"
ISSUER = "mxa-tutor-dev"
AUDIENCE = "mxa-matlab-bridge"
USER_ID = "user-alpha"
PROJECT_ID = "project-alpha"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _CountingStore(InMemoryBridgeRevocationStore):
    def __init__(self) -> None:
        super().__init__()
        self.checks = 0

    def is_revoked(self, token_id: str, now: datetime, skew: timedelta) -> bool:
        self.checks += 1
        return super().is_revoked(token_id, now, skew)


def _config(process_generation: str = "generation-1") -> BridgeAuthServiceConfig:
    return BridgeAuthServiceConfig(
        signing_key=SIGNING_KEY,
        key_id=KEY_ID,
        issuer=ISSUER,
        audience=AUDIENCE,
        token_ttl_seconds=300,
        max_token_lifetime_seconds=900,
        clock_skew_seconds=10,
        process_generation=process_generation,
    )


def _service(
    *,
    clock: _Clock | None = None,
    store: InMemoryBridgeRevocationStore | None = None,
    process_generation: str = "generation-1",
) -> BridgeAuthService:
    return BridgeAuthService(
        _config(process_generation=process_generation),
        revocation_store=store,
        clock=clock,
    )


def _issue(service: BridgeAuthService) -> str:
    return service.issue_token(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        session_id=SESSION_ID,
    ).access_token


def test_issue_and_verify_returns_frozen_context() -> None:
    service = _service()

    token = _issue(service)
    context = service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)

    assert context.user_id == USER_ID
    assert context.project_id == PROJECT_ID
    assert context.session_id == SESSION_ID
    assert context.capabilities == frozenset({RUN_STATE_WRITE_CAPABILITY})
    assert context.claims.issuer == ISSUER
    assert context.claims.audience == AUDIENCE
    assert context.claims.process_generation == "generation-1"


@pytest.mark.parametrize(
    "header_updates",
    [
        {"alg": "none"},
        {"alg": "HS512"},
        {"kid": "unknown-key"},
        {"typ": "not-jwt"},
    ],
)
def test_header_profile_rejects_unsupported_algorithms_and_unknown_keys(
    header_updates: dict[str, object],
) -> None:
    token = _issue(_service())
    header, payload = _decode_token(token)
    header.update(header_updates)

    with pytest.raises(BridgeAuthTokenError):
        _service().verify_token(
            _sign(header, payload), required_capability=RUN_STATE_WRITE_CAPABILITY
        )


@pytest.mark.parametrize(
    "payload_updates",
    [
        {"iss": "other-issuer"},
        {"aud": "other-audience"},
        {"capabilities": "run_state:write"},
        {"iat": True},
        {"nbf": int(datetime(2030, 1, 1, tzinfo=UTC).timestamp())},
    ],
)
def test_payload_profile_rejects_bad_claims(payload_updates: dict[str, object]) -> None:
    token = _issue(_service())
    header, payload = _decode_token(token)
    payload.update(payload_updates)

    with pytest.raises(BridgeAuthTokenError):
        _service().verify_token(
            _sign(header, payload), required_capability=RUN_STATE_WRITE_CAPABILITY
        )


def test_payload_profile_rejects_lifetime_above_configured_max() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    clock = _Clock(now)
    token = _issue(_service(clock=clock))
    header, payload = _decode_token(token)
    payload["exp"] = int((now + timedelta(seconds=901)).timestamp())

    with pytest.raises(BridgeAuthTokenError):
        _service(clock=clock).verify_token(
            _sign(header, payload),
            required_capability=RUN_STATE_WRITE_CAPABILITY,
        )


def test_tampered_signature_is_rejected() -> None:
    token = _issue(_service())

    with pytest.raises(BridgeAuthTokenError):
        _service().verify_token(token[:-1] + "x", required_capability=RUN_STATE_WRITE_CAPABILITY)


def test_expired_token_is_rejected_with_clock_skew_bound() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    clock = _Clock(now)
    service = _service(clock=clock)
    token = _issue(service)

    clock.now = now + timedelta(seconds=311)

    with pytest.raises(BridgeAuthTokenError):
        service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)


def test_required_capability_uses_exact_membership() -> None:
    service = _service()
    token = _issue(service)

    with pytest.raises(BridgeAuthForbiddenError):
        service.verify_token(token, required_capability="run_state")


def test_explain_capability_can_be_issued_without_implying_write() -> None:
    service = _service()
    token = service.issue_token(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        session_id=SESSION_ID,
        capabilities=(RUN_STATE_EXPLAIN_CAPABILITY,),
    ).access_token

    context = service.verify_token(token, required_capability=RUN_STATE_EXPLAIN_CAPABILITY)

    assert context.capabilities == frozenset({RUN_STATE_EXPLAIN_CAPABILITY})
    with pytest.raises(BridgeAuthForbiddenError):
        service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)


def test_disallowed_capability_cannot_be_issued() -> None:
    service = _service()

    with pytest.raises(BridgeAuthForbiddenError):
        service.issue_token(
            user_id=USER_ID,
            project_id=PROJECT_ID,
            session_id=SESSION_ID,
            capabilities=("run_state:write_extra",),
        )


def test_revocation_uses_token_id_and_every_verify_checks_store() -> None:
    store = _CountingStore()
    service = _service(store=store)
    token = _issue(service)

    service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)
    service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)
    assert store.checks == 2

    service.revoke_token(token)

    with pytest.raises(BridgeAuthTokenError):
        service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)
    assert store.checks == 3


def test_revocation_store_unavailable_fails_closed() -> None:
    store = InMemoryBridgeRevocationStore()
    service = _service(store=store)
    token = _issue(service)
    store.set_available(False)

    with pytest.raises(BridgeAuthRevocationStoreUnavailableError):
        service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)


def test_restart_process_generation_rejects_old_tokens() -> None:
    token = _issue(_service(process_generation="generation-1"))
    restarted = _service(process_generation="generation-2")

    with pytest.raises(BridgeAuthTokenError):
        restarted.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)


def test_auth_logs_do_not_leak_token_claim_values_or_exception_text() -> None:
    service = _service()
    lines: list[str] = []
    sink_id = logger.add(lambda message: lines.append(str(message)), format="{message}")
    try:
        token = _issue(service)
        service.verify_token(token, required_capability=RUN_STATE_WRITE_CAPABILITY)
        service.revoke_token(token)
        with pytest.raises(BridgeAuthTokenError):
            service.verify_token(token[:-1] + "x", required_capability=RUN_STATE_WRITE_CAPABILITY)
    finally:
        logger.remove(sink_id)

    _header, payload = _decode_token(token)
    log_text = "\n".join(lines)
    for leaked in (
        token,
        USER_ID,
        PROJECT_ID,
        SESSION_ID,
        payload["jti"],
        "invalid_signature",
        "Traceback",
    ):
        assert str(leaked) not in log_text


def _decode_token(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    header_b64, payload_b64, _signature = token.split(".")
    return _b64_json_decode(header_b64), _b64_json_decode(payload_b64)


def _sign(header: dict[str, Any], payload: dict[str, Any]) -> str:
    signing_input = ".".join((_b64_json(header), _b64_json(payload)))
    signature = _b64_bytes(
        hmac.new(
            SIGNING_KEY.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
        ).digest()
    )
    return f"{signing_input}.{signature}"


def _b64_json(value: dict[str, Any]) -> str:
    return _b64_bytes(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_json_decode(value: str) -> dict[str, Any]:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    data = json.loads(decoded)
    assert isinstance(data, dict)
    return data
