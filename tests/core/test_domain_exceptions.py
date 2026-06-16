from core.domain.exceptions import (
    DocumentParseError,
    EmbeddingError,
    EmbeddingModelLoadError,
    EvidenceMissingError,
    FileTypeNotAllowedError,
    LLMAuthError,
    LLMError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    MParseError,
    MxaError,
    OverviewGenerationError,
    PaperSpecGenerationError,
    ParseError,
    ProjectError,
    ProjectNotFoundError,
    ProjectTooLargeError,
    QuotaExhaustedError,
    SlxParseError,
    StoreError,
    UploadError,
    VectorStoreError,
    ZipBombError,
    ZipSlipError,
)


def test_llm_errors_inherit_from_llm_error_and_mxa_error() -> None:
    for error_type in [
        LLMAuthError,
        LLMQuotaError,
        LLMRateLimitError,
        LLMServerError,
        LLMTimeoutError,
    ]:
        error = error_type("x")
        assert isinstance(error, LLMError)
        assert isinstance(error, MxaError)


def test_parse_errors_inherit_from_parse_error_and_mxa_error() -> None:
    for error_type in [SlxParseError, MParseError, DocumentParseError]:
        error = error_type("x")
        assert isinstance(error, ParseError)
        assert isinstance(error, MxaError)


def test_embedding_errors_inherit_from_embedding_error_and_mxa_error() -> None:
    error = EmbeddingModelLoadError("x")
    assert isinstance(error, EmbeddingError)
    assert isinstance(error, MxaError)


def test_project_errors_inherit_from_project_error_and_mxa_error() -> None:
    for error_type in [ProjectNotFoundError, ProjectTooLargeError]:
        error = error_type("x")
        assert isinstance(error, ProjectError)
        assert isinstance(error, MxaError)


def test_upload_errors_inherit_from_upload_error_and_mxa_error() -> None:
    for error_type in [ZipBombError, ZipSlipError, FileTypeNotAllowedError]:
        error = error_type("x")
        assert isinstance(error, UploadError)
        assert isinstance(error, MxaError)


def test_top_level_business_errors_inherit_from_mxa_error() -> None:
    assert isinstance(QuotaExhaustedError("x"), MxaError)
    assert isinstance(EvidenceMissingError("x"), MxaError)
    assert isinstance(OverviewGenerationError("x"), MxaError)
    assert isinstance(PaperSpecGenerationError("x"), MxaError)


def test_vector_store_error_inherits_from_store_error() -> None:
    error = VectorStoreError("x")
    assert isinstance(error, StoreError)
    assert isinstance(error, MxaError)
