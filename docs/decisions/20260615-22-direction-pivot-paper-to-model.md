# 决策 22:方向 pivot — paper-to-model 副驾(MCS 二合一)

> **已触发升仪标注**(决策 12 v0.3.1 工艺纪律):本任 K_28a 单任密集触发约 7 次(项目首次单任高密度,GPT R1 抓 4 + Codex R6 抓 2 + GPT 联审抓 1),触发决策 12 v0.4 § 4.1 #6 反思(规则有效但起稿源头不充分);v0.5 协议候选累积至第 6 项。**本任起反例库改趋势记账**(不再逐位累加,理由见 § 9)。详 § 9。

## 背景

mxa-tutor 项目自 2026-06-01 立项(决策 20260601-01 / 02:报错救火 → 工程导览;桌面 → Web),经四周开发,MCS 主线进度 31/35 task,Week 4 剩 TASK-404 激活码 / TASK-405 部署 / TASK-406 内测,具备上线收费条件。

第 39 任完工 TASK-310 PR #1 / #2 / chore PR(前置 commit `562946d`)后,PM 重新审视产品定位,核心判断:

1. **MCS "工程导览 + 问答" 覆盖学生 A 类(本科)需求,但天花板有限** — 学生看懂手上工程的问题已经被 MCS 解决,但用户更迫切的下一步("我有论文 / 资料,想搭出 Simulink 模型来复现")没有人接
2. **paper-to-model 是 mxa-tutor 真正的差异化壁垒** — 通用 LLM 无法把论文方程精确映射到 Simulink 库元件 + 工程参数;mxa-tutor 三周建的 ProjectGraph + ProjectOverview + EvidencePack + TeachingUnit 基础设施,正是 paper-to-model 需要的
3. **MCS 资产不浪费** — 工程上传 / 解析 / 嵌入 / 向量 RAG / Citation Enforcer 整套基础设施,paper-to-model 仍然需要(详 § 资产复用度评估)

故 PM 主导本次方向 pivot:从"工程导览 + 问答(MCS)"主线,扩展为 **"据资料(论文 / 文献 / 报告)辅助生成仿真模型 + 指导调参"** 主线,二者并存(MCS 不废弃)。

本决策固化 40 任完成的十几轮拍点收束 + 迷你 PoC 实测的全部结论。

## 一句话决策

**mxa-tutor 主线从"工程导览 + 问答"扩展为"二合一产品:上传工程 或 上传资料二选入口";paper-to-model 副驾分三层承诺(稳交付 / 尽力交付 / 不承诺),帮用户完成复现的约 70%,不替代用户精确搭建 + 跑通的 30%。**

---

## 1. 方向七拍(A / B / C / D / X)

### 1.1 A1d → R1 降级(关键)

副驾分三层承诺:

| 层 | 承诺 | 内容 |
|---|---|---|
| **稳交付** | ✅ 必须做到 | 论文结构化摘要 + 公式 / 参数表抽取 + 物理含义讲解 + 模型搭建路线图(需要哪些 block / 库选型 / 参数对应 / 子系统拆分) |
| **尽力交付** | ⚠️ 努力但不保证 | `.m` 脚本骨架(状态方程 → 代码) |
| **不承诺** | ❌ 明示不做 | 打开即跑的完整 `.slx` 成品 |

R1 降级理由:迷你 PoC 实测(详 § 4)显示论文图示搭法 ≠ 实际成品搭法,`.slx` 自动生成不可靠。

**对外口径硬约束**(P0-4 防误导):对外不使用"自动生成 Simulink 模型 / paper-to-model 一键生成"表述;v0.1 对外口径统一为"复现路线图 / 模型搭建副驾 / 参数对应说明",不是"模型成品生成器"。前端文案 / 销售物料 / API 说明 / README 全部按此口径,违反即按 § 8 回滚要求处理。

### 1.2 A2c + A2d:调参方向 + 调参讲解(不做逆向调参)

- ✅ A2c:从语境推荐调参方向(用户描述场景 → 系统建议调哪个参数)
- ✅ A2d:调参影响讲解(用户改了参数 → 系统讲清楚物理意义)
- ❌ A2a:逆向调参(用户给目标曲线 → 系统反推参数)— 留 v0.3+

### 1.3 B2:新增 C 类不丢 A / B 类

- A 类:本科生(MCS 已服务)
- B 类:研究生(MCS 已部分服务)
- C 类:博士 / 复现用户(本次 pivot 新增主线)

三类并存,不互斥。

> **注脚**(GPT R1 P1-9 深度分层洞察吸收):C 类按身份是 40 任 B2 拍板主轴(本决策沿用);按**需求深度**可再分两层 — **C1**:论文 / 报告复现用户(v0.1 服务范围,稳交付三层);**C2**:研究型深度复现用户(多文档 + 公式严谨 + 可追溯,v0.2+ 服务,对应 § 2.2 多文档融合 + § 4.7 PDF 深读链路)。C1 / C2 是 v0.1 / v0.2 范围划分的辅助轴,不替换身份分层主轴。具体落点留 roadmap v2。

### 1.4 C:暂不收费,做完再议

故 TASK-404 激活码不做(F3 冻结)。

### 1.5 D1a:领域范围

v0.1 资料入口接受范围**字面映射既有 6 类 project_type**(避免和现有 classifier / UI / 06 契约漂移):

`control_system` / `signal_processing` / `power_electronics` / `communication` / `motor_control` / `new_energy`

`general` 仅作工程入口兜底,**不作资料入口主动承诺**(资料 PDF 落 general 直接拒,提示用户选具体类型)。

不接其他工科(机械 / 流体 / 化工等),与 MCS 教材语境一致。

### 1.6 D2b:MATLAB Engine

v0.1 不接 MATLAB Engine。理由:授权、运行环境、用户代码执行风险 v0.1 未评估,2.0 后单独评审(沿用 mxa-tutor-update-roadmap.md § 14.6)。Engine 集成留 v0.3+(PM 内部表述"万一 matlab 找我麻烦")。

### 1.7 X:paper-to-model 为新主线

优先级最高,独占资源。MCS Week 4 剩余 task 处置见 § 3.1 F3。

---

## 2. 形态四拍(E / M / O / K)

### 2.1 E2:二合一产品

主入口"上传工程 或 上传资料二选一":

