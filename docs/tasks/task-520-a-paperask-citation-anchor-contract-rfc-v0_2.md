# TASK-520-A:Paper 追问 · Citation / Anchor 契约 RFC(只定接口语言,不写实现)

**版本**:v0.2(已并 R1 + R6 双审 P0 + RFC 级 P1;**条件通过 → 定稿**,可据此起 Card 1/2;实施层 P1/P2 落各后续卡验收)
**所属线**:paper-to-model · 追问子线(decision 22:追问 / 多文件 = 520+)
**前置**:追问功能 PM 拍板(B 版精确跳转 / 公式区做 / 图索引这次不做走「丙」/ stateless / 给朋友用要能见人 / §6 接 Makefile)
**现状基线**:R6 实测 origin/main HEAD `6ed4574`;**派单后(若有实现部分)Codex Stage 0 复核最新 HEAD,用 live 值**

---

## 本版改动(v0.1 → v0.2,并审而来)

**[P0]**(R1 + R6 一致):
1. **§1 铁律 3 与 §5.2 打架修正**:后端 target 语义不存在 → **fallback**(不下发伪 citation);前端 DOM 无锚 → **不可点 badge**(不 fallback、不死链)。两层、两种处理,边界写清(见 §1 / §5.2 / §5.3)。
2. **`SectionTarget.paper_section_id` 语义混用修正**:`paper_section_id` 在仓库已是「论文原文小节 id」语义,不能当「结果页 UI 区块」DOM target。改为 `result_section: Literal[五个区块]`;论文小节 locator 若需展示放 citation `label`,不进 DOM target(见 §3)。
3. **figure-only / unsupported-only 证据缺失败裁决补齐**:若支撑答案的证据只有 figure / 不可引用的 build_step / subsystem,无法映射到合法 Section/Equation/Parameter target → 该 evidence 不进 citations;若因此无任何合法 citation → 整体 fallback(见 §5.4 / §5.1)。
4. **§6.6 开放措辞删除**:§6 已 PM 拍「接进 Makefile drift 闸」,删掉「或手动跑 / 请双审给意见」旧措辞,改为强制项(见 §6)。

**[P0]**(R6 实测):
5. **`Confidence` 命名纠正**:paper 侧无 `Confidence` 枚举;实测 paper 用 `ConfidenceValue = Literal["high","medium","low"]`(`core/domain/paper_tuning.py`),chat 的 `Confidence` 是 feature 私有、**不得 import**(decision 21)。PaperAsk **复用 core 的 `ConfidenceValue`**,或在 `paper_ask.py` 定本地 alias(见 §2)。
6. **`EquationTarget` 依赖标注**:实测结果页当前未渲染 `spec.equations`,无公式锚。`EquationTarget` 是 **Card 1(B1)新建公式区 + `paper-eq-*` 锚之后才有的能力**;Card 2 不得假设现有 DOM 已有公式锚(见 §3 / §4 / §8)。

**[P1]**(并入 RFC 主契约,防 Card 2 实现漂移):
7. **response 级不变量**(§2):`is_fallback=true` ⇒ `confidence=="low"` + `citations==[]` + `fallback_reason!=None`;`is_fallback=false` ⇒ `len(citations)>=1` + `fallback_reason==None`(**「非降级必须至少 1 条合法 citation」显式写死**,否则绕开「带出处回答」产品约束)。
8. **`session_id` 规则**(§2):request 可空;response 必填 = `request.session_id or 新生成`;v0 仅作前端 / 日志相关性,**不据此读历史**。
9. **`source_kind` × `excerpt` 交叉校验**(§2):`document_extracted` ⇒ `excerpt` 1..300;`user_supplied` ⇒ `excerpt is None`(防用户补充带文档摘录、伪装文档证据)。
10. **anchor alias 降级为 MAY**(§4):Card 1 **不得**用 name/symbol fuzzy 或名字相等创建 alias;默认每个可见行只注册自身 origin target;只有输入数据显式提供一一对应才允许多 alias。
11. **`fallback_reason` 改名**(§5.6):`no_relevant_source` → `insufficient_evidence`(覆盖「完全无 source / 相关性过低 / 只有不可引用证据」三种),不新增过多 reason。
12. **参数 target 范围约束**(§3):`row_index` `ge=0`,后端校验 `< len(plan.parameter_mapping)`;`prompt_id` 必须存在于当前 `missing_prompts`。
13. **`source_id` 生命周期**(§2):明确为「单次响应内临时 ID」,前端**不得跨请求缓存**它做跳转依据(跳转靠 `target` 语义,不靠 source_id)。

