# 工程问答评测题型设计 v0.1

> 本文档是评测体系长期 reference,由 TASK-305 产出,TASK-306 消费,后续 prompt 回归 / dashboard 复用。
> 本文档不含可执行评测脚本 / 真实评测题集 / baseline CSV,这些由 TASK-306 落地。

> 目录分工:
> - `docs/eval/` = 长期设计文档(题型设计 / 评分维度 / 评测体系 reference,本文档归此)
> - `eval/` = 可执行 cases / results / scripts(TASK-306 落地;`eval/cases/*.json` 真实题集、`eval/results/*.csv` baseline / 对照、`eval/run_eval.py` 脚本)
> - 后续路径不再摇摆

## 1. 评测目的

- 验证 v0.2-rc prompt 相比 v0.1 baseline 是否提升
- 验证向量 RAG(HybridRetriever)相比粗 RAG(KeywordRetriever)是否提升
- 验证 8 类 source_type 教学化说明是否帮助 LLM 正确引用
- 验证 glossary 快照是否提升中文术语对齐分

## 2. 题型分类(每工程 15 题)

| 类型 | 题数 | 描述 | 期望 `citation_ids` 类型(LLM 输出层) |
|---|:-:|---|---|
| 总体问题 | 5 | "这个工程在做什么?" / "主入口是哪个?" | overview / file / function |
| 模块问题 | 5 | "这个 block / 函数干什么?" / "SpeedLoop 子系统怎么工作?" | block / subsystem / function |
| 参数问题 | 3 | "这个参数为什么这么设?" / "Kp 设 5.0 合理吗?" | block / function / param |
| 修改问题 | 2 | "我要改速度环响应,应该动哪里?" | block / function |

字段命名约定:
- LLM 输出层:`citation_ids: ["S1", "S3"]`(source_id 字符串列表;ChatLLMResponse schema)
- 服务端展开后:`citations: list[SourceRef]`(SourceRef 列表;ChatAnswer / ChatResponse schema)
- 本文档评测维度的"引用"主要评 LLM 输出层是否正确给 source_id,故用 `citation_ids`
- "期望 citation_ids 类型"列指该 source_id 对应 RetrievalHit.source_type 在 8 类中的哪类

## 3. 评分维度(每题 100 分)

| 维度 | 分值 | 评分要点 |
|---|:-:|---|
| 事实正确 | 30 | 答案符合工程实际配置;不编造文件 / block / 函数名 |
| 引用完整 | 20 | LLM 输出 `citation_ids` 字段含至少 1 个有效 source_id;source_id 真实存在于「证据清单」 |
| 教学性 | 20 | 像老师讲,不像 ChatGPT 背书;无寒暄;先结论后依据 |
| 可操作 | 20 | 指明学生下一步看哪 / 改哪;不写"先理解基础概念"空话 |
| 不编造 | 10 | 证据不足时主动走 E 类(confidence=low,`citation_ids=[]`) |

通过线:平均分 >= 70 才能升 v0.2 final。

## 4. 每类题型典型样例

当前 `source_block` 渲染仅含 `source_id + source_type + snippet`,LLM 拿不到 `SourceRef.line_range`。样例中的引用措辞不暗示具体行号;若 v0.3+ 需要让 LLM 引用行号,要改 `source_block` 渲染,不在 TASK-305 范围。

### 4.1 总体问题

样例 1:
- 问:"这个工程是做什么的?"
- 期望答(摘要):"这是一个 PMSM 矢量控制仿真工程,顶层模型 pmsm_foc.slx 实现速度环 + 电流环闭环,主入口 run_simulation.m..."
- 期望 `citation_ids` 类型:`[overview]` 或 `[overview, file]`
- 评分预期:事实正确 30 / 引用 20 / 教学性 18-20 / 可操作 0-10(总体问题不强求可操作)/ 不编造 10