- 工程入口:沿用 MCS 全套流程(导览 + 问答)
- 资料入口:paper-to-model 新主线

### 2.2 M2:多文档融合分档

真实输入是资料包(论文 + 参考文献 + 报告异构多文档)。

- **v0.1 收窄单主资料**(架构师建议;PM 在 roadmap v2 拍板时复核)
- **v0.2 做多文档融合**

### 2.3 O1:只接 PDF / docx,弃 CAJ

v0.1 接受 PDF / docx 两种格式;不接 CAJ(知网封闭格式)。理由:格式封闭、解析成本高、版权 / 合规边界复杂(PM 内部表述"知网离远点")。

### 2.4 K 作废:不按子类细分逐个攻克,做泛化工程

PM 纠正 40 任架构师的"子类覆盖(控制 / 电力电子 / 信号处理各一篇)"错误框架:电气细分专业无底洞,应做泛化工程,而非按子类一个一个攻克。

电机短路作首验证样本(电机 / 电力电子类),**不代表只支持电机类**;v0.2 扩样本时再验证泛化到控制 / 信号处理类的边界。

---

## 3. 工艺五拍(F / G / J / L / H)

### 3.1 F3:Week 4 三 task 处置(冻结 vs 转交,两个状态)

| Task | 处置 | 状态符号 | 备注 |
|---|---|---|---|
| TASK-404 激活码 | **冻结**(暂不进入当前开发 lane) | ⏸ | 因 § 1.4 C 拍"暂不收费";v0.1 收费时机由 PM 重新评估再起 |
| TASK-405 部署 | **转交**(架构师不主导) | ↪ | 部署 / 运维专业范畴,留他人接;03 索引备注 owner |
| TASK-406 内测 | **转交**(架构师不主导) | ↪ | 内测组织 / 用户访谈范畴,留他人接;03 索引备注 owner |

**关键**:冻结(⏸)和转交(↪)是不同状态 — 冻结意味着 task 在当前 lane 暂停但保留;转交意味着 task 仍要做但负责人不再是架构师。03 索引 / Codex / PM review 时按符号区分,不可混用。**task 文档 + 索引行均保留,不删除**。

### 3.2 G2:宪法修订走 PR 流程

- feature branch + PR + squash merge
- main protected
- Codex 改,PM 批准后 squash merge + 打 tag(宪法升级 = `v3.0` tag)

### 3.3 J3:task 编号重新分段(PM 拍板 P3 = b)

| 编号范围 | 用途 |
|---|---|
| TASK-001 - TASK-499 | MCS 主线(已占用 001-310;311-499 为缓冲) |
| TASK-501 - TASK-999 | paper-to-model 主线(本次新增) |
| TASK-1000+ | 平台化(团队 / 私有部署等) |

化解简报"4 周 vs 9 周"口径冲突 → v3.0 宪法 § 13 明示"MCS 4 周 + paper-to-model 5 周"。

`mxa-tutor-update-roadmap.md`(v1)是一份**从未入仓的产品路线草案**(仅存在于项目知识库 / 历史对话,文件头自注"若要入仓建议单独走 docs/roadmap/ PR"),其 TASK-501 - TASK-1007 编号占用 **作废**,由本次 roadmap v2 重新规划。v1 **不入仓**(无仓库文件可标注),其产品思考(Phase 2-4 / § 14 论文复现数据模型 / § 17 架构原则等)已由 roadmap v2 § 1 继承并细化,仅作历史参考。

### 3.4 L1:工艺协议跨方向无缝延续

- 决策 12 v0.4 双 AI 互审协议沿用
- 决策 09 反例库累积同步(末态 162 起)
- K 账目继续累积
- v0.5 协议候选 5 项仍挂 v0.4,**不主动升级**(沿用 v0.4 § 4.1.1 反思结论:工艺规则有效但不充分,继续累积观察)

### 3.5 H:6 周节奏

距离上线 6 周。MCS 两周已完成后端 + 大部分前端;PoC 已前置完成(40 任决策阶段)。paper-to-model 从 Week 5 起算,首 task 编号 TASK-501。

### 3.6 无悬而未拍点

A / B / C / D / X / E / M / O / K / F / G / J / L / H 全部拍定。

---

## 4. 迷你 PoC 实测(决策 09 实证锚点,40 任完成)

### 4.1 PoC 范围与方法

PM 上传两个电机仿真工程包真文件。40 任架构师用工具(unzip / docx 解析)实地核查 `.slx` block 构成 + 读 docx 正文,**非推理**。

### 4.2 样本 1:同步发电机包(干净样本)

| 文件 | 类型 | 关键事实 |
|---|---|---|
| `dianlufangzhen.slx` | Simulink 模型 | 21 block;核心 = powerlib(SimPowerSystems)的 Synchronous Machine + Three-Phase Fault + powergui;教科书级标准接线 |
| `shuzhifangzhen.m` | MATLAB 脚本 | **不是仿真模型,是解析公式画图脚本**;定子电流闭式表达式 → subplot 画基频 / 倍频 / 非周期分量 |
| `同步发电机突然三相短路报告.docx` | 学生实验报告 | 21 段 / 0 表格 / **6 图片**;含完整"理论方程 → `.m` 计算 → Simulink 搭建配方 → 结果对照"链路 |

**模型搭建配方(纯文本可抽取)**:5MW 负荷 / 平衡节点 / 0.2s 故障 / ode15s 求解器 / 1s 仿真时长

**关键限制**:**参数值常在图片里,不在文本** — v0.1 纯文本抽取会漏(具体例证未盘点,留 v0.2 评估 OCR 时补)

### 4.3 样本 2:异步电机定子匝间短路包

| 文件 | 类型 | 关键事实 |
|---|---|---|
| `IM_sc_2014b.slx` | Simulink 模型 | **183 block**;6 子系统(Clarke ×3 / IM Modelling / Inv Clarke / Asynchronous Machine);用 sps_lib(SimPowerSystems)的 Asynchronous Machine + StateSpace block + 大量复数运算 |
| 两篇 PDF(苏晓丹 2007 / 施永茜 2020) | 学术论文 | 真 PDF;**未深读**(40 任只确认 PDF 真实性 + `.slx` block 构成;论文方程 → 状态方程 → `.m` 骨架链路深读留 § 4.7) |
| 两篇 CAJ | 知网论文 | PM 未传(§ 2.3 O1 弃 CAJ) |

