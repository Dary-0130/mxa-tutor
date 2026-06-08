# features/explanation - Simulation Explanation Pack

## 模块定位

讲解层产物层。基于 EvidencePack(纯结构化数据 from Parser / ProjectGraph / ProjectOverview)生成 mxa-tutor 的工程讲解文本,不进 RAG(本任 A+ 版本)。

## 三层架构

EvidenceBuilder -> ExplanationService -> ClaimEvidenceValidator -> MarkdownRenderer

- **EvidenceBuilder**:纯结构化,不调 LLM;14 类 EvidenceKind;3 类 typed payload(EndpointRef / SignalPathPayload / ParameterContextPayload)
- **ExplanationService**:LLM 写讲解文本;输入 EvidencePack + overview_hint;输出 ExplanationPack(8 节结构化 JSON)
- **ClaimEvidenceValidator**:11 条校验;三类失败(Recoverable / Fatal / Pack acceptance)
- **MarkdownRenderer**:渲染人类可读 + 角标 + 推断标记 + 双层守门

## 与既有 features/ 边界

- **features/overview/**:本模块消费 ProjectOverview(12 字段 main freeze + extra="forbid";不动 schema);ProjectOverview 字段作 `overview_hint` 弱辅助
- **features/chunking/**:本模块不动 7 类 chunk;explanation pack 不进向量库(A+ 版本)
- **features/chat/**:本模块不动 ChatService / v0.2-rc prompt;不影响问答路径

## 当前文件

- `_score_rules.py`:E1 分类标签、E3 模糊命名、参数默认值规则。
- `_score_types.py`:D2/D3 scoring dataclasses。
- `_score.py`:D2 等权打分骨架 + D3 分层 Top40-80 选择。
- `_evidence_pack.py`:EvidencePack schema + typed payload。
- `_evidence_helpers.py`:EvidenceBuilder 私有 helper。
- `_evidence_builder.py`:EvidenceBuilder 主流程。

## 后续接棒文件

- `_explanation_service.py`:ExplanationService(调 LLM)。
- `_claim_validator.py`:Validator 11 条规则 + 三类失败。
- `_markdown_renderer.py`:Renderer + normalize_evidence_id + 双层守门。
- `_acceptance.py`:文本自动验收(deterministic checker;不入 ad-hoc)。

## 产物

- 入仓:`features/explanation/*.py` + `tests/features/explanation/*.py` + `core/prompts/simulation_explanation_pack.yaml`
- 不入仓:`eval/ad_hoc/explanation/<alias>/{evidence_pack.json, project_explanation.md, claims.json, claim_validation_report.json}` x 4
