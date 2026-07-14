from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal, cast

from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_plan import (
    ConnectionHint,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceExecutionClosure,
    GuidanceGap,
    GuidanceObligationKind,
    GuidanceResolution,
    GuidanceTarget,
    GuidanceTargetKind,
    ModelBuildStep,
    StepBlockRef,
)
from features.paper.build_guidance_rules import (
    DISPLAY_BLOCK_TERMS,
    REAL_BLOCK_ALLOW_TERMS,
    canonicalize,
    clean_display_text,
    configuration_key,
    connection_key,
    parameter_ref_key,
)

ACTIONABLE_CLOSURES = frozenset({"closed", "guided_choice", "guided_probe"})
DOCUMENT_BASES = frozenset({"document_extracted", "document_derived"})
PUNT_REASON_CODES = frozenset(
    {
        "source_does_not_specify",
        "upstream_step_underspecified",
        "requires_user_context",
        "outside_guidance_contract",
    }
)
_CLOSED_BASES = frozenset(
    {"document_extracted", "document_derived", "domain_default", "engineering_choice"}
)
_RESOLUTION_KINDS = frozenset(
    {
        "fixed",
        "range",
        "enum_selection",
        "derivation",
        "conditional",
        "guided_user_decision",
        "environment_probe",
    }
)
_FIXED_RESOLUTION_KINDS = frozenset(
    {"numeric", "block_ref", "configuration_option", "connection_mode"}
)
_VALUE_TOKEN_RE = re.compile(r"^[A-Za-z0-9]{1,40}$")
_SOURCE_REDIRECT_RE = re.compile(
    r"\b(?:confirm|check|verify)\b[^。；;.!?]*(?:source material|paper)\.?",
    re.IGNORECASE,
)
_CHINESE_SOURCE_REDIRECT_RE = re.compile(
    r"(?:请)?(?:查看|核对|对照|回到|参照)[^。；;]{0,18}(?:论文|原文|文献|资料)"
)


@dataclass(frozen=True)
class GuidanceRequirement:
    """Private requirement with a prompt handle scoped to one generated artifact."""

    requirement_ref: str
    paper_id: str
    step_id: str
    obligation_kind: GuidanceObligationKind
    target: GuidanceTarget

    @property
    def requirement_key(self) -> tuple[object, ...]:
        return (
            self.paper_id,
            self.step_id,
            self.obligation_kind,
            self.target.target_kind,
            *_target_identity(self.target),
        )


@dataclass(frozen=True)
class GuidanceReduction:
    gaps: list[GuidanceGap]
    assessment: GuidanceAssessment
    machine_codes: list[str]


def enumerate_guidance_requirements(
    paper_id: str,
    build_steps: list[ModelBuildStep],
) -> list[GuidanceRequirement]:
    """Return deterministic requirement handles for object-level build obligations."""

    requirements: list[GuidanceRequirement] = []
    seen_keys: set[tuple[object, ...]] = set()
    for step in critical_steps(build_steps):
        for obligation_kind, target in required_targets_for_step(step):
            requirement = GuidanceRequirement(
                requirement_ref=f"REQ-{len(requirements) + 1:03d}",
                paper_id=paper_id,
                step_id=step.step_id,
                obligation_kind=obligation_kind,
                target=target,
            )
            if requirement.requirement_key in seen_keys:
                continue
            seen_keys.add(requirement.requirement_key)
            requirements.append(requirement)
    return requirements


def guidance_requirements_prompt_payload(
    requirements: list[GuidanceRequirement],
) -> list[dict[str, Any]]:
    """Return the private REQ handle list passed to the LLM."""

    return [
        {
            "requirement_ref": requirement.requirement_ref,
            "step_id": requirement.step_id,
            "target_kind": requirement.target.target_kind,
            "target_label": target_label(requirement.target),
        }
        for requirement in requirements
    ]


