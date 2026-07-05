import json
from pathlib import Path

from features.paper.paper_ask_schemas import PaperAskRequestModel, PaperAskResponseModel
from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)
from features.paper.paper_upload_job_schemas import (
    PaperStatusResponse,
    RerunPlanRequest,
    RerunPlanResponse,
)

ROOT = Path("eval/cases/paper_to_model")
PAPER_SPEC_PATH = (
    ROOT / "material_to_plan/case_01_motor_short_circuit/golden/expected_paper_spec.json"
)
PLAN_PATH = (
    ROOT / "material_to_plan/case_01_motor_short_circuit/golden/expected_model_generation_plan.json"
)
MISSING_PATH = (
    ROOT / "missing_param/case_01_missing_image_param/input/expected_missing_prompts.json"
)
UPDATED_PLAN_PATH = (
    ROOT / "missing_param/case_01_missing_image_param/golden/expected_updated_plan.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(model: object) -> object:
    return model.model_dump(mode="json")  # type: ignore[attr-defined]


def test_expected_paper_spec_roundtrip_matches_sample_json() -> None:
    data = _load(PAPER_SPEC_PATH)
    model = PaperSpecModel.model_validate(data)
    assert _json_dump(PaperSpecModel.from_domain(model.to_domain())) == data


def test_expected_model_generation_plan_roundtrip_matches_sample_json() -> None:
    data = _load(PLAN_PATH)
    model = ModelGenerationPlanModel.model_validate(data)
    assert data["build_steps"] is None
    assert model.build_steps is None
    assert _json_dump(ModelGenerationPlanModel.from_domain(model.to_domain())) == data


def test_expected_missing_prompts_dict_roundtrip_matches_sample_json() -> None:
    data = _load(MISSING_PATH)
    prompts = data["missing_prompts"]
    assert isinstance(prompts, list)

    models = [MissingParameterPromptModel.model_validate(item) for item in prompts]
    actual = {
        "missing_prompts": [
            _json_dump(MissingParameterPromptModel.from_domain(model.to_domain()))
            for model in models
        ]
    }

    assert actual == data


def test_expected_updated_plan_roundtrip_matches_sample_json() -> None:
    data = _load(UPDATED_PLAN_PATH)
    model = ModelGenerationPlanModel.model_validate(data)
    assert data["build_steps"] is None
    assert model.build_steps is None
    assert _json_dump(ModelGenerationPlanModel.from_domain(model.to_domain())) == data


def test_paper_ask_request_roundtrip_matches_sample_json() -> None:
    data = {
        "question": "How should I interpret the model structure?",
        "session_id": None,
    }
    model = PaperAskRequestModel.model_validate(data)

    assert _json_dump(PaperAskRequestModel.from_domain(model.to_domain())) == data


def test_paper_ask_success_multi_citation_roundtrip_matches_sample_json() -> None:
    data = {
        "session_id": "session-a",
        "message_id": "message-a",
        "answer": "The document summary and equation both support the modelling choice.",
        "confidence": "medium",
        "citations": [
            {
                "source_id": "S1",
                "label": "Paper summary",
                "excerpt": "The document describes the machine and the reproduction goal.",
                "source_kind": "document_extracted",
                "target": {"kind": "section", "result_section": "paper-summary"},
                "document_id": "DOC-001",
                "document_label": "paper-a.pdf",
            },
            {
                "source_id": "S2",
                "label": "Equation EQ-main",
                "excerpt": "The governing relation links the machine state to the response.",
                "source_kind": "document_extracted",
                "target": {"kind": "equation", "equation_id": "EQ-main"},
                "document_id": "DOC-002",
                "document_label": "paper-b.pdf",
            },
        ],
        "follow_up_suggestions": ["Which subsystem should I inspect first?"],
        "is_fallback": False,
        "fallback_reason": None,
    }
    model = PaperAskResponseModel.model_validate(data)

    assert _json_dump(PaperAskResponseModel.from_domain(model.to_domain())) == data


def test_paper_ask_user_supplied_citation_roundtrip_matches_sample_json() -> None:
    data = {
        "session_id": "session-b",
        "message_id": "message-b",
        "answer": "The mapped parameter came from the user-supplied completion.",
        "confidence": "low",
        "citations": [
            {
                "source_id": "S3",
                "label": "User-supplied parameter: inertia",
                "excerpt": None,
                "source_kind": "user_supplied",
                "target": {
                    "kind": "parameter",
                    "origin": "plan_mapping",
                    "row_index": 0,
                    "paper_param_name": "inertia",
                    "model_param_name": "machine inertia",
                },
                "document_id": None,
                "document_label": None,
            }
        ],
        "follow_up_suggestions": [],
        "is_fallback": False,
        "fallback_reason": None,
    }
    model = PaperAskResponseModel.model_validate(data)

    assert _json_dump(PaperAskResponseModel.from_domain(model.to_domain())) == data


def test_paper_ask_legacy_citation_without_document_fields_reads_as_null() -> None:
    data = {
        "session_id": "session-legacy",
        "message_id": "message-legacy",
        "answer": "The source supports this answer.",
        "confidence": "medium",
        "citations": [
            {
                "source_id": "S1",
                "label": "Paper summary",
                "excerpt": "The document describes the machine.",
                "source_kind": "document_extracted",
                "target": {"kind": "section", "result_section": "paper-summary"},
            }
        ],
        "follow_up_suggestions": [],
        "is_fallback": False,
        "fallback_reason": None,
    }

    model = PaperAskResponseModel.model_validate(data)

    assert model.citations[0].document_id is None
    assert model.citations[0].document_label is None


def test_paper_ask_fallback_reasons_roundtrip_match_sample_json() -> None:
    for reason in (
        "insufficient_evidence",
        "invalid_or_missing_citations",
        "citation_target_unresolved",
        "out_of_scope",
    ):
        data = {
            "session_id": "session-fallback",
            "message_id": f"message-{reason}",
            "answer": "Current parsed sources do not provide a citable answer.",
            "confidence": "low",
            "citations": [],
            "follow_up_suggestions": [],
            "is_fallback": True,
            "fallback_reason": reason,
        }
        model = PaperAskResponseModel.model_validate(data)

        assert _json_dump(PaperAskResponseModel.from_domain(model.to_domain())) == data


def test_paper_status_response_roundtrip_matches_sample_json() -> None:
    data = {
        "paper_id": "paper-1",
        "job_id": "PUJ-1",
        "execution_mode": "sync",
        "job_state": "plan_failed_retryable",
        "stage": "generating_plan",
        "failed_stage": "generating_plan",
        "error_code": "paper_plan_generation_failed",
        "retryable": True,
        "next_action": "rerun_plan",
        "expires_at": "2026-07-06T12:00:00",
        "documents": [
            {
                "document_id": "DOC-001",
                "status": "succeeded",
                "error_code": None,
            }
        ],
    }

    model = PaperStatusResponse.model_validate(data)

    assert _json_dump(model) == data


def test_rerun_plan_contracts_roundtrip_match_sample_json() -> None:
    request = {}
    response = {
        "paper_id": "paper-1",
        "job_id": "PUJ-1",
        "job_state": "ready",
        "plan": _load(PLAN_PATH),
        "missing_prompts": _load(MISSING_PATH)["missing_prompts"],
        "remaining_missing_prompts": [],
    }

    assert _json_dump(RerunPlanRequest.model_validate(request)) == request
    assert _json_dump(RerunPlanResponse.model_validate(response)) == response
