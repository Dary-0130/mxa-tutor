from dataclasses import fields

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction


def test_evidence_source_values_match_contract() -> None:
    assert {item.name: item.value for item in EvidenceSource} == {
        "DOCUMENT_EXTRACTED": "document_extracted",
        "USER_SUPPLIED": "user_supplied",
    }


def test_user_evidence_action_values_match_contract() -> None:
    assert {item.name: item.value for item in UserEvidenceAction} == {
        "FILL_MISSING": "fill_missing",
        "CORRECT_EXTRACTED": "correct_extracted",
    }


def test_paper_evidence_entry_fields_match_contract_order() -> None:
    assert [field.name for field in fields(PaperEvidenceEntry)] == [
        "source",
        "document_id",
        "paper_section_id",
        "equation_id",
        "figure_id",
        "excerpt",
        "missing_param_prompt_id",
        "user_action",
        "parameter_correction_id",
        "correction_param_key",
    ]


def test_paper_evidence_entry_accepts_document_extracted_shape() -> None:
    entry = PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The paper states the rated voltage.",
        missing_param_prompt_id=None,
    )

    assert entry.source is EvidenceSource.DOCUMENT_EXTRACTED
    assert entry.paper_section_id == "S1"