def required_targets_for_step(
    step: ModelBuildStep,
) -> list[tuple[GuidanceObligationKind, GuidanceTarget]]:
    """Map the existing object coverage seed to v2 target families."""

    result: list[tuple[GuidanceObligationKind, GuidanceTarget]] = []
    for block_ref in step.block_refs:
        if not block_ref_is_real(block_ref):
            continue
        result.append(
            (
                "select_component",
                GuidanceTarget(
                    target_kind="block_choice",
                    block_role_ref=block_ref.block_ref_id,
                ),
            )
        )
    for parameter_ref in step.parameter_refs:
        result.append(
            (
                "determine_parameter_value",
                GuidanceTarget(
                    target_kind="parameter",
                    model_param=parameter_ref.model_param_name,
                    paper_param=parameter_ref.paper_param_name or None,
                ),
            )
        )
    for connection in step.connection_hints:
        if connection_is_display_only(step, connection):
            continue
        result.append(
            (
                "connect_signal",
                GuidanceTarget(
                    target_kind="connection",
                    from_block=connection.from_block_ref,
                    from_port=connection.from_port,
                    to_block=connection.to_block_ref,
                    to_port=connection.to_port,
                    signal_role=connection.signal_meaning,
                ),
            )
        )
    for hint in step.configuration_hints:
        result.append(
            (
                "configure_setting",
                GuidanceTarget(
                    target_kind="configuration",
                    owner_ref=hint.target,
                    setting_name=hint.setting_name or hint.instruction,
                ),
            )
        )
    return result


def reduce_guidance_requirements(
    *,
    requirements: list[GuidanceRequirement],
    details: list[GuidanceDetail],
) -> GuidanceReduction:
    """Derive gaps and summary counts from requirement closure state."""

    details_by_requirement: dict[tuple[object, ...], list[GuidanceDetail]] = defaultdict(list)
    requirement_by_key = {
        requirement_key_without_paper(requirement): requirement for requirement in requirements
    }
    machine_codes: list[str] = []
    for detail in details:
        key = requirement_key_for_detail(detail)
        if key not in requirement_by_key:
            machine_codes.append("requirement_mismatch")
            continue
        if detail.execution_closure in ACTIONABLE_CLOSURES:
            details_by_requirement[key].append(detail)

    gaps: list[GuidanceGap] = []
    pending_user_choice_count = 0
    pending_environment_probe_count = 0
    open_requirement_count = 0
    for requirement in requirements:
        closers = details_by_requirement.get(requirement_key_without_paper(requirement), [])
        if len(closers) == 1:
            closure = closers[0].execution_closure
            if closure == "guided_choice":
                pending_user_choice_count += 1
            elif closure == "guided_probe":
                pending_environment_probe_count += 1
            continue
        open_requirement_count += 1
        failure_code = "requirement_ambiguous" if len(closers) > 1 else "does_not_close_gap"
        if len(closers) > 1:
            machine_codes.extend(["duplicate_closing_detail", "requirement_ambiguous"])
        gaps.append(
            GuidanceGap(
                gap_id=f"GAP-{len(gaps) + 1:03d}",
                gap_kind=cast(Any, gap_kind_for_target(requirement.target.target_kind)),
                scope="step",
                step_id=requirement.step_id,
                basis="user_confirmation_required",
                severity="blocking",
                display_text=gap_display_text(requirement),
                target=requirement.target,
                obligation_kind=requirement.obligation_kind,
                execution_closure="open",
                failure_code=failure_code,
            )
        )

    blocking_gap_ids = [gap.gap_id for gap in gaps if gap.severity == "blocking"]
    content_status: Literal["reproducible_candidate", "outline_with_gaps", "outline_only"] = (
        "outline_with_gaps" if blocking_gap_ids else "reproducible_candidate"
    )
    overall_status: Literal[
        "reproducible_candidate_env_unchecked", "outline_with_gaps", "outline_only"
    ] = "outline_with_gaps" if blocking_gap_ids else "reproducible_candidate_env_unchecked"
    return GuidanceReduction(
        gaps=gaps,
        assessment=GuidanceAssessment(
            content_status=content_status,
            environment_status="not_checked",
            overall_status=overall_status,
            blocking_gap_ids=blocking_gap_ids,
            pending_user_choice_count=pending_user_choice_count,
            pending_environment_probe_count=pending_environment_probe_count,
            open_requirement_count=open_requirement_count,
        ),
        machine_codes=unique_codes(machine_codes),
    )


def requirement_key_for_detail(detail: GuidanceDetail) -> tuple[object, ...] | None:
    if detail.target is None or detail.obligation_kind is None:
        return None
    return (
        None,
        detail.step_id,
        detail.obligation_kind,
        detail.target.target_kind,
        *_target_identity(detail.target),
    )


