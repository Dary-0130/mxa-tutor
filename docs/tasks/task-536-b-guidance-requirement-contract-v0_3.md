# TASK-536-B:建模指导 requirement 契约 + 来源分层 + gap reducer(v0.3)

> **性质**:契约卡。**改生产契约与判定**(与 TASK-535「只读遥测」不同,本卡明确改生产行为)。
> **不改生成口径**:prompt 六项禁令 / convention 白名单 / sanitizer —— **全部归 TASK-536-C**。
> **前置**:main 含 TASK-535(含 S7 正文落盘)
> **对照组**:`eval/out/baseline_pre_layered_basis_20260713_024111` —— ★ **别删。唯一一份「改之前长什么样」的实物。**
>
> ★ **编号说明(防撞号)**:TASK-536-B 为**暂定**。派单第一步 `git fetch` 后查 `docs/tasks/`,确认未被占用;占用则顺延、回报。**不得凭印象写编号。**
> ★ **入仓模式(决策 12 R5.1)**:本卡在 main 无前置同名实体卡 → **create_file 新建**,**卡随代码 PR**。

## 状态

🔲 v0.3 待 **Codex Stage-0**(§10,六项 confirm-and-stop)→ 实施

- **R1 设计审两轮已收**:第一轮 4×P0 全部采纳;第二轮四处 —— A 打回(已修)、B/C/D 通过(条件已并入)
- **R6 只读核查五轮已收**:S0-1…S0-27 + 全量映射审计
- **PM 终裁已并入**(§12)

---

## 1. 地基:以下全部是实测,不是推测

**基线(2026-07-13,8 篇真论文,生产口径 `max_tokens=8000` / `timeout=120`)**

| | 数 |
|---|---:|
| 出得来指导的论文 | **4 / 8** |
| detail 总数 | **75** |
| `actionable` | **18(24%)** |
| `blocked_pending_confirmation` | **57(76%)** |
| 阻塞缺口(gap) | **78** |

**basis × actionability(S0-9 实测)**:`document_extracted` 18 条(全部 actionable)/ `engineering_convention` **0 条** / `user_confirmation_required` 57 条(全部 blocked)。

**gap 构成(实测)**:参数 44 + 接线 15 + step 级证据 19 = 78。

**七个 `confirmation_reason_code` 的归属(S0-2 实测)**:六个非红线码**由模型在私有 draft 里自赋**,后端只做白名单验收与模板渲染;`document_evidence_unverified` 有三条路径(基线 10 条 = generator 降级 7 / validator 降级 2 / 模型自报 1)。
★ **不得凭码名推断其触发条件** —— 本项目已在「凭码名推断」上栽过三次。

### 1.1 ★ 本卡的真正病灶:身份缺失(R6 五轮全量映射审计)

**153 条产物(75 detail + 78 gap)中,142 条的 target 身份只活在 `display_text` 散文里,结构化字段取不到。** 只有 11 条干净。

- `GuidanceDetail` 无 `target`;`GuidanceGap` 无 `target`;`target` **只存在于私有 draft**,落盘前被折进散文(S0-21)
- 实例:2003 的 `GD-011` / `GD-012` 两条 detail,正文只写「Confirm step STEP-002」——**连自己在回答哪个参数都没说**

★ **一条不说自己在答什么问题的建议,系统无法判断它答没答。身份缺失是 76% 白条的结构性前提。**

### 1.2 ★ 与之配套的第二个结构错:gap 与 detail 各说各话

`covered_params` 只认 `EvidenceSource.DOCUMENT_EXTRACTED`(S0-11 实测,`build_guidance_generator.py:1169-1172`)。
→ **一条 detail 即使给出完整的值,只要来源不是论文,44 个参数 gap 一个都不会消。**
→ 若只做来源分层而不动 gap,产物会同时声称「该问题已解决」和「该参数仍缺失且阻塞」——**持久化语义自相矛盾**(R1 P0-4)。

### 1.3 ★ 一堵今天不存在的墙(S0-4b 实测)

非论文来源 detail 的正文里写「论文表 3 给出 γ=0.99」而结构化证据字段全空 → **现行管道没有任何一层会拦。** grounding 只跑在 `document_extracted` draft 上。
★ **本卡是新砌这堵墙,不是拆墙。**

---

## 2. ★ 核心设计:requirement 是第一性的

