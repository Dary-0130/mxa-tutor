# mxa-tutor Roadmap v2:paper-to-model 复现副驾

> **状态**:方向 pivot 后的主线路线图(决策 22 v1.2 配套产物)
> **日期**:2026-06-15
> **关联宪法**:v3.0
> **关联决策**:`docs/decisions/20260615-22-direction-pivot-paper-to-model.md`
> **取代**:`mxa-tutor-update-roadmap.md`(v1,未入仓产品草案;TASK 编号占用作废,产品思考已被本文 § 1 继承,仅历史参考)

---

## 0. 一句话路线

paper-to-model 副驾按**可信度阶梯**推进,不按用户身份倒推堆功能:

```text
v0.1  单主资料 → 模型搭建路线图(稳交付三层 + 电机短路验证)
v0.2  多文档融合 + 图片 OCR + 扩子类(控制 / 信号处理)
v0.3  逆向调参(A2a)+ MATLAB Engine 评估
v1.0+ 截图理解 / 报告答辩 / 课题组工作区 / 平台化(沿用 v1 长期路线)
```

核心原则(沿用 v1 § 25 + 决策 22 R1 降级):

> 先让系统可靠地"据资料给出搭建路线",再追求"自动生成成品"。
> 每升一级,证据链更强,而不是只让"输出更长"。
> 副驾不替代:帮用户完成复现的主要认知工作,精确搭建 / 跑通 / 收敛由用户自己来。

---

## 1. 与 v1 的关系(为什么需要 v2)

`mxa-tutor-update-roadmap.md`(v1,2026-06-05)是 MCS 之后的长期路线草案,把 paper-to-model 放在 **2.0 阶段**(博士生论文复现助手),前面要先走 0.2-1.5 的代码理解 / 参数图谱 / 报告答辩 / 研究生工作流。

决策 22 pivot 把 paper-to-model **提前为新主线**(不再等 2.0)。因此:

- **v1 的版本编号(0.2 / 0.3 / ... / 3.0)和 TASK 编号(501-1007)作废** — paper-to-model 用新的 v0.1 / v0.2 / v0.3 编号 + TASK-501 起新分段
- **v1 的产品思考保留参考价值** — v1 § 14(2.0 论文复现助手)的数据模型建议(Paper / PaperSection / PaperEquation / ReproductionPlan / EvidenceChain 等)、§ 17 跨版本架构原则、§ 20 数据隐私路线、§ 23 风险清单,v2 继承并细化
- **v1 未入仓,不入仓** — v1 仅在项目知识库(从未进 git 仓库,文件头自注"若要入仓建议单独走 PR"),其 Phase 2-4 长期思考已被本文继承;实施 v0.2+ 时回看 v1 内容需从知识库 / 历史对话获取

---

## 2. 当前基线(决策 22 PoC 实测)

paper-to-model 不是从零起步。决策 22 § 4 PoC 已实测两个电机仿真工程包,确立 v0.1 的真实边界:

### 2.1 已验证(v0.1 稳交付锚点)

- 从资料 / 报告(docx 学生实验报告类)抽取"模型搭建配方"可行(5MW / 平衡节点 / 0.2s 故障 / ode15s / 1s 等纯文本配方)
- 形成 plan 层"搭建路线图 + 库选型建议 + 参数对应表 + 子系统拆分"可行
- 范围:电机 / 电力电子类(SimPowerSystems 路线)

### 2.2 未验证(v0.1 实施期 + v0.2 验)

- 纯论文 PDF → 状态方程 → `.m` 骨架的稳定链路(决策 22 § 4.7,异步机两篇 PDF 未深读)
- 控制 / 信号处理类资料(可能不用 powerlib、搭法不同)
- 多文档融合
- 图片中参数自动抽取(决策 22 § 4.8,docx 暴露参数常在图片里)

### 2.3 三个定生死的发现(决策 22 § 4.4,决定 R1 降级)

1. ground-truth 模型用 SimPowerSystems 专业库,非基础 Simulink block
2. 论文图示搭法 ≠ 实际成品搭法(论文给物理方程 / 框图,不是接线图;人复现做了大量论文没写的工程决定)
3. `.slx` 自动生成不可靠(实测非推测)→ **不承诺打开即跑成品**

