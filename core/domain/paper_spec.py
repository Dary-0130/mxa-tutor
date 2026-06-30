"""Pure Python PaperSpec domain contract."""

from dataclasses import dataclass
from typing import Literal

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry

PaperDomain = Literal[
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
]
PaperType = Literal["paper", "report", "thesis"]


@dataclass(frozen=True)
class EquationEntry:
    """Extracted equation or formula text."""

    equation_id: str
    latex_or_text: str
    paper_section_id: str
    document_id: str | None


@dataclass(frozen=True)
class ParameterEntry:
    """Extracted paper parameter."""

    name: str
    symbol: str
    value: str
    unit: str
    source: EvidenceSource
    document_id: str | None


@dataclass(frozen=True)
class PaperDocument:
    """Document identity for one source file in a PaperSpec."""

    document_id: str
    filename: str


@dataclass(frozen=True)
class FigureRef:
    """Figure or image placeholder reference in the parsed document."""

    figure_id: str
    caption: str
    paper_section_id: str
    document_id: str | None


@dataclass(frozen=True)
class PaperSpec:
    """Structured specification extracted from a paper, report, or thesis."""

    paper_title: str
    paper_type: PaperType
    domain: PaperDomain
    documents: list[PaperDocument]
    primary_document_id: str | None
    abstract: str
    equations: list[EquationEntry]
    parameter_table: list[ParameterEntry]
    figure_locations: list[FigureRef]
    pseudocode_blocks: list[str]
    evidence: list[PaperEvidenceEntry]