**新模型:**

```
build_steps
  ⟹ 后端确定性枚举 requirement 集(每个带私有 handle REQ-###)
  ⟹ handle 端给模型;模型每条 detail 必须按号引用恰好一个 requirement
  ⟹ gap 不再由生成器另行合成,由 reducer 从 requirement 闭合状态导出
```

★ **这与现有证据 handle(`GEV-###`)机制完全同构** —— 决策 27 §3/§5/§6 全套适用:模型只给不透明引用号;后端按号自解析;私有号不外泄(不进公共 schema / API / 持久化 / 日志 / 前端)。

**requirement_key**:

```
paper_id + step_id + obligation_kind + target_kind + target_identity(canonical)
```

★ **禁止进键**(R1 P0-2):`basis`(否则 relabel 会伪装成新问题)/ `resolution.kind` / `closure` / 数组序号 / `detail_id` / 任何展示文本。
★ **作用域**:该键**只在同一冻结产物内稳定**,**不冒充跨版本稳定 ID**。跨 artifact 比较须带 artifact hash(归 536-C 的冻结输入包)。

**cardinality(R1 P0-2,硬不变量)**:

```
每个 requirement:
    0 条 closing detail  → open
    1 条                 → 按 payload 推导 closure
   >1 条                 → ambiguous,fail-closed（★ 不许任选一条清 gap）
input_fact_refs 指向的支撑事实,不自动成为 closing detail,不因被引用而清第二个 gap
```

**detail 引用失败的处理(★ 防管道打死)**:

```
requirement_ref_missing / requirement_ref_unknown
    → detail 级 drop + 可区分子码 + 计数
    → 沿用 528-C 既有降级放行语义:整份不报废
    → 只有全丢光才 generation_failed(不改这条既有规则)
```

### 2.1 ★ obligation_kind:我对 R1 的一处修正(必须记录)

R1 P0-2 给的枚举含 `set_parameter` / `derive_parameter`。**不采纳这两个名字**,理由:

> 「这个值论文给了没有」是**答案**,不是**问题**。把它放进键,一条 detail 从 `document_extracted` 改成 `domain_default`,键就变了 —— **正好违反 R1 自己定的「答案字段不进键」。**

**本卡采用**(每个 requirement 对象恰好一个 obligation,与 target 四族一一对应):

```
determine_parameter_value / select_component / configure_setting / connect_signal
```

★ 键里**保留 `obligation_kind` 字段**(R1 方案 B 的形状,便于将来扩「如何验证」「如何推导」等新 obligation 而不改键结构),但**当前每个 target 只有一个 obligation**(R1 方案 A 的不变量)。两方案的合并解。

---

## 3. target 四族(冻结;R6 五轮全量映射实测)

| 族 | 身份字段 | 实测条数(153 中) |
|---|---|---:|
| `parameter` | `model_param`(必填)+ `paper_param`(★ **可为空**) | 92 |
| `configuration` | `owner_ref` + `setting_name`(一元设置:solver / 仿真时长) | 5 |
| `block_choice` | `block_role_ref`(★ **待填的角色,不是最终选中的库路径**) | 13 |
| `connection` | `from_block` + `to_block`(+ `port` / `signal_role` 若有) | 23 |

★ **枚举种子(S0-28 实测)**:`_required_object_coverage()`(`build_guidance_generator.py:1045`)今天已枚举 `block` / `parameter` / `connection` / `configuration` 四类,可作 requirement 枚举基础。★ `block` → 映射为 `block_choice`,**身份用 `block\_ref\_id`,不是 `library\_path`**。缺的是:`obligation_kind` / 结构化 target union / `REQ-###` handle / 按 requirement 的 closure 与 reducer。

★ **`paper_param` 不得强制非空**(R1 P0-1):领域默认参数可能只有模型侧名字、没有论文侧名字 —— 强制必填 = **又一道没有合法答案的题**(决策 27)。

★ **`block_choice` 的身份不能用最终选中的库路径** —— 那是答案,不是问题。

### 3.1 ★ 已知边界(实测,不加族)