def requirement_key_without_paper(requirement: GuidanceRequirement) -> tuple[object, ...]:
    return (
        None,
        requirement.step_id,
        requirement.obligation_kind,
        requirement.target.target_kind,
        *_target_identity(requirement.target),
    )


def target_to_dict(target: GuidanceTarget) -> dict[str, str | None]:
    return {
        "target_kind": target.target_kind,
        "model_param": target.model_param,
        "paper_param": target.paper_param,
        "owner_ref": target.owner_ref,
        "setting_name": target.setting_name,
        "block_role_ref": target.block_role_ref,
        "from_block": target.from_block,
        "from_port": target.from_port,
        "to_block": target.to_block,
        "to_port": target.to_port,
        "signal_role": target.signal_role,
    }


def target_label(target: GuidanceTarget) -> str:
    if target.target_kind == "parameter":
        if target.paper_param:
            return f"参数 {target.paper_param} -> {target.model_param}"
        return f"参数 {target.model_param}"
    if target.target_kind == "block_choice":
        return f"模块角色 {target.block_role_ref}"
    if target.target_kind == "connection":
        from_ref = _port_label(target.from_block, target.from_port)
        to_ref = _port_label(target.to_block, target.to_port)
        suffix = f" ({target.signal_role})" if target.signal_role else ""
        return f"连接 {from_ref} -> {to_ref}{suffix}"
    owner = target.owner_ref or "模型"
    setting = target.setting_name or "设置"
    return f"配置 {owner}.{setting}"


def gap_display_text(requirement: GuidanceRequirement) -> str:
    label = target_label(requirement.target)
    if requirement.target.target_kind == "parameter":
        return f"需要确定{label}。"
    if requirement.target.target_kind == "block_choice":
        return f"需要选择{label}对应的可用模块。"
    if requirement.target.target_kind == "connection":
        return f"需要确定{label}。"
    return f"需要确定{label}。"


def render_detail_display_text(
    *,
    basis: str,
    target: GuidanceTarget,
    resolution: GuidanceResolution | dict[str, Any] | None,
    punt_reason_code: str | None = None,
) -> str:
    prefix = {
        "document_extracted": "论文明确给出",
        "document_derived": "由论文信息推导",
        "domain_default": "领域默认（非论文）",
        "engineering_choice": "本方案选择（可改）",
        "user_environment": "需确认你的环境",
        "user_decision": "需你决定",
        "user_confirmation_required": "暂无法确定",
        "document_claim_unverified": "论文依据未核实（未采用）",
    }.get(basis, "指导")
    label = target_label(target)
    if basis == "user_confirmation_required":
        reason = punt_reason_code or "source_does_not_specify"
        return f"{prefix}：{label}；原因：{reason}。"
    if basis == "document_claim_unverified":
        return f"{prefix}：{label}。"
    resolution_text = _resolution_text(resolution)
    if resolution_text:
        return f"{prefix}：{label}；{resolution_text}。"
    return f"{prefix}：{label}。"


def detail_kind_for_target(target_kind: GuidanceTargetKind) -> str:
    if target_kind == "parameter":
        return "parameter_value"
    if target_kind == "block_choice":
        return "block_selection"
    if target_kind == "connection":
        return "connection"
    return "configuration"


def gap_kind_for_target(target_kind: GuidanceTargetKind) -> str:
    if target_kind == "parameter":
        return "missing_parameter_value"
    if target_kind == "block_choice":
        return "missing_support_component"
    if target_kind == "connection":
        return "missing_connection_detail"
    return "missing_configuration_detail"


def actionability_for_closure(
    closure: GuidanceExecutionClosure,
) -> Literal["actionable", "notice_only", "blocked_pending_confirmation"]:
    if closure in ACTIONABLE_CLOSURES:
        return "actionable"
    return "blocked_pending_confirmation"


