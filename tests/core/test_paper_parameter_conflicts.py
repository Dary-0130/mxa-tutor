from dataclasses import replace

import pytest

from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_parameter_conflicts import (
    detect_parameter_conflicts,
    validate_parameter_conflicts_materialized,
    with_parameter_conflicts,
)
from core.domain.paper_spec import ParameterEntry


def test_detect_parameter_conflicts_groups_options_by_doc_order() -> None:
    conflicts = detect_parameter_conflicts(
        [
            _parameter("DOC-001", "3.5", "s"),
            _parameter("DOC-002", "3.5", "s"),
            _parameter("DOC-003", "4.0", "s"),
        ]
    )

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.parameter_name == "Inertia constant"
    assert conflict.parameter_symbol == "H"
    assert [(option.value, option.unit) for option in conflict.value_options] == [
        ("3.5", "s"),
        ("4.0", "s"),
    ]
    assert [observation.document_id for observation in conflict.value_options[0].observations] == [
        "DOC-001",
        "DOC-002",
    ]
    assert conflict.value_options[0].observations[0].locator is None
    assert conflict.value_options[0].observations[0].excerpt is None


def test_detect_parameter_conflicts_ignores_non_document_rows_and_same_value() -> None:
    assert (
        detect_parameter_conflicts(
            [
                _parameter("DOC-001", "3.5", "s"),
                _parameter("DOC-002", "3.5", "s"),
                _parameter(None, "4.0", "s", source=EvidenceSource.USER_SUPPLIED),
            ]
        )
        == []
    )


def test_detect_parameter_conflicts_uses_exact_value_and_unit_strings() -> None:
    conflicts = detect_parameter_conflicts(
        [
            _parameter("DOC-001", "5", "s"),
            _parameter("DOC-002", "5", "ms"),
            _parameter("DOC-003", "3.50", "s"),
        ]
    )

    assert [(option.value, option.unit) for option in conflicts[0].value_options] == [
        ("5", "s"),
        ("5", "ms"),
        ("3.50", "s"),
    ]


def test_with_parameter_conflicts_materializes_and_validation_rejects_drift() -> None:
    spec = with_parameter_conflicts(_spec())

    assert len(spec.parameter_conflicts) == 1
    with pytest.raises(ValueError, match="parameter_conflicts_mismatch"):
        validate_parameter_conflicts_materialized(replace(spec, parameter_conflicts=[]))


def _parameter(
    document_id: str | None,
    value: str,
    unit: str,
    *,
    source: EvidenceSource = EvidenceSource.DOCUMENT_EXTRACTED,
) -> ParameterEntry:
    return ParameterEntry(
        name=" Inertia constant ",
        symbol=" H ",
        value=value,
        unit=unit,
        source=source,
        document_id=document_id,
    )


def _spec():
    from core.domain.paper_spec import PaperDocument, PaperSpec

    return PaperSpec(
        paper_title="Report",
        paper_type="report",
        domain="motor_control",
        documents=[
            PaperDocument(document_id="DOC-001", filename="a.pdf"),
            PaperDocument(document_id="DOC-002", filename="b.pdf"),
        ],
        primary_document_id=None,
        abstract="Abstract",
        equations=[],
        parameter_table=[
            _parameter("DOC-001", "3.5", "s"),
            _parameter("DOC-002", "4.0", "s"),
        ],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[],
    )