- **`subsystem_structure`:全量 153 条中仅 1 条**(2003 `GD-010`,安全滤波器内部结构)。**不为 1 条建族** —— 前车之鉴:convention 白名单精心挑了 4 类,8 篇真论文命中 **0** 条。模型遇到时**走 punt**(§4)。
- **19 条 step 级 meta gap**(`insufficient_document_evidence`,原文一律是 `Step STEP-xxx has a detail that requires confirmation before reproduction.`):**不指向任何对象**。★ **新契约不生成这类 gap** —— 一个 step 的问题必须落在具体对象上;落不到,说明是上游 build_steps 没写清,归另一张卡。迁移账中标 `legacy_step_meta`,**不计入分母**。★ **断点已定位(S0-28 实测)**:这类 gap 由 `build_guidance_generator.py:802` 的 `blocked_detail` 合成路径产生。新契约在此断掉。
- ★ **R1 的两个假设被实测否定**:5 条 `engineering_decision_unverified` **全部是「选哪个模块」**(原文已核),不是拓扑 / 子系统结构决策。**没有为 R1 的猜测去凑族。**

---

## 4. Detail 判别联合(8 变体,`basis` 为判别字段)

| basis | 语义 | 论文证据字段 | 可达 closure |
|---|---|---|---|
| `document_extracted` | 论文直述 | **必填**(id + 定位 + 摘录) | `closed` |
| `document_derived` | 论文输入 + 推导 | **必填输入证据 + 推导规则** | `closed` |
| `domain_default` | 领域常规 | ★ **禁止** | `closed` |
| `engineering_choice` | 本方案选择 | ★ **禁止** | `closed` |
| `user_environment` | 用户环境可观察 | ★ **禁止** | `guided_probe` |
| `user_decision` | 用户规范性决定 | ★ **禁止** | `guided_choice` |
| `user_confirmation_required`(**punt**) | 合法的「不知道」 | 禁止 | ★ **恒 `open`** |
| `document_claim_unverified` | 声称论文依据,核不上 | 清空 | ★ **恒 `open`,前端独立分区** |

★ `engineering_convention` 并入 `engineering_choice`;`convention_code` 降为**可选槽位**,不删(避免二次动对外 schema)。

### 4.1 punt 变体:合法的「不知道」(R1 P1-1,六条约束)

**存在理由(决策 27)**:不许给模型一道没有合法答案的题。删掉 punt,模型遇到「既不是论文、也没有领域默认、也说不清取决于什么」时**只能被迫编一个 basis** —— 那正是本卡要防的。

```
1. 必须由模型显式输出该变体
2. ★ 解析 / 校验 / resolver 失败,不得自动降级为 punt
   （否则它就是 _DROP_EVIDENCE 换马甲 —— 决策 27 §4）
3. 必须绑定恰好一个 requirement
4. resolution = null 且 evidence = [] 且 input_fact_refs = []
5. 每个 requirement 最多一条 punt
6. punt_reason_code 为受控枚举（不靠自由散文描述状态）
★ punt 留在分母中。不得靠「改成 punt」减少困难项总数。
★ 不设 punt 数量硬上限 —— 硬逼模型少 punt,会重新产生「必须编一个 basis」的问题。
  正确做法:无评分收益 + 保留分母 + 单独披露数量。
```

**与 R1 P2-2 的关系(已裁)**:P2-2 禁的是**旧持久化数据批量洗标**;punt 是**新生成时的诚实出口**。两者不冲突 —— 旧数据走 §7 版本失效重生成,不做映射。

### 4.2 `document_derived` 守门(R1 P1-2;否则它就是改了名字的 `engineering_choice`)

```
推导规则非空
输入 refs 非空
所有输入均能追到 verified 的 document detail
输出 resolution 完整
```

### 4.3 `input_fact_refs`(依赖关系,★ 不是出处字段;R1 P1-3)

```
引用必须存在于同一 artifact / version
禁自引 / 禁成环
用作论文输入约束时,只能引 document_extracted | document_derived
被引 detail 必须已闭合且证据已验证
引用不改变本 detail 的 basis
★ 引用不得把论文 evidence 复制进非论文 detail 的证据字段
```

★ **混源必须拆成原子 claim**,不许一条 detail 混写两件事。
例:「用库变体 X,增益取论文给的 2.43」→ 拆两条:论文 detail(值 2.43,带证据)+ 工程选择 detail(选 X,证据为空,`input_fact_refs` 指向前者)。**前端不得合成为「论文建议使用 X」。**

---

## 5. resolution 联合(7 型,逐型确定性不变量)

