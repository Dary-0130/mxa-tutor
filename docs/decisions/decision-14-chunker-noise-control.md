# 决策 14: chunker 必须同时保证"不丢信息"和"不加噪音"

## 背景

TASK-303 设计原则"每个 SlxBlock 产 1 个 chunk",在 DAB_Control 工程上产出
119 个 chunks(含 57 slx_block + 57 m_file Section 4 per-block),
其中 ~100 个是低价值或重复的(8 个同参数 Mosfet、19 个 From/Goto 路由块、
5 个 Scope 显示块)。top_k=8 的检索被噪音占满,真正的参数 chunk 排到 29-107 名,
LLM 完全看不到,fallback 6/8。

chunk 质量过滤后 119→21 chunks,fallback 降到 2/8。

## 规则

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

## 理由

embedding 模型是通用语义模型,不理解"Mosfet 的 SourceBlock 元数据对回答电压问题没用"。
chunk 数量越多,噪音 chunk 占据 top_k 的概率越高。检索层的 top_k/rerank 是补丁,
不能替代 chunker 层的质量控制。
