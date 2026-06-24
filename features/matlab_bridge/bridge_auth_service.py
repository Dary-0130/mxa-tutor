"""Scoped-token signing, verification, and revocation for MATLAB bridge auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from loguru import logger

from core.domain.bridge_auth import (
    RUN_STATE_WRITE_CAPABILITY,
    BridgeAuthClaims,
    BridgeAuthContext,
)

JWT_ALGORITHM = "HS256"
JWT_TYPE = "JWT"
MIN_SIGNING_KEY_BYTES = 32
DEFAULT_PROCESS_GENERATION_BYTES = 16
UNSAFE_SIGNING_KEY_VALUES = frozenset(
    {
        "",
        "change-me",
        "changeme",
        "default",
        "dev-secret",
        "development-secret",
        "replace-me",
        "test-secret",
    }
)

BridgeAuthClock = Callable[[], datetime]


class BridgeAuthError(Exception):
    """Base class for sanitized bridge auth failures."""

    reason_code: str

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class BridgeAuthTokenError(BridgeAuthError):
    """Token is missing, malformed, expired, revoked, or cryptographically invalid."""


class BridgeAuthForbiddenError(BridgeAuthError):
    """Token is valid but lacks the exact requested capability."""


class BridgeAuthRevocationStoreUnavailableError(BridgeAuthError):
    """Revocation truth source cannot be checked."""


class BridgeAuthRevocationStore(Protocol):
    def revoke(self, token_id: str, expires_at: datetime, now: datetime, skew: timedelta) -> None:
        """Persist a revocation record until ``expires_at + skew``."""

    def is_revoked(self, token_id: str, now: datetime, skew: timedelta) -> bool:
        """Return the authoritative revocation state for ``token_id``."""


@dataclass(frozen=True, slots=True)
class BridgeAuthServiceConfig:
    signing_key: str
    key_id: str
    issuer: str
    audience: str
    token_ttl_seconds: int
    max_token_lifetime_seconds: int
    clock_skew_seconds: int
    process_generation: str
    allowed_capabilities: frozenset[str] = frozenset({RUN_STATE_WRITE_CAPABILITY})


@dataclass(frozen=True, slots=True)
class IssuedBridgeToken:
    access_token: str
    token_type: str
    expires_at: datetime
    expires_in_seconds: int


class InMemoryBridgeRevocationStore:
    """Authoritative in-process revocation state for dev/test single-worker mode."""

    def __init__(self) -> None:
        self._revoked_until_by_token_id: dict[str, datetime] = {}
        self._available = True

    def set_available(self, available: bool) -> None:
        self._available = available

    def revoke(self, token_id: str, expires_at: datetime, now: datetime, skew: timedelta) -> None:
        self._require_available()
        self._drop_expired(now)
        self._revoked_until_by_token_id[token_id] = expires_at + skew

    def is_revoked(self, token_id: str, now: datetime, skew: timedelta) -> bool:
        self._require_available()
        self._drop_expired(now)
        revoked_until = self._revoked_until_by_token_id.get(token_id)
        return revoked_until is not None and revoked_until >= now - skew

    def _drop_expired(self, now: datetime) -> None:
        expired = [
            token_id
            for token_id, revoked_until in self._revoked_until_by_token_id.items()
            if revoked_until < now
        ]
        for token_id in expired:
            del self._revoked_until_by_token_id[token_id]

    def _require_available(self) -> None:
        if not self._available:
            raise BridgeAuthRevocationStoreUnavailableError("revocation_store_unavailable")


class BridgeAuthService:
    """Issue, verify, and revoke short-lived bridge auth tokens."""

    def __init__(
        self,
        config: BridgeAuthServiceConfig,
        revocation_store: BridgeAuthRevocationStore | None = None,
        clock: BridgeAuthClock | None = None,
    ) -> None:
        self._config = config
        self._revocation_store = revocation_store or InMemoryBridgeRevocationStore()
        self._clock = clock or _utc_now
        self._signing_key_bytes = config.signing_key.encode("utf-8")
        self._clock_skew = timedelta(seconds=config.clock_skew_seconds)

    @property
    def process_generation(self) -> str:
        return self._config.process_generation

    def issue_token(
        self,
        *,
        user_id: str,
        project_id: str,
        session_id: str,
        capabilities: Iterable[str] | None = None,
    ) -> IssuedBridgeToken:
        requested_capabilities = frozenset(capabilities or {RUN_STATE_WRITE_CAPABILITY})
        self._require_allowed_capabilities(requested_capabilities)
        now = self._now()
        expires_at = now + timedelta(seconds=self._config.token_ttl_seconds)
        claims = BridgeAuthClaims(
            issuer=self._require_identifier(self._config.issuer, "issuer"),
            audience=self._require_identifier(self._config.audience, "audience"),
            subject=self._require_identifier(user_id, "subject"),
            user_id=self._require_identifier(user_id, "user_id"),
            project_id=self._require_identifier(project_id, "project_id"),
            session_id=self._require_identifier(session_id, "session_id"),
            capabilities=requested_capabilities,
            token_id=uuid4().hex,
            issued_at=now,
            not_before=now,
            expires_at=expires_at,
            process_generation=self._require_identifier(
                self._config.process_generation,
                "process_generation",
            ),
        )
        token = self._encode_claims(claims)
        logger.info("Bridge auth token issued: event_code={} status={}", "bridge_auth_issue", "ok")
        return IssuedBridgeToken(
            access_token=token,
            token_type="Bearer",
            expires_at=expires_at,
            expires_in_seconds=self._config.token_ttl_seconds,
        )

    def verify_token(self, token: str, *, required_capability: str) -> BridgeAuthContext:
        claims = self._decode_and_validate(token)
        self._check_revocation(claims)
        if required_capability not in claims.capabilities:
            logger.info(
                "Bridge auth token rejected: event_code={} status={}",
                "bridge_auth_forbidden",
                "denied",
            )
            raise BridgeAuthForbiddenError("capability_not_allowed") from None
        logger.info(
            "Bridge auth token verified: event_code={} status={}", "bridge_auth_verify", "ok"
        )
        return BridgeAuthContext(claims=claims)

    def revoke_token(self, token: str) -> None:
        claims = self._decode_and_validate(token)
        try:
            self._revocation_store.revoke(
                claims.token_id,
                claims.expires_at,
                self._now(),
                self._clock_skew,
            )
        except BridgeAuthRevocationStoreUnavailableError:
            logger.info(
                "Bridge auth revoke failed: event_code={} status={}",
                "bridge_auth_revoke",
                "store_unavailable",
            )
            raise
        logger.info(
            "Bridge auth token revoked: event_code={} status={}", "bridge_auth_revoke", "ok"
        )

    def _encode_claims(self, claims: BridgeAuthClaims) -> str:
        header = {"alg": JWT_ALGORITHM, "kid": self._config.key_id, "typ": JWT_TYPE}
        payload = {
            "iss": claims.issuer,
            "aud": claims.audience,
            "sub": claims.subject,
            "user_id": claims.user_id,
            "project_id": claims.project_id,
            "session_id": claims.session_id,
            "capabilities": sorted(claims.capabilities),
            "jti": claims.token_id,
            "iat": _to_epoch(claims.issued_at),
            "nbf": _to_epoch(claims.not_before),
            "exp": _to_epoch(claims.expires_at),
            "pg": claims.process_generation,
        }
        signing_input = ".".join((_b64_json(header), _b64_json(payload)))
        signature = _b64_bytes(
            hmac.new(
                self._signing_key_bytes, signing_input.encode("ascii"), hashlib.sha256
            ).digest()
        )
        return f"{signing_input}.{signature}"

    def _decode_and_validate(self, token: str) -> BridgeAuthClaims:
        try:
            header, payload, signing_input, signature = self._split_token(token)
            expected_signature = _b64_bytes(
                hmac.new(
                    self._signing_key_bytes,
                    signing_input.encode("ascii"),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(signature, expected_signature):
                raise BridgeAuthTokenError("invalid_signature")
            self._validate_header(header)
            claims = self._claims_from_payload(payload)
            self._validate_times(claims)
            return claims
        except BridgeAuthError:
            logger.info(
                "Bridge auth token rejected: event_code={} status={}",
                "bridge_auth_verify",
                "denied",
            )
            raise
        except Exception:
            logger.info(
                "Bridge auth token rejected: event_code={} status={}",
                "bridge_auth_verify",
                "denied",
            )
            raise BridgeAuthTokenError("malformed_token") from None

    def _split_token(self, token: str) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        if not isinstance(token, str) or not token or len(token.encode("utf-8")) > 8192:
            raise BridgeAuthTokenError("malformed_token")
        parts = token.split(".")
        if len(parts) != 3 or any(not part for part in parts):
            raise BridgeAuthTokenError("malformed_token")
        header = _json_from_b64(parts[0])
        payload = _json_from_b64(parts[1])
        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise BridgeAuthTokenError("malformed_token")
        return header, payload, ".".join(parts[:2]), parts[2]

    def _validate_header(self, header: dict[str, Any]) -> None:
        if header.get("alg") != JWT_ALGORITHM:
            raise BridgeAuthTokenError("unsupported_algorithm")
        if header.get("typ") != JWT_TYPE:
            raise BridgeAuthTokenError("malformed_token")
        if header.get("kid") != self._config.key_id:
            raise BridgeAuthTokenError("unknown_key")

    def _claims_from_payload(self, payload: dict[str, Any]) -> BridgeAuthClaims:
        issuer = self._require_payload_string(payload, "iss")
        audience = self._require_payload_string(payload, "aud")
        subject = self._require_payload_string(payload, "sub")
        user_id = self._require_payload_string(payload, "user_id")
        project_id = self._require_payload_string(payload, "project_id")
        session_id = self._require_payload_string(payload, "session_id")
        token_id = self._require_payload_string(payload, "jti")
        process_generation = self._require_payload_string(payload, "pg")
        capabilities = self._require_payload_capabilities(payload)
        issued_at = _datetime_from_epoch(_require_int(payload, "iat"))
        not_before = _datetime_from_epoch(_require_int(payload, "nbf"))
        expires_at = _datetime_from_epoch(_require_int(payload, "exp"))
        claims = BridgeAuthClaims(
            issuer=issuer,
            audience=audience,
            subject=subject,
            user_id=user_id,
            project_id=project_id,
            session_id=session_id,
            capabilities=capabilities,
            token_id=token_id,
            issued_at=issued_at,
            not_before=not_before,
            expires_at=expires_at,
            process_generation=process_generation,
        )
        if claims.issuer != self._config.issuer or claims.audience != self._config.audience:
            raise BridgeAuthTokenError("issuer_or_audience_mismatch")
        if claims.process_generation != self._config.process_generation:
            raise BridgeAuthTokenError("process_generation_mismatch")
        self._require_allowed_capabilities(claims.capabilities)
        return claims

    def _validate_times(self, claims: BridgeAuthClaims) -> None:
        now = self._now()
        if claims.not_before > now + self._clock_skew:
            raise BridgeAuthTokenError("token_not_yet_valid")
        if claims.issued_at > now + self._clock_skew:
            raise BridgeAuthTokenError("token_not_yet_valid")
        if claims.expires_at < now - self._clock_skew:
            raise BridgeAuthTokenError("token_expired")
        lifetime = claims.expires_at - claims.issued_at
        if lifetime > timedelta(seconds=self._config.max_token_lifetime_seconds):
            raise BridgeAuthTokenError("token_lifetime_too_long")
        if claims.expires_at <= claims.issued_at:
            raise BridgeAuthTokenError("token_lifetime_invalid")

    def _check_revocation(self, claims: BridgeAuthClaims) -> None:
        try:
            if self._revocation_store.is_revoked(claims.token_id, self._now(), self._clock_skew):
                raise BridgeAuthTokenError("token_revoked")
        except BridgeAuthRevocationStoreUnavailableError:
            logger.info(
                "Bridge auth verify failed: event_code={} status={}",
                "bridge_auth_verify",
                "store_unavailable",
            )
            raise

    def _require_payload_string(self, payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str):
            raise BridgeAuthTokenError("invalid_payload")
        return self._require_identifier(value, key)

    def _require_payload_capabilities(self, payload: dict[str, Any]) -> frozenset[str]:
        value = payload.get("capabilities")
        if not isinstance(value, list) or not value:
            raise BridgeAuthTokenError("invalid_payload")
        capabilities: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise BridgeAuthTokenError("invalid_payload")
            capabilities.append(self._require_identifier(item, "capability"))
        return frozenset(capabilities)

    def _require_allowed_capabilities(self, capabilities: frozenset[str]) -> None:
        if not capabilities or not capabilities.issubset(self._config.allowed_capabilities):
            raise BridgeAuthForbiddenError("capability_not_allowed")

    def _require_identifier(self, value: str, field_name: str) -> str:
        _ = field_name
        if (
            not isinstance(value, str)
            or value == ""
            or value != value.strip()
            or value != unicodedata.normalize("NFC", value)
            or len(value.encode("utf-8")) > 128
        ):
            raise BridgeAuthTokenError("invalid_identifier")
        if any(unicodedata.category(char) == "Cc" for char in value):
            raise BridgeAuthTokenError("invalid_identifier")
        return value

    def _now(self) -> datetime:
        return _ensure_utc(self._clock())


def build_bridge_auth_config(
    *,
    signing_key: str,
    key_id: str,
    issuer: str,
    audience: str,
    token_ttl_seconds: int,
    max_token_lifetime_seconds: int,
    clock_skew_seconds: int,
    process_generation: str | None = None,
) -> BridgeAuthServiceConfig:
    return BridgeAuthServiceConfig(
        signing_key=signing_key,
        key_id=key_id,
        issuer=issuer,
        audience=audience,
        token_ttl_seconds=token_ttl_seconds,
        max_token_lifetime_seconds=max_token_lifetime_seconds,
        clock_skew_seconds=clock_skew_seconds,
        process_generation=process_generation or new_process_generation(),
    )


def new_process_generation() -> str:
    return secrets.token_urlsafe(DEFAULT_PROCESS_GENERATION_BYTES)


def is_unsafe_signing_key(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return (
        stripped.casefold() in UNSAFE_SIGNING_KEY_VALUES
        or len(stripped.encode("utf-8")) < MIN_SIGNING_KEY_BYTES
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_epoch(value: datetime) -> int:
    return int(_ensure_utc(value).timestamp())


def _datetime_from_epoch(value: int) -> datetime:
    return datetime.fromtimestamp(value, UTC)


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BridgeAuthTokenError("invalid_payload")
    return value


def _b64_json(value: dict[str, Any]) -> str:
    return _b64_bytes(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _json_from_b64(value: str) -> Any:
    return json.loads(_b64_decode(value))


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