样例 2:
- 问:"主入口是哪个文件?为什么?"
- 期望答(摘要):"主入口是 run_simulation.m。从 ProjectGraph 看它调用 sim('pmsm_foc.slx') 启动仿真,且其他 .m 文件(init_params.m / plot_results.m)都通过它串起..."
- 期望 `citation_ids` 类型:`[file]` 或 `[file, function]`

### 4.2 模块问题

样例 1:
- 问:"SpeedLoop 子系统怎么工作?"
- 期望答(摘要):"SpeedLoop 子系统接收速度参考 omega_ref 和实测速度 omega,做差后通过 PI 控制器输出 Iq_ref 给电流环。PI 参数 Kp=5.0,Ki=100..."
- 期望 `citation_ids` 类型:`[subsystem, block]` 或 `[subsystem, block, file]`

样例 2:
- 问:"这个工程里的 FFT 模块怎么用的?"
- 期望答(摘要):"FFT 函数 fft_analysis.m 接收时域信号,输出频谱。从函数定义看,采样频率 fs 用作输入参数,N 点 FFT 默认 1024 点。你想分析频谱时调这个函数,把信号数组传进去..."
- 期望 `citation_ids` 类型:`[function, file]` 或 `[block]`(若 Simulink FFT block)
- 覆盖说明:若 306 评测集含信号处理 / 通信工程,本样例的术语对齐(FFT / 采样频率 / N 点)用得上 glossary 中的通信小类

### 4.3 参数问题

样例 1:
- 问:"速度环 Kp 设 5.0 是为什么?"
- 期望答(摘要):"从 init_params.m 的参数定义看 Kp=5.0,这是 PMSM 速度环常见经验起点。Kp 决定响应速度;如果你想调,先小幅改 Kp(±20%)观察转速曲线..."
- 期望 `citation_ids` 类型:`[file, block]`(参数本身在 .m 文件,使用在 Simulink block)
- 守门:答案不写"第 15 行";`source_block` 不渲染 line_range,LLM 看不到具体行号

### 4.4 修改问题

样例 1:
- 问:"我想让速度响应更快,应该改哪里?"
- 期望答(摘要):"主要改速度环 PI 参数:先小幅增大 init_params.m 里的 Kp,改完跑一次仿真看转速曲线。不要同时动 Ki..."
- 期望 `citation_ids` 类型:`[file, block]`

## 5. 边界 case(故意诱导出 E 类回答)

每工程额外 1-2 个,用于验证证据强制器 / E 类降级是否正常。

- "这个工程跑出来的转速峰值是多少?"(需运行仿真;期望 E 类,confidence=low,`citation_ids=[]`)
- "Kp 设到多少最好?"(无证据的具体建议;期望 E 类,不许编造)
- "为什么作者选了这个控制方案而不是 DTC?"(超出工程文件能回答的范围;期望 E 类)

## 6. 评分流程(给 TASK-306 参考)

由 TASK-306 落地;本文档不含脚本。

1. 选 5 个测试工程(03 索引 Week 0 验收 10 个的子集)
2. 每工程 15 题 x 5 工程 = 75 题
3. 跑 v0.1 baseline + v0.2-rc 对照各 1 轮(75 x 2 = 150 次 LLM 调用)
4. 每题人工评分(PM + 二审过)按 § 3 的 5 维打分
5. 输出 CSV:`eval/results/qa_v0.1_baseline_<date>.csv` + `eval/results/qa_v0.2_rc_<date>.csv`
6. v0.2-rc 平均分 - v0.1 平均分 >= 5 分(且 >= 70 分) -> PM 拍板升 v0.2 final
7. 不达标 -> 305 v0.3 草稿(由 PM 单独派活)

## 7. 不在本文档范围

- 评测脚本 `eval/run_eval.py`(TASK-306)
- 真实评测题集 `eval/cases/*.json`(TASK-306)
- baseline CSV(TASK-306)
- 人工评分细则模板(TASK-306,本设计文档仅给维度 + 分值)
- 评测 dashboard(Phase 2)
- 自动化打分(LLM-as-judge;Phase 2 候选,需独立评估对齐)
