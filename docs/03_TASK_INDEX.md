# Task 索引 · TASK INDEX

> **前置阅读**:
> 1. `01_PROJECT_CONSTITUTION.md` — 项目宪法
> 2. `02_ARCHITECTURE_OVERVIEW.md` — 架构总览
> 3. `04_ENGINEERING_STANDARDS.md` — 工程规范
> 4. `05_EXPLANATION_STYLE_GUIDE.md` — 教学输出风格
>
> 本文是 **MCS 阶段所有 Task 的总纲**(4 周交付可收费产品)。
> **版本:v3.0(delta)**

---

## Task 状态约定

- 🔲 未开始
- 🟡 进行中
- 🔍 等待验收
- ✅ 已通过
- ❌ 打回返工
- ⏸ 暂停 / 冻结
- ↪ 转交 / 移交他人负责

---

## Task 编号体系

```
TASK-WNN
       │
       └─ W = Week number (0-9), NN = 该周内序号
```

例:`TASK-101` = Week 1 第 01 个 Task。

### v3.0 编号分段(决策 22)

- `TASK-001` - `TASK-499`:MCS 主线(已占用 001-310;311-499 为缓冲)
- `TASK-501` - `TASK-999`:paper-to-model 主线(本次 pivot 后新增)
- `TASK-1000+`:平台化(团队 / 私有部署等)

---

## Week 0:基建准备

| 编号 | 名称 | 状态 | 负责 | 依赖 |
|------|------|------|------|------|
| TASK-001 | GitHub 私有仓库 + 项目骨架 | ✅ | Codex | 无 |
| TASK-002 | 开发环境 + CI 配置 | ✅ | Codex | 001 |
| TASK-003 | 收集 10 个真实 Simulink 工程做测试集 | ✅ | PM | 无 |
| TASK-004 | 合规一页纸归档 | 🔲 | PM | 无 |

**Week 0 验收**:
- 仓库已建,目录结构符合 `02_ARCHITECTURE_OVERVIEW.md` v2.1
- 本地 + CI 上 `pytest` 能跑通(虽然没有测试)
- 10 个真实 .slx / 工程文件,放在 `tests/fixtures/slx_samples/` 和 `eval/cases/`
- 合规一页纸签字归档

---

## Week 1:核心解析能力 + 教学理解中间层

| 编号 | 名称 | 状态 | 负责 | 依赖 |
|------|------|------|------|------|
| TASK-101 | core 接口 + domain 数据结构(基础) | ✅ | Codex | Week 0 |
| TASK-102 | .slx XML 解析器(P0/P1/P2 分级) | ✅ | Codex | 101 + 测试集 |
| TASK-103 | .m 文件解析器 | ✅ | Codex | 101 |
| TASK-104 | 工程压缩包安全解压 + 文件分类(含沙箱) | ✅ | Codex | 101 |
| TASK-105 | 文件依赖关系分析 | ✅ | Codex | 103 |
| TASK-106 | DeepSeek TextProvider 实现 | ✅ | Codex | 101 |
| TASK-107 | **ProjectGraph 构建器** ⭐ | ✅ | Codex | 102, 103, 105 |
| TASK-108 | app/config.py + pydantic-settings 配置层(基建桥接) | ✅ | Codex | 无 |

### Week 1 验收(分级)

**.slx 解析(TASK-102)**:

P0 必须解析(10 个测试工程中至少 8 个通过):
- ✅ model 名称
- ✅ top-level blocks
- ✅ block name / type / parameters 原始字典
- ✅ lines 的 from/to 关系
- ✅ subsystem 层级

P1 尽量解析(10 个测试工程中至少 6 个通过):
- 🔸 solver config
- 🔸 mask 参数
- 🔸 library link 标记(只识别"是引用",不展开)
- 🔸 model reference 标记(同上)
- 🔸 workspace 变量引用名称

P2 v0.1 不承诺:
- ❌ Stateflow 语义
- ❌ masked subsystem 内部语义还原
- ❌ 自定义 S-Function 行为
- ❌ 自动运行仿真

**失败要求**:
- 解析失败时必须给出**中文可理解的错误提示**
- 不能因为一个文件失败导致整个工程失败(失败隔离)

**.m 解析(TASK-103)**:
- 10 个测试工程的 .m 文件,**至少 80% 能正确分类**(script / function / class)
- 能提取函数名、输入输出、调用关系、注释