def closure_from_resolution(
    *,
    basis: str,
    target: GuidanceTarget,
    resolution: GuidanceResolution | dict[str, Any] | None,
    input_fact_refs: list[str],
    punt_reason_code: str | None,
    step: ModelBuildStep | None = None,
) -> tuple[GuidanceExecutionClosure | None, str | None]:
    """Validate the v2 resolution union and derive execution closure."""

    if basis == "user_confirmation_required":
        if resolution is not None or input_fact_refs:
            return None, "punt_from_exception_forbidden"
        if punt_reason_code not in PUNT_REASON_CODES:
            return None, "resolution_missing"
        return "open", None
    if basis == "document_claim_unverified":
        if resolution is not None or input_fact_refs:
            return None, "relabel_without_resolution"
        return "open", None
    if not isinstance(resolution, dict):
        return None, "resolution_missing"
    kind = resolution.get("kind")
    if kind not in _RESOLUTION_KINDS:
        return None, "resolution_kind_invalid"
    if basis in _CLOSED_BASES:
        if kind in {"guided_user_decision", "environment_probe"}:
            return None, "resolution_kind_invalid"
        code = _resolution_payload_error(kind, target, resolution, input_fact_refs, step)
        if code is not None:
            return None, code
        return "closed", None
    if basis == "user_decision":
        if kind != "guided_user_decision":
            return None, "decision_procedure_incomplete"
        code = _resolution_payload_error(kind, target, resolution, input_fact_refs, step)
        if code is not None:
            return None, code
        return "guided_choice", None
    if basis == "user_environment":
        if kind != "environment_probe":
            return None, "probe_incomplete"
        code = _resolution_payload_error(kind, target, resolution, input_fact_refs, step)
        if code is not None:
            return None, code
        return "guided_probe", None
    return None, "resolution_kind_invalid"


def critical_steps(build_steps: list[ModelBuildStep]) -> list[ModelBuildStep]:
    return [step for step in build_steps if is_critical_step(step)]


def _resolution_payload_error(
    kind: str,
    target: GuidanceTarget,
    resolution: GuidanceResolution | dict[str, Any],
    input_fact_refs: list[str],
    step: ModelBuildStep | None,
) -> str | None:
    if kind == "fixed":
        return _fixed_resolution_payload_error(target, resolution, step)
    if kind == "range":
        has_bounds = _present(resolution.get("lower")) and _present(resolution.get("upper"))
        has_values = isinstance(resolution.get("values"), list) and bool(resolution.get("values"))
        has_start = _present(resolution.get("recommended_start")) or _present(
            resolution.get("selection_rule")
        )
        return None if (has_bounds or has_values) and has_start else "range_incomplete"
    if kind == "enum_selection":
        return None if _present(resolution.get("selected")) else "resolution_missing"
    if kind == "derivation":
        has_rule = _present(resolution.get("formula")) or _present(resolution.get("rule"))
        inputs = resolution.get("inputs")
        if not has_rule or not isinstance(inputs, list) or not inputs or not input_fact_refs:
            return "derivation_input_unresolved"
        return None
    if kind == "conditional":
        branches = resolution.get("branches")
        has_fallback = _present(resolution.get("fallback")) or resolution.get("exhaustive") is True
        return (
            None
            if isinstance(branches, list) and branches and has_fallback
            else ("conditional_non_exhaustive")
        )
    if kind == "guided_user_decision":
        options = resolution.get("options")
        if not _present(resolution.get("decision_item")) or not _present(
            resolution.get("criteria")
        ):
            return "decision_procedure_incomplete"
        if not isinstance(options, list) or not options:
            return "decision_procedure_incomplete"
        for option in options:
            if not isinstance(option, dict):
                return "decision_procedure_incomplete"
            if not _present(option.get("option")) or not _present(option.get("consequence")):
                return "decision_procedure_incomplete"
        return None
    if kind == "environment_probe":
        actions = resolution.get("result_actions")
        if not _present(resolution.get("probe_item")) or not _present(resolution.get("procedure")):
            return "probe_incomplete"
        if not isinstance(actions, list) or not actions:
            return "probe_incomplete"
        for action in actions:
            if not isinstance(action, dict):
                return "probe_incomplete"
            if not _present(action.get("result")) or not _present(action.get("action")):
                return "probe_incomplete"
        return None
    return "resolution_kind_invalid"


