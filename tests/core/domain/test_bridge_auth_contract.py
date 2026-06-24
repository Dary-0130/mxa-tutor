from datetime import UTC, datetime
from pathlib import Path

from core.domain.bridge_auth import (
    RUN_STATE_WRITE_CAPABILITY,
    BridgeAuthClaims,
    BridgeAuthContext,
)


def test_bridge_auth_context_is_frozen_and_exposes_immutable_capabilities() -> None:
    claims = BridgeAuthClaims(
        issuer="issuer",
        audience="audience",
        subject="user-1",
        user_id="user-1",
        project_id="project-1",
        session_id="session-1",
        capabilities=frozenset({RUN_STATE_WRITE_CAPABILITY}),
        token_id="token-id",
        issued_at=datetime.now(UTC),
        not_before=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        process_generation="generation-1",
    )
    context = BridgeAuthContext(claims=claims)

    assert context.user_id == "user-1"
    assert context.project_id == "project-1"
    assert context.session_id == "session-1"
    assert context.capabilities == frozenset({RUN_STATE_WRITE_CAPABILITY})
    assert context.has_capability(RUN_STATE_WRITE_CAPABILITY)


def test_bridge_auth_domain_contract_does_not_import_framework_or_store_code() -> None:
    source = Path("core/domain/bridge_auth.py").read_text(encoding="utf-8").lower()

    for forbidden in ("pydantic", "fastapi", "starlette", "jose", "jwt", "store"):
        assert forbidden not in source
