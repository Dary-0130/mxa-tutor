# TASK-534 build_steps 私有 draft DTO 契约对齐（含 regenerate 路径）v0.1

顶部标注：R1（GPT）设计审已过、R6（Codex）可落核已过，两轮意见已收敛。

性质：契约修正卡。
编号：534。
分支名：codex/build-steps-draft-contract。
基线：origin/main live HEAD（实施 Stage 0：e9f0f9f）。

## 一句话

模型在草稿阶段，只许从后端给的清单里挑一个号码（source_ref）；文档编号、来源类型、定位符、摘录，一律由后端照号码解析注入。号码对不上，显式报错——不许悄悄丢。

## 根因（诊断已坐实，不重开）

24 轮真机主路：13/24 轮 build_steps 整份报废，其中 7 次 = dto_invalid。89 个字段错误全部围绕同一个 evidence 结构：paper_reference.source missing × 29 / document_id missing × 29 / [dynamic_key] extra_forbidden × 29 / to_block_ref string_type × 2。

完整死法：

1. 后端把白名单端给模型时，连 document_id / locator / excerpt 一并暴露（_prompt_builder.py:676）——等于把答案抄在卷子边上。
2. 模型照抄进 paper_reference。
3. bridge 遇到对不上的 source_ref，返回 _DROP_EVIDENCE 静默丢项（paper_plan_helpers.py:361/399），或补 invalid-marker（paper_plan_service.py:1064/1089）。
4. 公共 DTO 校验失败 → 整份 build_steps 报废 → guidance 连坐。

三件事同一个根：让模型碰了不该碰的东西，还在它碰错时不出声。

## 范围（必做）

① 白名单瘦身

build_plan_evidence_source_refs() 已存在、REF-001 后端编号已存在、prompt 已注入（_prompt_builder.py:198/228/234/281）——不重造。

改：给模型看的白名单只留 ref 号 + 人类可读的选择依据（足够它挑对）；撤掉 document_id / locator / excerpt 等 provenance 字段（_prompt_builder.py:676）。后端解析时仍用完整记录，只是不给模型看。

② 私有 draft evidence 模型（三处入口，一个不漏）

新建私有 draft 模型，只含 source_ref，extra="forbid"；不含 source / document_id / locator / excerpt / 任何成品 provenance 字段。

不动公共 PaperEvidenceEntryModel、不动 spec 侧、不动 export schema。

三处 evidence 入口全改：

1. build_steps[*].block_refs[*].paper_reference
2. build_steps[*].configuration_hints[*].evidence
3. build_steps[*].evidence

③ bridge 改为 fail-closed + 新建对象

draft（只含 source_ref）→ 按本轮白名单解析，唯一命中才通过 → 未命中 / 歧义 / 类型错 / 缺失 → 显式 fail-closed（带可区分机器码）→ 后端用白名单记录新建完整 PaperEvidenceEntry（不读模型给的任何 provenance）→ 走现有公共 DTO 正常 model_validate。

禁：静默丢弃 evidence、置 null 后继续、产生 invalid-marker、model_construct() / 手工拼 dict / model_copy(update=...) 绕过校验。

source_ref 不得进入公共 schema / API / 持久化 / 日志。

④ 可区分机器码（关键——防“重分类冒充救回”）

dto_invalid 现为统一码，fallback 只记一个 reason_code。

新增可区分子码：draft_schema_invalid / source_ref_missing / source_ref_type_invalid / source_ref_no_match / source_ref_ambiguous / final_evidence_invalid / source_ref_leaked。

smoke summary 一并带上，沿用 dto_invalid_errors 脱敏口径。

理由：修完 dto_invalid 必然下降，但可能只是换名字变成 bridge-resolution 失败。没有子码就分不清“真救回”与“换张脸”。

⑤ to_block_ref 类型契约（string_type × 2）

保持 strict string + membership 校验。禁：扩 union、隐式取值、str(...) 化。

验收计数与 evidence 分开数（这是独立子项，不混算）。

⑥ prompt 同步（消除已知漂移）

paper_plan_build_steps.yaml + paper_plan_build_steps_regenerate.yaml 均 bump（原均 v0.1）。明写：只输出 source_ref；不输出 source / document_id / locator / excerpt；to_block_ref 必须是既有 ID 字符串；不得自创引用。

