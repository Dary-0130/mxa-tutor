from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from core.domain.exceptions import (
    PaperReparseFailedError,
    PaperReparseInProgressError,
    PaperReparseSourceUnavailableError,
    PaperReparseStoreError,
    PaperSpecGenerationError,
    StoreError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_reparse_source import (
    PaperReparseDocumentSource,
    PaperReparseLocatorIndex,
    PaperReparseSource,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry
from features.paper.paper_reparse_service import PaperReparseLockRegistry, PaperReparseService


async def test_reparse_success_replaces_with_new_spec_and_plan() -> None:
    old_record = _record("paper-1", "3.5")
    store = _FakeStore(old_record, _source("paper-1", [0], ["9.0"]))
    spec_service = _FakeSpecService()
    plan_service = _FakePlanService()
    service = _service(store, spec_service, plan_service)

    record = await service.reparse("paper-1")

    assert record.paper_id == "paper-1"
    assert record.spec.parameter_table[0].value == "9.0"
    assert record.plan.parameter_mapping[0].value == "9.0"
    assert store.records["paper-1"] == record
    assert len(store.records) == 1
    assert plan_service.calls[0].parameter_table[0].value == "9.0"


async def test_reparse_failure_keeps_old_bundle_and_does_not_replace() -> None:
    old_record = _record("paper-1", "3.5")
    store = _FakeStore(old_record, _source("paper-1", [0, 1], ["9.0", "8.0"]))
    spec_service = _FakeSpecService(errors_by_document_id={"DOC-002": PaperSpecGenerationError()})
    service = _service(store, spec_service, _FakePlanService())

    with pytest.raises(PaperReparseFailedError):
        await service.reparse("paper-1")

    assert store.records["paper-1"] == old_record
    assert store.replace_calls == 0


async def test_reparse_source_unavailable_does_not_start_extraction() -> None:
    old_record = _record("paper-1", "3.5")
    store = _FakeStore(old_record, None)
    spec_service = _FakeSpecService()
    service = _service(store, spec_service, _FakePlanService())

    with pytest.raises(PaperReparseSourceUnavailableError):
        await service.reparse("paper-1")

    assert spec_service.calls == []


async def test_reparse_store_failure_surfaces_store_error_and_keeps_old() -> None:
    old_record = _record("paper-1", "3.5")
    store = _FakeStore(old_record, _source("paper-1", [0], ["9.0"]), replace_error=True)
    service = _service(store, _FakeSpecService(), _FakePlanService())

    with pytest.raises(PaperReparseStoreError):
        await service.reparse("paper-1")

    assert store.records["paper-1"] == old_record


async def test_concurrent_reparse_rejects_second_before_second_extraction() -> None:
    old_record = _record("paper-1", "3.5")
    store = _FakeStore(old_record, _source("paper-1", [0], ["9.0"]))
    started = asyncio.Event()
    release = asyncio.Event()
    spec_service = _FakeSpecService(started=started, release=release)
    service = _service(store, spec_service, _FakePlanService())

    first = asyncio.create_task(service.reparse("paper-1"))
    await started.wait()

    with pytest.raises(PaperReparseInProgressError):
        await service.reparse("paper-1")

    assert len(spec_service.calls) == 1
    release.set()
    await first


async def test_get_during_reparse_sees_old_until_commit() -> None:
    old_record = _record("paper-1", "3.5")
    store = _FakeStore(old_record, _source("paper-1", [0], ["9.0"]))
    started = asyncio.Event()
    release = asyncio.Event()
    plan_service = _FakePlanService(started=started, release=release)
    service = _service(store, _FakeSpecService(), plan_service)

    task = asyncio.create_task(service.reparse("paper-1"))
    await started.wait()
    assert await store.get_plan_record("paper-1") == old_record

    release.set()
    new_record = await task
    assert await store.get_plan_record("paper-1") == new_record


async def test_multi_doc_partial_gap_and_primary_are_preserved() -> None:
    old_record = _record("paper-1", "3.5")
    source = _source("paper-1", [0, 2], ["7.0", "9.0"], primary_index=2)
    store = _FakeStore(old_record, source)
    service = _service(store, _FakeSpecService(), _FakePlanService())

    record = await service.reparse("paper-1")

    assert [document.document_id for document in record.spec.documents] == ["DOC-001", "DOC-003"]
    assert record.spec.primary_document_id == "DOC-003"


def _service(
    store: _FakeStore,
    spec_service: _FakeSpecService,
    plan_service: _FakePlanService,
) -> PaperReparseService:
    return PaperReparseService(
        bundle_store=store,
        reparse_store=store,
        spec_service=spec_service,  # type: ignore[arg-type]
        plan_service=plan_service,  # type: ignore[arg-type]
        lock_registry=PaperReparseLockRegistry(),
    )


class _FakeStore:
    def __init__(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource | None,
        *,
        replace_error: bool = False,
    ) -> None:
        self.records = {record.paper_id: record}
        self.sources = {source.paper_id: source} if source is not None else {}
        self.replace_error = replace_error
        self.replace_calls = 0

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        return self.records.get(paper_id)

    async def get_reparse_source(self, paper_id: str) -> PaperReparseSource | None:
        return self.sources.get(paper_id)

    async def replace_ready_bundle_with_source(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource,
    ) -> None:
        self.replace_calls += 1
        if self.replace_error:
            raise StoreError("sqlite_operation_failed")
        self.records[record.paper_id] = record
        self.sources[source.paper_id] = source


class _FakeSpecService:
    def __init__(
        self,
        *,
        errors_by_document_id: dict[str, Exception] | None = None,
        started: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self.errors_by_document_id = errors_by_document_id or {}
        self.started = started
        self.release = release
        self.calls: list[str] = []

    async def extract_parsed_uncached(
        self,
        parsed,
        paper_id: str,
        display_filename: str | None = None,
        document_id: str = "DOC-001",
        retry_context: object | None = None,
    ) -> PaperSpec:
        _ = paper_id, retry_context
        self.calls.append(document_id)
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            await self.release.wait()
        error = self.errors_by_document_id.get(document_id)
        if error is not None:
            raise error
        return _spec(
            document_id=document_id,
            filename=display_filename or "paper.pdf",
            value=parsed.raw_text.strip(),
        )


class _FakePlanService:
    def __init__(
        self,
        *,
        started: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self.started = started
        self.release = release
        self.calls: list[PaperSpec] = []

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,
        retry_context: object | None = None,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingParameterBinding]]:
        _ = retry_context
        self.calls.append(spec)
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            await self.release.wait()
        value = spec.parameter_table[0].value
        return _plan(paper_id, value, spec.evidence[0]), [], []


def _source(
    paper_id: str,
    upload_indexes: list[int],
    values: list[str],
    *,
    primary_index: int | None = None,
) -> PaperReparseSource:
    documents = []
    for upload_index, value in zip(upload_indexes, values, strict=True):
        document_id = f"DOC-{upload_index + 1:03d}"
        documents.append(
            PaperReparseDocumentSource(
                document_id=document_id,
                upload_index=upload_index,
                filename=f"paper-{upload_index + 1}.pdf",
                raw_text=value,
                page_count=1,
                figure_placeholders=[],
                table_placeholders=[],
                locator_index=PaperReparseLocatorIndex(
                    section_ids=["S1"],
                    equation_ids=["EQ-01"],
                    figure_ids=[],
                ),
                file_hash=f"hash-{upload_index}",
                extracted_at=datetime(2026, 7, 2, 0, 0, 0),
            )
        )
    return PaperReparseSource(
        paper_id=paper_id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        documents=documents,
        primary_index=primary_index,
    )


def _record(paper_id: str, value: str) -> PaperPlanRecord:
    spec = _spec(document_id="DOC-001", filename="paper.pdf", value=value)
    return PaperPlanRecord(
        paper_id=paper_id,
        spec=spec,
        plan=_plan(paper_id, value, spec.evidence[0]),
        missing_prompts=[],
        missing_bindings=[],
    )


def _spec(*, document_id: str, filename: str, value: str) -> PaperSpec:
    evidence = _evidence(document_id)
    return PaperSpec(
        paper_title=f"Report {value}",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id=document_id, filename=filename)],
        primary_document_id=None,
        abstract="A synchronous machine short-circuit report.",
        equations=[EquationEntry("EQ-01", f"H = {value}", "S1", document_id)],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value=value,
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id=document_id,
            )
        ],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _plan(paper_id: str, value: str, evidence: PaperEvidenceEntry) -> ModelGenerationPlan:
    return ModelGenerationPlan(
        plan_id=f"PLAN-{paper_id}",
        paper_spec_id=paper_id,
        library_choice="SimPowerSystems",
        block_recommendations=[
            BlockRecommendation(
                block_type="Synchronous Machine",
                purpose="Model the generator.",
                paper_reference=evidence,
            )
        ],
        parameter_mapping=[
            ParameterMapping(
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
                value=value,
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=[evidence],
    )


def _evidence(document_id: str) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id=document_id,
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