**ProjectGraph(TASK-107)**:
- 能从 SlxModel + MFile + 文件树构建出 ProjectGraph
- 节点类型覆盖:file_m, file_slx, block, subsystem, function
- 边类型覆盖:calls, signal_flows, belongs_to
- **本 Task 不调用 LLM**(纯结构化转换)

**通用**:
- DeepSeek API 能稳定调用,有 mock 测试
- 单元测试覆盖核心解析逻辑,全绿

---

## Week 2:API 后端 + 导览生成 + 粗 RAG 问答

| 编号 | 名称 | 状态 | 负责 | 依赖 |
|------|------|------|------|------|
| TASK-201 | FastAPI 框架搭建 + 健康检查 | ✅ | Codex | Week 1 |
| TASK-202 | 上传 + 解析 API(异步,含沙箱) | ✅ | Codex | 104, 105, 201 |
| TASK-203 | ProjectOverviewService(基于 ProjectGraph,TeachingUnit 接口预留) | ✅ | Codex | 106, 107 |
| TASK-204 | SQLite 存储层(Project + Chat) | ✅ | Codex | 101 |
| TASK-205 | **粗 RAG 问答 API(关键词 + metadata 检索)** ⭐ | ✅ | Codex | 203, 204 |
| TASK-206 | 错误处理 + 中文化 | ✅ | Codex | 201-205 |
| TASK-207 | **ProjectOverview Schema + 教学输出契约** ⭐ | ✅ | Codex | 203 |
| TASK-208 | **chat citations payload 净化(file_path 相对化 + line_range 透传)** ⭐ | ✅ | Codex | 204, 303, 304 |
| TASK-209 | 完整版工程上传 + .c/.h 入 chunker + 完整版 v7 评测 | ✅ | Codex | 202, 303, 304 |

### Week 2 验收

**TASK-202 上传 + 沙箱**:
- 能拒绝 zip bomb(压缩比 > 100)
- 能拒绝 zip slip(路径含 `../` 或绝对路径)
- 能拒绝非白名单扩展名(白名单见 04 工程规范)
- 单文件 > 20MB 直接拒绝
- 总文件数 > 200 直接拒绝
- 解压在临时目录,不污染主目录
- TTL 24 小时自动清理

**TASK-203 导览生成**:
- 10 个测试工程,**每个都能生成像样的导览**
- 导览必须符合 TASK-207 定义的 schema(项目类型、文件树、主入口、主要模型、知识点等)
- 输出符合 `05_EXPLANATION_STYLE_GUIDE.md`

**TASK-205 粗 RAG**:
- 关键词检索能命中:文件名 / block 名 / function 名 / 参数名
- 检索结果按相关度排序,取 top-k
- LLM 回答带 `citations` 字段(SourceRef 列表)
- **无证据的回答必须降级为"不确定"** —— 不许硬答
- 大工程(> N tokens)不能整包塞 prompt,要走粗 RAG

**TASK-207 Schema**:
- ProjectOverview 输出 JSON schema 固定字段:
  ```json
  {
    "project_title": "...",
    "project_type": "...",
    "one_sentence_summary": "...",
    "main_entry_files": [],
    "main_simulink_models": [],
    "main_execution_flow": [],
    "key_files": [],
    "key_blocks": [],
    "knowledge_points": [],
    "beginner_reading_order": [],
    "likely_confusing_points": [],
    "evidence": []
  }
  ```
- Schema 与 `05_EXPLANATION_STYLE_GUIDE.md` 对齐

**通用**:
- 用 curl / Postman 能完整跑通:上传 → 解析 → 取导览 → 粗 RAG 问答
- 单次问答响应 < 8s
- 所有错误返回中文友好提示

---

## Week 3:向量 RAG + 证据强制 + 教学优化

| 编号 | 名称 | 状态 | 负责 | 依赖 |
|------|------|------|------|------|
| TASK-301 | sentence-transformers 嵌入适配器 | ✅ | Codex | 101 |
| TASK-302 | SQLite 向量存储 + 检索 | ✅ | Codex | 204, 301 |
| TASK-303 | 工程分块策略(chunk + metadata) | ✅ | Codex | 102, 103, 107 |
| TASK-304 | 向量 RAG 整合到 ChatService | ✅ | Codex | 205, 302, 303 |
| TASK-305 | 教学 Prompt 优化(电气教材语境) | ✅ | Codex + PM | 304 |
| TASK-306 | 评测脚本 + 评测集运行 | ⏸ | Codex + PM | 304 |
| TASK-307 | **Evidence Citation Enforcer(证据引用强制器)** ⭐ | ✅ | Codex | 304 |
| TASK-308 | Simulation Explanation Pack(EvidenceBuilder + 讲解产物链) | ✅ | Codex + PM | 303, 307 |
| TASK-310 | 架构债重构(ProjectOverview contract relocation + TeachingUnit 最小闭环) | ✅ | Codex | 203, 207, 308 |