| kind | 不变量 |
|---|---|
| `fixed` | 目标 + 值;**物理量必带单位** |
| `range` | 上下界(或明确集合)+ **推荐起点 或 选点规则** 二选一必填 |
| `enum_selection` | `selected` 必填(`engineering_choice`);`user_decision` 走 `guided_user_decision` |
| `derivation` | 公式 / 规则 + 输入清单;每个输入已解决或经 `input_fact_refs` 可解 |
| `conditional` | 分支**完备** 或 有显式 fallback;★ **裸「取决于 X」不合法** |
| `guided_user_decision` | 待决项 + 判据 + **各选项后果** |
| `environment_probe` | 查什么 + 怎么查 + **各结果分别执行什么** |

违反任一不变量 → **fail-closed,可区分子码**。

★ **不含安全五字段**(`applicability_conditions` / `assumptions` / `validation_check` / `failure_signal` / `rollback`)**与 `impact_tier`** —— **PM 终裁推迟**,见 §12。

---

## 6. execution_closure + gap reducer(R1 P0-4:与契约同卡、同一验收门)

**`execution_closure` 由后端从 resolution payload 确定性推导。★ 模型不产 `actionability`。**

```
closed / guided_choice / guided_probe / open
actionable ⟺ closure ∈ {closed, guided_choice, guided_probe}
```

**清 gap 表(冻结)**:

| variant | 合法 closure | 清 gap |
|---|---|---|
| `document_extracted` / `document_derived` / `domain_default` / `engineering_choice` | `closed` | 是 |
| `user_decision` | 完整则 `guided_choice`,否则 `open` | 前者是 |
| `user_environment` | 完整则 `guided_probe`,否则 `open` | 前者是 |
| `punt` | 恒 `open` | **否** |
| `document_claim_unverified` | 恒 `open` | **否** |
| 任何 free-text-only 内容 | — | **否** |

★ **清 gap 的唯一正确解读**:「用户已获得一个可继续执行的答案 / 选择程序 / 检查程序」。
**它不等于**「所有最终参数值和环境事实已确定」。
→ **必须附报**(防下游误读 —— R1 P1-4):

```
pending_user_choice_count
pending_environment_probe_count
open_requirement_count
```

`blocking_gap_count` / `fully_actionable` **全部由 reducer 输出重算**(S0-26 消费方逐项同步)。

---

## 7. 渲染:后端全面接管(R1 P0-1)

★ **一切用户可见文本(含出处句)由后端从结构化 payload 合成。模型不得自由撰写出处表述。**

理由(S0-4b):守门只能查结构化字段,而错误归因藏在正文里。**只要正文仍由模型自由生成,在「不用正则、不靠模型自觉」的前提下,就不存在确定性办法证明它没把建议写成「论文说的」。**

**出处前缀模板(后端产出)**:

```
论文明确给出
由论文式 X 推导（非论文直述）
领域默认（非论文）
本方案选择（可改）
需确认你的环境
需你决定
论文依据未核实（未采用）
```

★ **修正 B23 的自相矛盾**:`missing_parameter` 类模板**不得再指路回论文**(基线里后端说「check the source model or paper table」,模型紧接着说「论文中未给出具体值」——**同一句话里互相打脸**)。
★ 全部文案**改中文**。
★ **模型的散文槽位最少化 + 限长**。

**528-D 契约要求(本卡只锁契约,不做前端)**:

- 前端**只消费后端渲染串 + 类型字段**;★ **禁止自拼出处** —— `web/src/lib/paperEvidence.ts:7-21` 那种「前端自己拼『依据:章节/式/图』」的模式**不得复制到 guidance**(S0-24 实测该模式已存在于 build_steps / 参数表)
- `document_claim_unverified` **独立分区**,不得与可执行项混排
- 三个视觉区:**论文明确给出 / 由论文推导** | **不是论文说的:领域默认 / 本方案选择** | **需你检查环境 / 需你决定**

★ **残余风险(不粉饰)**:模型的散文槽内仍可能夹带「论文说」。**缓解 = 槽位最少化 + 限长 + 盲测兜底(536-C)。不假装确定性守门覆盖了它。** 记入决策 29。

---

## 8. 版本与旧数据(S0-23 实测机制)

