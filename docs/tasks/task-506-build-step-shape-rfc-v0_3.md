# TASK-506:建模指导结构化 · 目标形状 RFC(指导深度第一张:只定形状,不改代码)

**版本**:v0.3(定稿:R1 + R6 双审通过 + PM 拍板;作为 TASK-507 的绑定规格)
**所属线**:paper-to-model(decision 22 编号 5xx)
**现状断言来源**:实测自 `origin/main`,双审时核于 HEAD `0c5818d`(`8ec54ce → 0c5818d` 仅 TASK-505 索引收尾 docs PR #132,**无 paper 后端改动**;所有现状断言经 R6 逐字核对属实)

---

## 本版改动(v0.1 → v0.2,并审而来)
- **[P0]** 加「步骤文字不得写参数具体值 / 调参倍率 / 最优值」硬规则 + 机检口径(防绕过 TuningSuggestion 锁)。
- **[P0]** `display_text` 改为 **assembler 派生**(非 LLM 自由文本),彻底锁死单一真值源。
- **[P1]** `StepBlockRef` 加步内 `block_ref_id`;`ConnectionHint` 改为引用 ref(不再自由字符串)。
- **[P1]** `block_refs` 越界校验改用 PlanAssembler 生成的推荐项引用键(不只按 block_type)。
- **[P1]** `ParameterMappingRef` 维持复合键(不加 mapping_id),但加「parameter_mapping 复合键唯一」不变量。
- **[P1]** 新增 `ConfigurationHint`,承载「配置求解器 / powergui / 仿真时长」这类步骤。
- **[P1]** `StepBlockRef.paper_reference` 改为可空(不强制,防伪造 evidence)。
- **[P1]** 降级写成「正常 / legacy 两态」+ 结构化半失败 fail-closed 整体置 None;对齐 decision 25 双轴。
- **[P1]** evaluator 规则补全(覆盖度 / 顺序 / 派生一致性 / 双源 / 无参数值泄漏等)。
- **[P2]** HEAD 更新;`build_steps=None` vs `[]` 语义写死;可选 `step_kind`;端口非可执行契约说明。
- schema-sync 真实同步面由 R6 实测列全(替换原「预计」)。

## 本版改动(v0.2 → v0.3,PM 拍板定稿)
- A / B / C / D + 参数值红线五个待拍点 **PM 全部确认**,卡定稿。
- 红线节加澄清:**论文里抓出来、带出处的参数值照常给**(进参数对照表 `parameter_mapping`、步骤旁显示);红线只拦「无出处的瞎编数」和「替用户填缺失参数」,**不是「不准显示数字」**。区分三类数,见红线节。

---

## 状态
✅ 已定稿(设计 / RFC 卡:双审 ✅ + PM 拍板 ✅;TASK-507 据此实现)

## 上下文

PM 定的下一阶段头号方向 = 把 paper-to-model 做到「能真正辅助用户在本机搭出模型」。当前痛点:后端生成的建模步骤(`ModelGenerationPlan.subsystem_breakdown`)是一串纯文字(`list[str]`,如「第 2 步:放置 Synchronous Machine pu Standard,按 parameter_mapping 表逐项填入 12 项参数…」)。给了模块名、讲了拓扑,但**没有结构化的**:模块在库里的路径、这步要填哪些参数、模块间端口怎么接、步与步的依赖。照着搭不出来。

「浅」是**设计使然**——SubsystemPlanner 的 prompt 明确「步骤只讲拓扑、**不准写具体参数数值**、3–10 步」,参数被单列到 `parameter_mapping`。所以加深**不是**「让 AI 多写文字」就能解决——那条路出来的还是机器没法校验、前端没法渲成可勾清单、评测没法量的长文本。

本卡只做一件事:**把「结构化建模步骤」的目标形状定清楚**——字段、粒度、与旧字段的兼容/降级、前端渲染目标(概念级)、evaluator 可测规则。**不改任何代码。** 形状定稿 + PM 拍板后,再起实现卡:后端(TASK-507)、前端(TASK-508)、真实语料评测(TASK-509),分开走。

## 输入(前置依赖)
- 已完成的后端取证(`ModelGenerationPlan` / `PaperPlanService` DAG / prompt,R6 实测 origin/main 0c5818d 属实)。
- **PM 已拍板**:① 步骤粒度 = 子系统 / 功能块级(比接线粗一级,接线不单列步);② 采「并行结构化字段 + 旧字段兜底」路线。
- 不可重开的锁:`TuningSuggestion` 只给方向(枚举 + 物理含义,**不报具体数值 / 倍率**);**不替用户定缺失参数值**;不生成「打开即跑」`.slx`;改对外契约 / 枚举走 schema-sync 全清单(decision 13)+ PM 拍 + R1 审。双源证据 `document_extracted` / `user_supplied` 不得互相伪装(decision 21)。
- 必读:`01` / `02` / `04` / `06`(§12.5 ModelGenerationPlan)/ `05` / decision 13 / 21 / 22 / 25。

## 输出(交付物)
本卡产物 = 一份经双审 + PM 拍板的**目标形状定义**(本文档 v0.3 定稿即终稿,作为 TASK-507 的绑定规格)。**不产出任何代码改动。**

## 待 PM 拍板点 — **已全部 PM 确认(2026-06-28)**
- **A. 字段名 `build_steps`** — R1 + R6 均认;**PM ✅**。
- **B. `library_path` 可空 + 缺时显示「库路径待确认」(非错误)** — R1 + R6 均认;不强制必填(否则诱导 LLM 编库路径);**PM ✅**。
- **C. 本轮不加 `mapping_id`,用复合键** — R1 + R6 均认;**附加硬不变量**:`parameter_mapping` 的 `(paper_param_name, model_param_name)` 必须唯一;**PM ✅**。
- **D. 步骤粒度 = 子系统 / 功能块级** — PM 拍板;R1 + R6 均认;TASK-509 用真实论文复核手感;**PM ✅**。
- **★ 参数值红线(P0,见下「红线」节)** — **PM ✅**(已澄清:论文带出处的值照常给,只拦瞎编/替填)。

## 红线:步骤不得成为参数值 / 调参的后门(P0)

**先分清三类「数字」(防误读:红线 ≠ 不准显示数字)**:
1. **论文里给了、有出处的参数值**(如定子电阻 0.05Ω,来自论文式 3):**照常给、照常显示**。这类值进 `parameter_mapping`(参数对照表,TASK-504 已渲染),步骤经 `parameter_refs` 指过去,前端在该步旁把值连出处显示。**红线不拦这类。**
2. **论文没给、要用户补的参数值**:**不让 AI 瞎编**,引导用户自己填(沿用现有 `"null"` sentinel + MissingParameterPrompt)。
3. **调参方向**:只给方向,不给具体数 / 倍率(`TuningSuggestion` 锁,独立约束)。

红线真正管的是 **2 与 3**:AI 不准在步骤说明里随口敲一个**没出处**的数,也不准替用户编缺的那个值;`TuningSuggestion` 不被「步骤更细」绕开。具体值只有一处真源(`parameter_mapping`,带出处),步骤文字不重抄,机器还能查出处真假。

**硬规则**:
- 步骤文字字段(`title` / `intent` / `block_refs[*].purpose` / `connection_hints[*].signal_meaning` / `configuration_hints[*].instruction` / `display_text`)**不得直接写模型参数的具体值 / 调参倍率 / 最优值 / 「推荐设为 N」**。
- 模型参数的值**只能**通过 `parameter_refs` 指向 `parameter_mapping`(带出处)来展示,不重复抄进步骤文字。
- **机检(保守版,TASK-507 + TASK-509 实现)**:
  1. 对 `parameter_mapping` 中 `value != "null"` 的项,若其「参数名 + 值」在步骤文字邻近出现 → fail;
  2. 步骤文字禁止「增大 / 减小 N% / N 倍 / 最优 / 推荐设为 N」这类调参数值 / 倍率表述。
- **例外**:求解器类型、仿真时长(stop time)、powergui 模式等**搭建设置**属 `configuration_hints`,不受本规则约束(它们不是待调的模型参数);但同样不得伪造来源。

## 范围(本卡必须定清楚的)

### 1. 结构化步骤目标形状(提案见「接口契约」)
**additive**:**保留** `subsystem_breakdown: list[str]`,**新增** `build_steps: list[ModelBuildStep] | None`(domain + Pydantic **双默认 None**)。不替换、不删旧字段。

### 2. 步骤粒度(PM 已拍板)
一步 = 完成一个**功能单元 / 子系统级**动作(例:「搭同步电机本体」「接入三相测量与短路」「配置求解器」)。步内用 `block_refs` 列模块、`connection_hints` 描述怎么连、`configuration_hints` 描述配置。**不**细到每模块一步,**更不**细到每根线一步。

### 3. 兼容 + 降级(两态,fail-closed)
- **正常路径**:结构化源 → `build_steps`(校验全过)→ `subsystem_breakdown` 由 `build_steps[*].display_text` 派生。
- **降级路径**:结构化生成 / 校验失败 → `build_steps = None` → 走 **legacy 文本生成**得 `subsystem_breakdown`(保留旧 SubsystemPlanner 风格路径作为 fallback 源,**不是**从失败的结构化输出硬挤)。
- **fail-closed**:任一 step 校验失败 → **整个 `build_steps` 丢为 None**,不返回半截 list。
- `build_steps = None`:结构化失败 / 降级(唯一含义);`build_steps = []`:**非法**(除非未来明确允许「无步骤计划」)。
- **decision 25 对齐**:结构化规则失败 = `execution_status = succeeded + verdict = fail / partial`(**不伪装 pass**);只有 IO / 序列化 / provider / fixture 损坏等真异常才是 `case_failed + not_evaluated`。
- 旧前端不读 `build_steps`,行为不变。

### 4. 前端渲染目标(概念级)
- 把 `build_steps` 渲成「照着一步步勾」的清单:每步显示 标题 / 意图 / 涉及模块(含库路径或「待确认」)/ 关联参数(指向参数表)/ 接线提示 / 配置提示 / 证据 badge。
- **本卡不画视觉、不定组件 / token**;视觉实现是 TASK-508,且 **TASK-508 必须先取证现有皮(砼核风)+ 复用组件再做**(504-③ 教训)。
- 证据 badge **只挂在真有 evidence 的地方**(`step.evidence` / `parameter_refs` 指向项),忠实反映 `document_extracted` / `user_supplied` 双源,**不伪造、不引入第三源**;`library_path` 等无证据字段**不打 document_extracted badge**(`library_path` 为空时显示「库路径待确认」,不显示成失败)。
- 可选 `step_kind`(见接口契约)用于前端按类型展示,枚举面最终可留 TASK-508 定。

### 5. evaluator 可测规则(供 TASK-509)
1. `step_id` 唯一 + 格式稳定(如 `STEP-001`)。
2. **顺序**:`build_steps` 数组顺序即默认展示 / 执行顺序;`depends_on` **只能引用数组中前序 step 的 step_id**(因而天然无环);生成时不满足则实现端先拓扑排序再输出。
3. `parameter_mapping` 复合键 `(paper_param_name, model_param_name)` 唯一;`parameter_refs` 必须**恰好命中一项**(0 命中或多命中 = fail)。
4. `connection_hints` 的 `from_block_ref` / `to_block_ref` 必须指向**本 step 或其依赖 step 中已声明的 `block_ref_id`**(不许自由字符串)。
5. `block_refs` 必须命中某个 `block_recommendations` 项(按 PlanAssembler 生成的稳定引用键,如 `BR-001`,复合自 `(block_type, purpose, paper_reference locator)`),不引用推荐之外的 block。
6. **每步必须至少有一个可操作结构字段非空**(`block_refs` / `connection_hints` / `parameter_refs` / `configuration_hints` 之一);**`intent` 不算**(它必填,永远满足 = 无效门)。
7. **步骤文字不得泄漏参数值 / 调参倍率**(见「红线」节机检)。
8. `evidence` 满足 `PaperEvidenceEntry` 双源不变量;`document_extracted` 的 locator 必须存在于 `PaperSpec`;`user_supplied` 必须关联真实 resolved prompt(不只看 `source` 字面)。
9. `library_path` 非空时仅作 hint(不作可执行保证);为空时前端 fallback「待确认」。
10. **派生一致性**:`subsystem_breakdown == [s.display_text for s in build_steps]`,且 `display_text` 不引入结构字段之外的新 block / 参数 / 值 / evidence。
11. **覆盖度**:每个关键 `block_recommendations` 至少被某个 build step 覆盖,否则须有明确原因(防「推荐了 block 但步骤漏掉」)。

### 6. schema-sync 真实同步面(R6 实测,供实现卡 TASK-507)
实现卡走 **decision 13 全清单**。R6 实测至少需同步:
`core/domain/paper_plan.py`、`features/paper/paper_schemas.py`、`features/paper/paper_plan_service.py`、`features/paper/paper_plan_helpers.py`、`features/paper/_prompt_builder.py`、`core/prompts/paper_plan_subsystem.yaml`、`docs/06_OUTPUT_CONTRACTS.md` §12.5、`schemas/paper_plan.schema.json`(由 `scripts/export_paper_schemas.py` 生成)、`tests/features/paper/test_paper_schemas_freeze.py`、`tests/features/paper/test_paper_schemas_sample_roundtrip.py`、`tests/features/paper/test_paper_plan_service.py` / `test_paper_plan_helpers.py` / `test_paper_plan_prompts.py`、`eval/cases/paper_to_model/.../expected_model_generation_plan.json`、`eval/cases/paper_to_model/.../expected_updated_plan.json`、`web/src/lib/paperTypes.ts`。
另视范围可能碰 `tests/api/test_paper_*.py`、`tests/adapters/storage/test_sqlite_paper_cache.py`、`tests/core/test_paper_cache_contracts.py`。**注意**:`build_steps` 即便默认 None,`model_dump(mode="json")` 会吐 `"build_steps": null`,sample roundtrip / golden JSON 全等测试会断,须同步 golden 或定序列化策略。

## 不做(明确排除)
- ❌ 不改任何代码(domain / prompt / 前端 / eval 一律不动)——本卡是设计门。
- ❌ 不实现 `build_steps` 生成逻辑(TASK-507)、不做前端渲染(TASK-508)、不写 eval(TASK-509)。
- ❌ 不碰追问(单独卡);不碰多文件 / `PaperSpec` / `PaperEvidenceEntry` provenance(押后;本卡只动 `ModelGenerationPlan` 一侧)。
- ❌ 本轮不给 `ParameterMapping` / `BlockRecommendation` 加正式 ID(用复合键 / assembler 生成的临时引用键)。
- ❌ 步骤里不重复写参数值;`TuningSuggestion` 仍只给方向,不被「步骤更细」绕开(见红线)。
- ❌ 不细到每根接线单列一步。

## 接口契约(PROPOSED — 待 PM 拍板;批准后由 TASK-507 实现并走 schema-sync 全清单)

**现状**(实测 origin/main 0c5818d,`core/domain/paper_plan.py`):
```python
@dataclass(frozen=True)
class ModelGenerationPlan:
    plan_id: str
    paper_spec_id: str
    library_choice: str
    block_recommendations: list[BlockRecommendation]
    parameter_mapping: list[ParameterMapping]
    subsystem_breakdown: list[str]          # ← 当前:纯文字步骤
    m_script_skeleton: str | None
    evidence: list[PaperEvidenceEntry]
```

**拟新增(additive,v0.2 形状)**:
```python
@dataclass(frozen=True)
class StepBlockRef:
    block_ref_id: str                       # step 内唯一,如 "B1";connection_hints 据此引用
    block_type: str
    library_path: str | None                # 库路径 hint;未知为 None(待拍点 B)
    purpose: str
    paper_reference: PaperEvidenceEntry | None   # 可空:库选型/工程常识可无论文证据,不强制(防伪造)

@dataclass(frozen=True)
class ParameterMappingRef:
    paper_param_name: str                   # 复合键引用 parameter_mapping(本轮不加 mapping_id)
    model_param_name: str

@dataclass(frozen=True)
class ConnectionHint:
    from_block_ref: str                     # 指向本 step 或依赖 step 的 block_ref_id
    from_port: str | None                   # 人类搭建提示,非可执行 Simulink 端口契约
    to_block_ref: str
    to_port: str | None
    signal_meaning: str | None

@dataclass(frozen=True)
class ConfigurationHint:                    # 承载「配置求解器/powergui/仿真时长」类步骤
    target: str                             # e.g. "solver" / "powergui" / "simulation"
    setting_name: str | None
    instruction: str                        # 设置类指示;受红线约束(不写模型参数值)
    evidence: list[PaperEvidenceEntry]

@dataclass(frozen=True)
class ModelBuildStep:
    step_id: str                            # 稳定格式,如 "STEP-001"
    title: str
    intent: str
    block_refs: list[StepBlockRef]
    parameter_refs: list[ParameterMappingRef]
    connection_hints: list[ConnectionHint]
    configuration_hints: list[ConfigurationHint]
    depends_on: list[str]                   # 只引用前序 step_id
    evidence: list[PaperEvidenceEntry]
    display_text: str                       # ★ 由 assembler 从结构字段派生,非 LLM 自由文本

# 可选(枚举面可留 TASK-508 定):
#   step_kind: Literal["place_blocks","connect_blocks","configure","verify","other"]

# ModelGenerationPlan 追加一个字段(旧字段全部保留不动):
#   build_steps: list[ModelBuildStep] | None   # 双默认 None;新前端首选;生成/校验失败时 None
```

## 验收标准(本 RFC 卡 = 设计门;验收 = 形状定清楚、问题答完、可据此起实现卡)
- [ ] 结构化步骤字段集 v0.2 定稿(含 `block_ref_id` / `ConfigurationHint` / `paper_reference` 可空 / `display_text` 派生)。
- [ ] 红线机检口径定稿(参数值 / 倍率不入步骤文字)。
- [ ] 步骤粒度定稿。
- [ ] 兼容 + 降级两态 + fail-closed + decision 25 对齐定稿。
- [ ] 前端渲染目标定稿(概念级;写明 TASK-508 先取证现有皮 + badge 不伪造)。
- [ ] evaluator 11 条规则定稿。
- [ ] A / B / C / D + 红线 五个待拍点有 PM 结论。
- [ ] schema-sync 真实同步面列全(R6 已实测)。
- 本卡不改代码,故无「单测全绿」一项。

## 风险与注意点
- **参数值后门(P0)**:见红线节;evaluator 机检兜底,不靠 LLM 自觉。
- **三套真值源漂移**:`display_text` 由 assembler 派生(非 LLM);`subsystem_breakdown` 由 `display_text` 派生;结构字段是唯一真值源。
- **引用键歧义**:`block_ref_id`(步内)+ assembler 生成的 `BR-xxx`(推荐项)+ `parameter_mapping` 复合键唯一,三者支撑机检。
- **配置类步骤**:`ConfigurationHint` 承载;evaluator「每步至少一可操作结构字段」排除 `intent`。
- **降级语义**:None=失败/降级、[]=非法;半失败 fail-closed。
- **evidence 伪造**:badge 只挂真 evidence;`paper_reference` 可空;不为 UI badge 逼出假证据。
- **504-③**:前端实现卡(TASK-508)先取证现有皮,本 RFC 不画视觉。
- **与多文件交叉**:① 主要动 `ModelGenerationPlan`,③ 主要动 `PaperSpec` / `PaperEvidenceEntry`;先把 ① 的 step 引用模型定稳。
- **feature boundary(decision 21)**:实现卡保持 paper feature 独立,**不 import** overview / explanation 私有结构;跨 feature 共享只走 core / 公开契约。
- **DAG 改动点(供 TASK-507)**:生成链是 4 路 LLM(PlanComposer / MScriptDrafter / MissingDetector / SubsystemPlanner)+ PlanAssembler;结构化步骤改 SubsystemPlanner 输出 schema + PlanAssembler 校验 + 派生旧字段 + 保留 legacy fallback 源;`EvidenceTagger`/`validate_for_spec` 须把新增 step evidence + step block paper_reference 一并送检,否则双源漏检。`PaperPlanService` docstring「three-role」与实际 4 calls 不符,TASK-507 顺手改。

## 估时
设计 / RFC 卡,成本在双审 + PM 拍板,无编码。

## TASK-507 拆分(R6 建议,架构师采纳)
- **507-A**:contract / Pydantic schema / JSON schema / freeze / fixtures / 向后兼容(`build_steps=None` 默认 + 序列化策略 + golden 同步)。
- **507-B**:SubsystemPlanner prompt 改结构化输出 + PlanAssembler 校验(11 条规则)+ 降级 fallback + `display_text` 派生。
- 两张均走 decision 13 全清单 + PM 拍 + R1 审,R6 实测同步面。
