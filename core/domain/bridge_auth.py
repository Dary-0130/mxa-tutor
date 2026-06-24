"""Pure domain contracts for MATLAB bridge scoped-token auth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

RUN_STATE_WRITE_CAPABILITY = "run_state:write"


@dataclass(frozen=True, slots=True)
class BridgeAuthClaims:
    issuer: str
    audience: str
    subject: str
    user_id: str
    project_id: str
    session_id: str
    capabilities: frozenset[str]
    token_id: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    process_generation: str


@dataclass(frozen=True, slots=True)
class BridgeAuthContext:
    claims: BridgeAuthClaims

    @property
    def user_id(self) -> str:
        return self.claims.user_id

    @property
    def project_id(self) -> str:
        return self.claims.project_id

    @property
    def session_id(self) -> str:
        return self.claims.session_id

    @property
    def capabilities(self) -> frozenset[str]:
        return self.claims.capabilities

    def has_capability(self, capability: str) -> bool:
        return capability in self.claims.capabilities