---

## 3. v0.1:单主资料 → 模型搭建路线图

### 3.1 目标

学生上传**单份主资料**(论文或报告 PDF/docx),系统输出稳交付三层:论文理解 + 模型搭建路线图 + 调参指导。不承诺成品 `.slx`。

**资料入口领域范围**(决策 22 § 1.5,字面映射 6 类 project_type):`control_system` / `signal_processing` / `power_electronics` / `communication` / `motor_control` / `new_energy`。**`general` 仅工程入口兜底,不作资料入口主动承诺**;资料落 `general` 时拒绝并提示用户选具体类型。架构与枚举 v0.1 即接受 6 类(验收锚点先做电机短路,见 § 3.6;控制 / 信号处理类样本验证留 v0.2,见 § 4.2)。

### 3.2 前置硬门槛(决策 22 § 10.4,TASK-501 前必须完成)

> **口径锁定**(GPT 联审 P0):本节 5 项 = paper-to-model **开门 chore**,**不含 02 delta**。02 v3.0 delta 是**本 pivot chore PR 的同步文件**(决策 22 § 6.2 / § 10.3,与决策 22 / 宪法 v3.0 / roadmap v2 同一个 5 文件 PR,由 Codex 执行期对照真实 02 写),**不计入开门 chore 5 项**。

**本 chore PR 已含同步项**(非前置门槛):02 架构总览 v3.0 delta(资料入口数据流 + PaperSpec / PaperGraph / ModelGenerationPlan / TuningSuggestion 占位签名 + features/paper 边界,不冻结字段)。

**paper-to-model 开门 chore 五项前置硬门槛**(派任何 TASK-501 前必须先入仓,任一未完成 = TASK-501 封禁):

| 项 | 内容 |
|---|---|
| 1 | 06 输出契约新增 PaperSpec / ModelGenerationPlan / TuningSuggestion schema(D1-B 三层同源 + freeze test) |
| 2 | MissingParameterPrompt + EvidencePack 双源契约:`source: document_extracted` / `user_supplied` |
| 3 | 04 工程规范文档上传安全:magic sniffing / PDF·docx parser sandbox / 解析库审批 / 恶意 fixtures / 外链宏 OCR 策略 / raw 文档脱敏(决策 22 § 10.4 第 3 项加硬) |
| 4 | v0.1 产品文案与对外口径(不自动生成 .slx + 图片参数需用户补充 + 不承诺运行结果) |
| 5 | 评测准入(≥1 资料→路线图样本 + ≥1 缺参数→补充样本) |

> 五项作为 paper-to-model 开门 chore(预计 1-3 个 task),完成顺序自由;全部 ✅ 前 TASK-501 封禁。
>
> **门槛深度注**(GPT P2 防卡死):第 1 项 06 契约门槛是**最小可用 schema + freeze test 占位**,占位字段允许后续按 D5 流程演进,**不要求一次性冻结全部最终字段**;避免开门 chore 膨胀成大实现。

### 3.3 v0.1 新增能力

- **文档解析**:PDF / docx → 结构化(摘要 / 公式 / 参数表 / 图表位置 / 伪代码)
- **PaperSpec generator**:资料 → 结构化论文规格(决策 22 § 5.4)
- **ModelGenerationPlan generator**:规格 → 模型搭建路线图(需要哪些 block / 库选型 / 参数对应 / 子系统拆分)
- **`.m` 脚本骨架生成**(尽力交付):状态方程 → 代码,经 TASK-103 解析器回读验证语法
- **结构一致性校验**(决策 22 § 5.4):检查 plan 中 block / 参数 / 公式 / `.m` 骨架 / 证据引用是否闭合;**不声称可运行 / 可收敛 / 可复现**
- **MissingParameterPrompt**(决策 22 § 4.8):识别疑似缺失参数 → 用户补数值 / 单位 / 来源 → 标 `user_supplied`,与文档证据分开
- **调参建议引擎**(A2c + A2d):从语境推荐调参方向 + 讲解调参影响

### 3.4 v0.1 复用 MCS 资产(决策 22 § 5.1,Codex R6 实测分性质)