### Week 3 验收

**TASK-303 分块策略**:
每个 chunk 必须带这些 metadata:
```python
{
    "project_id": "...",
    "source_type": "m_file | slx_block | slx_subsystem | mat_variable | project_overview | teaching_unit",
    "file_path": "...",
    "symbol_name": "...",         # 函数名 / block 名 / 变量名
    "line_start": int,
    "line_end": int,
    "block_id": "...",
    "block_name": "...",
    "block_type": "...",
    "parent_subsystem": "...",
    "text": "自然语言描述,供 embedding 用"
}
```

**TASK-307 证据强制器**:
- 所有 LLM 回答必须包含 `citations` 字段(SourceRef 列表)
- 没有 citation 的回答 → 后端标记 warning,降级返回"不确定"答案
- 前端展示"依据"区块(文件路径 / 行号 / block 名)
- 评测脚本检查 citation 覆盖率,目标 ≥ 90%

**TASK-306 评测**:

每个测试工程准备 15 个问题:
- 5 个总体问题:"这个工程在做什么?"
- 5 个模块问题:"这个 block / 函数干什么?"
- 3 个参数问题:"这个参数为什么这么设?"
- 2 个修改问题:"我要改 XX 应该动哪里?"

评分标准(每题 100 分):
| 指标 | 分值 |
|------|------|
| 事实正确 | 30 |
| 能引用文件 / block / 行号 | 20 |
| 讲解像老师,不像文档 | 20 |
| 能指出用户下一步怎么操作 | 20 |
| 不编造 | 10 |

**平均分 < 70,不上线收费**。

**通用**:
- 同样问题,向量 RAG 模式 vs 粗 RAG 模式,**向量 RAG 准确率明显更高**
- 教学 prompt 输出符合 `05_EXPLANATION_STYLE_GUIDE.md`
- PM 主观评分 ≥ 7/10

---

## Week 4:Web 前端 + 上线收钱