**[P2]**(记入对应后续卡验收,RFC 不展开):citation 后端按 source_id 去重保序;前端 unresolved badge 文案固定(不让各组件自由写);highlight 带键盘 focus 语义、不只变色;Card 4 截图矩阵 +3(figure 提及不可点 / DOM unresolved badge / user_supplied badge);日志只记 `fallback_reason` / citation count / unresolved anchor count,不记 answer / excerpt / 问题全文。

---

## 这张卡是什么 / 不是什么

- **是**:跨前后端的**契约 RFC**。把「AI 回答里的出处(citation)指向什么、后端怎么给、前端怎么对到页面 DOM」这套接口语言定死。产出 = 一份定稿契约(domain dataclass + Pydantic wrapper 形状 + TS 类型 + schema 同步面 + 失败语义),后面 4(5)张卡都以本卡为准。
- **不是**:不实现后端 ask 端点、不渲染前端、不做 source_table 构造逻辑、不做 anchor registry。本卡只冻结契约面;若需落最小 domain/DTO 骨架(类型声明 + schema),也**不接任何行为**。

为什么单独成卡(R1 + R6 一致):核心风险不是「聊天框」,是 **AI citation → 可验证语义 target → 前端真实可跳 DOM** 三层真值源对齐。不先定死,后端会按自己想象造一种 citation、前端又造另一套 anchor id,B 版「精确跳转」就变成点了跳空的死链。

---

## 状态

✅ 契约定稿(双审条件通过,P0 + RFC 级 P1 已并)→ 可据此起 Card 1(B1)+ Card 2(C),B1/B2/C 可并行起,联调等 B2

## 上下文 / 已锁口径(PM 已拍,本卡不重开)