**真直接复用**:解析器(102/103,生成物回读)/ SQLite 存储(204)/ 中文化(206)/ embedding + 向量存储(301/302)/ async + logger 不变量(决策 11)

**框架 / 理念复用,需新建对等实现**:
- chunker(303/304)— 现状 8 种工程结构 source type 无 document;论文 PDF/docx 切 chunk + 新 SourceType 需新增
- Citation Enforcer(307)— 思路复用
- EvidencePack(308)— 受决策 21 boundary 约束,paper feature 不 import explanation 私有结构,在 core/ 公开 contract 共享或新建
- TeachingUnit cache 四态(310)— 同构借鉴做"复现计划 cache",新建对等 store
- ProjectGraph(107)— 框架借鉴做 PaperGraph 或扩展 paper 类节点
- OverviewService(203)— service 五步校验 + retry + cache 框架借鉴,新建 PaperPlanService

**仅 zip 工程成立,需新增文档路径**:上传沙箱 + API(104/202)— 现状 PDF skip / docx other,文档安全需新建(前置硬门槛第 4 项)

**红线(决策 22 § 5.2)**:禁止修改 ProjectOverview / overview_schemas.py / project_overview.yaml;新增 paper 输出新建 `features/paper/*` + `core/domain/paper_*.py`,不 import `features/overview/overview_schemas.py`。

### 3.5 v0.1 数据模型(占位,具体字段由 06 契约 + 首 task 落地)

继承 v1 § 14.4 论文复现数据模型思路,v0.1 收窄:

```text
PaperSpec          论文结构化规格(摘要 / 公式 / 参数表 / 图表位置 / 伪代码)
PaperGraph         论文-模型对应图(节点:段落 / 公式 / 参数 / 图表;边:引用 / 推导 / 对应)
                   或扩展 ProjectGraph 加 paper 类节点 —— 二选一以 02 v3.0 delta 最终拍板为准,
                   TASK-501 派单前不得保留二选一(GPT 联审 P1)
ModelGenerationPlan 模型搭建路线图(block 清单 / 库选型 / 参数对应 / 子系统拆分 / .m 骨架)
TuningSuggestion   调参建议(方向 + 影响讲解)
MissingParameterPrompt 缺失参数清单(用户补充入口)
EvidenceRef        证据引用(source: document_extracted / user_supplied 双源)
```

### 3.6 v0.1 验收标准

- 给单份电机短路类资料,能生成"模型搭建路线图"(block / 库选型 / 参数对应 / 子系统拆分)
- 关键结论有 evidence,文档证据 vs 用户补充来源分开
- 缺失参数能列出并让用户补充,补充后 plan 更新
- `.m` 骨架(若生成)经解析器回读语法正确
- **明示不承诺 `.slx` 成品 / 不承诺运行结果**
- eval:≥1 资料→路线图样本完整跑通 + ≥1 缺参数→补充样本跑通

### 3.7 v0.1 不做

- 不承诺成品 `.slx`(决策 22 § 1.1)
- 不承诺可运行 / 可收敛 / 可复现
- 不做多文档融合(v0.2)
- 不做图片 OCR(v0.2)
- 不做逆向调参(v0.3)
- 不接 MATLAB Engine(v0.3+ 评估)
- 不接 CAJ
- 不接电气 / 控制 / 通信 / 信号处理以外领域

---

## 4. v0.2:多文档融合 + 图片 OCR + 扩子类

### 4.1 目标

从单主资料升级到资料包(论文 + 参考文献 + 报告异构多文档);补图片参数抽取;验证泛化到控制 / 信号处理类。

### 4.2 新增能力

- **多文档融合**(决策 22 § 2.2 M2):异构多文档 → 统一 PaperSpec;冲突 / 重复 / 互补处理
- **图片 OCR**(决策 22 § 4.8 选项 ii):图片中参数 / 公式 / 框图抽取,替代 v0.1 的纯用户补充
- **扩样本验证控制 / 信号处理类路线图可用性**(非"v0.1 不认控制类" — v0.1 架构与枚举已接受 6 类,见 § 3.1):控制类(可能用基础 Simulink block 而非 powerlib)/ 信号处理类的资料抽取 + 路线图质量验证;确认泛化工程是否成立,不成立则该子类收窄回电机类
- **深读 PDF 链路验证**(决策 22 § 4.7):异步机两篇 PDF "论文方程 → 状态方程 → `.m` 骨架"链路稳定性

