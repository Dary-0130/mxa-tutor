"""Pure Python TuningSuggestion domain contract."""

from dataclasses import dataclass
from typing import Literal

from core.domain.paper_evidence import PaperEvidenceEntry

ParameterDirectionValue = Literal["increase", "decrease", "tune_within_range"]
ConfidenceValue = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ParameterDirection:
    """Direction to tune one parameter and its physical meaning."""

    param_name: str
    direction: ParameterDirectionValue
    physical_meaning: str


@dataclass(frozen=True)
class TuningSuggestion:
    """Parameter tuning suggestion that must be verified in MATLAB."""

    suggestion_id: str
    user_scenario: str
    parameter_directions: list[ParameterDirection]
    expected_effect: str
    confidence: ConfidenceValue
    evidence: list[PaperEvidenceEntry]
    disclaimer: str
