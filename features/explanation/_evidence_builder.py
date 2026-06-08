"""Build static evidence packs for simulation explanations."""

from __future__ import annotations

from core.domain.m_file import MFile
from core.domain.mat_metadata import MatMetadata
from core.domain.project import Project
from core.domain.project_graph import ProjectGraph
from core.domain.slx_model import SlxLine, SlxModel
from core.domain.source_ref import SourceRef
from features.overview.overview_schemas import ProjectOverview

from ._evidence_helpers import (
    block_index,
    block_source_ref,
    block_summary,
    clean_text,
    connector_tags,
    downstream_endpoints,
    endpoint,
    guess_parameter_role,
    is_measurement,
    line_summary,
    overview_source_ref,
    parameter_confidence,
    parameter_inference_basis,
    payload_dict,
    score_payload,
)
from ._evidence_pack import (
    EvidenceItem,
    EvidenceKind,
    EvidencePack,
    JsonValue,
    ParameterContextPayload,
    SignalPathPayload,
    _jsonify,
)
from ._score import ScoredBlock, normalize_block_type, select_high_value_blocks


class EvidenceBuilder:
    """Assemble structured, static evidence without running simulations or LLMs."""

    def __init__(
        self,
        *,
        max_blocks: int = 80,
        max_parameters_per_block: int = 2,
        max_lines: int = 60,
    ) -> None:
        self._max_blocks = max_blocks
        self._max_parameters_per_block = max_parameters_per_block
        self._max_lines = max_lines

    def build(
        self,
        project: Project,
        graph: ProjectGraph,
        overview: ProjectOverview | None = None,
        slx_model: SlxModel | None = None,
    ) -> EvidencePack:
        selection = select_high_value_blocks(project, graph, max_blocks=self._max_blocks)
        selected = [
            item
            for item in selection.selected
            if slx_model is None or item.file_path == slx_model.file_path
        ]
        models = project.slx_models if slx_model is None else [slx_model]
        items: list[EvidenceItem] = []
        self._add_overview_items(items, overview)
        self._add_block_items(items, selected)
        self._add_subsystem_items(items, models)
        self._add_line_items(items, project.slx_models, selected)
        self._add_m_file_items(items, project.m_files)
        self._add_mat_items(items, project.mat_files)
        self._add_caveats(items, models, selected)
        return EvidencePack(
            project_id=project.id,
            project_name=clean_text(project.name, 120),
            schema_version="v0.2.3",
            evidence=items,
            selection_diagnostics=selection.diagnostics,
            builder_notes=[
                "static_structural_evidence_only",
                "no_simulation_run_result_evidence",
                "claim_evidence_ids_required_by_prompt",
            ],
        )

    def _add_overview_items(
        self,
        items: list[EvidenceItem],
        overview: ProjectOverview | None,
    ) -> None:
        if overview is None:
            return
        fields = {
            "one_sentence_summary": overview.one_sentence_summary,
            "main_execution_flow": overview.main_execution_flow,
            "key_blocks": [entry.model_dump() for entry in overview.key_blocks],
            "beginner_reading_order": overview.beginner_reading_order,
            "likely_confusing_points": overview.likely_confusing_points,
        }
        for field_name, value in fields.items():
            self._append(
                items,
                "project_overview_field",
                overview_source_ref(overview),
                f"ProjectOverview.{field_name}: {clean_text(str(value), 160)}",
                {"field_name": field_name, "value": _jsonify(value)},
            )

    def _add_block_items(self, items: list[EvidenceItem], selected: list[ScoredBlock]) -> None:
        for scored in selected:
            payload = self._block_payload(scored)
            self._append(
                items,
                "slx_block",
                block_source_ref(scored.file_path, scored.block),
                block_summary(scored),
                payload,
            )
            if normalize_block_type(scored.block.block_type) == "Scope":
                self._append(
                    items,
                    "scope",
                    block_source_ref(scored.file_path, scored.block),
                    f"Scope {scored.block.name} 是静态观察点,可用于说明应查看的信号位置。",
                    payload,
                )
            if is_measurement(scored.block):
                self._append(
                    items,
                    "measurement",
                    block_source_ref(scored.file_path, scored.block),
                    f"测量/输出 block {scored.block.name} 可作为观察点证据。",
                    payload,
                )
            self._add_parameter_items(items, scored)
            self._add_connector_item(items, scored)

    def _block_payload(self, scored: ScoredBlock) -> dict[str, JsonValue]:
        block = scored.block
        return {
            "block_ref": payload_dict(endpoint(block)),
            "block_type": normalize_block_type(block.block_type),
            "parent_subsystem": block.parent_subsystem,
            "e1_category": scored.e1_category,
            "selection_layers": list(scored.selection_layers),
            "is_ambiguously_named": scored.is_ambiguously_named,
            "degree": scored.degree,
            "score": score_payload(scored),
            "flags": {
                "is_masked": block.is_masked,
                "is_library_link": block.is_library_link,
                "is_model_reference": block.is_model_reference,
            },
            "nondefault_parameter_names": [name for name, _ in scored.nondefault_parameters[:8]],
        }

    def _add_parameter_items(self, items: list[EvidenceItem], scored: ScoredBlock) -> None:
        downstream = downstream_endpoints(scored, limit=5)
        for name, value in scored.nondefault_parameters[: self._max_parameters_per_block]:
            payload = ParameterContextPayload(
                parameter_name=name,
                value=clean_text(value, 180),
                block_ref=endpoint(scored.block),
                role_guess=guess_parameter_role(name, value),
                is_default_value=False,
                downstream_endpoints=downstream,
                evidence_for_inference=parameter_inference_basis(scored, name),
                confidence=parameter_confidence(name),
            )
            self._append(
                items,
                "parameter",
                SourceRef(
                    scored.file_path,
                    block_id=scored.block.block_id,
                    block_name=scored.block.name,
                    parent_subsystem=scored.block.parent_subsystem,
                    parameter_name=name,
                ),
                f"参数 {name} 位于 {scored.block.name}({normalize_block_type(scored.block.block_type)}),可作为静态解释依据。",
                payload_dict(payload),
            )

    def _add_connector_item(self, items: list[EvidenceItem], scored: ScoredBlock) -> None:
        block_type = normalize_block_type(scored.block.block_type)
        if block_type not in {
            "Bus Creator",
            "Bus Selector",
            "Goto",
            "From",
            "Mux",
            "Demux",
            "Selector",
        }:
            return
        kind: EvidenceKind = "bus_signal" if "Bus" in block_type else "goto_from_tag"
        payload = SignalPathPayload(
            None, [endpoint(scored.block)], None, 0, connector_tags(scored.block)
        )
        self._append(
            items,
            kind,
            block_source_ref(scored.file_path, scored.block),
            f"{block_type} {scored.block.name} 是信号路由节点。",
            payload_dict(payload),
        )

    def _add_subsystem_items(self, items: list[EvidenceItem], models: list[SlxModel]) -> None:
        for model in models:
            subsystem_blocks = {
                block.name: block for block in model.blocks if block.block_type == "SubSystem"
            }
            for subsystem, child_ids in sorted(
                model.subsystems.items(), key=lambda item: (-len(item[1]), item[0])
            )[:12]:
                block = subsystem_blocks.get(subsystem)
                self._append(
                    items,
                    "subsystem",
                    SourceRef(
                        model.file_path,
                        block_id=block.block_id if block else None,
                        block_name=subsystem,
                        parent_subsystem=block.parent_subsystem if block else None,
                    ),
                    f"子系统 {subsystem} 包含 {len(child_ids)} 个解析到的 block。",
                    {"subsystem": subsystem, "child_block_count": len(child_ids)},
                )

    def _add_line_items(
        self, items: list[EvidenceItem], models: list[SlxModel], selected: list[ScoredBlock]
    ) -> None:
        blocks = block_index(models)
        selected_keys = {(item.file_path, item.block.block_id) for item in selected}
        added = 0
        for model in models:
            for line in model.lines:
                if added >= self._max_lines:
                    return
                if not _line_touches_selected(model.file_path, line, selected_keys):
                    continue
                source = blocks.get((model.file_path, line.from_block))
                target = blocks.get((model.file_path, line.to_block))
                payload = SignalPathPayload(
                    endpoint(source, str(line.from_port)) if source else None,
                    [],
                    endpoint(target, str(line.to_port)) if target else None,
                    1,
                    [],
                )
                self._append(
                    items,
                    "slx_line",
                    SourceRef(
                        model.file_path,
                        block_id=line.from_block,
                        block_name=source.name if source else line.from_block,
                    ),
                    line_summary(line, source, target),
                    payload_dict(payload),
                )
                added += 1

    def _add_m_file_items(self, items: list[EvidenceItem], m_files: list[MFile]) -> None:
        for m_file in m_files[:20]:
            self._append(
                items,
                "m_file",
                SourceRef(file_path=m_file.file_path),
                f"MATLAB 文件 {m_file.file_path} 的角色为 {m_file.file_role},包含 {len(m_file.functions)} 个函数。",
                {
                    "file_role": m_file.file_role,
                    "function_names": [func.name for func in m_file.functions[:10]],
                    "imports": m_file.imports[:10],
                    "uses_toolbox": m_file.uses_toolbox[:10],
                },
            )
            for func in m_file.functions[:10]:
                self._append(
                    items,
                    "m_function",
                    SourceRef(file_path=m_file.file_path, line_range=func.line_range),
                    f"函数 {func.name} 定义在 {m_file.file_path}:{func.line_range[0]}-{func.line_range[1]}。",
                    {
                        "function_name": func.name,
                        "inputs_count": len(func.inputs),
                        "outputs_count": len(func.outputs),
                    },
                )

    def _add_mat_items(self, items: list[EvidenceItem], mat_files: list[MatMetadata]) -> None:
        for mat_file in mat_files[:10]:
            for variable in mat_file.variables[:20]:
                self._append(
                    items,
                    "mat_variable",
                    SourceRef(file_path=mat_file.file_path),
                    f"MAT 文件变量 {variable.name} 类型为 {variable.var_type},shape={variable.shape}。",
                    {
                        "variable_name": variable.name,
                        "var_type": variable.var_type,
                        "shape": list(variable.shape),
                        "likely_role": variable.likely_role,
                        "first_field_names": variable.first_field_names[:10],
                    },
                )

    def _add_caveats(
        self, items: list[EvidenceItem], models: list[SlxModel], selected: list[ScoredBlock]
    ) -> None:
        for model in models:
            for warning in model.parse_warnings[:8]:
                self._append(
                    items,
                    "simulink_caveat",
                    SourceRef(file_path=model.file_path),
                    f"解析提示:{clean_text(warning, 160)}。",
                    {"warning": clean_text(warning, 180), "scope": "parser_static_warning"},
                )
        flagged = [
            item.block
            for item in selected
            if item.block.is_masked or item.block.is_library_link or item.block.is_model_reference
        ]
        if flagged:
            self._append(
                items,
                "simulink_caveat",
                SourceRef(file_path=selected[0].file_path),
                f"候选 block 中有 {len(flagged)} 个 masked/library/model-reference 标记,解释时应提示静态解析边界。",
                {
                    "masked_count": sum(1 for b in flagged if b.is_masked),
                    "library_link_count": sum(1 for b in flagged if b.is_library_link),
                    "model_reference_count": sum(1 for b in flagged if b.is_model_reference),
                },
            )

    def _append(
        self,
        items: list[EvidenceItem],
        kind: EvidenceKind,
        source_ref: SourceRef,
        summary: str,
        payload: dict[str, JsonValue],
    ) -> None:
        items.append(
            EvidenceItem(
                f"E{len(items) + 1:03d}", kind, source_ref, clean_text(summary, 200), payload
            )
        )


def _line_touches_selected(
    file_path: str, line: SlxLine, selected_keys: set[tuple[str, str]]
) -> bool:
    return (file_path, line.from_block) in selected_keys or (
        file_path,
        line.to_block,
    ) in selected_keys