### 4.4 三个定生死的发现(R1 降级实证)

**发现 1:两个 ground-truth 模型都用 SimPowerSystems 专业库**,不是基础 Simulink block。

**发现 2:论文图示搭法 ≠ 实际成品搭法**
- 异步机论文画的是 Fcn / Gain / Product 手搭子系统(物理方程框图)
- 实际成品用专业库元件 + StateSpace
- 论文给物理方程和原理框图,**不是 Simulink 接线图**
- 人复现时做了大量论文没写的工程决定(库选型 / 参数对应 / 求解器配置)

**发现 3:`.slx` 自动生成不可靠**
- 实测非推测
- R1 降级成立(§ 1.1 A1d → R1)

### 4.5 稳交付层 "paper-to-plan" 可行性印证(P1-6 降级措辞)

PoC 印证副驾**稳交付层**(=资料 → 模型搭建路线图,简称 paper-to-plan)可行:

- **稳交付层证据**:docx "模型搭建配方"是纯文本可结构化(5MW / 平衡节点 / 0.2s / ode15s / 1s)— 这是 paper-to-plan 输出的真实抓手
- **不承诺 30% 证据**:参数在图片 + 专业库元件 + 求解器选择,这部分需用户手动
- **A2d 调参讲解抓手**:docx 误差归因段(故障模拟器内阻 → dq 电势分压)是真实的调参讲解切入点

**不得把当前 PoC 表述为 paper-to-model 全链路已验证**(下方 § 4.6 严格二分)。

### 4.6 PoC 已验证 vs 未验证范围(严格二分,P1-6 防过度外推)

**已验证(v0.1 稳交付承诺锚点)**:
- 从资料 / 报告(docx 学生实验报告类)中抽取"模型搭建配方"可行
- 形成 plan 层"搭建路线图 + 库选型建议 + 参数对应表 + 子系统拆分"可行
- 范围:电机 / 电力电子类(SimPowerSystems 路线)的报告类资料

**未验证(留 v0.1 实施期 + v0.2 扩样本)**:
- 纯论文 PDF → 状态方程 → `.m` 骨架的稳定链路(见 § 4.7 未尽事项)
- 控制 / 信号处理类的资料抽取 + 搭建路线图(可能不用 powerlib、搭法不同)
- 多文档融合(异构论文 + 参考文献 + 报告组合,见 § 2.2 M2)
- 图片中参数的自动抽取(见 § 4.8 docx 暴露的图片参数问题)

PoC 结论仅覆盖"稳交付层 paper-to-plan + 报告类资料 + 电机 / 电力电子",不外推到"paper-to-model 全链路"。

### 4.7 PoC 未尽事项

- 异步机两篇 PDF 论文未深读(只确认 PDF 真实性 + `.slx` block 构成)
- 若 v0.1 设计需要,可深读两篇 PDF 验证"论文方程 → 状态方程 → `.m` 骨架"链路
- v0.1 实施期补充,或留 v0.2 扩样本时验

### 4.8 v0.1 承诺边界新约束(docx 暴露)

关键参数常在图片里,v0.1 纯文本抽取会漏。两个选项:

- **选项 i**:产品流程层 MissingParameterPrompt(v0.1 采用)
- **选项 ii**:v0.2 加图片 OCR(留 roadmap v2 § v0.2 范围评估)

**v0.1 选项 i 产品流程层落地(P1-7 防文案空转)**:

不能只在文案标注"图片参数需用户补充",必须落到 UI / API:

1. **系统识别**:plan 层抽取阶段识别"疑似缺失参数"(规则:公式 / 表 / 上下文提到的参数名,但未出现具体数值 / 单位)
2. **用户补充**:UI 呈现 `MissingParameterPrompt` 列表,用户手动填:数值 + 单位 + 来源(页码 / 截图说明 / "未在论文中找到")
3. **来源标注**:用户补充的参数在 EvidencePack 中标 `source: user_supplied`,与文档证据(`source: document_extracted`)**严格分开**
4. **回答时区分**:下游 QA / 调参建议引用参数时,明示来源("依据论文 § 3.2 表 2" vs "依据您补充的参数,论文中未直接给出")

具体 schema 字段 + UI 形态留 roadmap v2 § v0.1 实施期细化(关联 § 6.4 PaperSpec / EvidencePack 同源)。

---

## 5. 资产复用度评估(MCS 31 task → 新方向)

### 5.1 复用清单(Codex R6 实测降级措辞)

> **降级说明**(Codex R6 抓出原 v1.1 "直接复用 100%" 过乐观):下表区分**真直接复用**(import 即用)、**仅 zip 工程成立**(PDF/docx 路径需新增)、**框架/理念复用**(结构借鉴,非 import)。Codex 实地核查标注见各行。

| TASK | 内容 | 复用性质(实测后) |
|---|---|---|
| TASK-102 / 103 | `.slx` / `.m` 解析器 | **直接复用** — 生成物 `.m` 骨架回读验证可 import TASK-103 解析器 |
| TASK-104 / 202 | 上传沙箱 + API | **仅 zip 工程成立** — 现状 PDF skip / docx 归 other(Codex 实测 `adapters/parser/_zip_policy.py`);PDF/docx 文档安全需新增(见 § 10.4 第 3 项) |
| TASK-204 | SQLite project_status_record | **直接复用** |
| TASK-206 | 中文化 | **直接复用** |
| TASK-301 / 302 | 嵌入 + 向量存储 | **直接复用** — embedding adapter + SQLite vector store 与文档类型无关 |
| TASK-303 / 304 | chunker + 向量 RAG | **框架复用,非直接** — 现状 chunker 是工程结构 chunker(8 source type:m_file / m_function / slx_block / slx_subsystem / mat_variable / c_file / h_file / project_overview,Codex 实测 `features/chunking/chunking_service.py` + `core/interfaces/vector_store.py`),**无 PDF/docx/document source type**;向量存储 / embedding / RAG 框架可复用,论文 PDF/docx 解析 + 切 chunk + 新 SourceType + 证据锚需**新增** |
| TASK-307 / 308 | Citation Enforcer + EvidencePack | **理念 + 部分结构复用** — Citation Enforcer 思路可复用;EvidencePack 受决策 21 boundary 约束(paper feature 不 import explanation 私有结构),需在 core/ 公开 contract 层共享或新建 |
| TASK-310 PR #2 | TeachingUnit cache 4 态 record | **同构借鉴,非直接复用** — 四态 record(`core/interfaces/teaching_unit_store.py`,Codex 实测)模式可借鉴做"复现计划 cache",但需新建对等 store,不复用 TeachingUnit 实例 |
| 决策 11 | async + logger 双不变量 | **直接复用**(不变量,跨方向无条件沿用) |