- `BuildGuidance.version` **`v1` → `v2`**
- 读回 `v1` → **退化为 `stale_pending_regeneration`**,不报错、**不批量映射**(R1 P2-2:旧 `user_confirmation_required` 混着七种语义,不可确定性迁移)
- `lifecycle` 活性规则改写:**≥1 个 `document_extracted` 或 `document_derived`**(现为「≥1 个 `document_extracted`」,S0-26)
- ★ 决策 20 的 source_version 算法**只管 TeachingUnit,不管 paper guidance**(S0-23 实测)——本卡不复用它,走上面的 version 退化路径

---

## 9. 守门子码(全部可区分;决策 27 §4)

```
出处:      non_document_evidence_present / non_document_document_id_present /
           non_document_locator_present / non_document_excerpt_present
身份:      requirement_ref_missing / requirement_ref_unknown / duplicate_closing_detail
resolution: resolution_missing / resolution_kind_invalid / range_incomplete /
           derivation_input_unresolved / conditional_non_exhaustive /
           decision_procedure_incomplete / probe_incomplete / relabel_without_resolution
引用:      input_fact_ref_unknown / input_fact_ref_cycle / input_fact_ref_forbidden_basis
punt:      punt_from_exception_forbidden
reducer:   requirement_mismatch / does_not_close_gap / requirement_ambiguous
```

★ 子码必须能分辨「**真救回**」与「**换个名字接着废**」(决策 27 §4)。

---

## 10. ★ Stage-0(六项 confirm-and-stop;先诊断后修 —— 决策 15)

| # | 核什么 |
|---|---|
| **S0-28** | ★ **requirement 枚举的种子**:`_required_object_coverage(step, covered_params)`(`build_guidance_generator.py:1056-1058`)今天枚举哪几类对象?**能否直接作为 requirement 枚举基础?四族(parameter / configuration / block_choice / connection)是否全覆盖?缺什么?** |
| **S0-29** | ★ **detail 内部键唯一性复核**:R6 五轮报 30 组「碰撞」,列出的实例**全部是 detail↔gap 配对**(那正是 reducer 的匹配,不是碰撞),外加 2003 `GD-011`/`GD-012` 一处 **detail 自撞**(身份缺失)。★ **30 组未逐组摊开** —— 把 detail 与 gap **分开命名空间**后,**detail 内部还有没有别的自撞?**逐组核,贴实例。 |
| **S0-30** | **prompt 结构改动的边界**:把 requirement 清单(私有 handle)端给模型 + 要求按号引用,**是否触及六项禁令段 / convention 白名单段 / sanitizer?**(本卡**不得动**这三处)。给改动位置。 |
| **S0-31** | **决策 13 全同步面**:按 S0-25 清单逐项确认(公开 schema / TS / 06_OUTPUT_CONTRACTS / freeze / export 脚本 / storage 读回 validator / eval 统计),**列全**。SQLite DDL 是否需变(plan 存在 `plan_json` 里)? |
| **S0-32** | **eval 草稿留档(承 S0-13)**:在 `RecordingTextProvider` 抽取 guidance draft(`claim_text` / `direction_hint` / `supporting_evidence_refs` / `basis` / `confirmation_reason_code` / `target` / `step_id`)落 `eval/out/<run>/guidance_drafts/`,**生产零落盘**。改动面确认;若与本卡耦合过重 → **回报,可拆出独立小卡**。 |
| **S0-33** | **工作量估算**(★ 架构师不估:决策 12 R1 明列「工作量估算」为反例 28 类目)。**由你给分段估时。** |

★ **停手条件**:
- 编号被占用 → 顺延、回报
- 任一项**必须动 prompt 的六项禁令 / convention 白名单 / sanitizer** 才能落地 → **停手回报**(那是 536-C 的范围)
- **卡面与实测不符 → 以实测为准,回报,不迁就卡面**

---

## 11. 验收

### 11.1 确定性(主体;fake provider + 固定输入)