不得全局改 _shared_paper_plan_constraints()（_prompt_builder.py:78/498）——PlanComposer / MissingDetector 仍用公共 PaperEvidenceEntryModel，全局改会把它们弄坏。给 build_steps / build_steps_regenerate 单独 constraints。

不加 few-shot（R1 P1-4：属残余违规问题，同期做会污染归因；留后续卡按真机结果决定）。

⑦ regenerate 路径同修（PM 已拍）

paper_step_regeneration_service.py:174 走同一 draft / bridge。必须一起改——否则主路修好、学生一纠错重跑又崩。

注意：regenerate 当前允许 user_supplied evidence。须定义用户证据的 draft 引用契约（用户补的值不走文档白名单——明确它怎么表达、怎么校验、source=user_supplied 由谁盖章）。

⑧ eval smoke 同步

run_paper_pdf_smoke.py:291/303 复制了 build_steps bridge/DTO 流程，须同步，否则试车道量出来的不是真实行为。

## 不做（各自独立卡，不塞进来）

不做：稳定引用 ID（下一张卡）；structured retry 扩到 build_step_planner（再下一张）；few-shot；token 预算 / 输出瘦身（截断 2 次已确认，单起卡）；partial accept（独立产品卡，PM 未拍）；放宽 parameter_value_leak 检测（grounding 红线）；spec 侧 / guidance 侧 / 前端。

## 红线

成品契约一分不放宽。本卡只把“收草稿”与“验成品”分开。

禁静默：不忽略 extra_forbidden、不静默置 null、不静默丢 evidence。草稿与成品都 extra="forbid"，不许 ignore / 不许丢弃。

grounding 闸（506/528/529）、安全闸（530）不碰。

脱敏（决策 11）：机器码 / 字段路径 / 类型 / 计数 / 纯数字；Pydantic loc 中动态 key 一律替换占位符。禁 LLM 原始输出 / 步骤正文 / 参数值 / 论文原文 / 堆栈。

保原始字节（决策 08）：改文档用定点替换，禁整篇回写；git diff --unified=0 自查。

对外 schema 预期零 diff；若实际触及 → 停手报 PM（须走决策 13 全清单，卡面得改）。

## 验收

### A. 确定性测试

使用 PayloadPaperPlanService / QueueTextProvider（tests/features/paper/test_paper_plan_service.py:64/93）。三处 evidence 入口逐处覆盖：

1. 固定输入期望合法最小 draft（只含 source_ref）bridge 后通过成品校验。
2. 未知 source_ref 显式 fail-closed，不静默丢。
3. 歧义 / 多重命中显式 fail-closed。
4. source_ref 缺失 / null / 空白 / 非字符串显式 fail-closed。
5. LLM 自带 source / document_id / locator / excerpt 草稿层 extra_forbidden 失败。
6. bridge 后缺成品必需字段仍必须失败。
7. source_ref 残留到成品仍必须失败。
8. 非字符串 to_block_ref 仍必须失败。
9. grounding / parameter_value_leak 行为不变，仍可否决整份。

### B. 回归 / 零 diff

公共 schema export 零 diff；前端 typecheck 过；source_ref 不出现在公共 schema / API payload / 持久化 JSON / 日志。

旧 plan JSON 仍读得出（sqlite_paper_cache.py:1501 nested evidence migration）。

spec 侧 / guidance 侧 / user-supply / evaluator fixture 全绿。

prompt 渲染后 snapshot 测试（不只 grep yaml 源码）；_prompt_loader.py:26 有 lru_cache，测试须 cache_clear()。

make check 全管道 + 显式列 schema export、前端 typecheck 两条（不在 make check 里）。

### C. 真机复跑（支持性观察，不作因果证明）

8 篇 × 3 轮，同批同口径，与基线（成品率 10/24 = 41.7%）对比。报：总成品率 / dto_invalid 次数 / 各 bridge-resolution 子码次数 / 其他原因码 / guidance 下游结果 / 墙钟 + token telemetry。

验收口径（R1 P0-2）：目标字段族的错误在确定性测试中归零；真机复跑不再出现同一 contract mismatch，或明确转化为正确的 bridge-resolution 失败。总体成品率只作观察，不作为本卡因果证明。

dto_invalid 归零本身不是目标——模型若给了不存在的号码，正确结果是明确的引用解析失败，不是强行变成功。

不得把“重分类”当“救回”。

## 回退原子性

私有 draft DTO + bridge resolver + prompt 版本三者同进同退。只回退其一 = 重造三方漂移。