### 4.3 验收标准

- 能融合 2-3 篇异构资料生成统一路线图
- 图片参数抽取准确率达标(具体阈值 v0.2 立项定)
- 控制 / 信号处理类样本路线图可用(各 ≥1 样本)
- 多文档来源可追溯(哪个结论来自哪篇)

### 4.4 不做

- 不做逆向调参(v0.3)
- 不接 Engine

---

## 5. v0.3:逆向调参 + MATLAB Engine 评估

### 5.1 目标

补 A2a 逆向调参(用户给目标曲线 → 系统反推参数方向);评估是否接 MATLAB Engine。

### 5.2 新增能力

- **逆向调参**(A2a,决策 22 § 1.2):目标曲线 / 指标 → 反推参数调整方向;明示是建议非保证
- **MATLAB Engine 评估**(决策 22 § 1.6 + v1 § 14.6):授权 / 运行环境 / 用户代码执行风险 / 沙箱 / 超时 / 配额 / License 成本单独评审;**不默认接入**

### 5.3 Engine 推荐顺序(沿用 v1 § 14.6)

```text
先支持用户上传运行结果(截图 / CSV / MAT)
再支持结果解释
最后才考虑隔离运行 MATLAB
```

### 5.4 验收标准

- 逆向调参给出可追溯的参数调整建议 + 明示不保证
- Engine 若接入,单独完成沙箱 / 超时 / 配额 / 脱敏 / 恶意代码防护评审

---

## 6. v1.0+ 长期路线(沿用 v1 + 决策 22)

paper-to-model 跑通后,衔接 v1 的长期路线(版本号重新对齐,不沿用 v1 原编号):

- **截图与结果理解**:Scope 波形 / 结果曲线 / CSV / MAT 解释(v1 § 10)
- **报告 / 答辩辅助**:工程说明 / 参数表 / 答辩问题生成 / Markdown 导出(v1 § 9)
- **课题组工作区**:团队空间 / 权限 / 多工程库 / PostgreSQL + pgvector 迁移 / 私有部署(v1 § 15)
- **科研 / 工业平台化**:多模型图谱 / 工程质量检查 / 领域插件 / 可插拔 parser·analyzer·provider(v1 § 16)

---

## 7. 跨版本架构原则(沿用 v1 § 17 + 决策 22 红线)

### 7.1 三层不混(v1 § 17.1)

```text
Parser 还原(工程 / 论文)
中间层组织结构(ProjectGraph / PaperGraph)
LLM 讲 + 生成 plan
```

不让 LLM 直接猜结构。新增能力先进结构化层,再进讲解 / 生成层。

### 7.2 paper 不污染 MCS 契约(决策 22 § 5.2 + 决策 21)

- `features/paper/` 不 import `features/overview/` / `features/explanation/` 私有结构
- 跨 feature 共享只在 `core/` 公开 contract 层(沿用决策 18 ProjectOverview 下沉模式 / 决策 21 EvidencePack boundary)
- 禁止修改既有 MCS schema / service / prompt
- PaperGraph vs ProjectGraph 扩展二选一:以 02 v3.0 delta 拍板为准,TASK-501 派单前必须固化为一个方向,不留二选一(GPT 联审 P1)

### 7.3 所有回答可追溯(v1 § 17.3 + 决策 22 双源)

证据类型可新增(paper_section / equation_id / figure_id / user_supplied),但不取消证据原则。`document_extracted` 与 `user_supplied` 严格分开。

### 7.4 不确定是能力非失败(v1 § 17.4)

```text
有证据 → 回答
弱证据 → 保守回答
无证据 → 不确定
缺图片参数 → 提示用户补充(v0.1)/ OCR(v0.2)
需运行 → 要求用户提供结果(不自己跑,除非 v0.3 Engine 评审通过)
```

### 7.5 升级不破接口(v1 § 17.5)

TextProvider / Retriever / ProjectStore / 向量存储接口尽量稳定;换模型 / 换实现只改 adapter。

---

## 8. 评测体系(沿用 v1 § 18 + 决策 22 § 10.4 准入)