| 编号 | 名称 | 状态 | 负责 | 依赖 |
|------|------|------|------|------|
| TASK-401 | 前端框架选型 + 项目搭建 | ✅ | Codex | Week 3 |
| TASK-402 | 上传页 + 工程导览页 | ✅ | Codex | 401, 202, 203 |
| TASK-403 | 问答对话页(展示 citations;v0.4 chat 页背景复用 PanoramaScene,commit 3bfa496 / #85) | ✅ | Codex | 401, 304, 307 |
| TASK-404 | 激活码系统(手动发码模式;v3.0冻结:暂不收费,决策22§1.4) | ⏸ | Codex | 204 |
| TASK-405 | 服务器部署 + HTTPS + 域名 | ↪ | 转交 | 全部后端 |
| TASK-406 | 内测发布 + 第一笔收钱 | ↪ | 转交 | 405 |

### Week 4 验收

**TASK-403 问答页**:
- 每个回答必须显示"依据"区块(citations 可点击跳到对应文件 / block)
- 无依据的回答以"不确定"样式呈现
- 支持追问

**通用**:
- 网页能从 0 上传到完整问答全流程
- 域名 + HTTPS 可访问
- **至少 1 人完成"上传工程 → 用完免费额度 → 付费激活码 → 继续问答"完整付费流程**
- 5 个学生真实上传自己的工程
- 3 个学生用完免费额度
- 1-3 个学生真实付款
- 至少 1 个学生表示"这个能帮我答辩 / 写报告 / 改模型"

---

## Task 详细文档模板

每个 Task 单独一个 markdown 文件,放在 `docs/tasks/task-NNN-<slug>.md`:

```markdown
# TASK-NNN: <Task 标题>

## 状态
🔲 未开始

## 上下文
(为什么要做这个 Task,在整个项目里的位置)

## 输入(前置依赖)
- 必须已完成的 Task:TASK-XXX
- 必须存在的文件 / 数据:...
- 必须读过的文档:01, 02, 04, (05 如涉及讲解输出)

## 输出(交付物)
- 新增/修改的文件清单(路径 + 简述)
- 新增的依赖(必须 review)
- 新增的配置项
- 新增的测试

## 范围(必须做)
- [ ] 具体可勾选的事项 1
- [ ] 具体可勾选的事项 2

## 不做(明确排除)
- ❌ 不做 A
- ❌ 不做 B

## 接口契约
(贴具体的 Python 类型签名,不许改签名)

## 验收标准
- [ ] 可验收事项 1(给出具体可跑的命令)
- [ ] 可验收事项 2
- [ ] 单元测试全绿
- [ ] 性能 / 体验指标(如适用)

## 风险与注意点
(已知的坑、容易出错的地方)

## 估时
预估 X 小时

## 给 Codex 的提示
(具体技术建议)
```

---

## 进度同步规则

- **每完成一个 Task**,Codex 提交 PR + 在 PR 描述里贴验收标准勾选清单
- **Claude review**(通过 PM 中转),按验收标准逐条核对
- 通过 → 合并 → 更新本 Index 状态为 ✅
- 不通过 → 打回 + 写明具体问题 → Codex 修 → 再 review

**禁止**:
- 跨 Task 混合修改
- 未走 review 直接合并
- 口头确认替代验收清单

---

## 当前进度

```
Week 0:  [✅✅✅⬜]              3/4
Week 1:  [✅✅✅✅✅✅✅✅]           8/8  (含 TASK-107 / TASK-108)
Week 2:  [✅✅✅✅✅✅✅✅✅]      9/9  (含 TASK-207 / TASK-208 / TASK-209)
Week 3:  [✅✅✅✅✅✅⏸✅✅]  8/9
Week 4:  [✅✅✅⏸↪↪]           3/6
Week 5+: [✅✅✅✅🔍]            4/5  (paper-to-model TASK-500~503;TASK-510 待 PM 合并)

总计: 35/41
```

---

## 下一步

**当前状态**:**paper-to-model v0.1 主线门槛 5 已解封**(2026-06-20;TASK-500/501/502 ✅,TASK-503 v0.2.4 + decision 25 验收通过)。TASK-503 完成 TuningSuggestion、持久化 PaperBundleStore、GET spec/plan 路由、D 根因方向 A、上传真事务与 evaluator 双轴判分改造;R6 true run 两 case 达标(material `succeeded + partial`,missing `succeeded + pass`),fixture 零 diff,R2 真值源已入 main。Week 5+ paper-to-model 线当前 4/5;TASK-510 MATLAB Add-on 连接桥 spike 实施完成待 PM 合并,只证明传输桥,不接 Engine。总进度纳入 TASK-510 后为 35/41。下一步进入 paper-to-model 后续 task / v0.2 多 case 评测规划,judge 仍按 decision 25 留到 v0.2 多 case。

## Week 5+:paper-to-model 主线占位

TASK-501 系列用于 paper-to-model 主线。派发任何 TASK-501 前,必须先完成决策 22 § 10.4 的五项开门 chore:06 三套契约 / MissingParameterPrompt + EvidencePack 双源 / 文档上传安全 / 产品文案与对外口径 / 评测准入。五项全 ✅ 后,再进入文档解析 → PaperSpec → ModelGenerationPlan → 调参建议。

| 编号 | 名称 | 状态 | 负责 | 备注 |
|------|------|------|------|------|
| TASK-500 | paper-to-model 开门 chore(5 项前置硬门槛一锅炖) | ✅ | Codex | 5 项门槛全部入仓,paper-to-model 主线解封 |
| TASK-501 | PaperPlanService 与资料入口实现起点 | ✅ | Codex | TASK-500 已合并,可派单 |
| TASK-502 | PaperPlanService + 4 prompt yaml + Python helper + MissingDetector + UserSupplyMerger | ✅ | Codex | 已合并 main 2026-06-18 PR #99,转 TASK-503 |
| TASK-503 | TuningSuggestion + 持久化 PaperBundleStore + GET 路由 + D 根因方向 A + R6 整体门槛 5 解封 | ✅ | Codex | v0.2.4 + decision 25 验收通过，整体门槛 5 解封 |
| TASK-510 | MATLAB Add-on 连接桥 spike(v0.3-a) | 🔍 | Codex | 实施完成待 PM 合并;只证传输桥,不接 Engine;PM 合并后 ✅ |
└─ R6 后置修复(evaluator true run)PR #102(2026-06-19)

**决策 09 反例库**:108 → **171**(TASK-310 累积 +54;TASK-503 v0.2.4 第 49 任起草线 +9;含 38 任 PR 准备阶段 + 39 任 PR #1 / PR #2 / chore PR 阶段):

- K_28a 36 → **56**(+20):38 任 +13(R0 / R1 / Round 1 / Round 2 / D-E-F 五段)/ 39 任 +4(派单凭印象 migrations 目录 + projects 表名 + overview_schemas 期望窄 + 索引数字 32/34 凭印象)/ 49 任 +3(TASK-503 v0.2.4 起草线:凭交接包转述写"12 项参数"(实测 15)+ 凭印象写 decision 编号 23(实测应 25)+ 推 A 重做未核 v0.2.3→v0.2.4 改动范围)
- K_28b 4 → **10**(+6):38 任 +5(起稿粒度反复)/ 39 任 +1(治标 vs 治本决策点漏明示)
- K_30 23 → **31**(+8):38 任 +7(R0 / R1 / Round 1 / 派单 / freeze 跨段)/ 39 任 +1(派单验收 ruff format --check 漏列,PR #1 K_30 同款未消化)
- K_31 2 → 2(沿用)
- K_34 9 → 9(沿用)
- K_36 13 → **22**(+9):38 任 +6(env 项目级归档 / 验收清单粒度)/ 39 任 +2(派单验收清单只补 mypy 漏 ruff format / 同类 CI step 拆条)/ 49 任 +1(推 A 重做未核范围红线,与 K_28a 双重记账)
- **K 总(剔除救场)= 87 → 130**(+43)
- Codex 守门救场 13 → **23**(+10):38 任 +5(Round 1 命令本体错 / Round 2 派单 git 真值错 / Round 2 #7+#13 freeze 守门 / E 段找回 mxa env / F 段项目级归档补齐)/ 39 任 +4(PR #2 Stage 0 Round 3 #14 migrations 目录 + #3 overview_schemas 期望 + PR #1 CI mypy 自动化救场 + PR #2 CI ruff format 自动化救场)/ 49 任 +1(取证 16 第一行实测拦下"main 无 task-503 任务卡",派单 base 假设错)
- PM 救场架构师 6 → **18**(+12):38 任 +5(D1-B / R0 / 修订工艺 / 单文件整合 / env 归档不全)/ 39 任 +3(PR #1 治标 vs 治本 / PR #2 "一次跑绿 CI" / chore PR 数字 "一来就错")/ 49 任 +4(四次一句话点破:框架性授权后过度请示 / 推 A 重做 / "怎么还要拍"等)
- **反例库总计 = 130 + 23 + 18 = 171**

> **自 41 任(决策 22)起,反例库改趋势记账(不再逐位累加)**:第 49 任 TASK-503 v0.2.4 起草线新增趋势集中在 K_28a(+3:12 项参数 / decision 23 / 推 A 重做范围)、K_36(+1:范围红线)、Codex 守门救场(+1:取证 16 拦 base 假设错)、PM 救场架构师(+4:四次一句话点破)。三层审查(GPT 决策质量 / Codex 实测 / PM 兜底)继续正常工作,无漏入仓。详决策 22 § 9。

**触发独立阈值**:K_28a ≥ 10 / K_28b ≥ 5 / K_30 ≥ 5 / K_31 ≥ 2 / K_34 ≥ 5 / K_36 ≥ 2 / Codex 守门救场 ≥ 5 / PM 救场架构师 ≥ 5 全部稳定触发。

**v0.5 协议候选 6 项**(累积至本任,待后续正式起 v0.5 协议升级 task 立项):
1. 架构师采纳 R 轮带数值反馈前必须 Codex 摸底实证(R6/R7 子规则;38 任 P0-1 反例)
2. Stage 0 命令清单必须含 #0 baseline 健康检查(R7 子规则;38 任 D 段反例)
3. 工具环境真值识别为项目级时归档项目级文档(K_36 子规则;38 任 F 段反例)
4. 架构师起任何 git 操作前必须 `git log --oneline -10` 实测前任工作流(K_28a + K_36 子规则;38 任终任反例;本任 chore PR docs/04 § 1.4 已同步归档)
5. 派单 prompt 验收硬清单必含 `make check` 全管道,禁拆 CI step 列(K_36 子规则;39 任 PR #1 mypy + PR #2 ruff format 同款两次)
6. 架构师起稿宪法级 / 契约级文档时,必须 grep 现有 schema / contract / 治理流程 / 文件存在性 / 自身前序版本最终字面;不许凭概念名 / 知识库草案 / 历史印象假设(K_28a + K_34 子规则;41 任决策 22 反例)

---

**版本**:v3.0(delta)
**最后更新**:2026-06-20