### 5.2 治理机制 + 框架复用(P0-2 防 Codex 改 ProjectOverview)

**TASK-207 ProjectOverview schema 本身不改造**为 paper-to-model 输出。`ProjectOverview` 是契约级 freeze schema(06 + freeze test + JSON schema + prompt + 05 五处同源),改它会破坏前端 / 评测 / RAG 下游。

**可复用的是治理机制和框架**:

| 来源 | 复用对象 | paper-to-model 新增 |
|---|---|---|
| TASK-207 | **schema freeze + D1-B 三层同源 + D5 修订流程** 治理机制 | 新建 `PaperSpec` / `ModelGenerationPlan` / `TuningSuggestion` 各自独立 schema freeze,沿用 D1-B 三层同源(`core/domain/*` dataclass + `features/paper/_*_schemas.py` Pydantic wrapper + freeze test + 06 文档 + JSON schema) |
| TASK-107 ProjectGraph | 节点 / 边 / entry / flow 数据结构**框架** | 新建 `PaperGraph`(节点:段落 / 公式 / 参数 / 图表;边:引用 / 推导 / 对应)或扩展 ProjectGraph 加 paper 类节点,具体由 CHORE-ARCH-P2M-001(§ 6.2)拍板 |
| TASK-203 OverviewService | **service 五步校验 + LLM retry + cache** 框架 | 新建 `PaperPlanService`(讲论文 + 生成 ModelGenerationPlan + 调参建议),沿用五步校验 / retry / cache 模式,**不复用 OverviewService 实例** |

**红线**:Codex 实施任何 paper-to-model task 时,**禁止修改** `ProjectOverview` / `core/domain/project_overview.py` / `features/overview/overview_schemas.py` / `core/prompts/project_overview.yaml`。需要新增 paper 类输出时,**新建** `features/paper/*` + `core/domain/paper_*.py`。

### 5.3 基本变废

| TASK | 状态 | 原因 |
|---|---|---|
| TASK-401 / 402 / 403 | 重写 | 前端 3 页 UI 形态完全不同 |
| TASK-205 | 作废 | 粗 RAG 已被 TASK-304 向量替代 |
| TASK-208 | 重写 | chat citations payload 形态变 |

### 5.4 全新增(roadmap v1 未覆盖)

- 论文 PDF 解析(公式 / 图表 / 伪代码 / 参数表)
- PaperSpec generator(资料 → 结构化论文规格)
- ModelGenerationPlan generator(规格 → 模型搭建路线图 + 库选型 + 参数对应 + 子系统拆分)
- **生成物结构一致性校验**(P0-5 降级):检查 plan 中的 block / 参数 / 公式 / `.m` 骨架段落 / 证据引用是否闭合(`.m` 骨架若有,可经 TASK-103 解析器回读验证语法);**不声称可运行、可收敛、可复现结果**
- 调参建议引擎(A2c + A2d,§ 1.2)
- MissingParameterPrompt 流程(§ 4.8)

### 5.5 复用度估计

**MCS 资产不浪费,pivot 不从零开始**,但复用度需按 § 5.1 Codex 实测分性质看,不是笼统 "≥ 50% 直接复用":

- **真直接复用**(import 即用):解析器回读 / SQLite 存储 / 中文化 / embedding + 向量存储 / async + logger 不变量 — 基础设施层
- **框架 / 理念复用**(结构借鉴,需新建对等实现):chunker(无文档 source type)/ Citation Enforcer / EvidencePack(决策 21 约束)/ TeachingUnit cache 四态 / ProjectGraph / OverviewService / schema freeze 治理
- **需重写 / 新增**:前端 3 页 / 论文 PDF·docx 解析 + 文档 SourceType / PaperSpec·ModelGenerationPlan·TuningSuggestion / 文档上传安全 / 调参建议引擎 / MissingParameterPrompt

**关键边界**:复用 ≠ 改造既有 schema / service / contract;复用 = (a) 基础设施直接 import + (b) 上层沿用治理流程 + 框架,新建 paper 类对等实现。Codex 实施 paper-to-model task 时不准修改既有 MCS feature 的 schema / contract(§ 5.2 红线)。

---

## 6. 影响范围(具体到文件 / 章节)

### 6.1 宪法 v2.1 → v3.0(本次随同入仓)

- § 1 项目身份 — 一句话定位改写
- § 3 产品形态 — MCS v0.1 承诺 + paper-to-model v0.1 承诺并列(副驾三层 / 二合一入口 / 不承诺 `.slx` 自动生成)
- § 13 节奏与里程碑 — "MCS 4 周 + paper-to-model 5 周"
- 入仓模式:`git mv` 覆盖(PM 拍板 P1 = A)
- tag:v3.0

### 6.2 02 架构总览 v3.0 delta(本次随同入仓,P0-3 方案 1 拍板)

PM 拍 P0-3 方案 1:本 chore PR 同步改 02 最小 v3.0 delta,避免窗口期 Codex 误读。范围:

- **§ 2 数据流图**:加资料入口数据流支路(上传 PDF/docx → PaperParser → PaperSpec → PaperPlanService → ModelGenerationPlan + TuningSuggestion → 用户;EvidencePack 标 `document_extracted` / `user_supplied` 双源)
- **§ 4.2 数据结构**:新增 `PaperSpec` / `PaperGraph`(或 ProjectGraph paper 类节点扩展,由本次拍板) / `ModelGenerationPlan` / `TuningSuggestion` / `MissingParameterPrompt` 的**占位签名 + 职责边界描述,不冻结具体字段**(Codex R6 重点判断 2:02 § 4.2 当前是具体 dataclass/Enum 字段区,本次若写"字段表"会变成具体字段承诺,与"具体字段留后续 task"自相矛盾;故只写"这个结构负责什么 + 大致输入输出",字段表留 06 契约 + paper-to-model 首 task)
- **§ 4.x features/paper/ vs features/overview/ 边界**:明示新 feature `features/paper/` 与既有 `features/overview/` 不互相 import 私有结构(沿用决策 21 boundary 模式)
- **§ 3 目录树**(若涉及):加 `core/domain/paper_*.py` / `features/paper/` 占位说明

