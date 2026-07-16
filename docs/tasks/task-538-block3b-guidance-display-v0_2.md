# TASK-538 block 3b v0.2:guidance 前端显示面 + 诚实来源章 + 缺口清单

## 状态
🔲 未开始(v0.2;R1 设计审 + R6 可落核已并入;待架构师签字 + PM 话术确认 → 实施)

## 版本说明(v0.1 → v0.2 改了什么)
双审核心结论:方向成立,但 v0.1 诚实层仍有误读路径、异常数据下仍有吞点、落地口径有三处错。v0.2 按双审重写:
- **诚实降级矩阵**(R1 H3):展示档不再只看 `basis`,而由 `basis + evidence + confirmation_reason_code` 算"有效展示档";无 evidence 的"有据"不给绿、`document_evidence_unverified` 升 D、未知 basis 固定 D。
- **原文 / 推导分离**(R1 H2):`document_extracted` 与 `document_derived` 不再同绿同档;只有 extracted 显肯定绿。
- **来源章去"正确性背书"**(R1 H1):删掉"可直接采用 / 推导可信 / 通常适用"等替内容盖章的话;章只说"从哪来 + 出处定没定位",不证明"在你的模型里能跑"。
- **缺口去硬判**(R1 H5):`blocking` 不再显"必须补 / 搭不起来",改"关键待确认 / 可能影响搭建";缺口显式带"待你确认"语义。
- **orphan 区 + 数量守恒**(R1 H4 + R6 #3):补未匹配 step / 无 build_steps / stale 快照的兜底区;确定性不变量"输入条目数 = 可见条目数"。
- **detail_kind 只做图标不做可执行性分组**(R1 H6)。
- **落地口径纠错**(R6):确认原因码 **12 个**(非 5)、真实分隔是 **中文全角**、`document_claim_unverified` 也带 `confirmation_reason_code`、`BuildSteps.tsx` 代码禁出现 smoke 命中词。
- 其余:密度/分组/去重(R1 M6)、evidence 以摘录为主(R1 M7)、清洗加 basis 一致性(R1 M4)、空状态按 status 分文案(R1 M5)、视觉隔离步骤原始章(R1 M1)、配色收死(R1 M2)。

## 归属与边界
- 本卡是 **538 block 3b**;block 2(后端放行)、3a(恢复谓词 + 诚实横幅 + task508 基线)已合入 main(3a = PR #211 squash `5d13a11`)。
- **纯前端 additive**:`basis` / `gaps` 已由 block 2 后端盖章写入 `plan_json`,3b 只显示。不改后端 / schema / 版本。
- **副驾边界(宪法 §2 / 决策 22 §1.1)**:产品帮认知工作(读懂论文 / 理路线 / 参数对应),搭建、跑通、收敛由用户在 MATLAB 完成。**不生成模型、不产 .slx、不通电 MATLAB**。
- **不在本卡**:调参 / 调收敛动态指导(依赖 MATLAB 桥,另立项;桥进度须 Codex 对仓库现状核报)。

## 上下文
现状:后端已给每条 guidance 盖 `basis`、给缺口盖 `gaps`,但**前端没有 guidance 显示面**——`BuildSteps` 只渲染 `build_steps` / fallback / evidence,不消费 `build_guidance.details/gaps`。未核实的 guidance 现在**不是被显成"已验证",而是干脆看不见**。538 要产品把"查了 / 查不出 / 推回你确认 / 这块我没有"诚实显出来。

★ block 2 已保证"内容判定放行、不判废"。**3b 是显示层,绝不能又把放行的东西吞回去**(见"反抑制红线")。

## 落点(基于含 3a 的 main `5d13a11`;R6 已确认锚点未漂移)
- 诚实横幅 `web/src/routes/PaperResultPage.tsx:157`(**task522d1 守其文案,不动**)。
- `BuildSteps` 调用同文件 `:158`,已拿 `plan={data.plan}`。
- BuildSteps 内部数组 normalize 在 `web/src/routes/paper/BuildSteps.tsx:99-108`,结构化 gate `:128`(**真白屏点,不动**)。
- **不碰** `SourceBadge.tsx:7` 及两调用点 `ParameterTable.tsx:324`、`BuildSteps.tsx:50`。
- 既有 `formatEvidence`(`paperEvidence.ts:7-21`)只显章/式/图,不显 `document_id`/`excerpt` → 3b 自建 evidence chip。
- 类型锚 `paperTypes.ts`:`GuidanceBasis`:74 / `GuidanceDetail`:390 / `GuidanceGapKind`:102 / `GuidanceGap`:408 / evidence 字段 :252-259 / `confirmation_reason_code` :399。

## 数据事实(R6 已对代码 + `eval/out` 真实产物坐实)
- **basis 8 值**(后端 `core/domain/paper_plan.py` 与前端类型一致):`document_extracted` / `document_derived` / `domain_default` / `engineering_choice` / `user_environment` / `user_decision` / `user_confirmation_required` / `document_claim_unverified`。真实 final 出现前 6 减 `document_derived`/`user_environment`(后二仅草稿、latent)。`engineering_convention` 已退役并入 `engineering_choice`,旧缓存可能残留。`document_claim_unverified` 是活的(证据过不了改写成它;validator 也把坏 extracted/derived 降成它)。
- **detail_kind 真实占比**:`parameter_value` ~56% / `block_selection` ~16% / `connection` ~13% / `configuration` ~9% / 其余 <7%。
- **display_text**:1661 条零空值,一句人话(主标题级,非完整步骤),median ~86 字符。开头是**后端确定性模板拼的 basis 前缀**(`build_guidance_requirements.py:337`),**中文全角冒号**,8 种(见清洗)。**机器码会漏进文本**:尾部 `；原因：<punt_reason_code>。`(全角;如 `；原因：source_does_not_specify。`,`build_guidance_requirements.py:357`;码表 `PUNT_REASON_CODES` `:34`)。
- **confirmation_reason_code 是 12 值**(非 5;后端人话表 `build_guidance_rules.py:54`,带 `{target}` 插值),见下"确认原因"。**`document_claim_unverified` 也会被 validator 设成 `confirmation_reason_code="document_evidence_unverified"`**(`build_guidance_semantic_validator.py:645/660`)→ 原因显示按"有 code 就映射",不限 `user_confirmation_required`。
- **evidence**(有据 detail):final `document_extracted` 后端要求 `document_id` + ≥1 locator + `excerpt`;前端类型里 `paper_section_id`/`equation_id`/`figure_id`/`excerpt` 皆可空。**无 page/line 字段** → 不承诺行号。
- **gaps**:真实全 `scope="step"` 且 `step_id` 非空(挂步骤);真实 `gap_kind` 只 4 个(`missing_parameter_value`/`missing_support_component`/`missing_connection_detail`/`missing_configuration_detail`),`severity` 真实只 `blocking`;`basis` 恒 `user_confirmation_required`;当前 v2 gaps `target`/`obligation_kind` 全填,旧产物 null。**stale 快照后端允许保留 step 缺失的 gap**(`build_guidance_semantic_validator.py:808-819`)→ 必须有 orphan 兜底。
- **input_fact_refs 全空** → 砍参数依赖 UI。

## 范围 · 必须做

### 一、有效展示档矩阵(诚实层的脊梁,R1 H3)
逐条 detail 算 `有效展示档`(纯前端结构层降级,不改后端 basis、不隐藏正文):

| 条件(自上而下,先命中先定) | 有效档 | 视觉 | 章标签 |
|---|---|---|---|
| `confirmation_reason_code == "document_evidence_unverified"` 或 `basis == "document_claim_unverified"` | **D 未核** | 橙/琥珀警示(图标+描边+加重) | 出处待核 |
| display_text 前缀隐含 basis ≠ 实际 basis(不一致) | **D 未核** | 橙/琥珀 | 来源标注不一致 · 待核 |
| `basis == "document_extracted"` 且 ≥1 可展示 evidence | **A-原文** | 肯定绿(实心) | 论文原文 |
| `basis == "document_extracted"` 且无可展示 evidence | 降级 | 非绿(中性) | 来源信息不完整 |
| `basis == "document_derived"` 且 ≥1 可展示 evidence | **A-推导** | 蓝绿描边(**非**肯定绿) | 据论文推导 · 非原文结论 |
| `basis == "document_derived"` 且无可展示 evidence | 降级 | 非绿 | 来源信息不完整 |
| `basis ∈ {domain_default, engineering_choice}`(含 legacy `engineering_convention`) | **B 惯例** | 灰 | 领域默认 / 工程设定 |
| `basis ∈ {user_confirmation_required, user_environment, user_decision}` | **C 待你处理** | 蓝(固定) | 待你确认 / 环境相关 / 你的选择 |
| 未知 / 无法识别的 basis | **D 未核** | 橙/琥珀 | 来源待核 |

- 「可展示 evidence」= 某 entry 有非空 `excerpt`,或有非空 locator(`paper_section_id`/`equation_id`)。全空 → 无可展示 → 降级。
- **只有 A-原文 出现肯定绿"论文来源"章**;A-推导、B、C、D、降级一律不给肯定绿。
- 未知 basis 固定 D,**不许走普通中性**(防"系统不认识来源"被读成普通工程信息)。

### 二、配色(收死,R1 M2)
用现有 `paper.css` 设计 token,不新造配色体系。**颜色不是唯一编码,每档都有可见文本 + 图标。**
- A-原文 = 绿。A-推导 = 蓝绿/蓝描边(非肯定绿)。B = 灰。C = **固定蓝**。D = **固定橙/琥珀警示**(图标+描边+文字加重)。
- **实心红只留给真正错误/危险态,D 不用实心红墙**(避免故障感/警示疲劳)。
- 未知 basis 固定用 D。C 与 D 暖冷分开、勿互撞。

### 三、来源章悬浮文案(去正确性背书 + 用词更白,R1 H1/L2;甲版分工不变)
悬浮只说"从哪来 + 出处状态",**不替内容正确性/适用性盖章**。这段文字即注释:
- 论文原文 —— 已关联到论文原文摘录;仍需结合你的模型和上下文核对。
- 据论文推导 —— 基于论文内容推导,非论文原文结论;请核对推导过程和具体数值。
- 领域默认 —— 论文未提供,这是该领域常见起点;不保证适合当前场景,可按需要调整。
- 工程设定 —— 论文未规定,这是为搭建模型选的工程取值;可按需要调整。
- 待你确认 —— 这条不是已确定的事实,需要你核对或选择。(**是否阻塞只由缺口 severity 表达,悬浮不写"确认后再继续"**;确认原因走正文,见五)
- 环境相关 —— 取值取决于你的 MATLAB 环境(版本、工具箱、硬件),请按实际情况填写。
- 你的选择 —— 这是需你决定的设计取舍,请结合你的目标选择。
- 出处待核 —— 论文中可能提及,但本次未能核到确切出处;请对照论文核实后再采用,别直接信。
- 来源待核(未知) —— 系统未能识别这条的来源类别,请以论文核对为准。
- 来源标注不一致 · 待核 —— 这条的标注前后不一致,系统未采信;请以论文核对为准。

删除:"可直接采用" / "推导可信" / "通常适用"。
**安全关键语义**("非原文结论" / "出处未核实")必须在**标签或正文可见**,不能只藏悬浮(R1 L1)。

### 四、逐条建议渲染
每条 detail:清洗后 `display_text`(见六)当首句 + 有效展示档来源章(见一) + `detail_kind` 图标/类别(**仅图标+分组,不做"照做 vs 留意"二分**,R1 H6)+ evidence 区(仅 A-原文/A-推导)。
- **detail_kind 只驱动图标与内容分组**(参数 / 选块 / 连线 / 配置 / 其他);可靠性只由来源章表达,不借 detail_kind 暗示可执行性。
- evidence 区(R1 M7 + R6 #4):**摘录(`excerpt`)为主要核查内容**,内部 ID(`document_id`/`paper_section_id`/`equation_id`)放次级;A-原文标"论文摘录",A-推导标"推导依据"(不叫"出处");多条 evidence 显"N 条依据"可展开全部,**不默认只显第一条**;无外部定位时写"已关联到论文摘录",**不写"已定位到具体出处"**;`figure_id` 将来出现走通用图表兜底。3b 自建 chip 组装(既有 formatEvidence 不够用)。

### 五、确认原因走正文(甲版,细化;R1 M3 + R6 #1)
- **凡带 `confirmation_reason_code` 的 detail**(含 `user_confirmation_required` 与 `document_claim_unverified`),原因**显在该条正文明显处**,来源 = `confirmation_reason_code` → 人话映射(**不显 raw `punt_reason_code`**)。
- 前端维护**单一集中映射模块**,镜像后端 `build_guidance_rules.py:54` 的 **12 值**,带 `{target}` 插值(用 detail 的 `target` 组装可读串,无 target 时以"该项"替 `{target}`)。12 值后端实际文案:

| code | 文案(`{target}` 由前端插值) |
|---|---|
| `missing_parameter_value` | 需要确认 `{target}` 的参数值;请查看可复现实验材料或本地模型设置。 |
| `library_variant_unresolved` | 需要确认 `{target}` 的 Simulink 模块变体;请查看本地库版本。 |
| `toolbox_unverified` | 需要确认 `{target}` 的工具箱可用性;请查看已安装 MATLAB 产品。 |
| `solver_unverified` | 需要确认 `{target}` 的 solver 选择;请查看复现环境。 |
| `sample_time_unverified` | 需要确认 `{target}` 的采样时间处理;请查看本地模型设置。 |
| `connection_detail_missing` | 需要确认 `{target}` 的连接细节;请查看源模型图。 |
| `initial_condition_unverified` | 需要确认 `{target}` 的初始条件处理;请查看本地模型设置。 |
| `switching_frequency_unverified` | 需要确认 `{target}` 的开关频率处理;请查看本地模型设置。 |
| `simulation_time_unverified` | 需要确认 `{target}` 的仿真时长处理;请查看本地模型设置。 |
| `configuration_unverified` | 需要确认 `{target}` 的配置细节;请查看本地模型设置。 |
| `document_evidence_unverified` | 需要确认 `{target}`;该条声称的论文依据未能核实。 |
| `engineering_decision_unverified` | 需要确认 `{target}` 的工程选择;请查看本地模型设置。 |

- **未知 code** → "系统未能识别具体确认原因,请按上文内容核对"(**不重复"需确认"**,R1 M3)。
- 该映射模块以 12 值联合类型/冻结清单做**穷尽测试**,防双份表漂移。
- **通用 basis 悬浮里永不出现确认原因**。

### 六、display_text 清洗(白名单剥 + basis 一致 + 尾部去码;R1 M4 + R6 #2)
- **只剥"行首固定前缀 + 中文全角冒号(：)"**,8 种(每种绑一个 basis):
  `论文明确给出：` / `由论文信息推导：` / `领域默认（非论文）：` / `本方案选择（可改）：` / `需确认你的环境：` / `需你决定：` / `暂无法确定：` / `论文依据未核实（未采用）：`。
- **basis 一致才剥**(R1 M4):仅当"前缀隐含 basis == 当前规范化 basis"才剥;不一致 → 保留全文,有效档降 D"来源标注不一致 · 待核"(见一)。
- **匹配不上白名单 → 原样保留全文**(旧产物约 392 种自由开头,一律不动)。
- **只删尾部固定原因段** `；原因：<punt_reason_code>。`(**全角 ；：。**,覆盖标点变体/无终止符);**不做通用 snake_case 清扫**、**不删方括号**。真实数据里 `P_0`/`G_ik` 是内容名、`[1, D/(2H)]`/`[0,1,2,10,20]` 是数组/公式,**必须保留**。
- **清洗后正文为空** → 显"此条建议内容未完整生成",**保留来源章 + 类别**,不返 null、不产被过滤的空行。

### 七、缺口清单(去硬判 + 显式待确认;R1 H5 + M6)
区块标题:**「待核对的缺口 · 需你逐条确认」**(gap.basis 恒 `user_confirmation_required`,故区块显式带"待你确认"语义)。每条 gap:
- 首句 = `display_text`;`target`/`obligation_kind` 已填(当前 v2 全填)时可显更有指向的一句,旧产物 `null` 时 fallback 显 `display_text` 原句。
- 轻重标签:`blocking` → **「关键待确认」**(不写"必须补 / 搭不起来");`warning` → **「建议核对」**。悬浮可写"系统当前将其标记为关键,可能影响搭建",**不断言"模型一定无法搭建"**。
- 只对真实 4 个 `gap_kind` 做措辞/图标;其余类型走通用 + 兜底。

### 八、密度与去重(R1 M6)
- **每步计数摘要**:"建模建议 N 条 · 待核对缺口 M 条"。
- 步内按 参数 / 连线 / 配置 / 选块 分组,**不截条目**。
- **相同 `target + obligation_kind` 的 detail 与 gap 放同一小组**,分别保留"说明"与"缺口"角色,**不静默去重**。
- 允许折叠,但必须显总数 + 明确"展开全部",**不得默认只取前 N 条**。
- 页顶加**只含计数 + 跳转锚点**的汇总条(不复制正文)。
- 终态形态:**步骤内联主体 + 页顶汇总导航 + orphan 兜底区**(非独立 section 单选)。

### 九、guidance 显示不被 build_steps 拦(R1 H4)
- **`build_guidance` 非空就显 guidance,独立于 build_steps null-gate**。
- build_steps 有步骤 → details/gaps 按 `step_id` 内联到对应步骤 + orphan 区收未匹配。
- build_steps 为 null(走 `block_recommendations` fallback)→ **全部 guidance 进全局/orphan 区,照样渲染**。
- 实现:确保 guidance 区在结构化与 fallback 两分支都渲染;若需在 `PaperResultPage` 插入,**最小化、不动横幅:157、不动 regeneration UI**,并验 task508/task522d1 仍绿。

### 十、空状态按 status 分文案(R1 M5)
按 `guidance_status`(恒存在)分,与 3a 横幅语义一致,**不把技术失败伪装成正常无内容**:
- `no_document_basis` → 未从论文中形成可定位的逐条建议;现有搭建路线仍可参考。
- `not_generated` → 逐条建模建议尚未生成。
- `generation_failed` → 本次逐条建议未生成成功,现有步骤已保留。
- `stale_pending_regeneration` → 建议基于旧版本,等待更新。
- `generated` 但 details/gaps 全空或全不可归组 → 指导数据不完整。

### 十一、视觉隔离步骤原始章(R1 M1)
不改 `SourceBadge` 本体,但做隔离:步骤原有 evidence 章旁标"步骤原始依据";guidance 区前加分隔 + 一句"以下建议分别以各自来源章为准";**绿色背景/边框不得包住整个 guidance 区**;每条来源章置于正文前或标题紧邻处,不放行尾弱化。

## ★ 反抑制红线(与 538 命根同源,验收专测)
1. **数量守恒**:可见条目数 == 输入 details+gaps 数(除 C 类安全剥离);分组/折叠/orphan 只是布局,**不减条目、不静默去重、不默认只显前 N**。
2. **每条输入 → 恰好一个可见条目**;单条 malformed 只降级该条,**不波及兄弟条目**(render 错误边界隔离到条目级)。
3. 白名单剥不动 → 原样显全文;未知/legacy `basis`/`gap_kind`/`severity` → 兜底渲染(非绿);字段空 → 退到更粗可显信息。
4. **非数组 ≠ 正常空态** → 显"部分指导数据格式不完整",不伪装成"没内容"。
5. 清洗后正文为空 → 显"此条建议内容未完整生成",保留章 + 类别,不返 null。
6. guidance 显示不被 build_steps null-gate 拦(见九)。
7. **orphan 区固定存在**:未匹配 `step_id` / 无 step / `plan`|`subsystem` scope / build_steps null → 页末"未能归入具体步骤的建议 · 全局待确认"(R6 证:stale 快照会产生 step 缺失 gap)。
8. 空状态是按 status 的明确文案,不是空白页。
9. **禁止无提示的 line-clamp / 固定高度裁剪 / 只显前 N**。

一句话:当初"拿不准就清掉",538 之后"**拿不准也得显 + 标诚实**"。没有"数量守恒",红线只证"不崩"、证不了"不吞"。

## 拆法(两块)
- **substrate helper(新文件,纯数据纯函数,好测)**:有效展示档计算 / basis→{标签,档,悬浮} + legacy 别名 + 未知兜底 / `confirmation_reason_code`(12)→人话 + `{target}` 插值 + 未知兜底 / display_text 前缀白名单剥离(basis 一致才剥)+ 尾部原因段去除(全角)/ gap `severity`→标签 / `detail_kind`→图标类别 / evidence chip 组装 / details+gaps 按 `step_id` 分组 + orphan 分拣 / 数量守恒计数。
- **渲染(主要 `BuildSteps.tsx` + 极小 `PaperResultPage` 插入)**:步骤内联 + 每步计数摘要 + 分组 + orphan 区 + 页顶汇总导航 + 空状态 + 悬浮三触发(鼠标/触屏/键盘,badge 为可聚焦控件、Esc/点外关闭、有可访问名)。
- ★ **`BuildSteps.tsx` 代码里禁止出现 task508 smoke 命中词** `fallback` / `legacy` / `degraded` / `overview`(R6 #5):别名/兜底/清洗逻辑全放 substrate helper,`BuildSteps` 只 import + render;别名概念在代码里换不含禁词的命名(如 `retiredAlias`)。
- ★ **不改诚实横幅**(`PaperResultPage:157`,task522d1 守)、**不动 regeneration UI**、**不加 regeneration `console.*`**(task522d1 守)。

## 不做(明确排除)
- ❌ 参数依赖 UI(`input_fact_refs` 全空)。
- ❌ 改后端 / schema / 版本(basis/gaps 已由 block 2 盖)。
- ❌ 碰 `SourceBadge` 或两调用点。
- ❌ 动 BuildSteps 既有内部数组 normalize(`:99-108`/`:128`,真白屏点)。
- ❌ 模型生成 / .slx / 通电 MATLAB。
- ❌ 调参/调收敛动态指导(另立项)。

## 验收标准(确定性测试)
- **有效展示档**:八行矩阵逐条命中对;`document_claim_unverified` 与任何带 `confirmation_reason_code==document_evidence_unverified` 的条目 → D 警示;extracted/derived 无可展示 evidence → 非绿"来源信息不完整";未知 basis → D;**只有 A-原文显肯定绿**。
- **原文/推导分离**:derived 非绿、章标"据论文推导 · 非原文结论"、证据区叫"推导依据"。
- **来源章文案**:无"可直接采用/推导可信/通常适用";"非原文结论"/"出处未核实"在标签或正文可见。
- **确认原因**:12 值映射对 + `{target}` 插值 + 未知 code 诚实兜底(不重复"需确认");**永不显 raw `punt_reason_code`**;`document_claim_unverified` 也走原因映射;通用悬浮永不含确认原因。
- **清洗**:8 全角前缀 + basis 一致才剥;不一致 → 不剥 + 降 D;非白名单原样留;尾部 `；原因：<code>。`(全角/无终止符变体)被删;`P_0`/`G_ik`/`[1, D/(2H)]`/`[0,1,2,10,20]` 不误剥;正文含正常"原因："与正常参数名不误删;清洗后空 → 占位不返 null。
- **缺口**:标题带"需你逐条确认";`blocking`→"关键待确认"(无"搭不起来")/`warning`→"建议核对";`target` 填显具体、null fallback 显 `display_text`;一步多缺口(样本 25)不崩;detail-gap 同 target 不静默去重。
- **反抑制/数量守恒**(重点):输入 N 条 → 可见 N 条;未匹配 step / plan|subsystem scope / build_steps null / stale 快照缺 step 的 gap → 全显在 orphan 区;单条 malformed 只降级自身;非数组 → "格式不完整"非空态;无折叠吞条目。
- **空状态**:按 5 种 status 各显对应文案;generated 但空 → "指导数据不完整"。
- **evidence**:摘录为主、ID 次级;多条显"N 条依据"可展开、不只第一条;无外部定位不写"已定位到具体出处"。
- **回归 + smoke**:`SourceBadge` 两调用点不变;BuildSteps 内部 normalize 不变;**task508**(`structuredGate` 精确串 + `BuildSteps.tsx` 无禁词)全绿;**task522d1**(横幅文案原样 + 无 regeneration `console.*`)全绿;既有 build_steps/fallback/evidence 路径不变。
- **部署兼容(局部,完整矩阵归 538-2b)**:新前 + 旧后(旧后未发 gaps/某些 basis)不崩。

## R6 可落核结论(已并入)
无 P0 阻碍,可照 `5d13a11` 落地;锚点未漂移。已并入的纠错:确认原因码 **12 值**(非 5)、真实分隔为**中文全角**、`document_claim_unverified` **也带 `confirmation_reason_code`**、`BuildSteps.tsx` **避开 smoke 禁词**、stale/旧数据 **需 orphan 兜底**。实施前照本卡即可,无需二次可落核。

## 给 Codex 的实施提示
- 纯前端 additive;不改后端/schema/SourceBadge/既有 normalize;`BuildSteps.tsx` 不出现 `fallback`/`legacy`/`degraded`/`overview`;不动横幅与 regeneration UI。
- substrate(静态映射 + 纯函数,含有效展示档计算)先行、好测;渲染后置。
- 一切"没见过/空/剥不动/未匹配 step"**照显 + 兜底 + 计数守恒**,绝不吞、绝不白屏——命根,验收专测。
- 诚实硬线焊死:只有 A-原文显肯定绿;derived 非绿;无 evidence 的有据降级不绿;`document_evidence_unverified`/`document_claim_unverified`/未知 basis → D;确认原因走正文用 12 值人话表(带 `{target}`)、永不露 raw code;通用悬浮永不含确认原因。
