"""Apply and undo user corrections to extracted paper parameters."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, NoReturn

from loguru import logger

from core.domain.exceptions import PaperNotFoundError, PaperParameterCorrectionError, StoreError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_parameter_correction import (
    PaperParameterCorrection,
    PlanCorrectionTarget,
)
from core.domain.paper_plan import ModelGenerationPlan, PaperPlanRecord, ParameterMapping
from core.domain.paper_spec import PaperDocument, PaperSpec, ParameterConflict
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_parameter_correction_schemas import CorrectionTargetRequest

CanUndoReason = Literal["active", "target_stale", "missing_mapping"]


@dataclass(frozen=True)
class ParameterCorrectionView:
    correction: PaperParameterCorrection
    document_label: str | None
    can_undo: bool
    can_undo_reason: CanUndoReason


@dataclass(frozen=True)
class ParameterCorrectionApplyResult:
    record: PaperPlanRecord
    correction: PaperParameterCorrection
    view: ParameterCorrectionView


@dataclass(frozen=True)
class ParameterCorrectionsListResult:
    paper_id: str
    views: list[ParameterCorrectionView]


class ParameterCorrectionService:
    """State machine for correction overlays on plan parameter mappings."""

    _ERROR_STATUS: dict[str, int] = {
        "correction_target_not_extracted": 400,
        "correction_requires_local_rerun": 409,
        "correction_target_ambiguous": 400,
        "correction_target_stale": 409,
        "correction_target_not_correctable": 400,
        "correction_invalid_value": 400,
        "correction_unit_invalid": 400,
        "correction_not_found": 404,
        "correction_store_failed": 500,
    }
    _ERROR_TARGET_KIND: dict[str, str] = {
        "correction_target_not_extracted": "target_not_extracted",
        "correction_requires_local_rerun": "target_conflict",
        "correction_target_ambiguous": "target_ambiguous",
        "correction_target_stale": "target_stale",
        "correction_target_not_correctable": "target_not_correctable",
    }

    def __init__(self, store: PaperBundleStore) -> None:
        self._store = store

    async def apply(
        self,
        paper_id: str,
        *,
        target: CorrectionTargetRequest,
        corrected_value: str,
        corrected_unit: str | None,
        corrected_unit_supplied: bool,
    ) -> ParameterCorrectionApplyResult:
        record = await self._require_record(paper_id)
        corrections = await self._store.list_parameter_corrections(paper_id)

        mapping_index = self._locate_target(record, target)
        mapping = record.plan.parameter_mapping[mapping_index]
        value = self._clean_corrected_value(corrected_value)
        unit = self._clean_corrected_unit(
            corrected_unit,
            current_unit=mapping.unit,
            supplied=corrected_unit_supplied,
        )
        active_correction = self._active_correction_for_mapping(
            record,
            corrections,
            target=target,
            mapping_index=mapping_index,
        )

        now = _utcnow_iso_z()
        if mapping.source is EvidenceSource.DOCUMENT_EXTRACTED:
            correction = PaperParameterCorrection(
                correction_id=f"CORR-{uuid.uuid4()}",
                paper_id=record.paper_id,
                param_key=_param_key(mapping),
                plan_target=PlanCorrectionTarget(
                    paper_param_name=mapping.paper_param_name,
                    model_param_name=mapping.model_param_name,
                    plan_mapping_index=mapping_index,
                ),
                original_value=mapping.value,
                original_unit=mapping.unit,
                original_source=EvidenceSource.DOCUMENT_EXTRACTED,
                original_document_id=self._original_document_id(record.spec, mapping),
                corrected_value=value,
                corrected_unit=unit,
                created_at=now,
                updated_at=now,
            )
            is_recorrect = False
            target_kind = "created_document_extracted"
        elif mapping.source is EvidenceSource.USER_SUPPLIED and active_correction is not None:
            correction = replace(
                active_correction,
                corrected_value=value,
                corrected_unit=unit,
                updated_at=now,
            )
            is_recorrect = True
            target_kind = "updated_existing_correction"
        else:
            self._raise("correction_target_not_correctable")

        updated_record = self._record_with_applied_correction(
            record,
            mapping_index=mapping_index,
            correction=correction,
        )
        try:
            await self._store.apply_parameter_correction_atomically(
                paper_id,
                updated_record,
                correction,
                is_recorrect=is_recorrect,
            )
        except StoreError:
            self._raise("correction_store_failed")

        self._log_telemetry(target_kind, correction_created_count=1, undo_count=0)
        return ParameterCorrectionApplyResult(
            record=updated_record,
            correction=correction,
            view=self._view_for_correction(updated_record, correction),
        )

    async def undo(self, paper_id: str, correction_id: str) -> PaperPlanRecord:
        record = await self._require_record(paper_id)
        correction = await self._store.get_parameter_correction(paper_id, correction_id)
        if correction is None:
            self._raise("correction_not_found")

        mapping_index = correction.plan_target.plan_mapping_index
        if not _target_matches_mapping(record.plan, correction):
            self._raise("correction_target_stale")
        evidence_indexes = [
            index
            for index, entry in enumerate(record.plan.evidence)
            if _is_evidence_for_correction(entry, correction.correction_id)
        ]
        if len(evidence_indexes) != 1:
            self._raise("correction_store_failed")

        plan_copy = deepcopy(record.plan)
        mapping = plan_copy.parameter_mapping[mapping_index]
        parameter_mapping = list(plan_copy.parameter_mapping)
        parameter_mapping[mapping_index] = replace(
            mapping,
            value=correction.original_value,
            unit=correction.original_unit,
            source=correction.original_source,
        )
        evidence = [
            entry
            for entry in plan_copy.evidence
            if not _is_evidence_for_correction(entry, correction.correction_id)
        ]
        plan_copy = replace(
            plan_copy,
            parameter_mapping=parameter_mapping,
            evidence=evidence,
            m_script_skeleton=None,
            build_steps=None,
        )
        updated_record = replace(record, plan=plan_copy)

        try:
            await self._store.undo_parameter_correction_atomically(
                paper_id,
                updated_record,
                correction.correction_id,
            )
        except StoreError:
            self._raise("correction_store_failed")

        self._log_telemetry("undo", correction_created_count=0, undo_count=1)
        return updated_record

    async def list_corrections(self, paper_id: str) -> ParameterCorrectionsListResult:
        record = await self._require_record(paper_id)
        corrections = await self._store.list_parameter_corrections(paper_id)
        return ParameterCorrectionsListResult(
            paper_id=paper_id,
            views=[self._view_for_correction(record, correction) for correction in corrections],
        )

    async def _require_record(self, paper_id: str) -> PaperPlanRecord:
        record = await self._store.get_plan_record(paper_id)
        if record is None:
            raise PaperNotFoundError("paper_not_found") from None
        return record

    def _locate_target(self, record: PaperPlanRecord, target: CorrectionTargetRequest) -> int:
        candidates = [
            index
            for index, mapping in enumerate(record.plan.parameter_mapping)
            if mapping.paper_param_name == target.paper_param_name
            and mapping.model_param_name == target.model_param_name
        ]
        if not candidates:
            if self._hits_unique_conflict(record.spec.parameter_conflicts, target):
                self._raise("correction_requires_local_rerun")
            self._raise("correction_target_not_extracted")
        if len(candidates) > 1:
            self._raise("correction_target_ambiguous")

        mapping_index = candidates[0]
        mapping = record.plan.parameter_mapping[mapping_index]
        if mapping_index != target.plan_mapping_index:
            self._raise("correction_target_stale")
        if mapping.value != target.expected_value or mapping.unit != target.expected_unit:
            self._raise("correction_target_stale")
        return mapping_index

    def _active_correction_for_mapping(
        self,
        record: PaperPlanRecord,
        corrections: list[PaperParameterCorrection],
        *,
        target: CorrectionTargetRequest,
        mapping_index: int,
    ) -> PaperParameterCorrection | None:
        matching = [
            correction
            for correction in corrections
            if correction.param_key == f"{target.paper_param_name}::{target.model_param_name}"
            and correction.plan_target.plan_mapping_index == mapping_index
            and correction.plan_target.paper_param_name == target.paper_param_name
            and correction.plan_target.model_param_name == target.model_param_name
        ]
        if not matching:
            return None
        if len(matching) > 1:
            self._raise("correction_store_failed")
        correction = matching[0]
        evidence_count = sum(
            1
            for entry in record.plan.evidence
            if _is_evidence_for_correction(entry, correction.correction_id)
        )
        if evidence_count != 1:
            self._raise("correction_store_failed")
        return correction

    def _record_with_applied_correction(
        self,
        record: PaperPlanRecord,
        *,
        mapping_index: int,
        correction: PaperParameterCorrection,
    ) -> PaperPlanRecord:
        plan_copy = deepcopy(record.plan)
        mapping = plan_copy.parameter_mapping[mapping_index]
        parameter_mapping = list(plan_copy.parameter_mapping)
        parameter_mapping[mapping_index] = replace(
            mapping,
            value=correction.corrected_value,
            unit=correction.corrected_unit,
            source=EvidenceSource.USER_SUPPLIED,
        )
        evidence = [
            entry
            for entry in plan_copy.evidence
            if not _is_evidence_for_correction(entry, correction.correction_id)
        ]
        evidence.append(
            PaperEvidenceEntry(
                source=EvidenceSource.USER_SUPPLIED,
                document_id=None,
                paper_section_id=None,
                equation_id=None,
                figure_id=None,
                excerpt=None,
                missing_param_prompt_id=None,
                user_action=UserEvidenceAction.CORRECT_EXTRACTED,
                parameter_correction_id=correction.correction_id,
                correction_param_key=correction.param_key,
            )
        )
        plan_copy = replace(
            plan_copy,
            parameter_mapping=parameter_mapping,
            evidence=evidence,
            m_script_skeleton=None,
            build_steps=None,
        )
        return replace(record, plan=plan_copy)

    def _view_for_correction(
        self,
        record: PaperPlanRecord,
        correction: PaperParameterCorrection,
    ) -> ParameterCorrectionView:
        document_label = _document_label(record.spec.documents, correction.original_document_id)
        reason = _can_undo_reason(record, correction)
        return ParameterCorrectionView(
            correction=correction,
            document_label=document_label,
            can_undo=reason == "active",
            can_undo_reason=reason,
        )

    def _original_document_id(self, spec: PaperSpec, mapping: ParameterMapping) -> str | None:
        matches = [
            entry.document_id
            for entry in spec.parameter_table
            if entry.source is EvidenceSource.DOCUMENT_EXTRACTED
            and entry.document_id is not None
            and (entry.name == mapping.paper_param_name or entry.symbol == mapping.paper_param_name)
            and entry.value == mapping.value
            and entry.unit == (mapping.unit or "")
        ]
        unique = set(matches)
        if len(unique) != 1:
            return None
        return next(iter(unique))

    def _hits_unique_conflict(
        self,
        conflicts: list[ParameterConflict],
        target: CorrectionTargetRequest,
    ) -> bool:
        matches = [
            conflict
            for conflict in conflicts
            if target.paper_param_name in {conflict.parameter_name, conflict.parameter_symbol}
        ]
        return len(matches) == 1

    def _clean_corrected_value(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or _has_control_char(cleaned):
            self._raise("correction_invalid_value")
        return cleaned

    def _clean_corrected_unit(
        self,
        unit: str | None,
        *,
        current_unit: str | None,
        supplied: bool,
    ) -> str | None:
        if not supplied:
            return current_unit
        if unit is None:
            return None
        cleaned = unit.strip()
        if not cleaned or _has_control_char(cleaned):
            self._raise("correction_unit_invalid")
        return cleaned

    def _raise(self, error_code: str) -> NoReturn:
        target_kind = self._ERROR_TARGET_KIND.get(error_code)
        if target_kind is not None:
            self._log_telemetry(target_kind, correction_created_count=0, undo_count=0)
        raise PaperParameterCorrectionError(
            error_code,
            self._ERROR_STATUS[error_code],
        ) from None

    def _log_telemetry(
        self,
        target_kind: str,
        *,
        correction_created_count: int,
        undo_count: int,
    ) -> None:
        logger.info(
            "paper_parameter_correction event_code={} target_kind={} "
            "correction_created_count={} undo_count={}",
            "paper_parameter_correction",
            target_kind,
            correction_created_count,
            undo_count,
        )


def _param_key(mapping: ParameterMapping) -> str:
    return f"{mapping.paper_param_name}::{mapping.model_param_name}"


def _is_evidence_for_correction(entry: PaperEvidenceEntry, correction_id: str) -> bool:
    return (
        entry.source is EvidenceSource.USER_SUPPLIED
        and entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED
        and entry.parameter_correction_id == correction_id
    )


def _target_matches_mapping(
    plan: ModelGenerationPlan,
    correction: PaperParameterCorrection,
) -> bool:
    return _can_undo_reason_for_plan(plan, correction) == "active"


def _can_undo_reason(
    record: PaperPlanRecord, correction: PaperParameterCorrection
) -> CanUndoReason:
    return _can_undo_reason_for_plan(record.plan, correction)


def _can_undo_reason_for_plan(
    plan: ModelGenerationPlan,
    correction: PaperParameterCorrection,
) -> CanUndoReason:
    target = correction.plan_target
    if target.plan_mapping_index < 0 or target.plan_mapping_index >= len(plan.parameter_mapping):
        return "missing_mapping"
    mapping = plan.parameter_mapping[target.plan_mapping_index]
    if (
        correction.param_key != f"{target.paper_param_name}::{target.model_param_name}"
        or mapping.paper_param_name != target.paper_param_name
        or mapping.model_param_name != target.model_param_name
        or mapping.source is not EvidenceSource.USER_SUPPLIED
    ):
        return "target_stale"
    return "active"


def _document_label(documents: list[PaperDocument], document_id: str | None) -> str | None:
    if document_id is None:
        return None
    for document in documents:
        if document.document_id == document_id:
            return document.filename
    return None


def _has_control_char(value: str) -> bool:
    return any(ord(char) < 32 for char in value)


def _utcnow_iso_z() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
