# TASK-522-C2:用户纠错 · 纠错行为 + 前端(v0.2 — GPT R1 审卡 + Codex R6 live 核收敛版)

## 状态

🔲 v0.2(2026-07-02,待 Codex Stage 0 → 实现)
- 起稿基础:origin/main HEAD 本会话实测 = `4df6936`(522-C1 索引收尾 #163 顶;C1 代码 `2ef7a2d` #162 是 ancestor;链到 522-B #160 / 521-D 不断)。Stage 0 用 live 值校验,允许 main 合法前进。
- **GPT(R1)审卡**:方向条件通过(overlay 不重开)+ 4 P0(user-supply 并发缺口 / source=user_supplied 二义 / 原子事务缺 seam / tuning 输出校验漏接)+ 8 P1 + 4 P2,全数收敛进本卡。
- **Codex(R6)live 核**:整体可落 + 三处从 live 坐实的改实点(UpdatedPlanResponse 字段=paper_id+updated_plan、user-supply 无锁无事务、schema 手工白名单),全数收敛。
- v0.1→v0.2 结构变更:锁扩为 per-paper mutation 锁(含 user-supply,additive 不 rename)/ 补原子 store 事务方法 / correctable 硬谓词 + 新错误码(10→11)/ 四处消费方接线 / GET 清单进 schema(新增 alias+文件+Makefile)/ 一批 P1 契约细化。

---

## 上下文

### 在解析纠错子线(TASK-522)的位置

解析纠错四条:① 诚实提示(对内暂缓)/ ② 重新解析(**522-B ✅ #160**)/ ③ 用户纠错 / ④ 局部重跑(最难,排最后)。

③「用户纠错」= 让用户手动改 AI **抽错的参数值**。已拆两卡:**C1(契约 substrate)✅ #162**(出处契约扩展 + `paper_parameter_correction` 表 + 惰性 CRUD + 清理级联 + 统一判定器,全程惰性);**本卡(C2)= 纠错行为 + 端点 + 撤销 + 锁使用 + 建模步骤简化 + 消费方接线 + 前端**,把 C1 地基接活。

### overlay 模型(继承 C1,C2 不得违背)

- `PaperSpec.parameter_table` = **不可变**文档抽取结果(521-B2 `parameter_conflicts` 冲突检测真值源),纠错**永不改它**。
- `ModelGenerationPlan.parameter_mapping` = 实际建模**工作值**(前端参数表渲染这个)。纠错改这里对应那条 mapping 的 value/unit,source→`user_supplied`。
- 内部表 `paper_parameter_correction`(C1 已建)= 审计/撤销 overlay(存 AI 原抽值 + 纠错值)。
- **推论(核心简化)**:纠错改 plan mapping、不动 spec.parameter_table,冲突从不可变 spec 算 → **纠错永远够不到冲突参数、无需重算 `parameter_conflicts`**。C2 **不写任何冲突重算**。

### 现状地基(Codex R6 本轮 @ live `4df6936` 实测 — ★ 三处坐实的改实点已并入本卡)

**① UpdatedPlanResponse 形状(R6 实证,v0.1 写错已改)**:现有 user-supply 端点响应模型 = `UpdatedPlanResponse{ paper_id: str, updated_plan: ModelGenerationPlanModel }` + `ConfigDict(extra="forbid")`(**字段名 `updated_plan`,不是 `plan`**)。POST correction 要带 correction → **新 wrapper `{paper_id, updated_plan, correction}`**;undo 复用 `{paper_id, updated_plan}`(见 § 接口契约 A/B)。

**② user-supply 无锁无事务(R6 实证 → P0-1/P0-3 依据)**:现有 `UserSupplyService.merge` = 重读 record → `deepcopy(plan)` → 改 mapping + `replace(source=USER_SUPPLIED)` → `evidence.append(tag_user_supplied)` → `validate_for_spec` → 直接 `cache.set`。**无 stale/CAS、无 prepare-then-commit、无锁**;并发 = 后写覆盖前写。异常经全局 handler、`PaperUserSupplyError` 全压 `400 paper_user_supply_invalid`。store 侧 `set_plan` 单事务只写 `paper_plan_cache`(plan/missing/bindings)、不碰 correction 表。C1 的 correction CRUD 各自独立 commit。⇒ 纠错**不能照 user-supply 事务 pattern 写**、**必须新增原子 store 方法**(§ 接口契约 D);**user-supply 也须接入并发锁**否则与纠错互相 lost update(§ 范围 D)。

**③ schema 手工白名单(R6 实证 → P0-9/K 依据)**:`export_paper_schemas.py` 的 `OUTPUTS` 是**手工 alias 白名单**(paper_evidence/spec/plan/tuning/missing/ask_request/ask_response 七个);`make verify-schema` 只 `git diff` 这七个固定文件、**不扫 route/OpenAPI**。521-C 对外 governed 响应经 alias 进 exporter(`PaperAskResponseSchema = PaperAskResponseModel`);522-B 的 `PaperReparseResponse` 是 **route-local model、未进 exporter**(它复用的都是已 freeze 的 model,无全新结构)。⇒ GET 清单引入**全新对外结构** `ParameterCorrectionModel`,若算对外契约,**必须新增 alias + `schemas/paper_parameter_corrections.schema.json` + 加进 `export_paper_schemas.py` 和 Makefile verify-schema 列表**,否则 verify-schema 抓不到(§ 范围 K)。

**④ 三个高风险挂接点(上轮已核,全成立)**:锁 registry 可 additive 共享(`get_paper_reparse_lock_registry` 从 `app.state` 取单例、`acquire` fail-fast 抛 `PaperReparseInProgressError`);`build_steps=None`/`m_script_skeleton=None` 合法、508 自动回退块视图、`PaperPlanService.generate` 不持有 corrections(置 None 落纠错服务写 plan 时);`resolved_user_evidence_refs` 零消费方、三处(build_steps provenance / tuning / ask)可 additive 接。

### Base + 范围边界

- **Base**:main 必须含 C1 代码 `2ef7a2d`(#162)。Stage 0 用 `git merge-base --is-ancestor <live 2ef7a2d> origin/main` 校验,允许 main 合法前进。
- **范围(C2)**:三端点 + 纠错/撤销服务 + **per-paper mutation 锁(扩含 user-supply)** + **原子 store 事务方法** + build_steps/m_script 置 None + **四处**消费方接统一判定器 + 错误码(11)+ telemetry + 前端 + REPARSE 弹窗补文案 + schema-sync(GET 清单新对外响应进 schema)+ 截图。
- **不在本卡(留 522-D 或更后)**:局部重跑 / 消解冲突 / 带纠错重生成完整 build_steps;改「自己填的缺失值」的值(那是 user-supply 的事,不在 ③);批量同名参数改;figure/equation target。

---

## 输入(前置依赖)

- 必须已合并 main:TASK-502(UserSupplyService/EvidenceTagger/`UpdatedPlanResponse`)、TASK-503(PaperBundleStore SQLite)、TASK-507-A/B(build_steps provenance)、TASK-521-A/B1/B2/C(多文档身份 + 冲突 + citation)、**TASK-522-B**(reparse + prepare-then-commit + 锁 registry + 论文 TTL 清理)、**TASK-522-C1**(出处契约扩展 + `paper_parameter_correction` 表 + 惰性 CRUD + 清理级联 + `resolved_user_evidence_refs`)。
- 必读:`06_OUTPUT_CONTRACTS.md`、`04_ENGINEERING_STANDARDS.md`(§ 日志禁令)、`05_EXPLANATION_STYLE_GUIDE.md`(文案)、决策 11 / 12 v0.4 / 13 / 26。

---

## 输出(交付物)

- 新增:纠错服务(correctable 谓词 + target 定位 + stale/ambiguous 校验 + apply + undo)+ 三端点路由 + 请求/响应 pydantic 模型(`extra="forbid"`)。
- 新增:**store 级原子事务方法** `apply_parameter_correction_atomically` / `undo_parameter_correction_atomically`(一次 BEGIN 写 plan + 动 correction row + evidence)。
- 修改:**per-paper mutation 锁** — 复用 522-B `PaperReparseLockRegistry` 实例(不 rename),additive 注入 correction / undo / **user-supply merge**;拿不到锁各自映射 in-progress 码。
- 修改:纠错/撤销写 plan 时置 `build_steps=None` + `m_script_skeleton=None`(纠错服务内,经原子方法,不改 generator/507/508)。
- 修改:**四处**消费方接 `resolved_user_evidence_refs`(build_steps provenance / tuning **prompt source 表** / tuning **输出 evidence validator** / ask source 表),保留 `resolved_prompt_ids`。
- 新增:纠错行为 telemetry(枚举 target_kind 计数,不记内容)。
- 前端:参数表按 active corrections 渲染(document_extracted 显「改」/ 有 active correction 显「你改的+AI 原本抽+撤销」/ fill_missing 的 user_supplied 不显「改」)+ 内联编辑 + 丢 citation + stale/lock 错误态。
- 修改:522-B 前端 `REPARSE_CONFIRM_COPY` 补「已纠错的参数值」(改已合并产物,PM 知会,decision 13)。
- 新增:**GET 清单进 schema** — `PaperParameterCorrectionsSchema` alias + `schemas/paper_parameter_corrections.schema.json` + 加进 `export_paper_schemas.py` 和 Makefile verify-schema 列表。
- 修改:`06_OUTPUT_CONTRACTS.md` 加 correction 端点契约段。
- 新增:后端真测试(端点/服务/状态机/锁/并发/隐私)+ 前端静态守卫 smoke + 关键态截图(桌面+移动)。

---

## 范围(必须做)

- [ ] **A. 三个端点**(裁决 B、P1-3/P1-4)
  - `POST /api/v1/papers/{paper_id}/parameter-correction`:请求体只接 `{target, corrected_value, corrected_unit?}`、**`extra="forbid"`(外层 + 内层 target,P1-6)**;source/document_id/user_action/correction_id/created_at 全服务端注入。返回**新 wrapper** `{paper_id, updated_plan, correction}`(§ 接口契约 A)。
  - `POST .../{correction_id}/undo`:撤销,恢复 original 链、删 correction row + evidence。返回 `{paper_id, updated_plan}`(复用 UpdatedPlanResponse 结构)。
  - `GET /api/v1/papers/{paper_id}/parameter-corrections`:纠错清单(独立端点、进 schema);每条见 § 接口契约 C。
  - **GET /spec、/plan 不改**(返 effective 工作值;GET /spec、/plan 对外 schema 零 drift)。

- [ ] **B. 纠错服务:correctable 谓词 + target 定位 + apply**(P0-2/P0-3/P1-2)
  - **correctable 硬谓词 + 确定性定位算法**(§ 接口契约 E,逐步实现):按 `(paper_param_name, model_param_name)` 找候选 → 0 条走 conflict-key 判定(唯一命中冲突→409 requires_local_rerun / 否则 400 not_extracted)→ ≥2 条 400 ambiguous → 1 条校验 index + value/unit echo(不符 409 stale)→ 命中后按 source 分:`document_extracted` 首次纠错、`user_supplied` **仅当有 active correction row + plan_target 匹配 + evidence 有 correct_extracted** 才 re-correct,否则(fill_missing / 其他 user_supplied)**400 correction_target_not_correctable**。
  - **只改一行、不批量**;**③ 只纠 document_extracted mapping + re-correct 可证明的纠错 mapping**;不改缺失值(那走 user-supply)。
  - apply:改 mapping value/unit + source→user_supplied;append 一条 correct_extracted evidence(§ 接口契约 F);置 build_steps/m_script=None;写 correction row(首次 insert original=现值 / re-correct update corrected_*、**original_* 首次值不变**,P1-1);全部经**原子 store 方法**(§ D)。

- [ ] **C. 撤销服务**(P1-2/P1-4)
  - undo **重校验**:correction_id 不存在或属其他 paper → 404 correction_not_found;target 不再匹配当前 plan → 409 correction_target_stale;plan 中该 correction 的 evidence 0 条或多条 → 500 correction_store_failed(内部 data_corrupt,body 不带值)。
  - 恢复 mapping original_value/unit/source/document 链;删 correction row + 删对应 correct_extracted evidence;**build_steps/m_script 保持 None**(不因回到零纠错自动恢复,honest 限制,UI 交代);全部经原子 store 方法(§ D)。

- [ ] **D. ★ per-paper mutation 锁(扩含 user-supply,P0-1,依据见现状地基②)**
  - **复用 522-B `PaperReparseLockRegistry` 实例**(同一 `get_paper_reparse_lock_registry`,additive 注入、**不 rename 合并类**、不改锁本体)。
  - **correction / undo / user-supply merge 三条写 plan 路径** + 现有 reparse,均在写 plan 前 fail-fast `acquire`;拿不到锁映射各自 in-progress 码:reparse→现有 `reparse_in_progress`;correction/undo→**409 correction_lock_conflict**;**user-supply→409(新增 in-progress 映射,additive 加错误分支、不改 merge 成功逻辑)**。
  - **这是正确性必需的合并产物触碰**(碰 502 user-supply 端点/服务 additive 加锁 + 加 409 分支;碰 522-B registry 复用):走 decision 13 合并前 diff 亲核逐处贴 RAW,证明**纯 additive、user-supply merge 成功路径逐字不变、reparse 行为零变化、不 rename**。PM 已一句知会(并发安全加固)。

- [ ] **E. 持久化 + 原子(P0-3,补 seam,依据见现状地基②)**
  - **禁止** service 层顺序调 `set_plan()` + `insert/update/delete correction`(各自 commit、破坏原子红线)。**新增 store 级单事务方法**(§ 接口契约 D):一次 `BEGIN` 写 plan row(含纠错/恢复 mapping + evidence + build_steps=None)+ insert/update/delete correction row,`commit` 后才返回;任一失败 rollback、旧 bundle 字节不动(接 522-B prepare-then-commit 边界)。
  - **spec 不写、冲突不算**(overlay)。

- [ ] **F. build_steps / m_script 置 None**(P0-5,PM 已拍板)
  - 落点 = 纠错/撤销服务构造 `updated_record` 时置 `build_steps=None` + `m_script_skeleton=None`,经 **§ D 原子方法**整包写 plan(**不改 generator/507/508**);508 静默回退推荐块视图。
  - **fail-closed**(别改「留旧值+banner」);撤销恢复参数值但 build_steps/m_script 不自动回;完整步骤要重新解析(清纠错)或 522-D 局部重跑才回来,UI 交代。**恢复条件是「无活跃纠错且经过重生成」,不得按 correction row 数量在服务里自动恢复 build_steps。**

- [ ] **G. 四处消费方接统一判定器**(裁决 A + P0-4,接法见 § 接口契约 G)
  - ① build_steps provenance:additive 加 `correct_extracted` allowlist,保留 prompt-id 逻辑。
  - ② tuning **prompt source 表**:`build_messages_for_tuning_suggest` 接 `resolved_user_evidence_refs`,把 correct_extracted 纳入 allowed。
  - ③ **tuning 输出 evidence validator**(P0-4 新增):tuning 后处理校验 LLM 返回 evidence 处**也**接判定器,否则 correct_extracted「prompt 允许、输出被拒」成孤儿。Stage 0 核该 validator 具体调用点。
  - ④ ask source 表:additive correction-aware candidate/校验;`resolved_prompt_ids` 只管 remaining missing prompts、不替换。

- [ ] **H. 错误码(11,P0-2 + P1-6,body 不带原值/新值/参数名,§ 接口契约错误码表)。**

- [ ] **I. telemetry**(P2-3,收行为不收内容):枚举 `target_kind` 计数(§ 接口契约 telemetry 枚举);**绝不记参数名/值/单位/param_key**。

- [ ] **J. 前端**(P1-5、P2-1、P2-4,前端无测试框架 → 静态守卫 + 走查 + 截图)
  - 参数表**按 active corrections 清单**渲染:`document_extracted` mapping 显「改」;有 active correction 的 mapping 显「你改的」+「AI 原本抽:X(来自 <doc label>)」+「撤销」;**fill_missing 的 user_supplied mapping 不显 C2 的「改/AI 原本抽/撤销」**(防 P0-2 回归)。
  - 内联编辑 → 提交;丢出处不显 citation(按 mapping.source=user_supplied);文案「你改的」(**不写「用户权威值」**),对齐 05。
  - stale/lock 错误态可见、可关、可重试;console 干净。

- [ ] **K. REPARSE 文案 + GET 清单进 schema(P2-4 + P0-9,依据见现状地基③)**
  - 522-B 前端 `REPARSE_CONFIRM_COPY` 补「**已纠错的参数值**」(改已合并产物、decision 13、PM 知会)。
  - **GET 清单进 schema**:新增 `PaperParameterCorrectionsSchema = ParameterCorrectionsResponse` alias + `schemas/paper_parameter_corrections.schema.json`(加进 `export_paper_schemas.py` 的 `OUTPUTS` + Makefile `verify-schema` diff 列表);走 decision 13 全清单(freeze + 边界测试 + 06)。**POST correction/undo 的 wrapper 是 route-local**(复用已 freeze 的 ModelGenerationPlanModel + 新 freeze 的 ParameterCorrectionModel,不单独导出,同 UpdatedPlanResponse/PaperReparseResponse 先例)。GET /spec、/plan、evidence 等七个既有 schema **零 drift**。

---

## 不做(明确排除,红线 — 合并前逐条核 RAW)

- ❌ 局部重跑 / 消解冲突 / 带纠错重生成完整 build_steps(522-D)。
- ❌ 纠错**冲突参数**(不进 plan mapping、够不到;target 指向它 → 400/409,消解归 522-D)。
- ❌ **任何 `parameter_conflicts` 重算**(overlay 下多余)。
- ❌ 改 `PaperSpec.parameter_table`(overlay:抽取表永不可变)。
- ❌ 改「自己填的缺失值」的值(fill_missing 走 user-supply;correction 端点对 fill_missing mapping 返 400 not_correctable)。
- ❌ 批量同名参数改 / figure / equation target。
- ❌ **rename** 522-B `PaperReparseLockRegistry` 合并类;改锁本体;改 reparse 路由/seam/行为;改 user-supply merge **成功路径**逻辑(本卡对 user-supply 只 additive 加锁 + 加 409 in-progress 分支);改 generator/507/508 显示逻辑。
- ❌ 用户可传 source/document_id/user_action/correction_id(全服务端注入;请求 `extra="forbid"`)。
- ❌ 内部用 `param_key` 字符串还原身份(P1-7:param_key 仅 opaque display,内部身份用 `PlanCorrectionTarget`/plan_target_json)。

---

## 接口契约(贴具体签名/形状,Codex 不许改语义)

### A. POST 纠错请求 / 响应(★ wrapper 修正)

```
POST /api/v1/papers/{paper_id}/parameter-correction
Request(ConfigDict extra="forbid",外层 + 内层 target 均 forbid):
{
  "target": {
    "paper_param_name": str,
    "model_param_name": str,
    "plan_mapping_index": int,
    "expected_value": str,        # 当前 mapping value echo(stale 校验)
    "expected_unit": str | None   # 当前 mapping unit echo
  },
  "corrected_value": str,         # strip 后非空
  "corrected_unit": str | None    # 三态,见 P1-1(unit 语义)
}

Response 200(★ 新 route-local wrapper,非直接 UpdatedPlanResponse):
{
  "paper_id": str,
  "updated_plan": ModelGenerationPlanModel,   # 纠错 mapping source=user_supplied;build_steps=None
  "correction": ParameterCorrectionModel      # 见 C
}
```

### B. POST 撤销

```
POST /api/v1/papers/{paper_id}/parameter-correction/{correction_id}/undo
Request: 空
Response 200(复用 UpdatedPlanResponse 结构):
{ "paper_id": str, "updated_plan": ModelGenerationPlanModel }  # mapping 恢复 original;build_steps 仍 None
```

### C. GET 纠错清单(★ 新对外契约,进 schema,走 decision 13 新增套路)

```
GET /api/v1/papers/{paper_id}/parameter-corrections
Response 200(ParameterCorrectionsResponse,extra="forbid"):
{ "paper_id": str, "corrections": [ ParameterCorrectionModel, ... ] }

ParameterCorrectionModel(extra="forbid"):
{
  "correction_id": str,
  "param_key": str,                 # opaque display key(内部勿解析,P1-7)
  "target": {                       # P1-3/P1-7:audit 用确定身份
    "paper_param_name": str,
    "model_param_name": str,
    "plan_mapping_index": int
  },
  "original": {
    "value": str,
    "unit": str | None,
    "source": "document_extracted",
    "document_id": str | None,      # P1-5 匹配规则,唯一命中才写、否则 null
    "document_label": str | None    # 由 document_id 解析;filename 仅展示不落日志
  },
  "corrected": { "value": str, "unit": str | None },
  "created_at": str,                # P2-2:UTC ISO-8601 带 Z
  "updated_at": str,                # 同上
  "can_undo": bool,
  "can_undo_reason": "active" | "target_stale" | "missing_mapping"   # P1-3
}
```
> `can_undo` 规则(06 写明):`active correction row 且 target 仍匹配当前 plan mapping` → `can_undo=true, reason="active"`;target 与当前 plan 不符 → `false, "target_stale"`;找不到对应 mapping → `false, "missing_mapping"`。

### D. ★ 原子 store 事务方法(P0-3,新增,禁串 CRUD)

```python
async def apply_parameter_correction_atomically(
    self,
    paper_id: str,
    updated_record: PaperPlanRecord,        # 已含纠错 mapping + append 的 evidence + build_steps=None
    correction: PaperParameterCorrection,   # 首次=完整行;re-correct=带新 corrected_*、original_* 取库中首次值
    is_recorrect: bool,                     # False→INSERT;True→UPDATE corrected_*/updated_at,original_* 不动
) -> None: ...
# 一次 BEGIN:校验 spec 存在 → UPSERT paper_plan_cache(plan/missing/bindings) → INSERT 或 UPDATE correction row → commit;失败 rollback、旧 bundle 不动。

async def undo_parameter_correction_atomically(
    self,
    paper_id: str,
    updated_record: PaperPlanRecord,        # 已含恢复 mapping + 删掉 correct_extracted evidence、build_steps 仍 None
    correction_id: str,
) -> None: ...
# 一次 BEGIN:UPSERT paper_plan_cache → DELETE correction row(WHERE paper_id AND correction_id)→ commit;失败 rollback。
```
> evidence 的 append / 删除在 **service 构造 `updated_record` 时**完成(deepcopy plan → 改/恢复 mapping → append / remove 那条 `correct_extracted` evidence(按 correction_id 匹配)→ 置 build_steps=None);store 方法只整包写 plan + 动 correction row。序列化走 C1/522-B 已实证 wrapper,失败抛 StoreError、SQL 错误只 log `type(exc).__name__`。

### E. ★ correctable 谓词 + 确定性定位算法(P0-2/P1-2)

```text
1. record = get(paper_id);None → 404 paper_not_found
2. cands = [i for i,m in enumerate(plan.parameter_mapping)
            if (m.paper_param_name, m.model_param_name) == (target.name, target.model_name)]
3. len(cands)==0:
     # 按 spec.parameter_conflicts 稳定 key 查(不猜)
     若 target 能唯一命中一条 conflict 项(稳定 key) → 409 correction_requires_local_rerun
     否则 → 400 correction_target_not_extracted
4. len(cands)>=2 → 400 correction_target_ambiguous
5. len(cands)==1:
     i = cands[0]
     若 target.plan_mapping_index != i → 409 correction_target_stale
     若 mapping[i].value != target.expected_value 或 mapping[i].unit != target.expected_unit → 409 correction_target_stale
     m = mapping[i]
     若 m.source == document_extracted:  # 首次纠错
         original = 现值(value/unit/source=document_extracted);original_document_id 按 P1-5 匹配
         is_recorrect = False
     elif m.source == user_supplied:
         若 存在 active correction row(param_key 对应) 且 plan_target 匹配当前 i
            且 plan.evidence 有 user_action=correct_extracted + 该 correction_id:
             is_recorrect = True   # re-correct,original_* 取库中首次值不变
         否则 → 400 correction_target_not_correctable   # fill_missing / 其他 user_supplied
     else → 400 correction_target_not_correctable
6. 校验 corrected_value/unit(§ P1-8 边界),违反 → 400 correction_invalid_value / correction_unit_invalid
```

### F. 纠错 evidence 形状(裁决 A,C1 契约已备)

append 一条:`source=user_supplied`、`user_action=correct_extracted`、`parameter_correction_id=<correction_id>`、`correction_param_key=<param_key>`;`missing_param_prompt_id=None`、`document_id/paper_section_id/equation_id/figure_id/excerpt` 全 None(C1 invariant validator 强制)。撤销时按 correction_id 精确移除这条(0 或多条 → 500 data_corrupt)。

### 错误码表(11 个,body 只回 error_code + 稳定文案,★ 绝不带原值/新值/参数名)

| HTTP | error_code | 触发 |
|---|---|---|
| 404 | paper_not_found | paper_id 无 bundle |
| 400 | correction_target_not_extracted | target 名字无 mapping 且非冲突项 |
| 409 | correction_requires_local_rerun | target 唯一命中冲突 abstain 项(消解归 522-D) |
| 400 | correction_target_ambiguous | 同 (name,model_name) 多条 mapping |
| 409 | correction_target_stale | index/value/unit echo 与当前 mapping 不符 |
| 400 | **correction_target_not_correctable** | mapping 存在但非可纠错对象(fill_missing / 无 active correction 的 user_supplied) |
| 400 | correction_invalid_value | corrected_value 空/非法(§ P1-8) |
| 400 | correction_unit_invalid | corrected_unit 非法(空串/非法字符,§ P1-8) |
| 409 | correction_lock_conflict | 锁被占(reparse / user-supply / 另一纠错);`PaperReparseInProgressError` 映射 |
| 404 | correction_not_found | undo 时 correction_id 不存在或属其他 paper |
| 500 | correction_store_failed | 事务/序列化失败 或 undo evidence 0/多条(data_corrupt);body 只 type name |

### P1-1. corrected_unit 三态语义(用 model_fields_set 区分)

```text
corrected_unit omitted(不在 model_fields_set) → 保留当前 mapping.unit
corrected_unit: null                          → 显式清空 unit(mapping.unit=None)
corrected_unit: ""(strip 后空)                → 400 correction_unit_invalid
corrected_unit: str                           → trim 后写入(拒控制字符)
```

### P1-5. original_document_id / document_label 来源(不猜、不用 primary 兜底)

```text
首次纠错(document_extracted mapping)时,ParameterMapping 无 document 字段。
original_document_id 从 PaperSpec.parameter_table 按 (name, value, unit, source=document_extracted) 匹配:
  唯一命中          → 写该 entry 的 document_id
  多命中 / 0 命中   → original_document_id=null, document_label=null
绝不用 primary_document_id 兜底(多文档红线:不猜来源、同名多源不折叠)。
document_label 由 document_id 解析(复用现有 label 映射;filename 仅展示不落日志)。
(仅影响 audit 展示;plan mapping 无 document 字段,不影响撤销恢复。)
```

### P1-8. value / unit 输入边界(保 string 语义,不做数值解析)

```text
corrected_value:strip 后非空;max_length 与 ParameterMapping.value 对齐;拒控制字符 → 否则 400 correction_invalid_value
corrected_unit:null 或 strip 后 1..N;拒控制字符;空白串非法 → 否则 400 correction_unit_invalid
```

### G. 四处消费方 additive 接法(保留 resolved_prompt_ids,不替换)

```text
① build_steps provenance(validate_build_step_evidence_for_spec):
   现只收 allowed_user_prompt_ids: frozenset[str]、生成路径传空集合。
   additive 增加 correct_extracted allowlist(传 set[UserEvidenceRef] 或并列参数):
     fill_missing → prompt_id ∈ allowed prompt ids(现逻辑不动)
     correct_extracted → correction_id ∈ allowed correction refs
   生成路径调用点传 resolved_user_evidence_refs(record, corrections)(替代现在的空集合)。

② tuning prompt source 表(build_messages_for_tuning_suggest):
   现 allowed_resolved_user_evidence 只按 missing_param_prompt_id in resolved_ids 收。
   额外查 corrections、调 resolved_user_evidence_refs,把 correct_extracted 对应 evidence 纳入 allowed。

③ ★ tuning 输出 evidence validator(P0-4,Stage 0 核具体调用点):
   tuning 后处理校验 LLM 返回 evidence 的地方(validate_for_record / anti-hallucination guard),
   现若只接受 fill_missing → 必须同样接 resolved_user_evidence_refs,让 correct_extracted 输出被接受。
   否则「prompt 允许、输出被拒」成孤儿。

④ ask source 表(_user_supplied_parameter_candidates + 相关):
   遍历 plan.parameter_mapping 收 user_supplied 现逻辑不动(纠错 mapping 已 user_supplied、天然进表、document=None);
   additive correction-aware 校验/标注(确保 correct_extracted mapping candidate 被判定器认可、不孤儿);
   resolved_prompt_ids 继续只管 remaining missing prompts、不替换。
```

### H. 状态机

```text
未纠错 --correct(document_extracted)--> 已纠错
    (apply_atomically:INSERT correction[original=现值]; mapping→user_supplied; append correct_extracted evidence; build_steps=None)
已纠错 --correct(同 param_key,可证明)--> 已纠错
    (apply_atomically:UPDATE corrected_*/updated_at; original_* 不变)
已纠错 --undo--> 未纠错
    (undo_atomically:恢复 original_*/source/document; DELETE correction row; 删 correct_extracted evidence; build_steps 仍 None)
任意   --reparse 成功--> 清空所有纠错(C1 级联已落;新 spec/plan 无纠错、无残留 correct_extracted evidence)
任意   --reparse 失败--> 保持(旧 bundle + 纠错原封不动)
```
- **fill_missing 的 user_supplied mapping** 永不进此状态机(correct 端点对它 400 not_correctable)。
- **build_steps 恢复**只经「重新解析(清纠错重生成)」或「522-D 局部重跑(带纠错重生成)」,**服务不按 correction row 数量自动恢复**。

### telemetry 枚举(P2-3,只计数、不记内容)

```text
target_kind ∈ {
  created_document_extracted,   # 首次纠错成功
  updated_existing_correction,  # re-correct 成功
  undo,                         # 撤销成功
  target_not_extracted, target_conflict, target_ambiguous,
  target_stale, target_not_correctable, lock_conflict
}
计数:correction_created_count / undo_count / 按 target_kind 分桶。
★ 绝不把 param_key / paper_param_name / value / unit 塞进 telemetry payload。
```

---

## 验收标准(给出可跑命令;命令以 Stage 0 实测为准)

**后端契约 / 状态**
- [ ] 首次纠错:document_extracted mapping → POST 后 GET /plan 该 mapping value=新值、source=user_supplied;correction row original=原值;GET 清单该条 can_undo=true/reason=active;build_steps=None;响应 wrapper 字段 = paper_id/updated_plan/correction。
- [ ] re-correct 同 param_key:第二次改 → corrected_* 变、**original_* 首次值不变**;correction 行数不增(UPDATE 非 INSERT)。
- [ ] **not_correctable**:对 fill_missing 的 user_supplied mapping POST correction → 400 correction_target_not_correctable、不写任何东西。
- [ ] 撤销:undo → mapping 恢复 original value/unit/source/document;correction row 删、evidence 删;build_steps **仍 None**;undo 对其他 paper 的 correction_id → 404;target 已被 reparse 换掉再 undo → 409 stale。
- [ ] target 三态:名字无 mapping 非冲突 → 400 not_extracted;唯一命中冲突 → 409 requires_local_rerun;同名多行 → 400 ambiguous。
- [ ] stale:reparse 换 plan 或改 index/value echo → POST 409 stale、旧 mapping 不动。
- [ ] **原子(P0-3)**:store 第 2 写入点注入 SQLite fault → rollback,plan/correction/evidence 全不变、无 plan-only/correction-only 半态;**测试断言禁 service 分两次独立 store 调用模拟事务**(核 apply/undo 走单一原子方法)。
- [ ] unit 三态:omitted 保留原 unit / null 清空 / "" → 400 / str trim 写入,各一条断言。
- [ ] 冲突不重算:纠错前后 spec.parameter_table + parameter_conflicts 字节不变。
- [ ] GET /spec、/plan 契约不变:纠错只反映在 plan.parameter_mapping;两端点响应 schema 无新增字段。

**并发(P0-1)**
- [ ] correction 与 reparse 并发:reparse 中 POST correction → 409 correction_lock_conflict、不写;**reparse 行为零变化**(522-B 锁测试仍绿)。
- [ ] correction 与 correction 并发:同 paper 两 correction → 第二 409 correction_lock_conflict。
- [ ] **★ correction 与 user-supply 并发**:同 paper 同刻一个补缺失 + 一个纠错 → **只一个成功、另一个 409**(user-supply 拿不到锁返 409;correction 拿不到锁返 correction_lock_conflict);plan/evidence/correction **无半态、无 lost update**;user-supply 单独跑成功路径回归绿(不受加锁影响)。

**消费方接线(P0-4)**
- [ ] build_steps provenance:含 correct_extracted evidence 的 plan 过校验不 raise;fill_missing 现行为回归绿。
- [ ] tuning **prompt + 输出**:纠错后 tuning suggest 的 allowed 含该 correct_extracted;**LLM 返回指向 correct_extracted 的 evidence 时最终 response 过 validator(不被判无效)**;fill_missing 现行为回归绿。
- [ ] ask:纠错后 ask source 表含该参数(user_supplied、无 document citation);现有 candidate 回归绿。

**前端(无测试框架 → 静态守卫 smoke + 走查 + 截图 桌面+移动)**
- [ ] 参数表 document_extracted 有「改」入口;点击内联编辑;提交调 POST。
- [ ] 纠错后显「你改的」+「AI 原本抽:X」+撤销;不显论文 citation;撤销后回原值 + 原 citation;build_steps 区回退块视图(honest 交代)。
- [ ] **fill_missing 的 user_supplied 参数不显 C2 的「改/AI 原本抽/撤销」**(防 P0-2 回归,专项走查/截图)。
- [ ] stale/lock 错误态可见、可关、可重试;console 干净(不打 filename/error_code/error body/value/unit)。
- [ ] REPARSE_CONFIRM_COPY 含「已纠错的参数值」。
- [ ] 截图覆盖(桌面+移动):入口(改按钮)/ 编辑中 / 纠错后(你改的+原值)/ 撤销后 / 丢 citation / stale 或 lock 错误态 / **fill_missing 无改入口**。
- [ ] pnpm typecheck / lint / build 绿 + 静态守卫 smoke。

**隐私 / 日志**
- [ ] grep 守门:生产代码无 `logger.exception`/`str(exc)`/`repr(exc)`/`exc_info=True`;**纠错 value/unit/param_key/paper_param_name 不进日志·console·HTTP error body**(逐项确认字段命中不在这些位置);store SQL 错误只 log `type(exc).__name__`。
- [ ] telemetry 只计数(target_kind 枚举),grep 确认无参数名/值/单位/param_key 进 telemetry payload。
- [ ] 错误响应 body 逐个错误码核:只 error_code + 稳定文案,无原值/新值/参数名。

**收尾 / schema**
- [ ] `make check` 后端全绿;`make export-schema && make verify-schema` —— **新增 `schemas/paper_parameter_corrections.schema.json` 受控 drift(alias 已进 exporter + Makefile 列表),其余七个既有 schema(evidence/spec/plan/tuning/missing/ask_request/ask_response)对外零 drift**;06 同步。
- [ ] `git diff --check`(行尾/字节,decision 08);`git diff --name-only origin/main` 落点符合(后端 service+route+model+原子 store 方法+锁 wiring(含 user-supply)+四处消费方+telemetry + 前端参数表+REPARSE copy + exporter+新 schema JSON + 06 + 任务卡);任务卡随代码同 PR、索引收尾单独 PR、本代码 PR 不碰 `03_TASK_INDEX.md`。

---

## 风险与注意点(合并前亲核)

- **★ 触已合并 522-B/502 产物(合并前逐处贴 RAW 前后对比)**:①522-B 锁 registry 复用(DI additive、不 rename、不改锁本体、不改 reparse 行为);②**502 user-supply additive 加锁 + 加 409 in-progress 分支**(证明 merge 成功路径逐字不变、只加锁与错误分支);③522-B 前端 `REPARSE_CONFIRM_COPY` 文案改动。三处均 decision 13、合并前逐处核。
- **★ 四处消费方接线**:build_steps provenance / tuning prompt / **tuning 输出 validator** / ask,各贴前后 RAW,证明 fill_missing 现逻辑逐字不变、只加 correct_extracted 一路。
- **★ 新对外契约进 schema**:GET 清单 `ParameterCorrectionModel` 是全新对外结构 → 新增 alias + 文件 + Makefile 列表;schema drift 亲核 RAW 确认是**新增受控**、七个既有 schema 零 drift。本产品线继 C1 之后第二次动对外面,首/关键对外契约变更**必眼过 RAW**、不凭 verify-schema 绿放行。
- **原子红线(P0-3)**:apply/undo 必须经单一 store 事务方法,禁 service 串 CRUD;fault injection 验半态不产生。
- **锁语义(P0-1)**:reparse/correction/undo/user-supply 共用一把 per-paper fail-fast 锁;拿不到锁各返各的 in-progress 码(reparse_in_progress / correction_lock_conflict / user-supply 409);不阻塞等待、不启动第二组写入。
- **fail-closed(P0-5)**:build_steps 置 None 而非留旧值;撤销不自动恢复(honest,UI 交代);不按 correction row 数量在服务里恢复 build_steps。
- **二义防误改(P0-2)**:correctable 硬谓词拦住 fill_missing / 非纠错 user_supplied;前端也按 active corrections 判、fill_missing 不显「改」。
- **overlay 不可变红线**:parameter_table 不改、conflicts 不重算;冲突参数够不到 ③。

---

## Stage 0 可落性 gate(Codex 实现前核 live,不符停手报架构师,禁兜底硬上)

1. `git fetch origin && git rev-parse origin/main` —— 报 HEAD;`git merge-base --is-ancestor <live 2ef7a2d> origin/main` 通过(允许 main 合法前进,用 live 值)。
2. 确认本卡已随代码入 `docs/tasks/`(PM 预放,untracked=预期)。
3. **复核 C1 as-built 仍在**(贴 RAW 定性):PaperEvidenceEntry(Model) 3 可空字段 + invariant validator + `UserEvidenceAction`;`paper_parameter_correction` 表 + CRUD;`resolved_user_evidence_refs`;`CURRENT_SCHEMA_VERSION`=7。
4. **本轮 R6 三实证 live 复核(派单那刻仍成立)**:
   - UpdatedPlanResponse = `{paper_id, updated_plan}` + extra=forbid(POST wrapper/undo 照此)。
   - user-supply merge 无锁无事务、`set_plan` 单事务只写 plan、correction CRUD 各自 commit(⇒ 原子方法 + user-supply 加锁必需)。
   - schema 手工白名单(`OUTPUTS` + Makefile 固定列表)、alias 先例(521-C)/route-local 先例(522-B `PaperReparseResponse`)。
5. **本卡新增高风险落点 gate(核准才动)**:
   - **user-supply 可接同一把锁**:`get_paper_reparse_lock_registry` additive 注入 user-supply merge 路径、fail-fast acquire、拿不到锁映射 409,**不改 merge 成功逻辑、不 rename registry**。若判定无法干净加(如 merge 调用层拿不到 request/DI)→ 停手报架构师(备选:双侧 revision CAS)。
   - **tuning 输出 evidence validator 调用点**:贴 tuning 后处理校验 LLM evidence 的具体函数本体,确认能 additive 接 `resolved_user_evidence_refs`、保留 fill_missing;若不存在独立输出校验(即 prompt 侧已足够)→ 报架构师确认可去掉第③处。
   - **原子 store 方法可落**:`paper_plan_cache` UPSERT + correction 表 INSERT/UPDATE/DELETE 可进同一 `BEGIN/commit`(同连接);贴 `set_plan` 现事务本体确认可扩。
   - **GET 清单 alias 登记点**:`export_paper_schemas.py` 的 `OUTPUTS` + Makefile verify-schema 列表可加一项;贴两处本体。
6. 任一不符 → 停手诊断(decision 15:卡/包写错 vs main 真不对 vs 同步动作漏做)。

---

## 给 Codex 的提示

- 走 feature branch(**git fetch 后从 origin/main 切**,不许 main 直推)。
- **卡随代码同 PR**(本卡 `git add` 进代码 PR);**索引收尾单独 PR**;**本代码 PR 不碰 `03_TASK_INDEX.md`**。
- PR:Codex 给标题 + 正文草稿 + `pull/new` 链接,PM 网页侧建 PR + squash merge。
- `make check` 全管道跑,禁拆 CI step 列;显式加 `make export-schema && make verify-schema` + `pnpm typecheck`/lint/build + smoke。
- 请求 `extra="forbid"`(外 + 内层 target);source/document_id/user_action/correction_id 服务端注入;错误码 body 只回 error_code + 稳定文案,绝不带原值/新值/参数名。
- **apply/undo 走单一原子 store 方法**(禁串 `set_plan`+correction CRUD);evidence append/删在 service 构造 updated_record 时做。
- 锁复用 522-B registry(DI additive、不 rename)、correction/undo/user-supply 三路加锁、各映射各的 in-progress 码。
- 四处消费方 additive 接判定器、保留 fill_missing 逐字不变。
- GET 清单进 schema(alias + 新 JSON + Makefile 列表);POST wrapper/undo route-local。
- 前端截图作**图片附件传进对话**、不收本机路径,覆盖每个关键态(桌面+移动,含 fill_missing 无改入口)。
- **合并前节奏**(后端契约卡 + 前端):前端截图(关键态×桌面移动)+ 后端真测试 + diff 边界逐处核(尤其②user-supply 加锁 + ①522-B registry 复用 + ③REPARSE copy + 四处消费方接线 + 原子方法)+ 隐私红线点亲核(纠错 value/unit/param_key 绝不落日志/console/error body,贴本体不凭勾选)+ 对外受控/零 drift(新 corrections schema RAW 确认受控、七个既有 schema 零 drift)。
- RAW 取证/diff 贴对话、去行号、不收本机路径。

---

**版本**:v0.2(2026-07-02,GPT R1 审卡 + Codex R6 live 核收敛,派 Codex 终版)
**作者**:Claude(架构师)
**前置 commit**:main 必须含 C1 代码 `2ef7a2d`(#162)(Stage 0 用 `git merge-base --is-ancestor` 校验,允许 main 合法前进)
**入库改名**:入 `docs/tasks/task-522-c2-user-correction-behavior-frontend-v0_2.md`
**审批级别**:GPT R1 审卡(4 P0 + P1/P2 收敛)+ Codex R6 live 核(三实证)双通过 → PM 已一句知会(overlay 方向 / build_steps 置 None / REPARSE 补文案 / 前端「你改的」/ **并发安全加固含 user-supply 加锁**)→ 派 Codex Stage 0 → 实现
**后继**:TASK-522-D(局部重跑 · 消解冲突 · 带纠错重生成完整 build_steps),C2 合并后起草