**架构师起 02 delta 时的边界**:本任只动 02 的 **结构性 v3.0 delta**(数据流支路 + 高层数据结构签名 + feature 边界);**不动**具体字段 / Pydantic wrapper / 实施细节(那是后续 paper-to-model 主线首 task 的工作)。Codex 实施期任何动到具体字段的尝试,停手报 PM。

### 6.3 03 索引(本任随同 chore PR 入仓)

- Week 4 处置:TASK-404 改 ⏸ 冻结 / TASK-405 / 406 改 ↪ 转交(沿用 § 3.1 冻结 vs 转交两个状态)
- Week 5+ TASK-501 系列占位(具体首 task 编号 + 名称由 roadmap v2 确定)
- 原 v1 草案的 §12 - 16 长期路线条目作废说明(v1 未入仓,仅在 03 索引注明编号分段取代)
- task 编号重新分段说明(MCS = 001 - 499 / paper-to-model = 501 - 999 / 平台化 = 1000+)
- 反例库累积同步(详 § 9)

### 6.4 roadmap

- `mxa-tutor-update-roadmap.md`(v1)— 未入仓产品草案,编号占用作废,不入仓,仅历史参考
- `docs/roadmap/mxa-tutor-v2-paper-to-model.md`(v2)— 本次随同入仓,取代 v1 草案
- v1 产品思考(Phase 2-4)已由 roadmap v2 § 1 继承并细化

---

## 7. 与既有决策的关系

| 决策 | 关系 |
|---|---|
| 决策 02(宪法 § 14 示例 "20260601-02 放弃论文复现优先做工程导览";Codex R6 实测该决策文件**从未入仓**,仅作为宪法 § 14 决策日志示例文件名存在)| **方向部分回滚**:论文复现 / paper-to-model 复活,但工程导览不丢(二合一并存);因原决策无独立文件,本次不需 git mv 旧决策,直接由本决策 22 记录回滚 |
| 决策 03(宪法 § 14 示例 "20260601-03 MCS 不做截图分析 / Engine / 论文复现";同上,文件未入仓)| **方向部分回滚**:论文复现复活(本次主线);截图分析 / Engine 仍延后 |
| 决策 04(20260601-04 understanding 暂不作为顶层 feature;Codex R6 实测文件存在)| 沿用(paper-to-model 不新增顶层 `features/understanding/`,新主线复用基础设施 + 新增 `features/paper/`)|
| 决策 09(架构师必须实地核查)| **正面执行案例**:40 任 PoC 实测非推测(unzip + docx 解析),R1 降级建立在实测数据上;**但 41 任起稿期 K_28a +4**(凭印象写复用清单 / schema 措辞等,Codex R6 + GPT R1 抓出,详 § 9)— 决策 09 在本任是"正反两面教材" |
| 决策 11(async + logger 双不变量)| 沿用 |
| 决策 12 v0.4(双 AI 互审协议) | 沿用 |
| 决策 16(overview_schemas relocation) | TASK-310 PR #1 已实施,paper-to-model 继续受益(`core/domain/` 下沉契约让新 feature 也能消费 ProjectOverview) |
| 决策 18 - 21 | 沿用(TASK-310 落地的四态 cache / source_version / EvidencePack boundary) |

---

## 8. 回滚要求

**不可默默逆转**(宪法级方向变更,沿用宪法 § 15 "永远不要默默偏离宪法"):

- 决策 22 入仓 + 宪法 v3.0 tag 后,pivot 即生效
- 若 v0.1 paper-to-model 验证失败(eval 不达标 / 用户反馈差 / 资源不足),回滚必须通过**新的宪法级决策记录**(决策 NN,沿用 G2 PR + R 轮工艺);
- 不允许"悄悄回到 MCS only"或"暂时搁置 paper-to-model 走 MCS Week 4 收尾"等非显式偏离
- § 1.1 对外口径硬约束违反 = 触发回滚要求(产品文案 / 销售 / API 任何 "自动生成 Simulink 模型" 表述 = 红线)

---

## 9. 关联反例

