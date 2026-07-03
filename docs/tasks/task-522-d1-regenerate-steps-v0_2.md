# TASK-522-D1:纠错后重生成建模步骤(v0.2 — GPT R1 审卡 + Codex R6 live 核收敛版)

## 状态

🔲 v0.2(2026-07-03,待 Codex Stage 0 → 实现)
- 起稿基础:origin/main HEAD 本会话实测 = `08864c5`(522-C2 索引收尾 #165 顶;C2 代码 `66e1915` #164 是 ancestor;链到 522-B #160 / 521-D 不断)。Stage 0 用 live 值校验,允许 main 合法前进。
- **④ 局部重跑拆两件**:本卡(D1)= **纠错后就地重生成 build_steps + m_script(带纠错值、不重解析、不清纠错)**;D2(后继,单独立卡)= **消解冲突**(让用户拍板选一个把冲突参数消掉、进建模)。本卡不碰冲突消解。
- **GPT(R1)审卡**:方向通过(D1/D2 拆法对、别并 D2)+ **1 P0(先读再锁 stale write,v0.1 埋的真洞)** + 4 更多 P0(护栏须单一门 / m_script 绕冲突禁令 / gather 异常拖垮 / 多 worker 锁失效)+ P1×5 + P2×2,裁决点全数定案。
- **Codex(R6)live 核**:五实证复核(A1-A3 成立、A4 merge 不能盲用、A5 guard 调用点不止 generate 尾部)+ **锁粒度坐实(reparse 持锁跑完整 LLM、D1 照抄不需 CAS)** + 四落点可落 + 两处「照卡直接写会崩」(merge 按 sentinel 重算 missing bindings、build_steps prompt 明写禁 user_supplied 须重生成专用 prompt)。
- **PM 已拍**:重生成给「重新生成步骤」按钮、用户手点(不自动);重生成中转圈禁用、中途锁住不让操作;走 LLM 但**不告知用户**、文案不露机器口吻/免责话;**失败先自己重试(四次、只重瞬时类失败)、仍不成再给中性提示**。
- v0.1→v0.2 结构变更:**先加锁再读 record/corrections(P0-1 修)** / 所有写回经单一 pre-write validator(P0-2)/ mscript 冲突值后校验保留(P0-3)/ build_steps 与 m_script 独立错误处理(P0-4)/ 重试四次仅瞬时类(PM 拍)/ 谓词收窄为 `active corrections OR build_steps None OR m_script None`(E-1)/ evidence 无条件传两类 allowlist(P1-3)/ fill_missing + undo-after-regenerate 回归(P1-4)/ 单 worker 锁假设写明(P0-5)/ 一批裁决定案。

---

## 上下文

### 在解析纠错子线(TASK-522)的位置

解析纠错四条:① 诚实提示(对内暂缓,归上线公告批)/ ② 重新解析(**522-B ✅ #160**)/ ③ 用户纠错(**C1 ✅ #162 + C2 ✅ #164,整条落地**)/ ④ 局部重跑(最难,排最后)。

④「局部重跑」拆两件:
- **D1(本卡)= 纠错后重生成建模步骤**:接 C2 的缺口——C2 落地后,纠错/撤销都把 `build_steps` + `m_script_skeleton` 置 None(fail-closed,508 回退推荐块视图),完整分步步骤没了;想要完整步骤,现在只能「重新解析整篇」,但重解析会清空纠错(C1 级联)、等于白改。**D1 补它:不重解析、不清纠错,就地把完整 build_steps + m_script 带着纠错后的工作值重新生成回来。**
- **D2(后继)= 消解冲突**:几篇文档对同参数给打架的值时,系统现在如实标冲突、不替用户猜(521-B2 冲突检测 + 全后端产物 abstain);D2 让用户拍板选一个把冲突消掉、让该参数进建模。**碰底层更深(动 spec 抽取表以外的冲突真值面 / 可能碰对外契约),单独立卡,D1 合并后起草。**

### overlay 模型(继承 C1/C2,D1 不得违背)

- `PaperSpec.parameter_table` = **不可变**文档抽取结果(521-B2 `parameter_conflicts` 冲突检测真值源),重生成**永不读改它作为参数值来源**(m_script 现入口读它,D1 要改成读工作值,见 § 现状地基②)。
- `ModelGenerationPlan.parameter_mapping` = 实际建模**工作值**(已含 C2 纠错后的 user_supplied 值)。**D1 重生成的 build_steps / m_script 必须从这份工作值取参数值**,这样纠错值才带得进去。
- `paper_parameter_correction` 表(C1 建)= 审计/撤销 overlay。**D1 只读它**(算 `resolved_user_evidence_refs` 放行纠错值证据),**不改它**(重生成不产生新纠错、不动纠错行)。
- **推论(继承 C2 核心简化)**:重生成改的是 plan 的 build_steps/m_script/subsystem_breakdown,**不动 parameter_mapping、不动 spec.parameter_table、不重算 parameter_conflicts**。overlay 下纠错够不到冲突参数,常规重生成同样够不到——**D1 不写任何冲突重算**(冲突消解是 D2 的事)。

### 现状地基(Codex R6 本会话 @ live `08864c5` 实测 — ★ 五处坐实的改实点已并入本卡)

**① build_steps 生成函数可直接吃工作值(R6 实证,无需改签名)**:现 `_llm_build_steps(block_recommendations, parameter_mapping, spec)` 的 `parameter_mapping` 来自 `plan_composer_output.parameter_mapping`;`build_messages_for_build_steps` 直接序列化这个入参(`ParameterMappingModel.from_domain(mapping).model_dump`)。C2 纠错把 `correct_extracted` 写回 `record.plan.parameter_mapping`。⇒ **重生成只要传 `record.plan.parameter_mapping`,build_steps 自然带纠错后的 user_supplied 值,复用现函数、不改签名**。`build_plan_evidence_source_refs(spec)` 只从 `spec.evidence/equations/figure_locations` 建 REF(document_extracted 才收),与工作值无耦合。

**② m_script 现入口只吃 spec.parameter_table、须新开吃 mapping 的入口(R6 实证)**:现 `_llm_mscript_draft(self, spec)` 取 `without_conflicted_parameter_entries(spec).parameter_table` 喂 `build_messages_for_mscript_draft(equations, parameter_table, conflicts)`,dump `ParameterEntryModel`(不是 `ParameterMapping`)。纠错后的工作值**不在** parameter_table 里。⇒ **要让 .m 带纠错值,必须让 mscript 路径接收工作态 `parameter_mapping`**:新开 `_llm_mscript_draft_from_mapping(...)` 或 widening helper(而非改只吃 spec 的现入口——现入口生成路径仍用,不动)。这是 D1 唯一真新增的 LLM 调用形状。

**③ build_step evidence 校验现不放行任何用户证据(R6 实证)**:生成路径调 `_validate_build_step_evidence(build_steps, spec)`,内部三处都只传 `allowed_user_prompt_ids=frozenset()`(空集)、**不传 `allowed_user_evidence_refs`**。底层 `validate_build_step_evidence_for_spec` 已有 C2 加的 additive 参数 `allowed_user_evidence_refs`。⇒ **重生成路径校验必须传 `allowed_user_evidence_refs=resolved_user_evidence_refs(record, corrections)`**(放行 correct_extracted),若也允许 fill_missing 还要传 `allowed_user_prompt_ids=resolved_prompt_ids(record)`;否则重生成的 build_steps 引用纠错值参数会被判无效。

**④ 重生成可从 `generate()` 切出、只跑 mscript + build_steps(R6 实证)**:`_plan_assembler.merge(plan_composer_output, subsystem_steps, mscript, missing_prompts, paper_id, build_steps)` 用 `replace(plan_composer_output, subsystem_breakdown=..., m_script_skeleton=..., build_steps=...)` 装回,**不动 parameter_mapping**;`validate_and_derive_build_steps(draft_steps, parameter_mapping, block_recommendations)` 现成。⇒ **重生成入口形状**:读 record → 读 corrections → 用 `record.plan.block_recommendations + record.plan.parameter_mapping + record.spec` 重跑 build_steps + 用新 mapping-aware mscript helper 重跑 .m → `merge(record.plan, ...)` 或 `replace(record.plan, ...)` 写回,**不重跑 `_llm_plan_compose` / `_llm_missing_detect`**(parameter_mapping / missing_prompts 不变)。

**⑤ 冲突护栏须显式补调(R6 实证,不走 generate 就不自动跑)**:`validate_plan_does_not_resolve_conflicts(assembled_plan, spec.parameter_conflicts)` 现只在完整 `generate()` 尾部调(另有 `_llm_plan_compose` 内部 + ready bundle 读取入口的 integrity guard)。⇒ **重生成路径(只重跑 build_steps+m_script)不走 generate 尾部,必须在写回前显式补调** `validate_plan_does_not_resolve_conflicts(updated_plan, record.spec.parameter_conflicts)`,拦住重生成的 m_script / build_step refs / display_text / configuration_hints 万一引入冲突参数。

### Base + 范围边界

- **Base**:main 必须含 C2 代码 `66e1915`(#164)。Stage 0 用 `git merge-base --is-ancestor <live 66e1915> origin/main` 校验,允许 main 合法前进。
- **范围(D1)**:新增「重生成建模步骤」端点 + 重生成服务(**先锁后读** + 切 generate 子路径 + 新 mapping-aware mscript helper/builder + build_steps 重生成专用 prompt + 失败重试 4 次仅瞬时类 + 单一 pre-write validator)+ 冲突护栏显式补调 + build_step evidence 校验无条件传两类 refs + per-paper mutation 锁复用(C2 已建、持锁跑 LLM)+ 写回复用 522-B `set_plan`(只改 plan)+ 错误码 + telemetry + 前端「重新生成步骤」按钮(转圈锁 + fail-closed 中性提示)+ 截图。
- **不在本卡(留 D2 或更后)**:消解冲突 / 冲突参数进建模 / 任何 parameter_conflicts 重算或消解;改「自己填的缺失值」(那是 user-supply);批量 / figure / equation target;纠错本身的行为(C2 已落,D1 不碰纠错/撤销服务的纠错逻辑,只在其后提供重生成)。

---

## 输入(前置依赖)

- 必须已合并 main:TASK-502(UserSupplyService / `UpdatedPlanResponse`)、TASK-503(PaperBundleStore SQLite)、TASK-507-A/B(build_steps provenance + `build_step_planner` prompt)、TASK-508(508 回退推荐块视图)、TASK-521-A/B1/B2/C(多文档身份 + 冲突 + citation)、**TASK-522-B**(reparse + 锁 registry + 论文 TTL 清理)、**TASK-522-C1**(出处契约扩展 + `paper_parameter_correction` 表 + 惰性 CRUD + 清理级联 + `resolved_user_evidence_refs`)、**TASK-522-C2**(纠错/撤销服务 + 三端点 + per-paper mutation 锁扩含 user-supply + 原子 store 方法 + correctable 谓词 + 四处消费方接线 + build_steps 置 None)。
- 必读:`06_OUTPUT_CONTRACTS.md`、`04_ENGINEERING_STANDARDS.md`(§ 日志禁令)、`05_EXPLANATION_STYLE_GUIDE.md`(文案 + B/C 类步骤口吻)、决策 11 / 12 v0.4 / 13 / 26。

---

## 输出(交付物)

- 新增:重生成服务 `PaperStepRegenerationService`(或并入现服务模块)——切 `generate()` 子路径(只跑 mscript + build_steps)+ 新 mapping-aware mscript helper + 冲突护栏显式补调 + build_step evidence 校验接判定器 + 装回 plan(不动 parameter_mapping)。
- 新增:`_llm_mscript_draft_from_mapping(...)`(或等价 widening)——mscript 生成从工作态 `parameter_mapping` 取参数值(而非 spec.parameter_table),带纠错值;保留现 `_llm_mscript_draft(spec)` 供生成路径(不动)。
- 新增:重生成端点路由 + 响应 pydantic 模型(复用 `UpdatedPlanResponse` 结构,见 § A)。
- 修改:重生成路径**接入 per-paper mutation 锁**(复用 522-C2 已扩的 `PaperReparseLockRegistry`,additive 注入重生成路径;不改锁本体、不 rename)。
- 新增:build_steps **重生成专用 prompt/role**(现 prompt 禁 user_supplied、须分叉允许 corrected/fill_missing 值,R6 坑②);生成路径 prompt 逐字不动。
- 修改:build_step evidence 校验在**重生成路径**无条件传 `allowed_user_evidence_refs=resolved_user_evidence_refs(record, corrections)` + `allowed_user_prompt_ids=resolved_prompt_ids(record)`(P1-3 两类);**生成路径现行为不变**(仍传空集,见 § C 定案)。
- 新增:单一 pre-write validator `_validate_regenerated_plan_before_write`(P0-2,所有写回唯一门:evidence + 冲突护栏 + parameter_mapping 字节不变 + correction 不变 + schema)。
- 复用:写回走 522-B `set_plan`(定案 (a),单事务只改 plan、不动 correction;§ D);禁 522-C2 `apply_parameter_correction_atomically`。
- 新增:重生成 telemetry(枚举结果计数,不记内容)。
- 前端:纠错后 / build_steps 被压成回退视图时,展示「重新生成步骤」按钮;点击 → 转圈禁用、锁住页面交互 → 完成后步骤区出完整 build_steps;失败态(lock / 生成失败)可见可关可重试;文案不露机器口吻、不加免责话。
- 修改:`06_OUTPUT_CONTRACTS.md` 加重生成端点契约段(端点 + 响应形状 + 「重生成不改 parameter_mapping / 不清纠错 / build_steps 可能与上一版措辞不同」的契约说明)。
- 新增:后端真测试(端点 / 服务 / 重生成幂等与纠错值带入 / 冲突护栏 / evidence 放行 / 锁 / 并发 / 隐私)+ 前端静态守卫 smoke + 关键态截图(桌面+移动)。

---

## 范围(必须做)

- [ ] **A. 重生成端点**(P?-见错误码表)
  - `POST /api/v1/papers/{paper_id}/regenerate-steps`:请求体空(或仅可选幂等 token,见 § A 裁决);无参数注入面(不接受任何用户传值——重生成纯从已存 plan 工作值 + spec 跑)。
  - 返回**复用 `UpdatedPlanResponse` 结构** `{paper_id, updated_plan}`(`updated_plan` 含新 build_steps + m_script;parameter_mapping 逐字不变)。**route-local 复用,不进 exporter**(同 undo / user-supply 先例;对外七个既有 schema 零 drift、无新对外结构)。
  - **不新增 GET**;GET /spec、/plan 不改(重生成结果反映在 /plan 的 build_steps/m_script)。

- [ ] **B. 重生成服务:切 generate 子路径 + mapping-aware mscript**(依据现状地基①②④;★ 顺序按 P0-1 修正)
  - **★ 严格顺序(P0-1,先锁后读,不得颠倒)**:`acquire per-paper 锁`(§ F,失败 409)→ **锁内**读 `record = get(paper_id)`(None → 404 paper_not_found)+ `corrections = list_active_corrections(paper_id)` → 前置谓词判定(§ E)→ 跑 LLM → 护栏 → 断言 → `set_plan` 写回 → 出锁块释放。**禁止在 acquire 前读 record/corrections**(否则读到加锁间隙的 stale snapshot、覆盖期间的撤销/纠错)。对齐 522-B reparse 先例(R6 坐实:reparse 持锁跑完整 LLM 重解析再写回、无读写分离、无写回前 CAS)。
  - **前置谓词**(§ E 硬谓词):`active corrections 非空 OR build_steps is None OR m_script_skeleton is None` → 允许重生成;否则(无 active 纠错且 build_steps + m_script 均完整)→ 400 regenerate_nothing_to_do(§ E-1)。**冲突参数存在不拒绝重生成**(重生成不消解、护栏兜底)。
  - **★ 只切 mscript + build_steps 两段,禁重跑 plan_compose/missing_detect**(R6 坐实可切):
    - `build_steps_result = _llm_build_steps(record.plan.block_recommendations, record.plan.parameter_mapping, record.spec)` —— 复用现函数、传工作值(带纠错值)。**但 R6 坑②:现 build_steps prompt 明写"禁止 user_supplied",须用重生成专用 prompt/role 让 corrected 值可进 build_steps**(§ C-prompt)。
    - `mscript = _llm_mscript_draft_from_mapping(record.plan.parameter_mapping, record.spec.equations, record.spec.parameter_conflicts)` —— 新 mapping-aware helper(§ C-builder)。
  - **★ 两段独立错误处理(P0-4,禁盲用 gather 让一段拖垮另一段)**:build_steps 与 m_script 各自成败独立;**build_steps 成功即可写回,m_script 失败只让 m_script_skeleton 保持 None/原值、不阻断 build_steps**。若用 `gather(..., return_exceptions=True)` 则分 artifact 各自处理,不许任一 raise 取消另一路。
  - **★ 失败先重试(PM 拍:四次、仅瞬时类)**:LLM 失败分两类:
    - **瞬时/格式类**(网络抖 / DTO 校验失败 / 结构化解析崩,如 `BuildStepsDtoValidationError` / `BuildStepsStructuredError` / provider 超时)→ **重试,最多 4 次**(含首次共 4 次尝试,建议指数退避:首次立即、后续几百 ms 递增);
    - **红线/确定性拒绝类**(冲突值命中 `mscript_assigns_conflict_value`、evidence 校验拒、护栏拦)→ **立即停、不重试**(注定失败、重试白烧 LLM + 让用户干等)。
    - build_steps 与 m_script **各自独立重试**(build_steps 4 次、m_script 4 次,互不影响)。
    - 4 次瞬时失败仍不成 → 该 artifact **fail-closed 保持 None**(§ E-2);build_steps fail-closed 回 200(前端中性提示),m_script fail-closed 不阻断 build_steps。
  - 装回:见 § C-merge(★ R6 坑①:`merge()` 按 sentinel 重算 missing bindings,须用 `replace(record.plan, ...)` 直装、不走 merge 重算)。**parameter_mapping 逐字不变**(写回前字节级断言)。

- [ ] **C. build_step evidence 校验接判定器放行纠错值**(依据现状地基③;裁决 C 定案:R1 + R6)
  - **★ 重生成路径无条件传两类 allowlist(P1-3,非"视情")**:重生成的 build_steps 可能同时引用 correct_extracted(纠错值)和 fill_missing 的 user_supplied(补缺失值),只传 correction refs 不够。重生成路径调 `_validate_build_step_evidence`(或其内 `validate_build_step_evidence_for_spec`)**固定传**:
    ```
    allowed_user_evidence_refs = resolved_user_evidence_refs(record, corrections)
    allowed_user_prompt_ids     = resolved_prompt_ids(record)
    ```
  - **裁决 C 定案(生成路径逐字不动、安全)**:生成路径(`generate()`)继续传空集不放行纠错 refs——因为生成路径正常触发点是 upload(新 paper,无纠错)/ reparse(级联清纠错)。**Stage 0 gate 强制核** `_validate_build_step_evidence` / `validate_build_step_evidence_for_spec` **全部调用点**,确认无"active correction 存在时又走 generate()"的路径(如 plan 丢失懒生成 / 后台修复 plan / GET /plan miss 懒生成 / admin 全量重生成);**若发现此类路径 → 停手报架构师**(该路径要么先清 corrections、要么也接同一 allowlist)。生成路径改动:**逐字不变**(合并前贴生成 vs 重生成两路 RAW 佐证)。

- [ ] **D. 持久化写回:定案复用 `set_plan` + 单一 pre-write validator**(裁决 D 定案 + P0-2)
  - **定案 (a) 复用 522-B `set_plan`**(R6 坐实:单事务 `BEGIN` 写 paper_plan_cache、`SELECT 1 FROM paper_spec_cache` 校验 + rollback、**不碰 correction 表、不碰 spec row**);**禁用 522-C2 `apply_parameter_correction_atomically`**(它动 correction row、语义不合身)。
  - **★ missing_prompts / missing_bindings 原样回写(R1 硬要求)**:`set_plan` 需要它们;**从 record 原样带回、不在重生成服务里重算/过滤/清空**(重生成不改缺失面)。
  - **★ 单一 pre-write validator(P0-2,禁多处分散 set_plan)**:所有写回分支(build_steps 成功 / m_script partial / fail-closed)**必须经同一个** `_validate_regenerated_plan_before_write(updated_plan, original_record)`,固定顺序做:① evidence 校验(§ C 两类 allowlist)→ ② `validate_plan_does_not_resolve_conflicts`(§ 现状地基⑤)→ ③ `parameter_mapping` 字节级不变断言 → ④ correction 表 + correct_extracted evidence 不变断言 → ⑤ schema/domain validation。**任一写回不得绕过此 validator**;`set_plan` 只在 validator 通过后调一次。
  - **★ Stage 0 核 `set_plan` 无隐藏副作用**:贴本体确认不触发 correction 清理、不延长论文 bundle 24h TTL(P1-5);若有副作用 → 报架构师(备选新增 `set_plan_only` 薄方法)。
  - **禁**重生成里顺带动 correction 表(重生成不产生 / 不删纠错)。

- [ ] **E. ★ 重生成前置谓词 + 失败语义**(裁决 E 定案:R1 + PM)
  - **前置谓词定案(E-1,收窄为"有理由才重生成")**:
    ```
    允许重生成(任一成立):
      1. build_steps is None(被 C2 压掉 / 首次生成回退)  ← 主用例
      2. m_script_skeleton is None
      3. active corrections 非空(即便 build_steps 完整、允许带纠错值覆盖刷新)
    拒绝(无 active 纠错 且 build_steps + m_script 均完整):
      → 400 regenerate_nothing_to_do;前端不暴露按钮入口
    ```
    理由:有 active correction 即便 build_steps 非 None 也允许覆盖(避免竞态/残留卡死用户);无纠错且产物完整时重跑只是烧 LLM。**比"永远允许覆盖"稳(挡无谓消耗)、比"非 None 就拒"贴纠错场景**。冲突参数存在**不拒绝**(护栏兜底、D2 才消解)。
  - **失败语义定案(E-2,fail-closed + 重试 + 中性提示)**:
    - **先重试(PM 拍)**:瞬时/格式类失败重试最多 4 次(§ B),红线类立即停不重试。
    - **4 次仍失败 → fail-closed**:build_steps fail-closed **回 200**、`updated_plan.build_steps` 保持 None(主用例下本就 None;**已有非 None build_steps 时不被失败刷新清空**——见 § B 谓词 3 的覆盖场景需保护)、508 回退、telemetry 记 `regenerated_fail_closed`;**前端凭"请求成功但 updated_plan.build_steps 仍 None"显中性提示**「暂未生成完整步骤,可稍后重试」(P1-1,不加对外 schema 字段)。
    - **m_script 失败不阻断 build_steps(P0-4)**:build_steps 成功即写回,m_script fail-closed 保持 None/原值;telemetry 单记 `regenerated_with_steps_mscript_fail_closed`(P2-2)。
  - **裁决 E-3 定案:fail-closed 时保留原 `subsystem_breakdown`**(不重跑 `_llm_subsystem_plan`——不产新不确定数据、不引第三段 LLM);build_steps 成功时用 build_steps 派生刷新 subsystem_breakdown。

- [ ] **F. per-paper mutation 锁复用**(依据 522-C2 已建;R6 坐实锁模式)
  - **复用 522-C2 已扩的 `PaperReparseLockRegistry` 实例**(同一 `get_paper_reparse_lock_registry`,`async with await registry.acquire(paper_id)` 上下文;additive 注入重生成路径;不改锁本体、不 rename)。
  - **★ 持锁跑完整 LLM(对齐 reparse,R6 坐实)**:`acquire` 后**锁内**完成读 record/corrections → LLM(build_steps + mscript,含 4 次重试)→ 护栏 → set_plan 写回 → 出 `async with` 释放。持锁期间其他 mutation(reparse/correction/undo/user-supply/另一重生成)返回各自 409。PM 已拍"重生成中锁住不让操作",产品语义与持长锁一致。
  - 拿不到锁 → **409 regenerate_lock_conflict**(`PaperReparseInProgressError` 映射,新增 in-progress 分支)。
  - **★ 单 worker 锁假设(P0-5,Stage 0 强制核)**:`PaperReparseLockRegistry` 是**单进程 asyncio 锁**(per-process);D1 LLM 时间比 correction 更长、跨 worker 并发概率更高。**Stage 0 必须确认部署/测试环境 worker 数**:若单 worker → 本卡写明"v0.1 单进程锁假设"并保留后续升级点;**若多 worker → 停手报架构师**(补 DB 级 `updated_at`/revision CAS 或 lock table,单进程锁无法互斥)。此项与 reparse/correction 同前提(它们也靠这把单进程锁),D1 不新增风险、只是耗时更长放大窗口。
  - **这是 additive 触碰 522-C2 已合并锁 registry**(不改 registry 本体、只加一条 DI 注入 + 一个 in-progress 映射):走 decision 13 合并前 diff 亲核,证明纯 additive、C2/522-B 锁行为零变化。

- [ ] **G. telemetry**(收行为不收内容):枚举结果计数(§ telemetry 枚举);**绝不记 param_key / paper_param_name / value / unit / m_script 内容 / build_step 文本**。

- [ ] **H. 前端**(前端无测试框架 → 静态守卫 + 走查 + 截图)
  - build_steps 为回退视图(推荐块视图)且**存在可重生成条件**时,展示「重新生成步骤」按钮(文案见 § 前端文案)。
  - 点击 → **转圈禁用按钮 + 锁住页面交互(中途不让用户操作)** → 完成后:成功则步骤区渲染完整 build_steps;fail-closed(仍 None)则保持回退视图 + 允许再点。
  - 失败态(lock / 网络)可见、可关、可重试;console 干净(不打 error_code / error body / value / unit / m_script)。
  - **文案不露机器口吻**:按钮「重新生成步骤」;不写"基于当前参数重新推导""AI 重新生成";完成后不加"以下步骤为重新生成、可能与之前不同"免责话。对齐 05 教学口吻。

---

## 不做(明确排除,红线 — 合并前逐条核 RAW)

- ❌ 消解冲突 / 冲突参数进建模 / 任何 `parameter_conflicts` 重算或消解(D2)。
- ❌ 改 `PaperSpec.parameter_table`(overlay:抽取表永不可变;mscript 改从 mapping 读**不是**改 parameter_table)。
- ❌ 改 `record.plan.parameter_mapping`(重生成只改 build_steps/m_script/subsystem_breakdown;parameter_mapping 逐字不变,断言)。
- ❌ 动 `paper_parameter_correction` 表 / correct_extracted evidence 行(重生成不产生、不删、不改纠错;纠错仍在、可撤销)。
- ❌ 改纠错/撤销服务(C2)的纠错行为逻辑(D1 只在其后提供重生成,不碰 apply/undo)。
- ❌ 改现 `_llm_mscript_draft(spec)` / 生成路径 `generate()` 的现行为(D1 新开 mapping-aware helper + 切子路径,不动生成路径)。
- ❌ **rename** 522-B/C2 `PaperReparseLockRegistry`;改锁本体;改 reparse / correction / undo / user-supply 行为(本卡对锁只 additive 注入重生成路径 + 加一条 in-progress 映射)。
- ❌ 改 generator 507/508 显示逻辑(508 回退视图不动;D1 只是让 build_steps 从 None 变回有值,508 自然不再回退)。
- ❌ 新增对外 schema 结构 / 改七个既有 schema(重生成响应复用 UpdatedPlanResponse route-local;对外零 drift)。
- ❌ 用户传参数值 / build_steps 内容 / 任何注入面(请求体空或仅幂等 token;重生成纯从已存 plan + spec 跑)。

---

## 接口契约(贴具体签名/形状,Codex 不许改语义)

### A. POST 重生成请求 / 响应

```
POST /api/v1/papers/{paper_id}/regenerate-steps
Request(ConfigDict extra="forbid"):
{}                              # 空;无参数注入面
  # A-token 定案:不加幂等 token(per-paper 锁已挡并发写、前端按钮转圈禁用已挡重复点;
  #   token 只解网络重试、不解用户主动二次点击的成本问题,除非引 token 结果缓存=过度设计)。
  # 轻约束:前端同 paper 同时只保留一个 in-flight promise;后端同 paper 第二请求 409 regenerate_lock_conflict。

Response 200(复用 UpdatedPlanResponse 结构,route-local):
{
  "paper_id": str,
  "updated_plan": ModelGenerationPlanModel
     # build_steps:重生成成功→完整结构;fail-closed→仍 None(见 § E 失败语义)
     # m_script_skeleton:同上
     # subsystem_breakdown:build_steps 成功→由 build_steps 派生刷新;fail-closed→保留原值(replace 装回,非 merge)
     # parameter_mapping:★ 逐字不变(重生成不改工作值;含纠错后的 user_supplied 值)
     # evidence:纠错 correct_extracted 行不变(纠错仍在)
}
```

### B. 重生成服务入口(切 generate 子路径,★ 先锁后读定案)

```python
async def regenerate_steps(self, paper_id: str) -> ModelGenerationPlan:
    # ★ 顺序不得颠倒:先锁 → 锁内读 → LLM → 护栏 → 写回(P0-1)
    async with await self._lock_registry.acquire(paper_id):   # 失败 → PaperReparseInProgressError → route 映射 409 regenerate_lock_conflict
        # —— 以下全在锁内 ——
        record = await store.get_plan_record(paper_id)          # None → 404 paper_not_found
        corrections = await store.list_active_corrections(paper_id)   # C1 CRUD;拿 acquire 之后的最新值
        # 前置谓词(§ E-1):
        #   not (active corrections or plan.build_steps is None or plan.m_script_skeleton is None)
        #     → 400 regenerate_nothing_to_do
        allowed_refs   = resolved_user_evidence_refs(record, corrections)   # § C(无条件)
        allowed_prompts = resolved_prompt_ids(record)                        # § C(无条件)

        # ① build_steps:重试最多 4 次(仅瞬时/格式类;红线类立即停,§ B 重试策略)
        build_steps = await self._regenerate_build_steps_with_retry(
            record.plan.block_recommendations, record.plan.parameter_mapping, record.spec,
            allowed_refs=allowed_refs, allowed_prompts=allowed_prompts,
        )   # 成功→list[ModelBuildStep];4 次瞬时失败→None(fail-closed);红线失败→None(不重试)

        # ② m_script:独立重试最多 4 次(与 build_steps 各自成败,P0-4)
        mscript = await self._regenerate_mscript_with_retry(
            record.plan.parameter_mapping, record.spec.equations, record.spec.parameter_conflicts,
        )   # 成功→str;失败→None(不阻断 build_steps)

        # ③ subsystem_breakdown:build_steps 成功→由 build_steps 派生刷新;失败→保留原值(E-3)
        subsystem = derive_subsystem(build_steps) if build_steps is not None \
                    else record.plan.subsystem_breakdown

        # ④ 装回:★ replace 直装,不走 merge(R6 坑①:merge 按 sentinel 重算 missing bindings)
        updated_plan = replace(
            record.plan,
            build_steps=build_steps,               # None 时 508 自然回退
            m_script_skeleton=mscript,
            subsystem_breakdown=subsystem,
        )   # parameter_mapping / evidence / block_recommendations 逐字不动

        # ⑤ ★ 单一 pre-write validator(P0-2,所有写回唯一门)
        self._validate_regenerated_plan_before_write(updated_plan, record)
        #   内固定序:evidence 校验(allowed_refs+allowed_prompts) → validate_plan_does_not_resolve_conflicts
        #             → assert parameter_mapping 字节不变 → assert correction/correct_extracted evidence 不变 → schema/domain

        # ⑥ 写回:复用 set_plan(§ D),missing_prompts/bindings 从 record 原样带回
        await store.set_plan(paper_id, replace(record, plan=updated_plan))

        # ⑦ telemetry(§ 枚举);出 async with 释放锁;返回 updated_plan
        return updated_plan
```

> **evidence 校验落在 ⑤ 的 validator 内**(不是 build_steps 派生时);build_steps 成功分支产出的 refs 必过 validator 才写。**红线类失败(冲突值 / evidence 拒 / 护栏拦)在重试策略里判定为"不重试"**,直接 fail-closed。

### B-retry. 重试策略(PM 拍:4 次、仅瞬时类)

```text
_regenerate_build_steps_with_retry / _regenerate_mscript_with_retry 各自:
  for attempt in range(4):                # 含首次共 4 次
    try:
      result = await <_llm_build_steps 重生成专用 / _llm_mscript_draft_from_mapping>
      派生/校验(build_steps: validate_and_derive;mscript: mscript_assigns_conflict_value 后校验)
      return 成功产物
    except 瞬时/格式类 as e:               # BuildStepsDtoValidationError / BuildStepsStructuredError / provider timeout / 网络
      if attempt < 3: backoff(attempt); continue    # 指数退避:首次立即,后续 ~200ms*2^n
      else: telemetry(fail_closed); return None       # 4 次仍败 → fail-closed
    except 红线/确定性拒绝类 as e:          # mscript_assigns_conflict_value / evidence 拒 / 冲突护栏
      telemetry(fail_closed); return None             # ★ 立即停、不重试(注定失败、重试白烧)
```

> **区分两类失败是硬要求**:瞬时类重试有意义(换一次可能成),红线类重试无意义(设计故意拦、多试只是让用户干等 + 烧 LLM)。异常分类清单以 Stage 0 核 live 异常类型为准。

### C. mapping-aware mscript helper + build_steps 重生成专用 prompt(裁决 C 定案)

```python
async def _llm_mscript_draft_from_mapping(
    self,
    parameter_mapping: list[ParameterMapping],   # ★ 工作值(含纠错后 user_supplied)
    equations: list[EquationEntry],
    parameter_conflicts: list[ParameterConflict],
) -> str | None:
    # ★ C-builder 定案 (i):新开 build_messages_for_mscript_draft_from_mapping(吃 ParameterMapping),
    #   不把 ParameterMapping 适配成 ParameterEntry(语义不同:mapping 是工作值/source=user_supplied/无 document_id,
    #   entry 是文档抽取值;硬适配会制造 user_supplied 伪装成 document_extracted 的语义假象)。
    # 冲突过滤:过滤命中 conflict 的 mapping 行(冲突参数不进 .m,沿用 without_conflicted 等价语义)。
    # ★ 新 builder 显式告诉 LLM:这些是 effective model values、不是论文原文参数表;不得把 user_supplied 写成论文证据。
    # 保留现 mscript 后校验:非 str→error;mscript_assigns_conflict_value→红线失败(冲突值不得进 .m、不重试)。
```

> **现 `_llm_mscript_draft(spec)` 不动**(生成路径继续用);D1 新增此 helper 供重生成路径,两者并存。

**★ C-prompt(R6 坑②:build_steps prompt 明写禁 user_supplied)**:现 `build_messages_for_build_steps` / `paper_plan_build_steps.yaml`(507-B)prompt **明确禁止 user_supplied 证据**——直接复用会让重生成的 build_steps **拒绝引用纠错值参数**。D1 须为重生成路径提供**专用 build_steps prompt/role**(或参数化现 prompt),显式允许 correct_extracted / fill_missing 的 user_supplied 值作为合法参数来源(仍禁伪造 document 证据)。**生成路径 prompt 逐字不动**;重生成走专用 prompt。Stage 0 贴现 prompt 的"禁 user_supplied"措辞,确认须分叉。

### D. 写回:定案复用 `set_plan`(Stage 0 核本体)

```text
定案 (a) 复用 522-B store.set_plan(paper_id, record)   # record 内含 updated_plan
  —— 单事务 BEGIN 写 paper_plan_cache;SELECT 1 FROM paper_spec_cache 校验 + rollback;不碰 correction 表、不碰 spec row。
禁 (b) 522-C2 apply_parameter_correction_atomically(动 correction row、语义不合身)。
★ missing_prompts / missing_bindings 从 record 原样带回(set_plan 需要),不在重生成服务重算/过滤/清空。
★ Stage 0 贴 set_plan 本体确认三点(P1-5):不碰 spec row;不碰 correction row;不延长论文 bundle 24h TTL。
  若有隐藏副作用 → 报架构师(备选 set_plan_only 薄方法)。
```

### E. 前置谓词 + 失败语义(裁决 E 定案)

```text
前置谓词(E-1 定案,收窄):
  record None                                          → 404 paper_not_found
  active corrections 非空 OR build_steps None OR m_script_skeleton None → 允许重生成
  以上均否(无 active 纠错 且 build_steps + m_script 均完整)            → 400 regenerate_nothing_to_do(前端不暴露入口)
  冲突参数存在                                          → 允许(不消解、护栏兜底);不拒绝

失败语义(E-2 定案:重试 + fail-closed + 中性提示):
  瞬时/格式类失败 → 重试最多 4 次(§ B-retry);红线类 → 立即停不重试
  build_steps 4 次仍败 → fail-closed 回 200、build_steps 保持 None(已有非 None 不被清空)、508 回退、
                        telemetry regenerated_fail_closed、前端凭"200 但 build_steps 仍 None"显中性提示
  m_script 4 次仍败    → fail-closed 保持 None/原值、不阻断 build_steps、telemetry regenerated_with_steps_mscript_fail_closed

E-3 定案:fail-closed 时保留原 subsystem_breakdown(不重跑 _llm_subsystem_plan);build_steps 成功时由 build_steps 派生刷新
```

### 错误码表(定案,body 只回 error_code + 稳定文案,★ 绝不带参数名/值/单位/步骤文本)

| HTTP | error_code | 触发 |
|---|---|---|
| 404 | paper_not_found | paper_id 无 bundle |
| 409 | regenerate_lock_conflict | 锁被占(reparse / correction / undo / user-supply / 另一重生成);`PaperReparseInProgressError` 映射 |
| 400 | regenerate_nothing_to_do | E-1 定案:无 active 纠错 且 build_steps + m_script 均完整 |
| 500 | regenerate_store_failed | 写回事务/序列化失败;body 只 type name |

> **无 `regenerate_failed` 码**:E-2 定案为 fail-closed 回 200(build_steps 保持 None + 前端中性提示),LLM 失败不回 5xx。仅写回事务失败回 500 store_failed。

### telemetry 枚举(定案,只计数、不记内容)

```text
result_kind ∈ {
  regenerated_with_steps,                       # build_steps + m_script 均成功
  regenerated_with_steps_mscript_fail_closed,   # build_steps 成功、m_script 4 次失败保持 None(P2-2)
  regenerated_fail_closed,                       # build_steps 4 次失败、fail-closed 保持 None(区分"跑了但回退")
  nothing_to_regenerate,                         # 前置谓词 400
  lock_conflict,
  store_failed
}
计数:regenerate_attempt_count / regenerate_success_count / build_steps_retry_count / mscript_retry_count / 按 result_kind 分桶。
★ 绝不把 param_key / paper_param_name / value / unit / m_script / build_step 文本塞进 telemetry。
```

---

## 前端文案(对齐 05,★ 不露机器口吻、不加免责)

```text
按钮:重新生成步骤
  （不写"基于当前参数重新推导""AI 重新生成步骤""刷新建模步骤"）
重生成中:按钮转圈 + 禁用 + 锁住页面交互(遮罩或禁用态,中途不让操作)
  loading 文案(若有):朴素中性,如"生成中…"(不写"AI 正在重新推导")
成功:步骤区渲染完整 build_steps;不加"以下为重新生成的步骤，可能与之前不同"任何免责话
fail-closed(仍 None):保持回退推荐块视图 + 按钮可再点;
  若需提示,朴素中性、不露 LLM，如"暂未生成完整步骤，可稍后重试"(措辞待 05 对齐)
锁冲突/网络失败:可见、可关、可重试的错误态;不打 error_code/error body 到 console
```

---

## 验收标准(给出可跑命令;命令以 Stage 0 实测为准)

**后端契约 / 重生成正确性**
- [ ] 纠错后重生成:改一个 document_extracted 参数值 → POST regenerate-steps → GET /plan 该 mapping 仍是纠错值(source=user_supplied)、**build_steps 出现且引用了纠错值参数**、m_script 含纠错值;parameter_mapping 逐字不变(与重生成前比对)。
- [ ] **纠错值带入 build_steps**:重生成的 build_steps / m_script 里该参数用的是**纠错后的值**、不是 spec.parameter_table 的原抽值(专项断言:构造纠错值 ≠ 原抽值,查生成产物用哪个)。
- [ ] **纠错不被清**:重生成后 correction 表该行仍在、correct_extracted evidence 仍在、GET 纠错清单该条 can_undo=active;重生成**不产生新 correction 行**。
- [ ] **evidence 校验放行**:重生成 build_steps 引用 correct_extracted 参数 → 过 validator(传 `resolved_user_evidence_refs` + `resolved_prompt_ids`)不 raise;**去掉 refs 的对照测试必须 raise**(证明放行靠传参、非绕过校验)。**fill_missing 参数也覆盖**(P1-3:两类 allowlist 都放行)。
- [ ] **切 generate 后半段(P0 核心)**:fake provider 计数,POST regenerate 后确认 `_llm_plan_compose` / `_llm_missing_detect` **未被调用**,只调 mapping-aware mscript helper + build_steps 重生成 helper。
- [ ] **E-1 谓词**:build_steps=None → 允许;m_script=None → 允许;有 active correction 即便 build_steps 完整 → 允许(覆盖);**无 active 纠错 且 build_steps + m_script 均完整 → 400 regenerate_nothing_to_do、不烧 LLM**(断言 provider 未被调)。
- [ ] **★ 重试(PM 拍:4 次、仅瞬时类)**:注入瞬时失败(DTO/结构化)前 3 次、第 4 次成功 → 最终成功、provider 被调 4 次;注入瞬时失败全 4 次 → fail-closed;**注入红线失败(mscript_assigns_conflict_value / 护栏)→ provider 只被调 1 次(不重试)、立即 fail-closed**。build_steps 与 m_script 各自独立重试(一个失败不触发另一个重试)。
- [ ] **★ fail-closed(E-2)**:build_steps 4 次瞬时失败 → 回 200、updated_plan.build_steps=None、无脏数据、parameter_mapping 不变;telemetry 记 regenerated_fail_closed。**已有非 None build_steps 的覆盖场景(谓词 3)重生成失败 → 旧 build_steps 不被清空**(断言保护)。
- [ ] **★ m_script partial(P0-4)**:m_script 4 次失败但 build_steps 成功 → build_steps 写回、m_script_skeleton 保持 None/原值;telemetry 记 regenerated_with_steps_mscript_fail_closed。
- [ ] **冲突护栏(现状地基⑤)**:构造重生成产物引用冲突参数(fault:m_script / build_step display_text / configuration_hints)→ `validate_plan_does_not_resolve_conflicts` 拦截、**写回不发生**;正常无冲突参数时护栏通过。
- [ ] **★ 单一 pre-write validator(P0-2)**:测试确认所有写回分支(build_steps 成功 / m_script partial / fail-closed)**都经** `_validate_regenerated_plan_before_write`;无分支绕过直调 set_plan(核 set_plan 调用点唯一、在 validator 后)。
- [ ] **overlay 不可变**:重生成前后 spec.parameter_table + parameter_conflicts **字节不变**;parameter_mapping 逐字不变(只 build_steps/m_script/subsystem 变)。
- [ ] GET /spec、/plan 契约不变:重生成只反映在 plan.build_steps/m_script/subsystem_breakdown;响应 schema 无新增字段。
- [ ] **API 契约**:请求体 `{}` 成功;**带任意字段 → 422**(extra=forbid);响应 `{paper_id, updated_plan}`。

**并发 / 锁(复用 522-C2 锁;★ 先锁后读)**
- [ ] 重生成与 reparse 并发:reparse 中 POST regenerate → 409 regenerate_lock_conflict、不写;reparse 行为零变化(522-B 锁测试仍绿)。
- [ ] 重生成与 correction 并发:correction 中 POST regenerate → 409;correction 行为零变化(522-C2 锁测试仍绿)。
- [ ] 重生成与重生成并发:同 paper 两 regenerate → 第二 409;无半态。
- [ ] 重生成与 user-supply 并发:一个补缺失 + 一个重生成 → 只一个成功、另一个 409;无 lost update。
- [ ] **★ 锁在 LLM 期间仍持有(P0-1)**:LLM barrier 测试 —— 重生成持锁跑 LLM 期间,另一 mutation acquire 立即 409(证明持长锁、非读完即放)。
- [ ] **★ 锁内读最新值(P0-1 核心)**:acquire 后读 record/corrections —— 测试构造"acquire 前 record 是 X、acquire 后(实际读时)已是 Y",断言重生成用的是 Y(证明先锁后读、非 stale snapshot)。
- [ ] **★ 单 worker 假设(P0-5)**:测试/文档明确单进程锁前提;Stage 0 已核 worker 数(多 worker 则本卡不予实现、报架构师)。

**持久化 / 原子**
- [ ] 写回原子:注入 store 写入失败 → rollback、plan 不变、correction 不变;无 plan-half 态;**测试断言重生成不写 correction 表**(核 store 调用只碰 paper_plan_cache)。

**消费方 + 跨卡回归(复用 522-C2 判定器)**
- [ ] 重生成后 build_steps provenance 校验绿(含 correct_extracted);fill_missing 场景重生成也绿(若含 fill_missing 参数)。
- [ ] **★ undo-after-regenerate(P1-4,跨 C2/D1)**:correct → regenerate(build_steps 出) → undo → **plan.build_steps 重新 None、m_script None、correct_extracted evidence 删、correction row 删、无 orphan refs**(证明撤销把重生成的步骤也压回、不留引用已撤销纠错值的步骤)。

**前端(无测试框架 → 静态守卫 smoke + 走查 + 截图 桌面+移动)**
- [ ] build_steps=None(回退视图)时「重新生成步骤」按钮可见;点击 → 转圈禁用 + 页面交互锁住(中途不可操作)。
- [ ] 重生成成功 → 步骤区出完整 build_steps;文案无机器口吻、无免责话。
- [ ] fail-closed → 保持回退视图 + 按钮可再点;错误态(lock/网络)可见可关可重试;console 干净(不打 error_code/error body/value/unit/m_script)。
- [ ] 截图覆盖(桌面+移动):回退视图带重生成按钮 / 重生成中(转圈锁) / 重生成后完整步骤 / fail-closed 保持回退 / lock 或网络错误态。
- [ ] pnpm typecheck / lint / build 绿 + 静态守卫 smoke。

**隐私 / 日志**
- [ ] grep 守门:生产代码无 `logger.exception`/`str(exc)`/`repr(exc)`/`exc_info=True`;**参数值/单位/param_key/m_script 内容/build_step 文本不进日志·console·HTTP error body**;store SQL 错误只 log `type(exc).__name__`。
- [ ] telemetry 只计数(result_kind 枚举),grep 确认无参数名/值/单位/param_key/步骤文本进 telemetry payload。
- [ ] 错误响应 body 逐个错误码核:只 error_code + 稳定文案,无参数名/值/步骤内容。

**收尾 / schema**
- [ ] `make check` 后端全绿;`make export-schema && make verify-schema` —— **七个既有 schema(evidence/spec/plan/tuning/missing/ask_request/ask_response)+ C2 的 paper_parameter_corrections 全部对外零 drift**(重生成响应 route-local、无新对外结构);06 同步。
- [ ] `git diff --check`(行尾/字节,decision 08);`git diff --name-only origin/main` 落点符合(后端 service+route+model+新 mscript helper+锁 wiring(重生成路径)+telemetry + 前端重生成按钮+状态 + 06 + 任务卡);任务卡随代码同 PR、索引收尾单独 PR、本代码 PR 不碰 `03_TASK_INDEX.md`。

---

## 风险与注意点(合并前亲核)

- **★★ 先锁后读(P0-1,v0.1 埋的真洞、最高优先)**:acquire 锁后才读 record/corrections——合并前贴服务入口 RAW,证明读在 acquire 之内、无"读→加锁"间隙 stale snapshot;锁内读最新值 + 锁在 LLM 全程持有(对齐 reparse 先例)。
- **★ 单一 pre-write validator(P0-2)**:所有写回分支经同一 `_validate_regenerated_plan_before_write`(evidence + 冲突护栏 + parameter_mapping 字节不变 + correction 不变 + schema);贴本体 + 确认 set_plan 调用点唯一、在 validator 后,无分支绕过。
- **★ 触已合并 522-C2/522-B 锁 registry(合并前贴 RAW 前后对比)**:重生成 additive 注入 per-paper 锁——证明纯 additive(加一条 DI 注入 + 一个 in-progress 映射)、reparse/correction/undo/user-supply 锁行为逐字不变、不 rename registry、不改锁本体。decision 13。
- **★ build_step evidence 校验改动(现状地基③)**:重生成路径无条件传 `resolved_user_evidence_refs` + `resolved_prompt_ids`——贴生成路径 vs 重生成路径调用点前后 RAW,证明**生成路径逐字不变**(仍空集)、只重生成路径新传两类 refs;裁决 C 的"生成路径不放行安全"结论(Stage 0 核无 correction 后 generate 路径)写进卡。
- **★ build_steps 重生成专用 prompt(R6 坑②)**:现 build_steps prompt 禁 user_supplied——贴现 prompt 禁令措辞 + 重生成专用 prompt/role,证明分叉(重生成允许 correct_extracted/fill_missing 值、仍禁伪造 document 证据)、生成路径 prompt 逐字不动。
- **★ mscript 新 helper + 新 builder(现状地基②,C-builder 定案 i)**:新 `_llm_mscript_draft_from_mapping` + 新 `build_messages_for_mscript_draft_from_mapping`——贴本体确认从工作值取参数、显式标 effective model values、保留 `mscript_assigns_conflict_value` 后校验(冲突值命中→红线失败不重试)、现 `_llm_mscript_draft(spec)` + 现 builder 逐字不动。
- **★ 重试分类(PM 拍)**:贴重试 helper 本体,确认瞬时/格式类重试 ≤4、红线类立即停不重试;异常分类清单对齐 live 异常类型。
- **★ replace 不用 merge(R6 坑①)**:装回用 `replace(record.plan, ...)`,不走 `merge()`(它按 sentinel 重算 missing bindings)——贴装回本体确认 missing_prompts/bindings 原样、不重算。
- **overlay 不可变红线**:parameter_mapping / parameter_table / parameter_conflicts 重生成不改(断言字节不变);纠错行 + correct_extracted evidence 不动。
- **fail-closed 红线(E-2)**:LLM 4 次仍败保持 build_steps=None、不产脏数据、不写半态、已有非 None 不被清空;与既有 508 回退语义一致。
- **原子写回**:只写 plan、不动 correction 表;fault injection 验半态不产生。

---

## Stage 0 可落性 gate(Codex 实现前核 live,不符停手报架构师,禁兜底硬上)

1. `git fetch origin && git rev-parse origin/main` —— 报 HEAD;`git merge-base --is-ancestor <live 66e1915> origin/main` 通过(允许 main 合法前进,用 live 值)。
2. 确认本卡已随代码入 `docs/tasks/`(PM 预放,untracked=预期)。
3. **复核 C2 as-built 仍在**(贴 RAW 定性):纠错/撤销服务置 build_steps=None;per-paper 锁 registry(含 user-supply 扩展);`apply_parameter_correction_atomically`/`undo_parameter_correction_atomically`;`resolved_user_evidence_refs`;C2 三端点。
4. **本会话 R6 五实证 live 复核(派单那刻仍成立)**:
   - build_steps 生成函数吃 plan 工作值(`_llm_build_steps` 传 record.plan.parameter_mapping 自然带纠错值)。
   - m_script 现入口只吃 spec.parameter_table(须新 mapping-aware helper)。
   - build_step evidence 校验生成路径传空集(重生成须传 resolved refs)。
   - `merge` / `validate_and_derive_build_steps` 可复用装回、不动 parameter_mapping。
   - `validate_plan_does_not_resolve_conflicts` 只在 generate 尾部(重生成须显式补调)。
5. **本卡新增高风险落点 gate(核准才动,R6 本会话已初核、派单那刻复核)**:
   - **切 generate 子路径可行**:`_llm_build_steps` + mscript helper 可独立于 `_llm_plan_compose`/`_llm_missing_detect` 调用(不隐式依赖后者产物,除已存 plan 的 parameter_mapping/block_recommendations);贴 generate 内这两段依赖确认可切。
   - **`_validate_build_step_evidence` 全调用点**:贴全部调用点,确认只重生成路径需传两类 resolved refs、**无"active correction 存在时又走 generate()"的路径**(plan 丢失懒生成 / 后台修复 / GET miss 懒生成 / admin 全量);发现此类 → 停手报架构师(裁决 C)。
   - **★ build_steps prompt 禁 user_supplied(R6 坑②)**:贴现 `build_messages_for_build_steps` / `paper_plan_build_steps.yaml` 的禁 user_supplied 措辞,确认重生成须专用 prompt/role 分叉。
   - **★ merge 按 sentinel 重算 missing bindings(R6 坑①)**:确认 `merge()` 会重算 missing bindings、装回须用 `replace(record.plan, ...)` 绕开。
   - **`set_plan` 可承接重生成写回**:贴 set_plan 本体,确认单事务只写 plan、保留 spec 校验 + rollback、**无隐藏副作用**(不碰 correction row、不碰 spec row、不延长 24h TTL,P1-5);有副作用 → 报架构师(备选 set_plan_only)。
   - **锁可 additive 注入重生成路径 + 单 worker 前提(P0-5)**:`get_paper_reparse_lock_registry` 可注入重生成 route/service、`async with acquire` 持锁跑 LLM、映射 409,不改 registry/锁本体;**确认部署/测试 worker 数**——单 worker 则写明假设,**多 worker → 停手报架构师**(单进程锁无法互斥、需 DB CAS/lock table)。
6. 任一不符 → 停手诊断(decision 15:卡/包写错 vs main 真不对 vs 同步动作漏做)。

---

## 给 Codex 的提示

- 走 feature branch(**git fetch 后从 origin/main 切**,不许 main 直推)。
- **卡随代码同 PR**(本卡 `git add` 进代码 PR);**索引收尾单独 PR**;**本代码 PR 不碰 `03_TASK_INDEX.md`**。
- PR:Codex 给标题 + 正文草稿 + `pull/new` 链接,PM 网页侧建 PR + squash merge。
- `make check` 全管道跑,禁拆 CI step 列;显式加 `make export-schema && make verify-schema` + `pnpm typecheck`/lint/build + smoke。
- 请求体空 / `extra="forbid"`;无参数注入面;重生成纯从已存 plan 工作值 + spec 跑;错误码 body 只回 error_code + 稳定文案,绝不带参数名/值/步骤内容。
- **★ 先锁后读(P0-1,不得颠倒)**:`async with acquire(paper_id)` 内才读 record/corrections;持锁跑完整 LLM(含重试)再 set_plan 写回、出块释放(对齐 reparse)。
- **重生成只改 plan**(build_steps/m_script/subsystem_breakdown),**不动 correction 表 / correct_extracted evidence**;parameter_mapping 逐字不变(写回前字节断言)。
- **切 generate 子路径**:只重跑 `_llm_build_steps`(重生成专用 prompt、允许 user_supplied 值)+ 新 `_llm_mscript_draft_from_mapping`(新 builder、吃工作值);不重跑 `_llm_plan_compose`/`_llm_missing_detect`;装回用 `replace(record.plan, ...)` 不用 `merge()`(避 sentinel 重算)。
- **★ 单一 pre-write validator(P0-2)**:所有写回经 `_validate_regenerated_plan_before_write`(evidence 两类 refs + `validate_plan_does_not_resolve_conflicts` + parameter_mapping 字节不变 + correction 不变 + schema);set_plan 只在 validator 后调一次。
- **★ 重试(4 次、仅瞬时类)**:瞬时/格式失败重试 ≤4、红线失败(冲突值/护栏/evidence 拒)立即停;build_steps 与 m_script 各自独立重试;m_script 失败不阻断 build_steps。
- build_step evidence 校验重生成路径**无条件传两类** `resolved_user_evidence_refs(record, corrections)` + `resolved_prompt_ids(record)`;生成路径逐字不动。
- 锁复用 522-C2 registry(DI additive、不 rename)、重生成路径加锁、映射 409 regenerate_lock_conflict;**确认单 worker 前提**(多 worker 停手报架构师)。
- 写回复用 `set_plan`(Stage 0 确认无副作用、missing_prompts/bindings 原样带回);禁重生成里动 correction 表。
- 前端「重新生成步骤」按钮转圈禁用 + 锁页面;fail-closed 时前端凭"200 但 build_steps 仍 None"显中性提示「暂未生成完整步骤,可稍后重试」;**文案不露机器口吻、不加免责话**;截图作**图片附件传进对话**、不收本机路径,覆盖每个关键态(桌面+移动)。
- **合并前节奏**(后端契约卡 + 前端):前端截图(关键态×桌面移动)+ 后端真测试 + diff 边界逐处核(**先锁后读服务入口 + 单一 validator + 锁 additive 注入 + build_step evidence 生成/重生成两路 + build_steps 专用 prompt 分叉 + 新 mscript helper/builder + replace 装回 + 重试分类 + 写回只碰 plan**)+ 隐私红线点亲核(参数值/单位/m_script/步骤文本绝不落日志/console/error body/telemetry,贴本体不凭勾选)+ 对外零 drift(七个 + corrections schema 全零 drift、无新对外结构)。
- RAW 取证/diff 贴对话、去行号、不收本机路径。

---

**版本**:v0.2(2026-07-03,GPT R1 审卡 + Codex R6 live 核收敛,派 Codex 终版)
**作者**:Claude(架构师)
**前置 commit**:main 必须含 C2 代码 `66e1915`(#164)(Stage 0 用 `git merge-base --is-ancestor` 校验,允许 main 合法前进)
**入库改名**:入 `docs/tasks/task-522-d1-regenerate-steps-v0_2.md`
**审批级别**:GPT R1 审卡(1 P0 先读再锁 + 4 P0 + P1/P2 收敛、裁决全定案)+ Codex R6 live 核(五实证 + 锁粒度坐实 + 四落点 + 两坑)双通过 → PM 已拍(④ 第一件形状 / 按钮/锁/走 LLM 不告知/文案口吻 / 失败重试 4 次仅瞬时类)→ 派 Codex Stage 0 → 实现
**后继**:TASK-522-D2(消解冲突 · 让用户拍板选值消掉冲突参数),D1 合并后起草