def _fixed_resolution_payload_error(
    target: GuidanceTarget,
    resolution: GuidanceResolution | dict[str, Any],
    step: ModelBuildStep | None,
) -> str | None:
    fixed_kind = resolution.get("fixed_kind")
    if fixed_kind not in _FIXED_RESOLUTION_KINDS:
        return "resolution_kind_invalid"
    if fixed_kind == "numeric":
        if target.target_kind != "parameter":
            return "resolution_kind_invalid"
        value = resolution.get("value")
        if not _strict_number(value):
            return "resolution_missing"
        if not _present(resolution.get("unit")):
            return "resolution_missing"
        return None
    if fixed_kind == "block_ref":
        if target.target_kind != "block_choice":
            return "resolution_kind_invalid"
        selected_id = resolution.get("selected_id")
        if not isinstance(selected_id, str) or not selected_id.strip():
            return "resolution_missing"
        candidate_ids = {block_ref.block_ref_id for block_ref in step.block_refs} if step else set()
        target_id = target.block_role_ref
        if selected_id not in candidate_ids or (target_id is not None and selected_id != target_id):
            return "choice_not_allowed"
        return None
    if fixed_kind == "configuration_option":
        if target.target_kind != "configuration":
            return "resolution_kind_invalid"
        return _choice_token_error(resolution)
    if fixed_kind == "connection_mode":
        if target.target_kind != "connection":
            return "resolution_kind_invalid"
        return _choice_token_error(resolution)
    return "resolution_kind_invalid"


def _choice_token_error(resolution: GuidanceResolution | dict[str, Any]) -> str | None:
    token = resolution.get("value_token")
    if not isinstance(token, str) or not _VALUE_TOKEN_RE.fullmatch(token):
        return "value_token_invalid"
    if not _present(resolution.get("display_label")):
        return "resolution_missing"
    return None


def _strict_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def is_critical_step(step: ModelBuildStep) -> bool:
    if step.parameter_refs or step.configuration_hints:
        return True
    if step.connection_hints and not all(
        connection_is_display_only(step, hint) for hint in step.connection_hints
    ):
        return True
    if not step.block_refs:
        return False
    return any(block_ref_is_real(block_ref) for block_ref in step.block_refs)


def block_ref_is_real(block_ref: StepBlockRef) -> bool:
    text = " ".join(
        part for part in (block_ref.block_type, block_ref.purpose, block_ref.library_path) if part
    ).casefold()
    if any(term in text for term in REAL_BLOCK_ALLOW_TERMS):
        return True
    return not any(term in text for term in DISPLAY_BLOCK_TERMS)


def connection_is_display_only(step: ModelBuildStep, hint: ConnectionHint) -> bool:
    refs = {block_ref.block_ref_id: block_ref for block_ref in step.block_refs}
    blocks = [refs.get(hint.from_block_ref), refs.get(hint.to_block_ref)]
    present = [block for block in blocks if block is not None]
    return bool(present) and all(not block_ref_is_real(block) for block in present)


def required_object_coverage(
    step: ModelBuildStep,
    covered_params: set[tuple[str, str]],
) -> list[tuple[str, str, bool]]:
    """Compatibility view of the old object coverage seed."""

    result: list[tuple[str, str, bool]] = []
    for block_ref in step.block_refs:
        covered = (
            block_ref.paper_reference is not None
            and block_ref.paper_reference.source is EvidenceSource.DOCUMENT_EXTRACTED
        )
        result.append(("block", block_ref.block_ref_id, covered))
    for parameter_ref in step.parameter_refs:
        key = (parameter_ref.paper_param_name, parameter_ref.model_param_name)
        result.append(("parameter", parameter_ref_key(parameter_ref), key in covered_params))
    for index, connection in enumerate(step.connection_hints, start=1):
        result.append(("connection", connection_key(connection, index), False))
    for index, hint in enumerate(step.configuration_hints, start=1):
        covered = any(entry.source is EvidenceSource.DOCUMENT_EXTRACTED for entry in hint.evidence)
        result.append(("configuration", configuration_key(step.step_id, hint, index), covered))
    return result


def claim_mentions_other_requirement(
    claim_text: str,
    requirement: GuidanceRequirement,
    requirements: list[GuidanceRequirement],
) -> bool:
    """Conservative guard against one draft detail closing multiple object claims."""

    claim = canonicalize(claim_text)
    if not claim:
        return False
    for other in requirements:
        if other.requirement_ref == requirement.requirement_ref:
            continue
        if other.step_id != requirement.step_id:
            continue
        if _target_markers_present(claim, other.target):
            return True
    return False