1. **requirement 枚举确定性**:同一 build_steps ⟹ 同一 requirement 集;**键零碰撞**(在基线 8 篇的 build_steps 上跑)
2. **八变体契约测试**:四个「证据禁止」子码各有正反例
3. **punt 六约束**:含 ★「解析/校验失败不得自动降级为 punt」的反例测试
4. **`document_derived` 四守门** / **`input_fact_refs` 六校验** / **resolution 七型不变量**:各有正反例
5. **reducer 1:1**:0 / 1 / >1 条 closing detail 三种基数各有测试;>1 必 fail-closed
6. **清 gap 表**:八变体逐行断言
7. **渲染 golden**:后端模板产出;★ `missing_parameter` 类**不含**指回论文字样
8. **v1 → v2 退化**:读回旧 `plan_json` → `stale_pending_regeneration`,API 正常返回
9. **私有 handle 不外泄**(决策 27 §6):公开 schema / TS / API / 持久化 / 日志中**不出现 `REQ-###` 或 requirement 私有号** —— 搜索证零命中。★ **公开契约本身的 diff 是本卡的预期产物**(basis / resolution / closure 是公开契约变化),按决策 13 全清单同步(S0-31),**不适用「零 diff」**。
   ★ eval-only 草稿留档允许携带 REQ 号,边界同 TASK-535 S7(eval-only / 本地公开论文 / gitignored / 生产零落盘)。
10. **决策 13 全同步**:按 S0-31 清单逐项
11. **四条固定回归**(真实产物 fixture,★ **测最终渲染,不测 draft**):
    - `A02`(论文直值 λ_p = 2.43)→ `document_extracted` + `closed` + actionable
    - `B23`(死区 κ)→ 渲染**不含**指回论文字样
    - `B31`(折扣因子 α,纯弹回)→ **无合法 payload 时,任何 basis 均不得晋升**(relabel 穿透测试)
    - `2003 GD-011/GD-012`(只说「Confirm step STEP-002」)→ **身份缺失必须 fail-closed**
12. `make check` 全管道 + **显式列** schema export、前端 typecheck
13. **脱敏亲核**(贴本体,不凭勾选;决策 11)

### 11.2 真机 sanity(★ 不是效果证明)

跑同一批 8 篇 × 1 轮,**生产口径 `8000` / `120`,串行**(并发会把排队时间计进 guidance 自己的时间预算 —— TASK-535 S0-8)。

**只回答三个问题**:

```
1. 模型能不能按 REQ 号答题？（requirement_ref_missing / _unknown 的条数）
2. 管道有没有被打死？（4/8 出指导的数,别掉下去）
3. 草稿留档跑通了没有？（S0-32,眼看一份）
```

★ **本卡不做任何效果断言。** 可执行率 / 论文依据率 / 盲测闭合率 **全部归 536-C**(决策 28:效果断言只认同场配对 + 冻结输入)。
★ 若真机显示模型**大面积答不上号** → **不许跳到 retry**(决策 27 修法顺序:契约 → 稳定 ID → few-shot → retry)。回报,按顺序处理。

---

## 12. PM 终裁(决策 12 R4;后续 R 轮不得重议)

1. **拆卡**:536-B(契约,本卡)→ 536-C(解禁 + 复跑 + 盲测)
2. **R1 P1-3 整体推迟**:安全五字段 + `impact_tier` **不做**。PM 原话:「**先生成有用的玩意,再想安全**」。
   理由:确定性守门只能验非空、验不了有用;必填散文栏 = 模板废话培养皿;且拉长输出(已有一篇因顶满 8000 token 截断报废)。
   **C 的真实产物回来后,按真实错误分布立卡补,不凭空必填。**
3. **效果判官**:GPT + Claude **双新会话**、双盲、两臂混洗、陷阱题(归 536-C)。
   ★ **PM 不使用 Simulink,验收环内无人类领域专家** —— 首次人类验证 = 外部测试者。此原则须成文(决策 29),`TASK-515` b3 的「人工裁定」坑位按此重排。
4. **审核收口**:R6 五轮 + R1 两轮已跑完,**本卡不再送审,直接施工**。

---

## 13. 继承红线(不回退)

- **决策 07**(索引单独 closeout PR)/ **08**(改文本文件保原始字节:定点替换 + `git diff --unified=0` 自查)/ **11**(脱敏)/ **13**(改对外 schema 须列全同步)/ **15**(先诊断后修)/ **25**(硬契约由确定性规则验证,不靠模型判卷)/ **27**(全部六条 + **修法顺序:契约 → 稳定 ID → few-shot → retry,不得倒**)/ **28**(效果判据)
- **反编造防线(506 + 528 + 529)不得放宽** —— ★ 本卡**收紧**它(§7 新砌出处墙),不放宽。**放宽归 536-C + 决策 29。**
- **`document_evidence_unverified` 拦死,一步不让**
- **TASK-535 as-built**(provider 边界同源 / `null ≠ 0` / S7 eval-only 落盘 / 生产路径不落模型正文)不回退
- **依赖措辞 v0.3** 生产路径(渲染哈希 `053561af…` / `f5b564fc…`)**不得改字**
- **同场配对评测台**(`--paired-build-steps` / `--paired-build-steps-full`)是资产,**不许拆**
- **禁两套 pipeline**