### 8.1 v0.1 重点

- 资料解析准确率(摘要 / 公式 / 参数表抽取)
- 模型搭建路线图可用性(人工评分:block / 库选型 / 参数对应 / 子系统拆分是否合理)
- 证据引用覆盖率 + 双源区分正确性
- 缺失参数识别准确率
- `.m` 骨架语法正确率(解析器回读)
- 幻觉率(是否编造资料中没有的参数 / 结论)

### 8.2 v0.2+ 重点

- 多文档融合一致性
- 图片 OCR 抽取准确率
- 扩子类(控制 / 信号处理)路线图可用性
- paper-to-project mapping 准确率(v1 § 18.4)

---

## 9. 风险清单(沿用 v1 § 23 + 决策 22 新增)

| 风险 | 影响 | 控制方式 |
|---|---|---|
| "paper-to-model" 命名被当成"自动生成模型" | 用户 / 销售越界承诺 | 决策 22 § 1.1 对外口径硬约束;前端 / 文案禁用"自动生成"表述 |
| `.slx` 自动生成不可靠 | 承诺打不住 | R1 降级三层承诺;不承诺成品 |
| 图片参数抽取漏 | 路线图参数不全 | v0.1 MissingParameterPrompt 用户补充;v0.2 OCR |
| 文档上传安全(恶意 PDF/docx) | 安全风险 | 前置硬门槛第 4 项:sandbox / magic sniffing / 不执行不联网 |
| paper feature 改坏 MCS 契约 | 前端 / 评测 / RAG 下游崩 | 决策 22 § 5.2 红线;决策 21 boundary;自动升 R2 守门 |
| 泛化工程不成立(控制类搭法不同) | v0.2 扩子类失败 | v0.2 各子类 ≥1 样本验证;不成立则收窄回电机类 |
| 多文档融合复杂度爆炸 | v0.2 范围失控 | v0.1 先收窄单主资料,v0.2 再做融合 |
| 太早接 MATLAB Engine | 安全 / 成本失控 | v0.3+ 单独评审,不进 v0.1/v0.2 |
| 复用 MCS 资产过乐观 | 实施返工 | Codex R6 已实测复用分性质(决策 22 § 5.1);框架复用需新建对等实现 |

---

## 10. 发布门槛

### 10.1 v0.1 门槛

- 单份电机短路类资料 → 完整路线图跑通
- 资料入口领域校验:接受 6 类 project_type 枚举,`general` 资料入口拒绝(决策 22 § 1.5)
- 证据双源区分正确(`document_extracted` / `user_supplied`)
- 缺参数补充流程跑通
- 明示不承诺成品 / 运行结果
- eval ≥1 资料→路线图 + ≥1 缺参数→补充样本

### 10.2 v0.2 门槛

- 多文档融合 ≥1 样本
- 图片 OCR 准确率达标
- 控制 / 信号处理类各 ≥1 样本路线图可用

### 10.3 v0.3 门槛

- 逆向调参建议可追溯
- Engine 若接入,安全评审完成

---

## 11. 近期行动(决策 22 落地后)

1. **本次 chore PR**:决策 22 + 宪法 v3.0 + 本 roadmap v2 + 02 v3.0 delta + 03 索引(5 文件;v1 未入仓不在范围)
2. **paper-to-model 开门 chore**(决策 22 § 10.4 五项前置硬门槛,1-3 个 task):06 三套契约 / MissingParameterPrompt + EvidencePack 双源 / 文档上传安全 / 产品文案与对外口径 / 评测准入
3. **TASK-501 系列**:文档解析 → PaperSpec → ModelGenerationPlan → 调参建议(五项前置硬门槛全 ✅ 后派单)

---

**版本**:v2.0
**日期**:2026-06-15
**作者**:Claude(架构师,第四十一任)
**关联宪法**:v3.0
**关联决策**:`docs/decisions/20260615-22-direction-pivot-paper-to-model.md`(v1.3.1)
**取代**:`mxa-tutor-update-roadmap.md`(v1,未入仓草案,不入仓)
**入仓**:chore PR(5 文件之一,新建 `docs/roadmap/mxa-tutor-v2-paper-to-model.md`);**当前为草稿,PM 暂不入仓**