## as-built

实际改动文件：

1. features/paper/paper_plan_helpers.py：新增 regenerate 用户证据 USER-* 私有 source_ref 构造。
2. features/paper/_prompt_builder.py：build_steps / regenerate 改用专属 constraints；plan_evidence_sources_json 瘦身为 source_ref + basis；allowed_user_evidence_json 改为 USER-* 私有 ref。
3. features/paper/paper_plan_service.py：新增 build_steps 私有 DraftEvidence 模型、source_ref fail-closed resolver、成品 PaperEvidenceEntry 重建与子码映射；移除 build_steps 路径的静默 drop / invalid-marker 依赖。
4. features/paper/paper_schemas.py：from_block_ref / to_block_ref 改为 strict string，membership 仍走既有 semantic validation。
5. core/prompts/paper_plan_build_steps.yaml：bump v0.2，写明 DraftEvidenceRef 只输出 source_ref。
6. core/prompts/paper_plan_build_steps_regenerate.yaml：bump v0.2，写明 REF-* / USER-* source_ref 契约。
7. eval/run_paper_pdf_smoke.py：复用主 service build_steps 解析路径；summary 保留 bridge-resolution 子码；Pydantic loc 动态 key 脱敏。
8. tests/features/paper/test_paper_plan_service.py：补三处 evidence 入口、source_ref 缺失/类型/未命中/歧义、final_evidence_invalid、source_ref_leaked、to_block_ref 非字符串、regenerate USER-* 的确定性覆盖。
9. tests/features/paper/test_paper_plan_prompts.py：同步 prompt v0.2 与渲染后断言。
10. tests/eval/test_run_paper_pdf_smoke.py：补 bridge 子码分类与 loc 脱敏断言。
11. docs/tasks/task-534-build-steps-draft-contract-v0_1.md：本任务卡。

确定性测试实测结果：

1. python -m pytest tests/features/paper/test_paper_plan_service.py -q：76 passed。
2. python -m pytest tests/features/paper/test_paper_plan_prompts.py -q：33 passed。
3. python -m pytest tests/eval/test_run_paper_pdf_smoke.py -q：8 passed。
4. python -m pytest tests/features/paper -q：404 passed。
5. python -m pytest tests/eval -q：51 passed。
6. pnpm --dir web typecheck：passed。
7. PYTHONPATH=. python scripts/export_paper_schemas.py：passed，schemas/ 零 diff。
8. make check：passed（ruff、ruff format、mypy、pytest、repo hygiene；1911 passed / 17 skipped）。
9. rg -n '"source_ref"|\bsource_ref\b' schemas api web/src/lib adapters/storage/sqlite_paper_cache.py：未发现 build_steps draft source_ref 进入公共 schema / API / 前端 lib / paper cache；仅 api/routes/teaching_unit.py 存在既有 SourceRef import，非本卡契约。

真机复跑数据：

截至本 as-built 回填时尚未执行 8 × 3 真机复跑。本机默认样例目录 E:\桌面\样例 存在 8 篇 PDF，.env 中可见 DeepSeek key 字段；未执行原因是完整车道预计数小时且消耗外部 API 额度。该项需 PM/车道按 eval/run_paper_pdf_smoke.py 同批同口径补跑并回填总成品率、dto_invalid 次数、bridge-resolution 子码次数、其他原因码、guidance 下游结果、墙钟 + token telemetry。

哪些是真救回 / 哪些只是重分类：

1. 真救回：确定性层面，合法最小 draft（只含 source_ref）在三处 build_steps evidence 入口均能被后端解析并重建为完整 PaperEvidenceEntry，通过公共 DTO；旧的 source/document_id/locator/excerpt 缺失族不再由模型承担。
2. 真救回：regenerate 的已解析用户证据改为 USER-* source_ref，由后端盖章 source=user_supplied 并复用已验证 provenance，不再要求模型输出用户证据成品字段。
3. 重分类：source_ref 未命中、缺失、类型错误、歧义、成品重建失败、source_ref 泄漏会从泛化 dto_invalid 转为明确子码；这不是救回，是真正 fail-closed。
4. 重分类：to_block_ref 非字符串仍是 DTO 失败，单独计数，不并入 evidence 修复成效。

老实记账：

本卡修完仍会剩：引用脆弱（1 次）、redline 违规（2 次）、截断（2 次）、自依赖（1 次）。这些归后续卡，本卡不包治。