- **追问 = 整份解析结果都能就地问**(不只建模步骤);AI 带出处答;**出处可点击,精确跳到结果页对应的那条公式 / 那行参数并高亮**(B 版)。
- **v0 stateless**:不建向量库、不存对话历史、现读现构上下文;后端 DTO **留挂存储位**(以后想存不返工);UI **不暗示多轮记忆**。
- **参数值红线**:回答不替用户编论文没给的值;论文有出处的值可显;调参只给方向。
- **injection 防御照 MCS 语义**(不复用 MCS / paper 现有 prompt builder 实现):上下文是数据不是指令 + 截断;用户补充 / 问题文本同按 data 处理。
- **来源双源不变量**(decision 21 同源):`document_extracted` 必有 locator + excerpt;`user_supplied` 必须无 paper locator 且关联 `missing_param_prompt_id`;回答 citation **不得把用户补充伪装成文档证据**。
- **复用**:GlassCard / SourceBadge;仿 TuningPanel 输入框(不用 chat Tailwind footer);砼核风视觉皮(#2c2c2c / 信号橙 #e85d3a / IBM Plex + 思源黑 / border-radius:0 / 半透玻璃);不新造 token。`formatEvidence` 现为两份局部函数(BuildSteps / ParameterTable),**Card 1 先抽公共 paper helper 再复用**。
- **§6 已拍:把 paper schemas 接进 `Makefile export-schema/verify-schema` drift 闸**(不再是开放问题)。
- **标准**:给朋友用、要能见人可靠——失败态都要兜住且体面、都要截图验收(失败态清单见 §5)。
- **feature 边界(decision 21)**:PaperAsk 放 `features/paper/`,跨层只走 `core/` 公开契约,**不 import** overview / explanation / chat 私有结构。

## 不在本卡(明确排除)

- ❌ 不实现 ask 端点 / source_table 构造 / LLM 调用 / 校验逻辑(Card 2/C)。
- ❌ 不建公式区 / 参数行锚 / AnchorRegistry / scroll-highlight 机制(Card 1/B1+B2)。
- ❌ 不做前端问答 UI / citation wiring(Card D)。
- ❌ 不做 hardening / 截图矩阵(Card E)。
- ❌ **不做图索引、不定 figure 可跳 target**(走「丙」;figure 出处按 §5.4 非可跳处理)。
- ❌ 不补解析器抓图(独立卡,交接待办)。
- ❌ 不碰追问外的 PaperSpec / Plan 生成链 / 现有渲染产物语义。

---

## §1 三层真值源(本卡最核心的约定)

```
  AI 输出            后端 source table            前端 AnchorRegistry
 (受约束)            (citation 真值源)             (DOM 真值源)
┌──────────┐       ┌─────────────────┐         ┌──────────────────┐
│ 只输出    │  ──►  │ 编号 S1..Sn       │  ──►   │ 按 PaperCitation  │
│ citation │       │ 校验 + 展开为      │  序列化 │ Target 解析 DOM   │
│ _ids     │       │ PaperCitation     │  下发   │ id;解析不到 →     │
│ ["S1"]   │       │ Target            │         │ 不渲染可点链接     │
└──────────┘       └─────────────────┘         └──────────────────┘
```

铁律(三条,贯穿所有追问卡):
1. **citation 真值源在后端 source_table,不在 LLM 输出。** LLM 只能引后端编的 `source_id`,**不准自造 anchor / locator / DOM id**。
2. **anchor(DOM)真值源在前端 AnchorRegistry,不在 LLM、也不在后端。** 后端给的是**语义 target**(指向哪条公式 / 哪行参数),前端负责把语义 target 解析成当前页面的 DOM id。
3. **可点击是能力,不是承诺。两阶段、两种处理(v0.2 P0 修正)**:
   - **后端阶段**:`source_id` 无效、或 target 语义不存在于当前 spec/plan → **整体 fallback,不下发伪 citation**(见 §5.1 / §5.2)。
   - **前端阶段**:target 语义合法,但当前页面无对应 DOM anchor → **来源 badge 渲染为不可点,不 fallback、不死链**(见 §5.3)。

职责切分(R6 确认,不可混):**后端校验「语义 target 存在于 spec/plan」;前端校验「该 target 当前有没有 DOM anchor」。后端不碰 DOM、不知道 React 渲染细节。**

---

## §2 PaperAsk 对外 DTO(契约定稿 — Card 2/C 实现)

> 落位(R6 实测,符合现有 paper 惯例):core 纯 dataclass/typing 落 `core/domain/paper_ask.py`;Pydantic wrapper 落 `features/paper/paper_ask_schemas.py`;route request/response 可在 `api/routes`,**schema 导出指向 feature wrapper**。

```python
# 置信度:复用 core 的 ConfidenceValue(v0.2 P0;不得 import chat 私有 Confidence)
ConfidenceValue = Literal["high", "medium", "low"]   # 已存在于 core/domain/paper_tuning.py

# 请求
@dataclass(frozen=True)
class PaperAskRequest:
    question: str                 # wrapper: min_length=1, max_length=1000
    session_id: str | None        # v0 仅回显;stateless,不据此读历史(留挂存储位)

# 响应(整体形状对齐 MCS ChatResponse 语义,但 citations 指向 paper,不复用 SourceRefDTO)
@dataclass(frozen=True)
class PaperAskResponse:
    session_id: str               # = request.session_id or 新生成(v0.2 P1)
    message_id: str
    answer: str                   # wrapper: min_length=1, max_length=3000(建议)
    confidence: ConfidenceValue
    citations: list[PaperAskCitation]
    follow_up_suggestions: list[str]   # wrapper: max_length=3;item 1..100
    is_fallback: bool                  # 默认 False
    fallback_reason: PaperAskFallbackReason | None

@dataclass(frozen=True)
class PaperAskCitation:
    source_id: str                # 后端编的 S1..Sn;单次响应内临时 ID(v0.2 P1:前端不得跨请求缓存)
    label: str                    # 人类可读来源标签,如「式(4)」「参数 Kp」「论文摘要」
    excerpt: str | None           # document_extracted ⇒ 1..300;user_supplied ⇒ None(v0.2 P1 交叉校验)
    source_kind: EvidenceSource   # document_extracted / user_supplied —— 决定 badge,不得伪装
    target: PaperCitationTarget   # 语义 target,前端据此解析 DOM(见 §3)
```

**response 级不变量(v0.2 P1,wrapper / 服务端双重保证)**:
```python
if is_fallback:
    assert confidence == "low"
    assert citations == []
    assert fallback_reason is not None
else:
    assert len(citations) >= 1          # 非降级回答必须至少 1 条合法 citation
    assert fallback_reason is None
```

**约束**:所有 wrapper 子模型 `extra="forbid"`(防塞非契约字段绕红线 / 造第三真值源,沿用 507-A 惯例)。

---

## §3 PaperCitationTarget(语义 target — figure 按「丙」剔除;参数靠 origin+index)

target 是**语义**指向,不是 DOM id。前端 AnchorRegistry 拿 target 去解析当前页面真实 DOM。

```python
PaperCitationTarget = (
    SectionTarget | EquationTarget | ParameterTarget
)

@dataclass(frozen=True)
class SectionTarget:
    kind: Literal["section"]
    # v0.2 P0:专用 UI 区块枚举,不复用论文小节语义的 paper_section_id
    result_section: Literal[
        "paper-summary",
        "paper-subsystems",
        "paper-build-steps",
        "paper-parameters",
        "paper-tuning",
    ]

@dataclass(frozen=True)
class EquationTarget:
    kind: Literal["equation"]
    equation_id: str              # 对应 Card 1(B1)新建公式区某条公式
                                  # v0.2 P0:依赖 B1 公式区 + paper-eq-* 锚;Card 2 不得假设现有 DOM 已有公式锚

# 参数 target 分两 origin(实测:可见行只有 plan_mapping + missing_prompt 两类)
ParameterTarget = (
    PlanMappingParameterTarget | MissingPromptParameterTarget
)

@dataclass(frozen=True)
class PlanMappingParameterTarget:
    kind: Literal["parameter"]
    origin: Literal["plan_mapping"]
    row_index: int                # ge=0;后端校验 < len(plan.parameter_mapping)(v0.2 P1)
    paper_param_name: str         # 仅供 label / 诊断,不作匹配键
    model_param_name: str

@dataclass(frozen=True)
class MissingPromptParameterTarget:
    kind: Literal["parameter"]
    origin: Literal["missing_prompt"]
    prompt_id: str                # 必须存在于当前 missing_prompts(v0.2 P1);格式 MISS-{index:03d}
    parameter_name: str           # 仅供 label / 诊断
```

**关键裁决(写死)**:
- **不含 `figure` target**(走「丙」;figure 出处按 §5.4 非可跳)。
- **不含 `spec_parameter` origin**(实测:`spec.parameter_table` 当前不在可见表)。
- **不含 `build_step` / `subsystem` 可跳 target**:build step 仅标题 index 型 id、subsystem 无 DOM id;AI 若引到它们,按 §5.4 / §5.5 降级为 section 级或不可点(Card 1 不为它们新建细粒度锚)。
- 参数定位**唯一键 = `origin + row_index`(plan_mapping)或 `origin + prompt_id`(missing_prompt)**;`paper_param_name` / `symbol` **只作 label 和诊断,绝不作匹配键**(论文重复参数名 H/K/R/L 必出现,靠名字会对错)。
- **user_supplied 参数**:后端**直接给 `PlanMappingParameterTarget`(带 row_index)**,不让前端用 prompt_id 推(实测:前端拿不到 `missing_bindings`);`source_kind` 仍为 `user_supplied`,badge 显「用户补充」。

---

## §4 锚点 id 生成约定(Card 1/B1 落地,本卡定形状)

DOM id 是**前端实现细节、非业务真值**(业务真值是 §3 target)。约定 id 形状供 Card 1 与 smoke 守门一致:

```
section:           (沿用现有)paper-summary / paper-subsystems / paper-build-steps / paper-parameters / paper-tuning
equation:          paper-eq-{equation_id}              (B1 新建公式区后才有)
plan_mapping 参数:  paper-param-map-{row_index}-{hash(paper_param_name|model_param_name)}
missing_prompt 参数: paper-param-missing-{prompt_id}
```

- `hash` **仅用于 DOM id 字符安全 / 去重**(中英文别名、特殊字符),**不是业务键**;解析仍靠 §3 target 的 `origin + row_index/prompt_id`。
- **alias 降级为 MAY(v0.2 P1)**:AnchorRegistry **可**支持 alias,但 Card 1 **不得**用 name/symbol fuzzy 或名字相等创建 alias。本版默认每个可见行只注册自身 origin target(plan_mapping 行注册 `PlanMappingParameterTarget`;remaining missing prompt 行注册 `MissingPromptParameterTarget`);只有前端输入数据显式提供一一对应关系时才允许注册多 alias。
- **无锚不跳空**:registry 解析失败返回 `null`,调用方**不得**直接 `location.hash = id` 或 `scrollIntoView` 一个不存在的元素。

---

## §5 失败语义裁决(本卡定死,Card C/D/E 据此实现)

### 5.1 AI 引了不存在的 source_id —— 裁决:**fallback,不 raise**

实测:MCS 是 `raise unknown_citation_id`(硬错)。**PaperAsk 改用 fallback**——面向最终用户的就地问答,硬错会把整次回答崩成 500,降级成「这次没能给出可靠依据」更体面、更符合「给朋友用要能见人」。**这是裁决,不照搬 MCS 实现。**
- LLM 输出 unknown citation_id → **整体 fallback**(`is_fallback=true` + `confidence=low` + `citations=[]`),`fallback_reason="invalid_or_missing_citations"`。**不**做「剔除坏 id 后续答」(半真半假引用更危险)。
- LLM 输出空 citations → fallback,同上 reason。
- LLM 输出 raw locator / raw anchor(违反「只准给 source_id」)→ 视为 invalid → fallback。

### 5.2 citation target 语义不在当前 spec/plan —— 裁决:**后端 fallback**(v0.2 P0 边界)

后端展开 source_id → target 时,若 target 指的公式 / 参数行已不在当前 spec/plan(数据漂移)→ 整体 fallback,`fallback_reason="citation_target_unresolved"`。**这是后端阶段,fallback;区别于 5.3 前端阶段的不可点。**

### 5.3 前端 DOM 解析不到 target —— 裁决:**降级为不可点 badge,不 fallback、不死链**(v0.2 P0 边界)

后端 target 合法,但前端当前页面没渲染该 DOM(版本落后 / 条件渲染 / 数组空 / 公式区未建 / helper 漂移)→ citation **仍展示为来源 badge,但不渲染成 `<a>` 可点链接**;附固定弱提示(P2:文案统一,不让各组件自由写)。**这是 200 正常响应,不是 fallback。绝不渲染点了跳空的死链;绝不用 fuzzy「猜最近似行」自动跳转**(最多日志诊断,不作用户可见行为)。

### 5.4 figure-only / unsupported-only 证据 —— 裁决:**不可引用;若无其它合法 citation 则 fallback**(v0.2 P0 补齐)

本版无图索引、无 figure target。
- 若支撑答案的证据**只有** figure / 不可引用的 build_step / subsystem,无法映射到合法 Section/Equation/Parameter target → 该 evidence **不进 citations**;若因此**没有任何合法 citation** → 整体 fallback,`fallback_reason="insufficient_evidence"`。
- 若答案有合法 section/equation/parameter citation 支撑核心结论,正文顺带提到「论文图 2」→ 可正常回答,figure **只落 answer 正文文字、不变成可点 citation**。

### 5.5 section-only 出处 —— 裁决:**有锚跳 section,无锚不可点**

`SectionTarget` 命中结果页五区块之一 → 跳该区块;若该区块语义无对应 DOM → 不可点 badge。**不假装跳到公式或参数。** AI 若引到 build_step / subsystem,降级为对应 `SectionTarget`(paper-build-steps / paper-subsystems)或不可点。

### 5.6 fallback_reason 枚举(v0.2 P1 改名)

```python
PaperAskFallbackReason = Literal[
    "insufficient_evidence",         # 无相关合法证据 / 相关性过低 / 只有本版不可引用证据(原 no_relevant_source)
    "invalid_or_missing_citations",  # AI 引空 / unknown id / raw anchor(5.1)
    "citation_target_unresolved",    # target 语义不在当前 spec/plan(5.2)
    "out_of_scope",                  # 问题超出本资料范围
]
```
fallback 时文案口径:平实说明「这份资料里没看到相关依据 / 当前解析结果里没找到能支撑的出处」,**不编、不暗示有但没找到**。

### 5.7 端到端失败态 / 错误码矩阵(Card E 验收基线)

| 场景 | 后端 | 前端 |
|---|---|---|
| paper_id 不存在 | 404 `paper_not_found`(实测 route 现状) | 「这份资料记录不存在或已失效」 |
| bundle incomplete(plan 在 spec 缺) | 500 `store_error`(实测 StoreError 映射,**不伪装 404**) | 「资料记录不完整,请重新上传或稍后重试」 |
| question 空 / 超长 | 422 | inline 校验 |
| LLM timeout / quota / 不可用 | 504 / 429 / 503 | 保留输入、可重试 |
| 无相关 / 不可引用证据(5.4) | 200 fallback(insufficient_evidence) | fallback 答、无 citations |
| AI citation invalid(5.1) | 200 fallback | 不显示伪引用 |
| target 语义漂移(5.2) | 200 fallback | 同上 |
| 前端 anchor 解析不到(5.3) | 200 正常 | badge 非点击、不死链 |

---

## §6 schema 同步面(decision 13 全清单 — Card 2/C 落地;**已拍接 Makefile**)

新增 PaperAsk 对外 DTO 触发以下同步(实测:`make check` 不自动覆盖 paper schema):
1. `scripts/export_paper_schemas.py` 的 `OUTPUTS` 加 **`paper_ask_request.schema.json` + `paper_ask_response.schema.json`**(分两个,贴合现有「一顶层模型一文件」习惯)。
2. **`Makefile export-schema` 加 `python -m scripts.export_paper_schemas`;`verify-schema` 追加 paper diff 清单**(现有 5 个 `paper_*.schema.json` + 新增 2 个 paper_ask)。R6 实测:文件名独立,**不与 overview/bridge export 冲突**。本项为**强制**(PM 拍,无手动 / 开放分支)。
3. `tests/features/paper/test_paper_schemas_freeze.py`:顶层模型列表 + request/response;新增 citation + target variants freeze;`extra=forbid`;fallback_reason / target kind / origin 的 Literal 集合冻结。
4. `tests/features/paper/test_paper_schemas_sample_roundtrip.py`:加 PaperAsk 样例 roundtrip,**至少覆盖**正常多 citation / user_supplied citation / fallback response / request 样例(样例文字**不得含模型参数值 / 倍率**)。
5. `docs/06_OUTPUT_CONTRACTS.md`:新增 PaperAsk 契约小节(citation target 种类 / 失败语义 / 三层真值源铁律 / response 不变量)。
6. `git diff --exit-code schemas/*.schema.json` 守门;Card 2/C 完工报告必须贴:`export_paper_schemas.py` diff + `Makefile` diff + `paper_ask*.schema.json` diff + `make export-schema` + `make verify-schema` + `git diff --exit-code`。
7. TS 类型(`web/src/lib/paperTypes.ts`,手维护)加 PaperAsk 请求 / 响应 / citation / target(discriminated union)类型,与后端镜像;`pnpm typecheck` 守门。

(以下两项落 **Card 2/C 验收**,非 RFC 主契约字段:① API route serialization 测试至少覆盖 request 422 / extra forbid / fallback response;② 前端静态 smoke 确保 union target 的 discriminated union 写法能被 typecheck。)

---

## §7 验收标准(本 RFC 卡)

本卡是 RFC,验收 = **契约定稿且自洽**,而非功能跑通:
- [x] §2 DTO / §3 target / §4 锚 id / §5 失败语义 / §6 同步面 四处契约镜像可对齐(domain ↔ wrapper ↔ TS ↔ schema 形状一致,可空性 / 枚举对齐)。
- [x] §1 铁律 3 与 §5.2/§5.3 边界无冲突(后端 fallback vs 前端不可点,两阶段分清)。
- [x] §3 target 种类与现状真实可跳目标一致(不含 figure / spec_parameter / build_step / subsystem 细粒度跳;参数靠 origin+row_index/prompt_id;`SectionTarget` 用 `result_section` 不混 `paper_section_id`)。
- [x] §5 每个失败态有明确裁决(5.1 fallback-not-raise / 5.2 后端 fallback / 5.3 前端不可点-not-死链 / 5.4 figure-only fallback / 5.5 section 降级),无「照搬 MCS」式含糊。
- [x] §2 response 不变量(fallback ↔ citations/confidence/fallback_reason 互斥;非 fallback ≥1 citation)写死。
- [x] §6 Makefile drift 闸为强制项,无开放措辞。
- [x] `Confidence` → `ConfidenceValue`;`EquationTarget` 标注依赖 B1 公式区。
- [x] feature 边界明确:`core/domain/paper_ask.py` + `features/paper/paper_ask_schemas.py`,不 import overview/explanation/chat 私有。
- [ ] (若本卡落最小 domain/DTO 骨架)「只声明不接行为」,`make check` + 显式 export + `git diff --exit-code` + `pnpm typecheck` 绿;**端到端无 ask 行为接入**。

## §8 后续卡依赖关系(本卡定稿后)

```
TASK-520-A RFC(本卡,✅ 定稿)
   ├─► 520-B1  可见锚点 substrate(公式区逐条渲染 + 参数行 row id + 抽公共 formatEvidence + 基础 smoke:公式/参数真实 DOM 存在)
   │      └─► 520-B2  AnchorRegistry + scroll/highlight(target→DOM resolver + scrollIntoView + highlight + unresolved→null + 不 location.hash + smoke:无锚不死链/旧高亮清理)
   ├─► 520-C  后端 POST /papers/{id}/ask(可与 B1/B2 并行起;依赖本卡 target 契约;equation/param 可点联调等 B2)
   │      └─► 520-D  前端就地问 UI + citation wiring(等 B2 + C)
   │             └─► 520-E  hardening / smoke / 截图矩阵(最后)
```
(编号 520-x 为占位,实际起卡时按 decision 22 追问段顺延确认。)

## §9 风险与注意点

- **三层真值源是命脉**:任何一卡若让 LLM 直接给 anchor、或让前端信任后端 target 一定有 DOM,都会出死链——本卡铁律不得在后续卡被绕过。
- **后端 fallback vs 前端不可点不可再混**(v0.2 P0 已修):后端 target 语义不存在 = fallback;前端无 DOM = 不可点。两阶段两处理。
- **figure 缺口是已知、刻意的**(走「丙」):figure-only 证据走 fallback(§5.4);Card E 截图需覆盖「答里提到图但不可点」不报错。
- **`EquationTarget` 依赖 B1**:Card 2/C 不得假设现有 DOM 已有公式锚;公式可点联调必须等 B1 公式区。
- **参数 row_index 稳定性**:实测 `PlanAssembler.merge()` 保留 parameter_mapping 原顺序、用户补充走原 index replace 不重排;若后续生成链改成会重排,本契约 row_index 假设失效 → 停手报架构师(decision 15)。
- **user_supplied 不得伪装 document**(红线 + decision 21):citation `source_kind` 忠实;badge 显「用户补充」;`excerpt` 交叉校验(§2)。
- **injection / 截断不复用现有 builder**:实测 paper 现有 `_prompt_builder` 直塞 raw_text / 全量 JSON;PaperAsk 须自建 source_table context 截断 + data-not-instruction prompt,按 MCS 语义 cap context(spec/plan/missing_prompts 整体可能很长,不可全量塞)。
- **日志隐私(decision 11)**:不落 LLM raw output / document excerpt / 用户问题全文;只落 paper_id / error type / reason code / citation count / unresolved anchor count。
- **stateless 不可被 UI 误导**:`session_id` 仅回显;前端文案不得写「上下文已保留 / 继续上一轮」。

## §10 给 Codex 的提示(若本卡含最小骨架实现)

- 本卡主体是 RFC 文档(`docs/` + `docs/06` 小节);若落 domain/DTO 骨架,参 507-A「只声明不接行为」模式。
- feature 边界:core dataclass + features/paper wrapper,**不** import overview/explanation/chat 私有(decision 21);`ConfidenceValue` 复用 core,别 import chat `Confidence`。
- schema 同步严格按 §6(含强制接 Makefile);显式补 `make export-schema` + `make verify-schema` + `git diff --exit-code` + `pnpm typecheck`。
- 行尾 / 异步 / 日志照 decision 20 / 11;改已存在文本文件保留原始字节(decision 08)。
- 派单前若预放本卡到 `docs/tasks/`,列进 Stage 0 baseline 白名单 + 允许 diff 清单。
