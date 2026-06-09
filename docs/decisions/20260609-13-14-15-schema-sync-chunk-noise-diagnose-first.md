# 本轮可永久固化的决策

以下 3 条建议作为新决策写入项目决策日志,跟 chunk 质量过滤一起 commit。

---

## 决策 13: schema 约束改动必须列出全部同步文件

### 背景

PR #58 改了 overview_schemas.py 的 3 个约束值(min_length/max_length),
CI 连挂三轮才发现 test_schema_freeze.py、test_overview_schemas.py、
06_OUTPUT_CONTRACTS.md、project_overview.schema.json 没同步。

### 规则

凡改动 `*_schemas.py` 或 `core/interfaces/*.py` 中的 Pydantic Field 约束
(min_length/max_length/ge/le/Literal 枚举值),PR 任务文档**必须**列出以下同步清单
并逐项确认:

```text
□ 对应的 test_schema_freeze.py 期望值
□ 对应的 test_*_schemas.py 边界测试数据
□ docs/06_OUTPUT_CONTRACTS.md 相关描述
□ schemas/*.schema.json 相关字段
□ 如涉及 project_type Literal: core/prompts/*.yaml + docs/05_EXPLANATION_STYLE_GUIDE.md
```

Codex 完工报告里必须贴这些文件的 diff。缺任何一项 = 未完工。

### 理由

freeze 测试和 schema JSON 是项目的"契约守门",改了源不同步守门等于绕过了守门。
这轮多花了 3 轮 CI 修复,耗时 ~40 分钟。

---

## 决策 14: chunker 必须同时保证"不丢信息"和"不加噪音"

### 背景

TASK-303 设计原则"每个 SlxBlock 产 1 个 chunk",在 DAB_Control 工程上产出
119 个 chunks(含 57 slx_block + 57 m_file Section 4 per-block),
其中 ~100 个是低价值或重复的(8 个同参数 Mosfet、19 个 From/Goto 路由块、
5 个 Scope 显示块)。top_k=8 的检索被噪音占满,真正的参数 chunk 排到 29-107 名,
LLM 完全看不到,fallback 6/8。

chunk 质量过滤后 119→21 chunks,fallback 降到 2/8。

### 规则

1. **Parser 层全量保留**:所有 block、所有 section、所有变量都保留在 domain 对象里,
   不在 parser 层丢弃任何信息。

2. **Chunker 层按价值筛选**:不是每个 domain 对象都产 chunk。判断标准:
   - block_type 在 DROP_BLOCK_TYPES(Scope/Clock/From/Goto/Mux/Demux/Display)→ 不产 chunk
   - block.parameters 过滤掉 METADATA_PARAM_KEYS 后为空 → 不产 chunk
   - 同参数重复 block(group_key 相同,≥3 个,同 family name)→ 合并为 1 个代表 chunk

3. **source_text 只含有意义的参数**:构造 source_text 时使用 _meaningful_params
   过滤后的参数,不塞 Position/SourceType/RTW 等元数据。

4. **.m 导出脚本的 Block Parameters 段不产 per-block chunk**:
   该段内容与 slx_block chunks 冗余且更贫瘠,产 chunk 只会稀释检索质量。

5. **新增 chunk 类型或批量扩展前必须评估噪音影响**:
   跑至少 1 个真实工程的 top_k 检索,确认新 chunks 不会把高价值 chunks 挤出 top_k。

### 理由

embedding 模型是通用语义模型,不理解"Mosfet 的 SourceBlock 元数据对回答电压问题没用"。
chunk 数量越多,噪音 chunk 占据 top_k 的概率越高。检索层的 top_k/rerank 是补丁,
不能替代 chunker 层的质量控制。

---

## 决策 15: 诊断先行,定位瓶颈再改代码

### 背景

本轮 chunker 改造经历了"改了没用 → 再改更差 → 诊断定位 → 治本见效"的过程:
- v3(MScript 切段):以为 Section 4 截断是主因,切了段,fallback 从 2 涨到 5
- v4(per-block 拆分):以为切得不够细,拆成 per-block,fallback 涨到 6
- 诊断脚本跑完才发现:chunks 在 DB、embedding 正常、相似度过阈值,
  但 top_k=8 被 7 个 Mosfet 占满——瓶颈根本不在"切得细不细",在"噪音太多"

如果一开始就跑诊断,可以省掉 v3→v4 两轮无效改造。

### 规则

遇到"改了代码但效果没改善"时,**禁止连续盲改**。必须:

1. 写诊断脚本逐层检查数据流(DB → embedding → 相似度排名 → top_k 内容 → prompt → LLM 输出)
2. 定位到具体哪一层丢了数据或引入了噪音
3. 针对定位结果改代码
4. 改完再跑评测确认

诊断脚本不入仓,但保留在工作目录供后续复用。

### 理由

LLM 应用的 debug 链路长(数据 → chunk → embedding → 检索 → prompt → LLM → 校验 → 输出),
凭直觉改某一层很容易改错方向。诊断脚本的成本(30 分钟)远低于盲改两轮的成本(3+ 小时)。
