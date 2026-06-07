# 评分员指南 v0.1

## 0 评分前准备

### 0.1 一致性校准

正式评分前,PM 与 reviewer 先共同试评 10 条,讨论事实正确、引用完整、教学性、可操作、不编造五个维度的锚点。校准结束后再独立评分正式队列。

### 0.2 半盲化评分

评分员只填写 `scoring_queue_scored_<scorer>.csv`,不直接查看 raw、unblind 或 final 层文件。

`scoring_queue.csv` 不含 `prompt_version`、`prompt_path`、`loaded_prompt_*`、`model_name`、`temperature`、`top_p`、`run_id`。队列保留 `project_alias` 与 `case_id`,用于核对工程语境,但不暴露 baseline/rc 身份。

### 0.3 评分独立

PM 与 reviewer 正式评分时不互看分数和备注。两份评分交给 `finalize_scores.py` 合并,脚本会自动检测是否需要 adjudication。

### 0.4 工程上下文核对

评分员可查看 `scoring_project_key.csv`,用 `project_alias` 找到 `source_case_dir`、`domain`、`fixture_class`。事实评分时应对照解压后的 `.slx`、`.m` 与模型结构,确认答案提到的文件、block、function、parameter 是否真实属于该工程。

## 1 事实正确

满分 30 分。

- 0 分:与工程实际明显冲突,或把另一个工程的文件/模块说成本工程内容。
- 10 分:只说对少量泛化背景,关键工程事实缺失或混乱。
- 20 分:主体事实正确,但有局部遗漏、顺序混淆或轻微过度概括。
- 30 分:能准确对应工程文件、模型、子系统、信号流或参数语境,且没有关键事实错误。

edge 题如果静态文件无法回答,正确行为是低置信拒绝拍板;编造仿真结果或最优参数应在事实维度扣重分。

## 2 引用完整

满分 20 分。

引用评分只依据 `source_table_json` 和 citation 字段,其中 `source_table_json` 来自 `RecordingPromptBuilder` 捕获的 `ChatPromptBuilder.build_messages(source_entries=...)` 实际输入。`retrieval_hit_types_json` 仅供诊断,不作为评分依据。

三档优先级:

1. `citation_type_source=raw_llm`:用 `raw_citation_id_type_map_json` 判断 LLM 返回的 source_id 是否命中题目要求的 `expected_citation_types_any_of` 和 `required_citation_types_all_of`。
2. `citation_type_source=recording_prompt_builder_match`:当 raw citation id 不可用,但 returned citations 能与 `source_table_json` 匹配时,按匹配到的 source_type 评分,报告中标注 prompt-builder matched mode。
3. `citation_type_source=unavailable`:source table 不可得,该 case 的 citation 维度不做 final 结论;core answer set 若出现 unavailable,本轮 citation comparison 标 invalid。

锚点:

- 0 分:无 citation,或 citation 与答案主张无关,或 required all_of 明显缺失。
- 10 分:引用覆盖部分关键证据,但 any_of/all_of 命中不足或引用粒度偏泛。
- 20 分:引用类型和答案主张匹配,能覆盖题目要求的核心文件、子系统、block、overview 或 graph entry。

## 3 教学性

满分 20 分。

- 0 分:只给结论或堆名词,不能帮助本科生理解。
- 5 分:有少量解释,但结构松散或术语未解释。
- 10 分:能解释基本作用和因果关系,但缺少学习顺序或重点。
- 15 分:说明清楚,能把模型结构、控制目标、信号流或参数作用讲成可学习路径。
- 20 分:像助教一样分层讲解,既准确又易读,能帮助学生建立工程整体认知。

## 4 可操作

满分 20 分。

- 0 分:没有可执行建议,或建议会误导用户乱改模型。
- 5 分:给出泛化建议,但不能定位到具体文件/模块/参数。
- 10 分:能指出大致位置或检查方向。
- 15 分:给出合理阅读、定位、修改或实验顺序,并说明主要风险。
- 20 分:建议具体、稳妥、可复现,能区分先观察、再调参、最后验证的步骤。

## 5 不编造

满分 10 分。

- 0 分:编造静态工程中不存在的结果、最优参数、仿真数值或文件结构。
- 5 分:多数内容有根据,但有未经证据支持的拍板式表述。
- 10 分:能明确区分证据可支持的结论和需要运行仿真/额外实验才能确认的内容。

## 6 边界 Case

`expected_behavior=edge_e_class` 的题通常要求运行时数据、最优整定或静态工程无法确定的结果。理想答案应:

- 明确说明当前静态工程证据不足。
- `confidence` 倾向 low。
- 不给具体仿真数值或最优参数。
- citation 可以为空;若引用,只能引用能说明为什么无法直接拍板的工程结构证据。

边界题中,低置信拒绝编造比貌似完整但无依据的答案更高分。

## 7 R12 Sentinel 扣分

若答案泄漏 `__project_overview__` 等内部 sentinel 字面,按以下原则扣分:

- 轻微泄漏但事实和引用仍可用:事实或教学维度酌情扣分。
- 把 sentinel 当成用户可见文件、模型或真实工程对象:事实维度重扣。
- sentinel 泄漏伴随编造内部机制:不编造维度重扣。

`sentinel_leaked=true` 是提醒字段,最终扣分仍由评分员结合答案内容判断。

## 8 一致性与 Adjudication

### 8.1 阈值

`finalize_scores.py` 自动触发 adjudication 的条件:

- 单题 `total` delta > 15。
- 任一 20 分维度 delta > 10。
- `factual` 30 分维度 delta > 15。

### 8.2 全集守门

若评分后 `mean_abs_delta > 8` 或 flagged cases > 20%,PM 与 reviewer 应二次校准后再继续。脚本层面会列出 required adjudication cases,但评分一致性解释需要写入评测报告。

### 8.3 Final 公式

`case_final_total = adjudicated_total if adjudicated_total != blank else (pm_total + reviewer_total) / 2`

adjudicated case 以 adjudicator 拍板分为准;非 adjudicated case 取两人均值。

### 8.4 两阶段流程

第一阶段运行 `finalize_scores.py` 不传 `--adjudication-resolved`。若存在 required case,脚本生成 `adjudication_queue.csv`,返回退出码 2,不生成 `qa_final_scored_merged.csv`。

adjudicator 填写 `adjudication_resolved.csv`,包含 `blind_id`、`adjudicated_total`、`adjudicator_notes`。

第二阶段重新运行 `finalize_scores.py --adjudication-resolved ...`。脚本校验所有 required case 均已 resolved 后,生成 4 个 unblind per-version per-scorer CSV 和 `qa_final_scored_merged.csv`。评测报告只消费 `qa_final_scored_merged.csv`,且要求 `unresolved_adjudication_count == 0`。