---

## 14. 挂账(本卡不做,单列)

1. ★ **上游 4/8 失败**:2107 / 2110 / 2410 死在 **build_steps**;2605 触达 guidance 但 `completion_tokens = 8000` **顶满上限**(★ 生产口径 8000 下仍截断 —— 「写爆是 6000 评测预算掐的」这个推测**未被证实**)。**即便指导层完美,交付上限仍是 4/8。**
2. **536-C**:解除六项禁令 / 扩 convention 白名单 / sanitizer 按 basis 分流 / **冻结 guidance 输入包**(★ 按 R6 Q5 实测清单:`spec` 的 documents·evidence·equations·parameter_table + `plan.library_choice` + `block_recommendations` + `parameter_mapping` + `plan.evidence` + 完整 `build_steps` + 证据卡与其背后的证据池 + prompt 模板 hash + LLM 配置 —— **只冻 build_steps 不够**,R1 P1-5)/ 逐项迁移账 / 盲测闭合率 / `relabel_only_promotion_count == 0`
3. **决策 29**(放宽三条 + 收紧四条 + 代价 + PM 终裁落档):最迟随 536-C 入仓。
   ★ **决策 28 原文不在项目知识库** —— 它是 536-C 效果判据的依据,**请补一份**。
4. **迁移账口径**(536-C):`unverified_to_verified_document` / `unverified_to_substantive_non_document_resolution` / **`unverified_to_punt`(= `claim_withdrawn_open`,★ 不算改善)** / `unverified_remaining`;文档类分列 `document_direct_count` / `document_derived_count` / `direct_to_derived_count`(R1 P2-3)
5. ★ **归因墙目前只覆盖 guidance 层**。S0-27 实测:另有多条模型自由文本直达 UI(build_steps 正文 / 参数表 / 参数冲突 / 调参面板 / paper-ask 等)。**这是边界,不是漏洞** —— 但必须成文(决策 29),否则半年后会有人拿它当「归因墙失效」的证据。
6. **CI 断言**:焊死「评测侧 guidance 有效配置必须与生产同源」(TASK-535 挂账;三处不同构全部让评测比生产更苛刻 —— 不加这道,会有第四处)
7. **528-D 前端上屏**:三视觉区 + 禁自拼出处(§7)
8. ★ **chore 挂账**:本地 `make check` 用 Python 3.13、CI 用 Python 3.11,两条跑道各跑各的,迟早再出事;要么把本地开发环境锁到 3.11(与 CI 同源),要么 CI 加 3.13 矩阵。此病与 TASK-535「评测跑道与生产不同构」同源,PM 定优先级。

---

## 15. 派单说明

- **新开 Codex 会话专办本卡**(★ 不复用诊断会话:同一会话既派 A 又插 B,上下文会被搅乱 —— 已有前科)
- feature branch 从 `origin/main`(`git fetch` 后切)
- **卡随代码 PR**;**不碰 `03_TASK_INDEX.md`**(决策 07;合并后由 PM 走索引 closeout PR)
- 改对外 schema → **必列全同步**(决策 13,按 S0-31 清单)
- `make check` 全管道 + 显式列 schema export、前端 typecheck
- **脱敏亲核**(贴本体)
- **不得删改** `eval/out/baseline_pre_layered_basis_20260713_024111`
- PR 全走 PM 网页侧:只 push 分支 + 给标题 / 正文 / compare 链接,**不自建、不登录、不合并**
- 完工 report 须含 `git diff --stat` 实证;**范围外文件停手**(决策 12 R6.1)

---

**版本**:v0.3
**作者**:Claude(架构师)
**依据**:2026-07-13 基线实测(8 篇真论文,生产口径)+ R6 只读核查五轮 + R1 设计审两轮 + PM 终裁
**审批**:PM 已拍 → **直接派 Codex**(本卡不再送审;Stage-0 六项 confirm-and-stop 先行)
