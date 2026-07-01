"""Pure Python PaperAsk domain contract."""

from dataclasses import dataclass
from typing import Literal

from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_tuning import ConfidenceValue

PaperAskFallbackReason = Literal[
    "insufficient_evidence",
    "invalid_or_missing_citations",
    "citation_target_unresolved",
    "out_of_scope",
]
PaperResultSection = Literal[
    "paper-summary",
    "paper-subsystems",
    "paper-build-steps",
    "paper-parameters",
    "paper-tuning",
]


@dataclass(frozen=True)
class SectionTarget:
    """Citation target for a coarse paper result section."""

    kind: Literal["section"]
    result_section: PaperResultSection


@dataclass(frozen=True)
class EquationTarget:
    """Citation target for one extracted equation."""

    kind: Literal["equation"]
    equation_id: str


@dataclass(frozen=True)
class PlanMappingParameterTarget:
    """Citation target for one rendered plan parameter row."""

    kind: Literal["parameter"]
    origin: Literal["plan_mapping"]
    row_index: int
    paper_param_name: str
    model_param_name: str


@dataclass(frozen=True)
class MissingPromptParameterTarget:
    """Citation target for one unresolved user-supply prompt."""

    kind: Literal["parameter"]
    origin: Literal["missing_prompt"]
    prompt_id: str
    parameter_name: str


PaperCitationTarget = (
    SectionTarget | EquationTarget | PlanMappingParameterTarget | MissingPromptParameterTarget
)


@dataclass(frozen=True)
class PaperAskRequest:
    """Stateless paper follow-up request."""

    question: str
    session_id: str | None = None


@dataclass(frozen=True)
class PaperAskCitation:
    """One response citation expanded from the backend source table."""

    source_id: str
    label: str
    excerpt: str | None
    source_kind: EvidenceSource
    target: PaperCitationTarget
    document_id: str | None = None
    document_label: str | None = None


@dataclass(frozen=True)
class PaperAskResponse:
    """Stateless paper follow-up response."""

    session_id: str
    message_id: str
    answer: str
    confidence: ConfidenceValue
    citations: list[PaperAskCitation]
    follow_up_suggestions: list[str]
    is_fallback: bool = False
    fallback_reason: PaperAskFallbackReason | None = None