- **反例 28**(架构师无 repo 凭推理写):40 任 PoC 实测是反例 28 的正面教训(实地 unzip + docx,非推理);40 任 PoC 实测 K_28a 0;**41 任 v1.0 起稿期 K_28a +4(GPT R1 抓)+ K_28a +2(Codex R6 抓)+ K_28a +1(GPT 三份联审抓)= +7**(详下方"K_28a 集中反思")
- **反例 30**(跨段同步漏):**41 任累积 +5** — GPT R1 抓 3(冻结 vs 转交 § 3.1 / 不可逆 vs 回滚矛盾 § 8 / 三份 vs 5 份 § 10)+ Codex R6 抓 1(§ 10.3 标题"5 份"vs 正文 6 文件)+ **GPT 三份联审抓 1(前置硬门槛 5 项跨三份不同步 — 决策 22 § 10.4 / 宪法 § 13·16 / roadmap § 3.2·11 各写各的;宪法 roadmap 把 02 delta 塞进 5 项 + 漏 EvidencePack 双源)**
- **反例 31**(协议自反 / 反面同源):无触发
- **反例 34**(语义记忆错位):**41 任累积 +3** — 自抓 1(v1.0 § 9 "反例库总计 162" 误引为 "K 总 162",R7.1 grep 兜底抓到)+ Codex R6 抓 1(§ 7 引用决策 02/03 文件,实际从未入仓)+ **入仓 Stage 0 抓 1(把 `mxa-tutor-update-roadmap.md` 当成 git 仓库文件,一路假设到 v1.3"v1 原位保留 + 加 deprecated 标注";Codex 入仓 Stage 0 #5 实测仓库无此文件 — 它仅在项目知识库,文件头自注"若要入仓建议单独走 PR" = 本就是未入仓草案;v1.3→v1.3.1 改为"v1 不入仓",chore PR 6 文件 → 5 文件)** — **知识库 ≠ git 仓库,文件存在性必须实测**,v0.5 候选第 6 项又一实证
- **反例 36**(工程职责边界漏):**41 任 +1** — v1.0 § 6.2 把 "02 架构总览升级" 误判为 "后续 chore 本任不动",GPT R1 P0-3 抓出窗口期误读风险;PM 拍 P0-3 方案 1 后修订内化
- **GPT 三份联审 challenge(架构师不接受归类)**:GPT 把"'02 留给 Codex 执行期改'架构假设"归为反例 28 第 4 条。架构师 challenge:决策 22 § 6.2 / § 10.3 正文从头到尾写的是"02 在 6 文件 chore PR 范围内",**无任何"02 留到 TASK-501"字面**;这不是文档正文的架构假设错误,是 PM-架构师对话中的**口语歧义**("留给 Codex 执行期改"在 B 方案语境 = 同 PR 内 Codex 代笔,非"不入本 PR")。反例 28 定义是"凭推理写进文档/派单的错误",此条未进任何正文,**记为沟通澄清项(已在 Codex 派单写死"02 本 PR 内 + Codex 执行期写"杜绝歧义),不计 K_28a**
- **40 任内部反例**(40 任简报 § 9 自审,本任入仓 chore PR 同步累积):
  - **K_28a 候选 +1**:中途用"PoC"术语未先解释,PM 反问"poc是什么"
  - **K_28b 候选 +1**:"子类覆盖(控制 / 电力电子 / 信号处理各一篇)"框架被推翻 — 把战术问题误当目标问题,PM 救场拦截
  - **PM 救场架构师 +2**:术语解释 + 子类框架两次
- **41 任 PM 救场架构师 +2**:(a) 用户提问"给 gpt 审批还是 codex 对照文件审批?"触发 § 10.2 "不走 R 轮" 工艺分层错位自抓;(b) 用户提问"02 delta 是什么"触发架构师未解释术语自抓(40 任 PoC 同款毛病再犯 — 全程用"02 delta"简写未向 PM 解释),已补完整解释

### K_28a 集中反思(41 任 v1.0 起稿期单任约 +7,项目首次单任高密度累积)

GPT R1 抓 4 + Codex R6 抓 2 + GPT 三份联审抓 1,共同根因:**架构师起稿宪法级 / 契约级文档时,凭概念名 / 历史印象写,未 grep 现有 schema / contract / 治理流程 / 文件存在性 / 自身前序版本(尤其 R 轮新补段)最终字面**。

| # | 反例 | 抓出方 | 根因 |
|---|---|---|---|
| 1 | 工艺分层错位(P0-1) | GPT R1 | 凭印象引用 v0.4 § 7.1,未 grep 原文区分"决策类自身升级"vs "架构升级" |
| 2 | Schema 复用措辞(P0-2) | GPT R1 | 凭概念名("形态变骨架复用")写,未 grep 06 / TASK-207 schema freeze 治理流程 |
| 3 | 可执行性过度承诺(P0-5) | GPT R1 | 凭印象写"可执行性",未识别"无 Engine + parser 回读"实际能验范围 |
| 4 | 7 类对齐(P1-10) | GPT R1 | 凭中文专业名概括,未 grep overview_schemas.py / project_overview.py ProjectTypeValue 字面 |
| 5 | TASK-303/304 PDF 直接复用 | Codex R6 | 凭印象写"论文 PDF 切 chunk 直接复用",未实测 chunker 是工程结构 chunker(8 source type 无 document)|
| 6 | 上传安全门槛漏项 | Codex R6 | 凭印象写"沙箱加 PDF/docx 规则",未实测 TASK-104 是 zip 沙箱(PDF skip / docx other)|
| 7 | 前置门槛 5 项内容写错 | GPT 联审 | 写宪法 § 13 + roadmap § 3.2 时凭印象记前置门槛,未回查 § 10.4 v1.2 最终 5 项字面(漏 EvidencePack 双源 + 误塞 02)— § 10.4 是 v1.1→v1.2 才补,起稿宪法/roadmap 未回查最新字面 |

**v0.5 协议候选第 6 项**(沿用 40 任 L1 "不主动升 v0.5",仅累积):
> 架构师起稿宪法级 / 契约级文档时,必须 grep 现有 schema / contract / 治理流程 / 文件存在性 / **自身前序版本(尤其 R 轮新补段)最终字面**;不许凭概念名 / 宪法示例 / 历史印象假设

**升仪反思**(决策 12 v0.4 § 4.1 #6):本任 K_28a 单任 +7 是项目首次单任高密度,GPT R1 抓 4 + Codex R6 抓 2 + GPT 联审抓 1,**三道审查各有斩获 → 工艺规则有效(无一漏到入仓)但起稿源头不充分**(架构师 v1.0 凭印象密度过高)。第 7 条尤其暴露"自身文档版本演进同步漏"(§ 10.4 是 R 轮才补,后续起稿仍凭旧印象),比引用外部 schema 更隐蔽。继续沿用 v0.4 § 4.1.1 反思结论(规则有效但不充分,继续累积观察);**若 paper-to-model 主线首 task(TASK-501 系列)仍密集触发 K_28a,触发深挖根因 task**(v0.4 § 4.1 #6 路径)。v0.5 协议升级 task 立项时机由后续任评估。

### 反例库记账法调整(本任工艺变更)

**变更**:本任起,决策 09 反例库从**精确逐位累加记账**(每类 K 值精确到个位 + 总计校验)降级为**趋势清单**。

**理由**(本任实证):精确数字账本在本任内部反复制造"算术对不齐 / 跨段同步漏"一类错误(v1.0 把"反例库总计 162"误当"K 总";v1.3.1 累加表 144+23+18 写成 184 实为 185,PM 人肉抓出;K_28a 反思标题 +6/+7 不同步),且精确数字**不影响架构师实际谨慎度**(每轮谨慎程度与计数器读数无关)——账本的维护成本和出错面 > 它防的价值。保留有用的部分(反例清单 + 高发区趋势 + 阈值触发机制),砍掉逐位累加。

> 本调整仅改**记账粒度**,不改决策 12 v0.4 的反例分类 / 阈值触发机制本身;后续若要进一步简化反例库,另起决策。

### 反例趋势(本任末态,粗粒度)

**本任高发区**:K_28a(架构师凭印象写宪法/契约级文档,未核字面)单任密集触发约 7 次,GPT R1 + Codex R6 + GPT 联审三道审查各有斩获 —— **项目首次单任高密度,是当前最值得警惕的反例类型**(详上方 K_28a 集中反思 7 条)。

**其余触发**:K_30 跨段/跨文档同步漏(约 5 次,本任反复出现于数字/文件数同步)、K_34 语义记忆错位(约 3 次,含"知识库≠仓库"的 v1 roadmap 误判)、K_36 工程职责边界(1 次)、K_28b(40 任传入 1 次)。

**救场有效性**:本任 Codex 守门 + PM 救场多次拦截(Codex Stage 0 拦下 v1 roadmap 不在仓库;PM 拦下工艺分层错位、02 术语未解释、反例库算术错)——**三层审查机制(GPT 决策质量 / Codex 实测字面 / PM 兜底)正常工作,无一漏到入仓**。

**阈值触发状态**(决策 12 v0.4 § 4.1):K_28a / K_30 / K_34 / K_36 / Codex 守门 / PM 救场各项均已超独立阈值,持续触发;v0.5 协议候选累积至第 6 项(架构师起稿宪法/契约级文档必须 grep 现有 schema/contract/治理流程/文件存在性/自身前序版本最终字面)。沿用 v0.4 § 4.1.1 反思结论(规则有效但不充分,继续累积观察);若 paper-to-model 首 task 仍密集触发 K_28a,触发深挖根因 task。

> **给 03 索引同步的提示**(本任 chore PR):03 索引反例库累积段同步改为趋势描述(不再逐位累加);若 03 索引现有精确计数,本任 chore PR 在其后追加"自本任起改趋势记账"说明,不强行回填历史精确值。

---

## 10. 起稿与审批

### 10.1 起稿

- **架构师**:Claude(第四十一任),基于 40 任末态交接简报全决策清单 + PoC 实测结论起稿
- **40 任工作**:全程纯决策任务,未写一行代码、未起任何文档、未动 git;PoC 实测 + 十几轮拍点收束全部完成
- **前置 commit**:`562946d`(39 任 chore PR #92 squash merge)— 40 任未动 git,本任 base 为同 commit
  - **Codex 实施期 Stage 0 #1 兜底实测**:`git log -1 --oneline main` 期望 = `562946d ...`;若漂移停手报 PM(R7 精确事实校验)
  - **工作树状态注**(Codex R6 实测):main up to date,但有 untracked `eval/ad_hoc/`(38/39 任遗留摸底报告目录,03 索引关联文件已登记 `D:\eval\ad_hoc\task310_premortem\`);非本任产生,入仓 chore PR 时 `git add` 精确指定 docs 文件,不带入 untracked eval 目录

### 10.2 审批级别

- PM 已拍板 P1(宪法 `git mv` 覆盖)/ P2(三份合一个 chore PR)/ P3(task 编号重新分段)/ P0-3 方案 1(02 v3.0 delta 本次随同入仓)
- **R 轮分类:架构升级**(沿用宪法 § 5 "AI 二审节点"硬规则;决策 12 v0.4 § 7.1 主线 task / 架构升级必走 R 轮)
- **GPT R1 已执行(范围受限二审)**:只审方向一致性 / 承诺边界 / 架构同步 / 执行风险 / 反例 28 / 30 / 31 / 34 语义层互抓;**不复验 40 任 PoC 工程真实性**(GPT 无文件访问)。PoC 真实性由 40 任实测记录(详 § 4)+ Codex 入仓前 Stage 0 兜底负责
- **GPT R1 conditional pass**:14 条反馈(P0 ×5 / P1 ×5 / P2 ×3 + 补段 ×1)+ 反例 28 / 30 / 31 / 34 互抓累积;**架构师 challenge 1 条**(P1-9 半接受,身份分层主轴 vs 需求深度分层洞察并存);**GPT 反例 0**(KPI #1 实测引用全部一致)
- **Codex R6 后置实测层**:5 份 docs(详 § 10.3)入仓由 Codex 从代码层面 review(grep 跨段同步漏 + 字节级一致兜底 + R6.1 完工 `git diff --stat` 实证)

### 10.3 入仓时机 + chore PR 范围(5 个文件 = 3 核心 + 1 v3.0 delta + 1 同步)

- 与宪法 v3.0 + roadmap v2 + 03 索引修订 + 02 v3.0 delta **合一个 chore PR**(P2 = B + P0-3 方案 1 拍板;v1 草案未入仓,不在 PR 范围)
- chore PR 范围 **5 个文件**(3 核心 + 1 v3.0 delta + 1 同步):

  **3 个核心 docs(本任主体产出)**:
  1. `docs/decisions/20260615-22-direction-pivot-paper-to-model.md`(本决策,create)
  2. `docs/01_PROJECT_CONSTITUTION.md`(v3.0,同路径覆盖,保留 git history)
  3. `docs/roadmap/mxa-tutor-v2-paper-to-model.md`(v2 新建,create)

  **1 个 v3.0 delta**:
  4. `docs/02_ARCHITECTURE_OVERVIEW.md`(v3.0 delta:§ 2 数据流图 + § 4.2 数据结构 + § 4.x feature 边界;高层结构性改动,具体字段不动)

  **1 个同步 docs**:
  5. `docs/03_TASK_INDEX.md`(Week 4 处置 ⏸ / ↪ + Week 5+ 占位 + 反例库累积段改趋势记账,见 § 9;不再逐位累加)

- v1 roadmap 草案**不入仓**(Stage 0 #5 实测仓库无此文件;v1 仅在项目知识库,无仓库文件可标注),其编号作废 + 取代关系已在决策 22 § 3.3 / § 6.4 + roadmap v2 § 1 交代
- 范围外文件改动 = Codex 停手报 PM(R6.1 完工 `git diff --stat` 兜底)
- tag 时机:5 个文件 squash merge 完成 + PM 验收通过 → 打 `v3.0` tag(宪法升级)

### 10.4 TASK-501 前置硬门槛(本次入仓后开门 chore 前 paper-to-model 主线封禁)

> **防误读注**(GPT R1 联审 P0 防 K_30):本节 5 项前置硬门槛是 **paper-to-model 开门 chore** 的内容,**不含 02 架构总览 v3.0 delta**。02 delta 是**本次 chore PR 的同步文件**(详 § 6.2 / § 10.3,与决策 22 / 宪法 v3.0 / roadmap v2 同一个 5 文件 PR 入仓,由 Codex 执行期对照真实 `02_ARCHITECTURE_OVERVIEW.md` 写),**不计入本节 5 项**。宪法 § 13 / § 16 + roadmap § 3.2 / § 11 引用本节时必须照抄以下 5 项字面,不得把 02 delta 算进来,也不得漏 EvidencePack 双源。

**在派发任何 TASK-501 实施任务前,必须先完成并入仓以下同步**(任一未完成 → TASK-501 派单 = 违反宪法 § 15,PM 拒绝接稿):

| 项 | 内容 | 入仓形式 |
|---|---|---|
| 1 | **06 输出契约新增 paper-to-model 三套契约** | `docs/06_OUTPUT_CONTRACTS.md` 新增 PaperSpec / ModelGenerationPlan / TuningSuggestion 章节(沿用 D1-B 三层同源 + D5 修订流程);schema freeze test 占位条目 |
| 2 | **MissingParameterPrompt + EvidencePack 双源契约** | EvidencePack 字段加 `source: document_extracted` / `user_supplied` 二选一;06 同步;§ 4.8 落地 |
| 3 | **文档上传安全规范**(PDF / docx,Codex R6 加硬)| **现状**(Codex R6 实测):TASK-104 是 **zip 工程沙箱**,非文档安全规范;PDF 在 `adapters/parser/_zip_policy.py` 策略里是 **skip**,docx 归 **other**,无文档级安全规则。**本项必须新增**:(a) 新增文档上传入口 **或** 明确复用 `/upload` 的边界;(b) magic byte sniffing(防伪装扩展名);(c) PDF/docx parser sandbox(解析器超时 + 内存上限);(d) 解析依赖审批(新增 PDF/docx 解析库走 requirements review);(e) 恶意 PDF/docx fixtures 测试集;(f) 外链 / 嵌入对象 / 宏 / OCR 处理策略(不执行 / 不联网 / 不解析远程资源);(g) raw 文档留存与脱敏策略(对齐 01 § 9 隐私:不存原文 + 24h TTL)。`docs/04_ENGINEERING_STANDARDS.md` 沙箱章节扩展 |
| 4 | **v0.1 产品文案 / 对外口径**(§ 1.1 硬约束落实) | 前端文案 / 销售物料 / API 说明 / README 落"复现路线图 / 模型搭建副驾 / 参数对应说明"统一口径;明示不自动生成 .slx + 图片参数需用户补充 + 不承诺运行结果正确或最优调参 |
| 5 | **评测准入**(eval 集 + 阈值) | 至少 1 个"资料 → 搭建路线图"样本完整跑通(电机短路类,沿用 PoC 样本);至少 1 个"缺图片参数 → 用户补充 → 输出更新"样本跑通;eval/cases 新增样本目录 + 评分模板 |

**前置硬门槛实施方式**:5 项可拆分为若干 chore task(预计 1 - 3 个,具体由 roadmap v2 拍板);**完成顺序**自由,但全部完成前 TASK-501 主线封禁。Codex 任何 TASK-501 派单收到前 stage 0 必须 grep 03 索引确认前置硬门槛 5 项全部 ✅,任一未完成停手报 PM。

---

**版本**:v1.3.1(2026-06-15 入仓 Stage 0 #5 实测 v1 roadmap 不在仓库,修正 v1 入仓假设;chore PR 6 文件 → 5 文件)
**日期**:2026-06-15
**作者**:Claude(架构师,第四十一任)
**关联宪法版本**:v2.1(冻结)→ **v3.0**(本次随同升级)
**关联协议**:决策 12 v0.4(沿用,不升 v0.5;v0.5 协议候选累积至 6 项)
**入仓**:chore PR(5 个文件:决策 22 + 宪法 v3.0 + roadmap v2 + 02 v3.0 delta + 03 索引修订;v1 roadmap 未入仓不在范围);02 delta 本 PR 内由 Codex 执行期对照真实 02 写;**当前为草稿,PM 暂不入仓**
**tag**:v3.0(宪法升级)
**审批历史**:
- v1.0 起稿(2026-06-15)— 基于 40 任末态交接简报 + PM 拍板 P1 / P2 / P3
- v1.0.1(2026-06-15)— R7.1 起稿后 grep 兜底自抓 K_34 +1(数字概念混淆)
- v1.1(2026-06-15)— GPT R1 反审 conditional pass:14 条 + 1 注脚,13 全采纳 + 1 部分采纳(P1-9);架构师 challenge 1 条;GPT 反例 0;PM 拍 P0-3 方案 1;累积 K_28a +4 / K_30 +3 / K_36 +1 / PM 救场 +1
- v1.2(2026-06-15)— Codex R6 代码层实测审查 conditional pass:抓出 5 条全采纳;Codex 重点判断印证 § 5.2 红线 + 细化 § 6.2 不冻结字段 + § 5.1 复用降级;累积 K_28a +2 / K_30 +1 / K_34 +1;Codex R6 守门 5 条全拦在入仓前
- v1.3.1(2026-06-15)— 入仓 Stage 0 #5 Codex 实测 `mxa-tutor-update-roadmap.md` 不在 git 仓库(仅项目知识库,文件头自注"若要入仓建议单独走 PR"),修正 v1.0-v1.3 一路"v1 原位保留 + deprecated 标注"的入仓假设(反例 34 / Codex 守门 各 +1);§ 3.3 / § 6.3 / § 6.4 / § 10.3 改"v1 不入仓",chore PR 6 文件 → 5 文件;**反例库改趋势记账**(见 § 9)
- **v1.3**(2026-06-15)— GPT 三份联审 conditional pass(决策 22 + 宪法 v3.0 + roadmap v2 一起审):核心抓 1 P0(前置硬门槛 5 项跨三份不同步)+ 一批 P1(general 拒绝 / § 2 痛点 C 类 / 支持 vs 验证范围 / PaperGraph 二选一 / EvidencePack 双源硬约束);**本决策加 § 10.4 防误读注 + 配套宪法 v3.0 五处 + roadmap v2 五处一次性同步修订**;架构师 challenge 1 条(GPT 把"02 留 Codex 执行期改"归反例 28,实为口语歧义非文档错误,记沟通澄清不计 K_28a);累积 K_28a +1 / K_30 +1 / PM 救场 +2(02 术语未解释自抓);GPT 联审 P0 条件项(02 时机)经 PM 确认 = 本 PR 内 Codex 写,不成立