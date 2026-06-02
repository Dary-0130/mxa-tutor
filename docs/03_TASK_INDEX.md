# Task 索引 · TASK INDEX

> **前置阅读**:
> 1. `01_PROJECT_CONSTITUTION.md` — 项目宪法
> 2. `02_ARCHITECTURE_OVERVIEW.md` — 架构总览
> 3. `04_ENGINEERING_STANDARDS.md` — 工程规范
> 4. `05_EXPLANATION_STYLE_GUIDE.md` — 教学输出风格
>
> 本文是 **MCS 阶段所有 Task 的总纲**(4 周交付可收费产品)。
> **版本:v2.1(冻结)**

---

## Task 状态约定

- 🔲 未开始
- 🟡 进行中
- 🔍 等待验收
- ✅ 已通过
- ❌ 打回返工
- ⏸ 暂停 / 冻结

---

## Task 编号体系

```
TASK-WNN
       │
       └─ W = Week number (0-9), NN = 该周内序号
```

例:`TASK-101` = Week 1 第 01 个 Task。

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
| TASK-103 | .m 文件解析器 | 🔲 | Codex | 101 |
| TASK-104 | 工程压缩包安全解压 + 文件分类(含沙箱) | 🔲 | Codex | 101 |
| TASK-105 | 文件依赖关系分析 | 🔲 | Codex | 103 |
| TASK-106 | DeepSeek TextProvider 实现 | 🔲 | Codex | 101 |
| TASK-107 | **ProjectGraph + TeachingUnit 基础构建器** ⭐ | 🔲 | Codex | 102, 103, 105 |

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
| TASK-201 | FastAPI 框架搭建 + 健康检查 | 🔲 | Codex | Week 1 |
| TASK-202 | 上传 + 解析 API(异步,含沙箱) | 🔲 | Codex | 104, 105, 201 |
| TASK-203 | ProjectOverviewService(基于 TeachingUnit 生成导览) | 🔲 | Codex | 106, 107 |
| TASK-204 | SQLite 存储层(Project + Chat) | 🔲 | Codex | 101 |
| TASK-205 | **粗 RAG 问答 API(关键词 + metadata 检索)** ⭐ | 🔲 | Codex | 203, 204 |
| TASK-206 | 错误处理 + 中文化 | 🔲 | Codex | 201-205 |
| TASK-207 | **ProjectOverview Schema + 教学输出契约** ⭐ | 🔲 | Codex | 203 |

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
| TASK-301 | sentence-transformers 嵌入适配器 | 🔲 | Codex | 101 |
| TASK-302 | SQLite 向量存储 + 检索 | 🔲 | Codex | 204, 301 |
| TASK-303 | 工程分块策略(chunk + metadata) | 🔲 | Codex | 102, 103, 107 |
| TASK-304 | 向量 RAG 整合到 ChatService | 🔲 | Codex | 205, 302, 303 |
| TASK-305 | 教学 Prompt 优化(电气教材语境) | 🔲 | Codex + PM | 304 |
| TASK-306 | 评测脚本 + 评测集运行 | 🔲 | Codex + PM | 304 |
| TASK-307 | **Evidence Citation Enforcer(证据引用强制器)** ⭐ | 🔲 | Codex | 304 |

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
| TASK-401 | 前端框架选型 + 项目搭建 | 🔲 | Codex | Week 3 |
| TASK-402 | 上传页 + 工程导览页 | 🔲 | Codex | 401, 202, 203 |
| TASK-403 | 问答对话页(展示 citations) | 🔲 | Codex | 401, 304, 307 |
| TASK-404 | 激活码系统(手动发码模式) | 🔲 | Codex | 204 |
| TASK-405 | 服务器部署 + HTTPS + 域名 | 🔲 | Codex + PM | 全部后端 |
| TASK-406 | 内测发布 + 第一笔收钱 | 🔲 | PM | 405 |

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
Week 0:  [✅🔍✅⬜]              2/4
Week 1:  [✅✅⬜⬜⬜⬜⬜]         2/7  (含 TASK-107)
Week 2:  [⬜⬜⬜⬜⬜⬜⬜]         0/7  (含 TASK-207)
Week 3:  [⬜⬜⬜⬜⬜⬜⬜]         0/7  (含 TASK-307)
Week 4:  [⬜⬜⬜⬜⬜⬜]           0/6

总计: 1/31
```

---

## 下一步

**下一个待启动**:TASK-001 GitHub 私有仓库 + 项目骨架

PM 准备好:
1. GitHub 账号 + 创建 private repo
2. 本地开发机 Python 3.11 环境
3. 准备好 10 个真实 .slx / 工程文件,放在专门文件夹备用
4. 5 份文档放入仓库 `docs/`

完成后通知 Claude → Claude 写 TASK-001 详细文档 → PM 传给 Codex → 开干。

---

**版本**:v2.1(冻结)
**最后更新**:2026-06-01
