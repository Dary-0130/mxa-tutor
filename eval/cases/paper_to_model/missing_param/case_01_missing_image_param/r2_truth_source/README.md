# R2 真值源事实表 — `document_facts.json`

> 用途:TASK-503 v0.2.4 evaluator R2 死规则裁决冲突型 + 幻觉型误报。
> 维护:架构师起草 + PM 核审。
> 触碰约束:**actor 不读**。

## 1. 用途

R2 评测两类误报:

- **冲突型**:文档已给值,SUT 却把该参数报为缺失(`actual_prompt.parameter_name ∈ document_given_values[*].canonical_param_name`)
- **幻觉型**:文档完全未提,SUT 凭空报缺失(`actual_prompt.parameter_name ∈ document_not_mentioned[*].canonical_param_name`)

R2 **不验**:
- SUT 是否报全所有 missing 参数(漏报盲评 → v0.2 多 case + judge)
- SUT 对开放世界参数(既不在 given_values 也不在 not_mentioned)的合理性(那是 judge 域)

## 2. 与 `input/expected_missing_prompts.json` 的区别

| 维度 | `expected_missing_prompts.json`(降级为参考样例) | `document_facts.json`(R2 判分真值源) |
|---|---|---|
| 声明对象 | SUT 应列出哪 N 个 missing prompt(N 固定) | 文档对参数 X 的明确陈述(给值 / 未提) |
| 数量约束 | 隐含 actual == expected | 数量不约束;只验冲突 + 幻觉 |
| ID 依赖 | 依赖固定 `MISS-001..006` 字面 | 不依赖 prompt_id,按 canonical name |
| 漏报判断 | 隐含 | 不判 |
| 多报判断 | 隐含 | 只判冲突 / 幻觉子集 |
| evaluator 读取 | 不读(降级注见 `case_README.md`) | 读 |

## 3. actor 不读保证

`actor`(PaperSpecService.extract / PaperPlanService.generate / MissingDetector)在评测运行期**不接收**本目录任何文件作为输入。evaluator 在所有 actor 调用完成后,才读取本目录数据进行 R2 判分。

防答案泄漏由 evaluator 代码保证(TASK-503 v0.2.4 R1a-pre-5 答案泄漏防护):runtime 实测 actor 调用阶段无 `r2_truth_source/` 路径出现在文件读取栈;若有,R1a-pre-5 fail。

## 4. locator 锚定策略

本 case 无 `expected_paper_spec.json`(无 PaperSpec golden),因此 locator **单源** = source_doc markdown 标题 + 行号:

```json
"locator": {
  "source_doc_heading": "## 2 电机参数与工况",
  "source_doc_line_range": [27, 41],
  "excerpt": "..."
}
```

R2 算法不强校验 locator 实际命中 source_doc(那是 PM / 架构师人工核审真值源事实正确性的依据,不是机器判分输入)。

未来若 case 增加 `expected_paper_spec.json`,可双源对齐 PaperSpec `paper_section_id`,提升真值源可信度。

## 5. 维护责任

- **架构师**起草 `document_given_values` 与 `document_not_mentioned` 候选条目,逐条对照 `input/source_doc_stripped.md` 标记 locator
- **PM** 核审两个列表的事实正确性(架构师无 docx 原文,架构师摘字面后 PM 核 vs 同步发电机原 docx)
- **case 增加 / 改动时**:遵守"事实正确性优先于覆盖率"— `document_not_mentioned` 只列有把握声明且 SUT 可能误报的具体参数,**不穷举开放世界**

## 6. 当前状态

- `document_given_values`:**15 项**,取自 `input/source_doc_stripped.md` `## 2 电机参数与工况` 行 27-41(同步发电机 12 项 pu 参数 + 3 项工程参数)
- `document_not_mentioned`:**空列表 `[]`**(初始无具体声明;case 增加时按需补)

## 7. 改动入仓

本目录任何文件改动需经 R6 实测(TASK-503 v0.2.4 evaluator R2 集成测试两 case 真跑;材料 case R2 不适用 → N/A;missing case R2 验冲突 + 幻觉)+ PM 核审通过。