def detail_has_document_basis(detail: GuidanceDetail) -> bool:
    return (
        detail.basis in DOCUMENT_BASES
        and detail.execution_closure == "closed"
        and bool(detail.evidence)
    )


def unique_codes(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result


def _target_identity(target: GuidanceTarget) -> tuple[str, ...]:
    if target.target_kind == "parameter":
        return (
            canonicalize(target.model_param),
            canonicalize(target.paper_param),
        )
    if target.target_kind == "configuration":
        return (
            canonicalize(target.owner_ref),
            canonicalize(target.setting_name),
        )
    if target.target_kind == "block_choice":
        return (canonicalize(target.block_role_ref),)
    return (
        canonicalize(target.from_block),
        canonicalize(target.from_port),
        canonicalize(target.to_block),
        canonicalize(target.to_port),
        canonicalize(target.signal_role),
    )


def _target_markers_present(claim: str, target: GuidanceTarget) -> bool:
    markers = _target_markers(target)
    if not markers:
        return False
    if target.target_kind == "connection":
        required = [marker for marker in markers[:2] if marker]
        return bool(required) and all(marker in claim for marker in required)
    return any(marker in claim for marker in markers)


def _target_markers(target: GuidanceTarget) -> list[str]:
    markers = [
        target.model_param,
        target.paper_param,
        target.owner_ref,
        target.setting_name,
        target.block_role_ref,
        target.from_block,
        target.to_block,
        target.signal_role,
    ]
    return [
        canonical
        for marker in markers
        if (canonical := canonicalize(marker)) and len(canonical) >= 2
    ]


def _resolution_text(resolution: GuidanceResolution | dict[str, Any] | None) -> str:
    if not isinstance(resolution, dict):
        return ""
    kind = str(resolution.get("kind") or "")
    if kind == "fixed":
        fixed_kind = str(resolution.get("fixed_kind") or "")
        if fixed_kind == "numeric":
            value = _resolution_fragment(resolution.get("value"), fallback="待确认")
            unit = _resolution_fragment(resolution.get("unit"), fallback="")
            return f"取值 {value}{(' ' + unit) if unit else ''}".strip()
        if fixed_kind == "block_ref":
            selected_id = _resolution_fragment(resolution.get("selected_id"), fallback="待确认")
            return f"选择模块 {selected_id}"
        if fixed_kind in {"configuration_option", "connection_mode"}:
            label = _resolution_fragment(resolution.get("display_label"), fallback="待确认")
            return f"设为 {label}"
        return ""
    if kind == "range":
        lower = _resolution_fragment(resolution.get("lower"), fallback="待确认")
        upper = _resolution_fragment(resolution.get("upper"), fallback="待确认")
        start = _resolution_fragment(
            resolution.get("recommended_start") or resolution.get("selection_rule"),
            fallback="待确认",
        )
        return f"范围 {lower} 到 {upper}；起点/规则 {start}"
    if kind == "enum_selection":
        return f"选择 {_resolution_fragment(resolution.get('selected'), fallback='待确认')}"
    if kind == "derivation":
        rule = _resolution_fragment(
            resolution.get("rule") or resolution.get("formula"),
            fallback="待确认",
        )
        return f"按规则推导：{rule}"
    if kind == "conditional":
        return "按完整条件分支执行"
    if kind == "guided_user_decision":
        return f"按判据选择：{_resolution_fragment(resolution.get('criteria'), fallback='待确认')}"
    if kind == "environment_probe":
        return f"检查方法：{_resolution_fragment(resolution.get('procedure'), fallback='待确认')}"
    return ""


def _resolution_fragment(value: Any, *, fallback: str) -> str:
    text = clean_display_text(str(value or ""))
    text = _SOURCE_REDIRECT_RE.sub("", text)
    text = _CHINESE_SOURCE_REDIRECT_RE.sub("", text)
    text = text.replace("Confirm this step against the source material.", "")
    text = text.replace("confirm this step against the source material.", "")
    text = " ".join(text.split())
    text = text.strip(" \t\r\n。；;,.，")
    return text or fallback


def _port_label(block: str | None, port: str | None) -> str:
    if block and port:
        return f"{block}.{port}"
    return block or "未知端点"
