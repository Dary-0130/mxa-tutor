# TASK-305:教学 Prompt 优化(候选驱动 + glossary + 评测设计)

## 状态

🟢 v0.1.4(2026-06-07;GPT R1 + R2 + R3 + R4 = 22 条反馈全采纳;**PM 拍板不进行 R5**,修完直接进 Codex 第一棒)

---

## GPT R4 反馈台账(2026-06-07,2 P1 + 2 P2 + 1 P3 全采纳;**最后一轮兜底**)

> **R4 主判定**:**小修后可放行,主体架构边界已稳**;唯一阻断是**执行清单文案在 Windows + PowerShell + venv 真能跑的最后一公里**。PM 拍板不进行 R5;修完直接进 Codex。

| # | 严重度 | 问题 | v0.1.4 修订位置 | 反例溯源 |
|:-:|:-:|---|---|---|
| **P1-1** | P1 | Shell 约定误停手:R3 说"默认 bash + 找不到工具停手",但 PowerShell 跑 bash 字面必失败,明明有 rg 备选却被要求停手 | **Shell 约定大重写**:Codex 实施前**选定一套工具链**(推荐 PowerShell + rg + .venv),全程统一;**只在选定工具链工具不可用时停手**;不因另一套不可用而停手 | **流程逻辑错位**(R3 修订写得对但触发条件错位)|
| **P1-2** | P1 | #22 显式 venv 方案**不等价** `make check`:漏 `pytest -v` 全测试 / `ruff format --check` / `mypy core/ adapters/ features/ api/` 4 目录 / `hygiene` 4 个 step | #22 改:**首选激活 venv 再跑 `make check`**(完整管道);备选必须**对齐 Makefile 完整 5 step**(`pytest -v` / `ruff check` / `ruff format --check` / `mypy core adapters features api` / `make hygiene`);漏任一 = #22 FAIL | **反例 27 接续**(凭印象写"等价",未 cat Makefile 核查 step 清单)|
| **P2-3** | P2 | PowerShell 对照表实测不可用:`Select-String -Recurse` 参数不存在;`Test-Path dir; if (-not $?)` 误判($? 是命令成功标志非路径存在) | 改对照表:`Get-ChildItem -Recurse -File dir/ \| Select-String -Pattern 'pat'`(管道写法);`if (-not (Test-Path dir)) { "NOT_EXIST" }`(直接判路径) | **反例 28 接续**(架构师无 repo 凭印象写 PowerShell 命令,未实测)|
| **P2-4** | P2 | Stage 0 #3 `view features/...` 放在 bash code block 误导(`view` 是 Codex 文件读取工具,**不是** shell 命令)| 改"核查方式:用 Codex 自身 `view` 工具读取(等价 `Get-Content` / `cat` / `rg . <file>`)",移出 code block | **反例 25 同源**(给 Codex 跑的命令必须本地实测形态;`view` 是 Codex 工具不是 shell 命令)|
| **P3-5** | P3 | glossary 数量口径 sweep 漏 4 处:line 261 / 629 / 634 / 1128 仍残留 "30-40 / 33 条" | 4 处统一改"40 条草案 / 5 大方向 / 最多 50" | **反例 29 接续**(全文 sweep 不彻底;架构师做大批量替换后未跨段 grep 核查残留)|

### 第二十二任 KPI 候选(累计够稳定 → **本任完工后必须升仪决策 09**)

四轮审查累积 6 处反例 27/28(R1 × 2 + R2 × 2 + R3 × 2)+ R4 × 2,接续反例 29 sweep 不彻底 × 2,反例 25 命令实测不彻底 × 1 = **3 类反例形态稳定**:

| KPI 候选 | 累计证据 |
|---|---|
| KPI-A(给 Codex 的命令 4 维度明示) | R1 P1-2(函数名)+ R2 P2-a(Python 环境)+ R2 P2-b(字面)+ R3 P1-1(shell)+ R3 P1-2(CI 工具链)+ R4 P1-1(选定工具链)+ R4 P1-2(等价 Makefile)= **7 次累积** |
| KPI-B(任何 PowerShell / bash 命令架构师本地实测形态) | R3 P1-1 + R4 P2-3 + R4 P2-4 = **3 次累积** |
| KPI-C(全文 sweep 后必须 grep 残留) | R2 P2-c 通信缺位 + R3 P2-4 + R4 P3-5 = **3 次累积** |

**第二十二任 KPI 升仪条款**(本任完工 PR merge 后,PM 单独 chore PR 入仓决策 09 反例 32):

> **反例 32 — 架构师无 repo 时,给 Codex 跑的命令 / 文档全文 sweep 必须满足 3 条 KPI**:
> 1. **KPI-A**:任何给 Codex 跑的命令必须 4 维度明示(shell / Python / PATH 工具链 / 跨平台等价)— **不允许凭印象默认**;架构师无 repo 时**默认假设最少 / 要求 Codex 报告最多**
> 2. **KPI-B**:任何 PowerShell / bash / make 等环境命令,架构师必须**调用工具(view / grep / cat 本地实测)核查输出形态**;未实测前不下笔
> 3. **KPI-C**:任何"全文 sweep"(批量字面替换)后必须 `grep <旧字面> <文档>` 核查残留,残留 ≥ 1 = sweep 未完成,**不允许声明"sweep 完成"**

---

## GPT R3 反馈台账(2026-06-07,2 P1 + 2 P2 + 1 P3 全采纳)

> **R3 主判定**:**架构边界已锁,主体可实施**;唯一阻断是**执行环境层**——架构师无 repo + 凭印象写 bash 命令,Windows workspace 默认 PowerShell 跑挂(grep / bash 不可用,系统 Python ≠ 项目 venv)。**收口 shell / venv / CI 命令后可进 Codex 第一棒**。

| # | 严重度 | 问题 | v0.1.3 修订位置 | 反例溯源 |
|:-:|:-:|---|---|---|
| **P1-1** | P1 | Stage 0 / 验收命令仍默认 bash(grep / cat / head / ls);PM 实测 Windows workspace 默认 PowerShell,bash / grep 不可用,`rg` workspace 已有 | § Stage 0 开头加 **Shell 工具链约定**:Codex 实施前**必报告 shell 环境 + 工具可用性**;命令等价对照表(bash / PowerShell / 跨平台 rg 三列);任一命令"找不到工具" → 停手报 PM,**不**自行替换工具 | **反例 27 + 反例 28 累积同源**(架构师无 repo + 凭印象写默认 shell + 未核查 Codex 实施环境真有什么工具)|
| **P1-2** | P1 | #22 / #23 仍用裸 `make check` / `bash scripts/check_repo_hygiene.sh`;Windows PATH 上 python/pytest/ruff/mypy 来自系统 / Anaconda 不是项目 venv,裸 pytest 缺 sentence_transformers;bash 不可用导致 hygiene.sh 跑挂 | #22 改"先激活 venv 或显式调 `.venv\Scripts\python.exe -m pytest / ruff / mypy`";#23 改 `make hygiene` 或 `<项目 python> scripts/check_repo_hygiene.py`(走 .py 跨平台) | **反例 27 接续**(工具默认行为未核查 PATH 实际指向)|
| **P2-3** | P2 | § 输出 § 修改文件清单只列 2 个,后文已允许 test_prompt_loader.py 字面同步,PR scope 显示"不按任务书来" | § 输出 § 修改文件改"**2 个 + 可选测试同步 1 个**";表加可选行 | **反例 29 同源**(D9 修订未传播到 § 输出文件清单)|
| **P2-4** | P2 | Codex 提示段 glossary 残留 "4 大方向 / 33 条"旧口径;正文已是 5 大方向 / 40 条 | Codex 提示段改"5 大方向 / 40 条草案 / 最多 50";全文 sweep 11 处 "30-40 条" → "40 条草案";1 处"四专业"→"5 大方向" | **反例 29 接续**(R2 P2-c 修订未传播到 Codex 提示段)|
| **P3-5** | P3 | #11' grep 守门偏弱,只能过滤 v0.1/v0.2-rc diff 行,**不能严格证明"仅字面替换"**(可能伪装) | #11' 改:**机械守门 + PM 人工 review 兜底**;Phase 2 候选写 `scripts/check_tests_literal_sync.py` 严格证明 | — |

### 反例 27 + 反例 28 累积同源 KPI 兑现声明(R3 抓 P1-1 + P1-2)

GPT R3 的 P1-1 + P1-2 = **反例 27 + 反例 28 累积同源** —— 不是单次踩坑,是**三轮审查累积**:

| # | 反例 | 现象 |
|:-:|:-:|---|
| 27/28-1 | R1 P1-2 函数名错(`_load_qa_template`) | 凭设计稿写,未核查 main HEAD |
| 27/28-2 | R1 P1-3 命令逻辑错位(`git diff` 含 `core/`) | 凭印象写命令,未思考误报路径 |
| 27/28-3 | R2 P2-a Python 环境(裸 `python`) | 凭印象写默认 Python,未核查 PATH 实际 |
| 27/28-4 | R2 P2-b source_block 字面 | 凭设计稿写,未核查代码 `_truncate` |
| 27/28-5 | **R3 P1-1 shell 环境(裸 bash 命令)** | 凭印象写默认 shell,**未核查 Codex 实施环境真有什么 shell + 工具** |
| 27/28-6 | **R3 P1-2 CI 工具链(裸 `make check`)** | 凭印象写"项目工具走 PATH",**未核查 PATH 实际指向系统 / Anaconda 而非 venv** |

**第二十二任 KPI 强化候选**(累计 6 处反例 27/28 形态稳定 → 必须升仪决策 09):

> 架构师写任何**给 Codex 跑的命令**(grep / git diff / make / python / pytest / ruff / mypy / bash 脚本)前,**必须把以下 4 个维度全部明示或要求 Codex 第一棒报告**:
> 1. **Shell 环境**(bash / Git Bash / PowerShell / zsh)— 不同 shell 工具集不同
> 2. **Python 环境**(系统 / venv / poetry / conda)— 不同环境包不同
> 3. **PATH 工具链**(`make check` / `pytest` / `ruff` 实际指向哪个 binary)
> 4. **跨平台等价**(grep ↔ rg ↔ Select-String;cat ↔ Get-Content;ls ↔ Get-ChildItem)
>
> 任一未明示 → 反例 27 + 28 累积同源,等 Codex 实施时阻断,派活循环。架构师无 repo 时**默认假设最少**,要求 Codex 第一棒报告**最多**。

---

## GPT R2 反馈台账(2026-06-07,1 P1 + 3 P2 + 5 次要建议全采纳)

> **R2 主判定**:**仍需小修不放行**,R1 核心 5 条大方向已采纳但**贯穿不全**(D9 修订仅在前段,后段保留旧措辞);8 条反馈集中在跨段一致性 / 实施环境 / 维护风险。**反例 29 大命中**(架构师做局部修订后未全文 grep 同步)。

| # | 严重度 | 问题 | v0.1.2 修订位置 | 反例溯源 |
|:-:|:-:|---|---|---|
| **P1** | P1 | D9 R1 修订没贯穿全文:line 896 / 987 / Checklist 仍写"不动任何 .py" + "3+1 个文件",Codex 按 v0.1.1 仍会自撞 | § 给 Codex 提示段重写"只动 3+1 个交付文件 + 可选 1 个 tests 字面同步";Checklist 同步;**commit 拆分 4 → 5**(tests 字面同步独立 commit 3,review 注意力清晰) | **反例 29 大命中**(局部修订 D9 后未全文 grep 同步,跨段一致性失败)|
| **P2-a** | P2 | Stage 0 #2 / 验收 #9 / #10 用裸 `python -c "import yaml"`,Windows F:\python\python.exe 无 yaml,Codex 跑会假阴性 | Stage 0 #2 + 验收 #9 / #10 改"用项目 Python 环境"(`.venv/bin/python` / `.venv\Scripts\python.exe` / `poetry run python`);Codex 报告用了哪种环境 | **反例 27 同源**("工具默认行为"陈述未实地核查项目 Python 环境)|
| **P2-b** | P2 | Stage 0 #3 + § 输入契约 § 2 写 source_block 字面 `f"[{entry.source_id}] {entry.hit.source_type}: {entry.snippet}"`,真实代码是 `_truncate(snippet, MAX_SNIPPET_CHARS)`;Codex 严格匹配会停手 | Stage 0 #3 + § 输入契约 § 2 改"语义上仅含 source_id + source_type + snippet(snippet 可经 _truncate 截断);关键守门:不含 line_range" | **反例 27 同源**(凭印象写字面;实际有截断 wrap)|
| **P2-c** | P2 | glossary 没兑现通信覆盖:D4 承诺四专业,草案只有 control / motor / power electronics / signal processing | § 接口契约 2 草案添加 communication 小类(7 条:modulation / demodulation / carrier / bandwidth / snr / bit_error_rate / qam);v0.2-rc prompt 内嵌快照同步;total 40 条,仍 < 50 | **反例 29 同源**(D4 承诺 vs 草案跨段一致性失败)|
| **次要 1** | P3 | 上线语义冲突:D2 "rc 不算上线" vs R6 "进 main 即上线" | 统一为"**v0.2-rc 会在运行时生效,但不视为 v0.2 final 正式定版**"(D2 + R6 + Checklist 三处同步)| — |
| **次要 2** | P3 | system prompt 3000 字上限偏紧:补通信 glossary 后逼近 | R2 风险段加注 token 预估;Codex 提示"术语快照写压缩列表,不逐条解释" | — |
| **次要 3** | P3 | glossary 双维护风险(glossary.yaml + prompt 快照) | 新增 R8 风险声明;glossary.yaml 文件头加同步要求注释 | — |
| **次要 4** | P3 | 评测样例偏 PMSM / 速度环 | § 接口契约 3 § 4.2 模块问题加 1 个通信/信号处理样例(FFT 函数) | — |
| **次要 5** | P3 | "不引入 few-shot"与"教学口吻反例"边界模糊 | § 范围"不做"段措辞改:"不引入完整多轮业务 few-shot;仅保留短反例 / 短正例作为风格约束" | — |

### 反例 29 大命中 KPI 兑现声明(v0.1.1 局部修订后未全文同步)

GPT R2 抓住的 P1 + P2-c + 次要 1 = **3 处反例 29 同源**(局部修订后跨段未同步):

| # | 反例 | 现象 |
|:-:|:-:|---|
| 29-1 | P1 D9 贯穿不全 | R1 修了 § 范围 / D9 / 验收,**但漏改** § 给 Codex 提示(line 896-897)+ Checklist(line 987-988) |
| 29-2 | P2-c glossary 通信缺位 | D4 承诺 4 专业,草案只列 4 类但**漏通信**;承诺 vs 落实跨段一致性失败 |
| 29-3 | 次要 1 上线语义 | D2 / R6 两段对"上线"定义不一致 |

**第二十二任 KPI 候选**(等 v0.1.2 通过 R2 / Codex 第一棒后,反例 29 形态稳定 → 升仪决策 09):
- **新维度**:架构师做任何局部修订(D 段 / R 段 / 验收 / Stage 0 任一处)后,**强制 grep**:(a) `grep -nE "<被改的关键词>" task-XXX-v0.X.md` 列出所有出现点;(b) 每个出现点逐字核查描述与新修订一致;(c) 跨段一致性 KPI **机械执行**,不允许凭"我已经改过了"印象跳过
- 接续反例 30 KPI(变更跨段同步项数)+ 反例 29 KPI(接口名 / 字段名 grep):**修订传播 KPI** = 反例 29 + 30 + 第二十二任新维度三重叠加

### 反例 28 KPI 接续兑现声明(GPT R2 P2-a + P2-b 同源)

GPT R2 抓住的 P2-a / P2-b = **接续反例 28**(架构师无 repo,凭印象写工具命令 / 字面格式):

| # | 反例 | 现象 |
|:-:|:-:|---|
| 28-4 | P2-a python 环境 | 凭印象写裸 `python`,未确认项目 Python 环境(venv / poetry / 系统 python);Windows 实测系统 python 无 yaml |
| 28-5 | P2-b source_block 字面 | 凭 task-205 设计稿写字面,实际代码含 `_truncate` 截断 wrap;字面对不上 |

反例 28 KPI 第一条(弹性描述)需要扩展到 **工具命令 / 字面格式 / Python 环境**;不仅函数名 / 文件路径。

---

## GPT R1 反馈台账(2026-06-07,3 P1 + 2 P2 全采纳)

> **R1 主判定**:**暂不直接放行**,需小修后再放行 Codex 实施。主体方案(A 档范围 / 候选驱动 / R12 sentinel 边界 / 8 类 source_type 软消解)成立;5 条反馈集中在**会让实施自撞**的验收 / 测试 / 命名边界。

| # | 严重度 | 问题 | v0.1.1 修订位置 | 反例溯源 |
|:-:|:-:|---|---|---|
| **P1-1** | P1 | 现有 `tests/features/chat/test_prompt_loader.py` 含 `template.version == "v0.1"` 断言,本任升 v0.2-rc 后 `make check` 必挂 | D9 重写:**生产 Python 零变更 + 允许 tests 断言机械同步**(仅 v0.1 → v0.2-rc 字面同步,不允许新增 assert);Stage 0 加 #3' 兜底核查 tests 中字面;验收 #11 + #11' 守门拆 | **反例 24 同源**(凭印象写"不动任何 .py"未核查测试与 prod 版本号字面耦合) |
| **P1-2** | P1 | Stage 0 #3 写 `_load_qa_template()`,实际是 `features/chat/_prompt_loader.py::load_prompt_template()`(由 `_prompt_builder.py::ChatPromptBuilder` 调用);Codex 按 v0.1 跑会停手抛冲突 | Stage 0 #3 大重写:函数名 + 文件路径 + 调用方全部按实地核查写;D9 不动清单加 `_prompt_loader.py` | **反例 28 大命中**(task-205-v0.2 设计稿与 main HEAD 实际入库形态有差异;架构师无 repo 边界下,设计稿 ≠ freeze 契约) |
| **P1-3** | P1 | 验收 #11 用 `git diff main --stat features/ api/ adapters/ core/ app/` 证 Python 零变更,但本任改 `core/prompts/*.yaml` 必让 `core/` 非空,**命令逻辑错位必误报** | 验收 #11 改 `git diff --name-only main -- '*.py' ':!tests/'` 应空;新增 #11' 守门 tests 改动仅字面同步 | **反例 24 + 反例 28 同源**(凭印象写命令,未本地实测命令输出形态;反例 28 KPI 升级:架构师任何 grep / git diff 命令必须**思考可能误报路径**) |
| **P2-4** | P2 | 评测文档 `citations` / `citation_ids` 混用:v0.1 设计稿 § 4 / 边界 case 写 `citations=[]`,但 LLM 输出协议是 `citation_ids` | 评测文档 § 2 / § 3 / § 4 / § 5 全部按层级区分:LLM 输出层用 `citation_ids`;API 响应层用 `citations`;表头 / 样例 / 边界 case 统一 `citation_ids` | **反例 29 同源**(跨段一致性:同一概念在 LLM 层 vs API 层用不同字段名,文档未明示) |
| **P2-5** | P2 | 评测样例 / 教学口吻反例样例含"init_params.m 第 15 行",但 `_prompt_builder.py::ChatPromptBuilder` 的 `source_block` 渲染**不含** `line_range`,LLM 拿不到行号,声称行号 = 编造 = 违反 prompt v0.1 证据规则第 3 条 | v0.2-rc prompt 教学口吻反例段去掉"第 15 行" + 加显式提示"不要写第 N 行";评测文档 § 4 样例改"从参数定义看 / 从证据片段看";Stage 0 #3 加守门核查 `source_block` 不含 `line_range`;若 v0.3+ 需要行号引用,要改 source_block 渲染(超本任范围,触发 R2 ④)| **反例 27 同源**(凭印象认为 SourceRef 有 line_range 就能渲染,实地核查发现 `_prompt_builder.py` 渲染只 3 字段)|

### v0.1.1 没改的次要建议(明示采纳)

- **`docs/eval/` 与 `eval/` 目录分工**:D8 段加边界声明 + `qa_eval_design.md` 首段加注

### 反例 28 KPI 兑现声明(v0.1 起稿期间漏抓 2 处)

GPT R1 抓住的 5 条反馈中,**3 处是反例 28 同源**(架构师无 repo,凭设计稿 / 印象写未实地核查):

| # | 反例 | 现象 |
|:-:|:-:|---|
| 28-1 | P1-2 函数名错 | task-205-v0.2 § 7.4 设计稿写 `_load_qa_template`,main HEAD 实际是 `load_prompt_template`(+ 文件拆分);架构师无 repo,**没有用更弹性的描述**(如"prompt 加载函数,位于 `_prompt_builder.py` 或拆分后的子模块") |
| 28-2 | P1-3 命令逻辑错位 | 验收 #11 `git diff features/ ... core/ ...` 凭印象写,**未思考本任改动会让 `core/` 必非空** = 命令必然误报 |
| 28-3 | P2-5 行号样例 | 凭印象认为 SourceRef 有 line_range 就能渲染进 prompt,**未跨段核查 `_prompt_builder.py::build_messages` 实际渲染字段集** |

**第二十一任 KPI 候选**(等 v0.1.1 通过 R1 复审后,若反例 28 形态稳定 → 升仪决策 09):
- **新维度**:架构师写"前置契约 / Stage 0 实地核查"段时,**任何函数名 / 文件路径 / 命令 / 字段集**必须用**弹性描述**(如"prompt 加载函数 X,Codex 实地核查具体名 / 路径")或明示"以 main HEAD 实地核查为准"
- 任何 grep / git diff 命令写完后,架构师必须**自审"可能误报路径"**:本任改动会让哪些路径非空?命令能区分吗?
- 任何跨段引用的字段集(如"SourceRef.line_range")必须实地核查**消费方**(`_prompt_builder.py` 渲染)是否真的用了该字段

---

## 审批级别评估(反例 18 KPI 兑现:5 维评估)

| 维度 | 评分 | 说明 |
|---|---|---|
| 决策密度 | **中**(D1-D10) | A 档范围内,主要是 prompt 结构 + glossary 落地策略 + 8 类 source_type 教学化说明 + 评测题型设计 |
| 下游扩散面 | **2 Task** | TASK-306(评测直接消费 prompt + 题型设计)+ TASK-403(前端展示文案受 LLM 输出风格影响) |
| 用户可见性 | **高** | 每次问答 LLM 回答风格由此 prompt 决定;直接影响付费转化 |
| 异步 / LLM 模式 | **低** | 纯 yaml / 设计文档改动,**无新 Python 代码路径**(D9 严守);prompt 由既有 `_prompt_builder.py` 消费 |
| 隐私 / 安全 | **中** | prompt injection 防御段措辞微调(不改语义);glossary 不引入新数据流 |

**结论**:**GPT 一审 R1**(不强制二审);若 R1 期间触发以下 **5 个升级触发器**任一 → 自动升 R2:

1. 改 `ChatLLMResponse` / `ChatAnswer` / `ChatResponse` schema
2. 改 source_id / citation_ids 协议(间接层语义)
3. 改 ChatService / fallback 逻辑
4. 改 `_prompt_builder.py`(或新增 prompt builder 路径)
5. 范围扩到 `project_overview.yaml` / B / C 类 prompt(超出 A 档)

---

## 上下文(在项目里的位置)

- **架构面**:TASK-205 落地了 v0.1 `qa_with_context.yaml`(简单结构 + source_id 间接层 + 基础 injection 防御);TASK-304 把检索从 KeywordRetriever 升级到 HybridRetriever(向量主路 + keyword fallback),**`RetrievalHit.source_type` 从 6 类扩到 8 类**(加 `subsystem` / `overview`)。**v0.1 prompt 设计时不知道 8 类 source_type 存在**,LLM 看到新类型标签会困惑——本任补这块缺口。
- **业务面**:壁垒 2(中文教学语境的 Prompt 工程)= 国内电气教材术语对齐 + 教学口吻硬约束;v0.1 已经有基础措辞,但**没有术语对照表 reference**(05 § 8.2 line 442 明示 "完整对照表见 `core/prompts/glossary.yaml`,Task 305 时补充")—— 本任落地。
- **流程面**:**305 / 306 解耦,候选驱动**(PM 拍板)——305 产 prompt v0.2 **候选**(`version: "v0.2-rc"`)+ glossary v0.1 + 评测题型设计文档;306 跑评测拿 v0.1 baseline + v0.2-rc 对照;**v0.2 final 由 PM 在 306 评测后另拍**,不在本任范围。
- **风险面**:本任是 RAG 链路输出质量的**主观艺术 + 客观验收的边界**;A 档严守"只动 prompt yaml / 设计文档,不动 Python 代码"是抗风险关键(D9)。

---

## 输入(前置依赖)

### 上游关键契约(已 main HEAD freeze,本任不动)

> **决策 09 + 反例 28 KPI**:架构师无 repo,以下契约**以 task 设计文档为最佳近似**,Codex 第一棒 Stage 0 实地核查兜底(详 § Stage 0)。

**1. `core/prompts/qa_with_context.yaml` v0.1**(TASK-205 main HEAD 已落,本任**升 v0.2-rc**)

设计稿位置:`docs/tasks/task-205-v0.2.md` § 7.5(stand-alone reference)

关键 invariant(本任**不破坏**):
- `version: "v0.1"` → 本任改为 `"v0.2-rc"`(D2)
- `description` 字段保留,内容可微调
- `system` 段:输出协议 / 证据规则 / 教学口吻 / 安全约束(prompt injection 防御) — **核心语义不变,本任只在末尾追加 + 强化**(D5 / D6)
- `user` 段:模板变量 `{project_name}` / `{project_type}` / `{source_block}` / `{question}` — **零变更**(D9)
- 输出协议 4 字段:`answer` / `confidence` / `citation_ids` / `follow_up_suggestions` — **零变更**(D9)

**2. `features/chat/_prompt_builder.py`**(TASK-205 main HEAD 已落,本任**零变更**;Stage 0 #3 核查)

关键 invariant:
- `load_prompt_template()` 函数(实际在 `features/chat/_prompt_loader.py`,GPT R1 P1-2 修订)读 `core/prompts/qa_with_context.yaml` 解析 `system` / `user` / `version` 字段
- `ChatPromptBuilder` 类(在 `features/chat/_prompt_builder.py`)调用 `load_prompt_template()`,然后 `build_messages(project, source_entries, history, question) -> list[LLMMessage]`
- `source_block` 渲染语义:**仅含** `source_id + source_type + snippet`(snippet 可经 `_truncate` 截断;GPT R2 P2 修订:不假设字面格式)— **本任不改渲染代码**;但 `entry.hit.source_type` 从 6 类扩到 8 类(TASK-304),v0.2-rc system prompt 需对 8 类作教学化说明(D5)

**3. `features/chat/_retriever.py::SourceType` Literal 8 类**(TASK-304 main HEAD 已落)

```python
SourceType = Literal[
    "file", "block", "function", "param",
    "graph_entry", "unresolved",
    "subsystem", "overview",   # TASK-304 D3 新增
]
```

**关键性质**:`overview` 类型 `source_ref.file_path == "__project_overview__"` 哨兵(TASK-304 R12);本任 prompt **不消解**该 UX 泄露(D7);只在教学化说明里告诉 LLM "overview 类型的来源是项目总览,不要把 `__project_overview__` 当文件名引用"。

**4. `core/prompts/glossary.yaml`**(本任**新建** v0.1)

05 § 8.2 line 442 明示:"完整对照表见 `core/prompts/glossary.yaml`,Task 305 时补充"。
本任落地 40 条草案电气 / 自动化 / 控制 / 通信专业核心术语对照(最多 50 条,D4)。

**5. `docs/eval/qa_eval_design.md`**(本任**新建**;306 消费)

题型设计文档(架构师产出),包含:4 类题型(总体 / 模块 / 参数 / 修改)× 5 维评分(03 索引 line 219-227)+ 每类 2-3 个典型样例。**不含**:可执行评测脚本 / 真实评测题集 / baseline CSV(全归 306)。

### 关键宪法 / 决策 / 反例引用

- **01 § 8 line 311**:所有 prompt 在 `core/prompts/*.yaml`,**不写死代码**(本任严守)
- **01 § 11 line 364**:单次问答响应 **< 8 秒**(本任不引入新代码,响应时间不变)
- **05 § 0**:三条铁律 + 反模式 ——本任 D6 强化措辞依据
- **05 § 5 D 类 line 269-292**:问答 JSON schema 4 字段(`answer / confidence / citations / follow_up_suggestions`)— 本任不改
- **05 § 6 E 类 line 325-359**:不确定回答模板(citations 可空,confidence=low) — 本任在 prompt 里强化"证据不足时主动走 E 类"
- **05 § 8 line 416-456**:教学口吻 + 不寒暄 + 中文术语对齐国内教材 — 本任 D6 核心依据
- **05 § 8.2 line 442**:glossary 落地承诺 — 本任 D3 / D4 兑现
- **05 § 9.2 line 502**:prompt 版本号 + 评测 + PR review — 本任 D2 "v0.2-rc" 语义对接
- **决策 09**:架构师实地核查 — 架构师无 repo,Stage 0 转 Codex 兜底
- **决策 11**:async + logger 双不变量 — 本任不引入新 async / 新日志,但勿动既有
- **反例 18**:审批级别 5 维评估 — § 状态段已兑现
- **反例 28**:架构师无 repo → Stage 0 / PM 兜底
- **反例 31**:决策回避 / 软妥协 / 转嫁 — 本任 R12 sentinel **明示不承接 + 明示去向**(不写"留给 307 修")

---

## 输出(交付物)

### 新增文件(2 个)

```
core/prompts/
└── glossary.yaml                       ~80 行,40 条术语对照(含通信小类;R2 后)(D3 + D4)

docs/eval/
└── qa_eval_design.md                   ~250 行,题型设计 + 评分维度 + 样例(D8)
```

预估总 ~330 行;均 < 01 § 8 的 300 行约束(`qa_eval_design.md` 是文档非代码,300 行约束不严格适用;但内容控制在 250 行内)。

### 修改文件(2 个 + 可选测试同步 1 个)

| 路径 | 改动范围 | 决策 |
|---|---|---|
| `core/prompts/qa_with_context.yaml` | (a) `version: "v0.1"` → `"v0.2-rc"`(D2);(b) `description` 微调反映候选语义;(c) **system 段追加**:8 类 RetrievalHit.source_type 教学化说明(D5)+ 40 条术语快照内嵌(D3 c 方案;含通信小类)+ 教学口吻强化 + 1-2 个短负例(D6);(d) **user 段**:**零变更**(D9 严守);(e) 输出协议 4 字段 / citation_ids 间接层 / prompt injection 防御段核心语义 / Pydantic schema:**全部零变更**(D9 严守) | D2 + D3 + D5 + D6 + D9 |
| `docs/03_TASK_INDEX.md` | **305 自己的搭车 chore**:TASK-305 行 🔲 → 🔍(Codex 完工写 🔍;✅ 由 PM 在 merge 后单独 chore 改;进度条 / 总计 / 当前状态本任**不动**) | 搭车 chore(决策 07 + 第二十任接力规则) |
| `tests/features/chat/test_prompt_loader.py`(**可选,GPT R3 P2-3 修订**) | **仅字面同步**:含 `template.version == "v0.1"` 的断言改 `"v0.2-rc"`;**不允许**新增 assert / 新增 test function / 改测试逻辑;由 Stage 0 #3' 实地核查确认是否需要(若 grep 命中 0 → 不需要此文件改动) | D9 + GPT R2 P1 + GPT R3 P2-3 |

### 不动文件(明示,反例 31 KPI 兑现:**不留余地**)

| 路径 | 不动理由 |
|---|---|
| `features/chat/_prompt_builder.py` | D9 严守;改此触发 R2 升级触发器 ④ |
| `features/chat/chat_service.py` | D9 严守;ChatService 7 步流程零变更(TASK-205 main freeze) |
| `features/chat/_chat_persist.py` | D7 R12 sentinel 不承接;backend 文案泄露由 PM 另开 backend chore |
| `features/chat/_retriever.py` | TASK-304 main freeze;本任不动 SourceType Literal / Retriever ABC / KeywordRetriever / VectorRetriever / HybridRetriever |
| `features/chat/chat_schemas.py`(若存在;Stage 0 #5 兜底) | ChatLLMResponse / ChatAnswer / ChatResponse 字段集不变 |
| `core/domain/source_ref.py` | TASK-101 跨 Task 锁的契约,本任不动 |
| `core/domain/exceptions.py` | 不新增异常类(D10) |
| `app/config.py` / `.env.example` | 配置零增量(D10) |
| `core/prompts/project_overview.yaml` | D1 严守 A 档;306 评测不混入 overview 变量 |
| `core/prompts/slx_block_explain.yaml` / `m_code_explain.yaml` | D1 A 档不新建;Week 4 / Phase 2 接力(B / C 类 prompt 当前无调用方) |
| `eval/run_eval.py` / `eval/cases/*` | D8 严守;306 接管(脚本 / 真实评测题集 / baseline CSV) |

---

## 范围

### 必做(检查清单 D1-D10)

- [ ] **D1 A 档范围锁定**:升 `qa_with_context.yaml` v0.1 → v0.2-rc + 新建 `glossary.yaml` v0.1 + 新建 `docs/eval/qa_eval_design.md`;不升 `project_overview.yaml`,不新建 B / C 类 prompt yaml
- [ ] **D2 v0.2-rc 候选标记**:`version: "v0.2-rc"`(release candidate),不是 `"v0.2"`;**v0.2-rc 会在运行时生效**(yaml 即文件,ChatService 加载即用),**但不视为 v0.2 final 正式定版**(GPT R2 其他建议 1 修订:统一上线语义);v0.2 final 由 PM 在 306 评测后另拍(详 R6)
- [ ] **D3 glossary 静态内嵌(c 方案)**:`glossary.yaml` 单独文件作为可维护 reference;v0.2-rc system prompt 内嵌当前快照副本;**不改** `_prompt_builder.py`,**不做**动态注入
- [ ] **D4 glossary 40 条草案(最多 50)**:覆盖控制 / 电机 / 电力电子 / 信号处理 / 通信 5 大方向核心术语;v0.1 草稿先列 40 条优先级最高词,R1-R4 期间裁定
- [ ] **D5 8 类 RetrievalHit.source_type 教学化说明**:system prompt 追加段;明示 LLM 视角(8 类:`file / function / block / subsystem / param / overview / graph_entry / unresolved`),**不是** chunk source_type(向量库视角,7 类含 reserved)
- [ ] **D6 教学口吻强化 + 1-2 个短负例**:对齐 05 § 8 + 05 § 0.3 反模式;允许 "先判断证据是否足够,再组织回答" 措辞;**不引入 chain-of-thought**(不要求模型输出或显式暴露思维链)
- [ ] **D7 R12 sentinel 不承接 + 明示去向**:本任不动 backend;消解落到 backend `ChatService` / `_chat_persist.py`,由 PM 另开**独立 backend chore**(预估 5-10 行 + 1 单测);**禁用措辞**"留给 TASK-307 修"
- [ ] **D8 评测题型设计**:`docs/eval/qa_eval_design.md` 包含 4 类题型(总体 5 题 / 模块 5 题 / 参数 3 题 / 修改 2 题,每工程 15 题)× 5 维评分(事实正确 30 / 引用 20 / 教学性 20 / 可操作 20 / 不编造 10)+ 每类 2-3 个典型样例(中文 + 期望 citation 类型 + 评分预期)
- [ ] **D9 严守"生产 Python 代码零变更" + 允许 tests 断言机械同步**(GPT R1 P1-1 修订):
  - **生产 Python 严守不动**:不改 `_prompt_builder.py` / `_prompt_loader.py` / `ChatService` / `_chat_persist.py` / 任何 Pydantic schema / Python 函数签名;任一生产代码改动 → 自动升 R2(触发器 ①-④)
  - **测试断言允许机械同步**:`tests/features/chat/test_prompt_loader.py` 等含 `template.version == "v0.1"` 字面断言的测试,**允许**改 `"v0.1"` → `"v0.2-rc"`(纯字面同步,**不**触发 R2)
  - **测试改动硬约束**:**仅允许** v0.1 → v0.2-rc 字面同步;**不允许**新增 assert / 新增 test function / 改测试逻辑(任一触发 R2 ④)
- [ ] **D10 零配置增量**:不加 AppSettings 字段;不动 `.env.example`;不引入新依赖(yaml 已用 pyyaml,glossary 沿用)
- [ ] **搭车 chore**:03 索引 TASK-305 行 🔲 → 🔍(Codex 完工写 🔍;**不动**进度条 / 总计 / 当前状态字面)

### 不做(明确排除,反例 31 KPI 兑现:**不留余地**)

- ❌ **不升 `project_overview.yaml`**(D1)— 306 评测不混入 overview 变量
- ❌ **不新建 `slx_block_explain.yaml` / `m_code_explain.yaml`**(D1)— B / C 类 prompt 当前无调用方;Week 4 / Phase 2 接力
- ❌ **不动 `_prompt_builder.py`**(D9 严守 + R2 触发器 ④)
- ❌ **不动 `ChatService.handle_chat` / 7 步流程 / 校验五步**(TASK-205 main freeze + R2 触发器 ③)
- ❌ **不动 ChatLLMResponse / ChatAnswer / ChatResponse schema**(R2 触发器 ①)
- ❌ **不改 source_id / citation_ids 协议**(R2 触发器 ②)
- ❌ **不消解 R12 sentinel**(D7)— 推 backend chore
- ❌ **不引入 chain-of-thought**(D6)— 允许"先判断证据"措辞但不要求输出思维链
- ❌ **不引入完整多轮业务 few-shot 示例**(GPT R2 其他建议 5 修订:措辞边界澄清);**仅保留短反例 / 短正例作为风格约束**(教学口吻反例段;MCS 阶段 token 预算紧;若 306 评测后发现完整多轮 few-shot 显著提分,Phase 2 重评)
- ❌ **不引入 query rewriting / HyDE / Multi-Query**(Phase 2 候选)
- ❌ **不跑评测 / 不建评测题集 / 不写 `eval/run_eval.py`**(D8 边界;306 接管)
- ❌ **不新增 AppSettings 字段 / `.env.example` 字段**(D10)
- ❌ **不新增 Python 依赖**(D10)
- ❌ **不在 03 索引写 `✅`**(沿 TASK-304 模式;Codex 完工只能写 🔍)

---

## 接口契约

### 1. `core/prompts/qa_with_context.yaml` v0.2-rc 结构

> **架构师无 repo 边界(反例 28)**:以下结构以 `task-205-v0.2.md § 7.5` 设计稿为最佳近似;**Codex 第一棒 Stage 0 实地核查 main HEAD 真实形态**;若 v0.1 实际入库形态与设计稿有出入,Codex 停手报 PM(决策 09 纪律 1)。

**v0.1 → v0.2-rc 改动 4 处锚点**(grep-friendly,不假设 v0.1 完整字面):

| # | 改动锚点 | 改动方向 |
|---|---|---|
| A | `version: "v0.1"` | → `version: "v0.2-rc"` |
| B | `description: "..."` | 微调反映"候选语义";建议:`"工程问答 + source_id 间接层 + 防 prompt injection + 教学口吻 + glossary v0.1(v0.2-rc,候选驱动,待 TASK-306 评测后定型)"` |
| C | system 段**末尾**(在 "## 安全约束(prompt injection 防御)" **之后**追加,或在适当章节追加) | 追加 3 段:**## 证据类型说明**(8 类 source_type;D5)+ **## 国内教材术语对齐**(40 条 glossary 快照;D3 c 方案)+ **## 教学口吻反例**(1-2 个负例;D6) |
| D | user 段 | **零变更**(D9) |

**核心语义不变,明示守门**:
- `system` 段原有"## 输出协议"/"## 证据规则"/"## 教学口吻(对齐国内教材)"/"## 安全约束(prompt injection 防御)" **四章核心语义保留**(措辞可微调但语义守恒)
- `user` 段 `{project_name}` / `{project_type}` / `{source_block}` / `{question}` 4 个模板变量字面 **零变更**(D9 / 验收 grep 守门)
- 输出 JSON 字段 `answer` / `confidence` / `citation_ids` / `follow_up_suggestions` 字面 **零变更**(R2 触发器 ① 守门)

**v0.2-rc 追加段示例**(完整文案在 Codex 实施时按本设计落)

```yaml
# (位于 system 段内,继 "## 安全约束(prompt injection 防御)" 之后)

  ## 证据类型说明(8 类)

  你看到的「证据清单」每条形如 `[S1] <来源类型>: <证据片段>`。来源类型有 8 种,各自含义:

  - `file`:MATLAB .m 文件级证据(文件路径 / 角色 / 函数数)
  - `function`:MATLAB 函数级证据(函数名 / 输入输出 / docstring)
  - `block`:Simulink block 级证据(block 名 / 类型 / 参数)
  - `subsystem`:Simulink 子系统级证据(子系统名 / 含 block 数 / 子 block 列表)
  - `param`:.mat 变量元信息证据(变量名 / 类型 / shape)
  - `overview`:**项目总览**级证据(项目主流程 / 知识点 / 阅读顺序)
  - `graph_entry`:工程执行入口点
  - `unresolved`:工程中未解析的引用符号(可能是缺失文件 / 未导入工具箱)

  规则:
  1. `overview` 类型的证据**来源是项目总览,不是某个具体文件**。引用时**不要**把 `__project_overview__` 当文件名给学生,**改用"项目总览"**称呼
  2. `unresolved` 类型的证据意味着这个符号工程里没找到定义。引用时必须在 answer 明示"未能确定 X"(05 § 6 E 类)
  3. 不同类型证据可以混合引用,但 `block` 类引用要带具体 block 名,`function` 类引用要带具体函数名

  ## 国内教材术语对齐

  统一用以下中文教材术语(来源:`core/prompts/glossary.yaml` v0.1 快照,40 条):

  - 控制原理:状态空间 / 反馈回路 / 闭环 / 开环 / 伯德图 / 根轨迹 / 增益裕度 / 相位裕度 / ...
  - 电机控制:Park 变换 / Clarke 变换 / 矢量控制(FOC)/ 直接转矩控制(DTC)/ 永磁同步电机(PMSM)/ ...
  - 电力电子:脉宽调制(PWM)/ 空间矢量脉宽调制(SVPWM)/ 整流器 / 逆变器 / ...
  - 信号处理:傅里叶变换 / 卷积 / 离散傅里叶变换(DFT)/ 快速傅里叶变换(FFT)/ ...
  - 通信:调制 / 解调 / 载波 / 带宽 / 信噪比 / 误码率 / ...

  (完整 40 条由 Codex 按 `core/prompts/glossary.yaml` 内嵌)

  ## 教学口吻反例(禁止)

  反例 1(背教科书):
  问:"这个工程的速度环 Kp 设 5.0 是为什么?"
  ❌ 错答:"Kp 是 PID 控制器的比例增益,根据 Ziegler-Nichols 整定方法,通常..."
  ✅ 对答:"从 init_params.m 的参数定义看 Kp=5.0,Ki=100,这是 PMSM 速度环常见经验起点。你想调可以先小幅改 Kp(±20%)观察转速曲线..."

  注:**不要**写"第 N 行"这种具体行号;证据片段不含行号信息,声称行号是编造(违反证据规则第 3 条)。引用时改用"从 X 文件的参数定义看 / 从证据片段看 / 从函数定义看"等表述。

  反例 2(没看证据硬答):
  问:"这个工程能跑出什么仿真结果?"
  ❌ 错答:"该工程会输出速度响应曲线、电流响应曲线..."(实际工程文件里没仿真结果数据)
  ✅ 对答:"根据当前工程文件,我能看到 plot_results.m 里设置了绘图代码,但具体结果需要你运行 sim 才能知道。"(走 E 类,confidence=low,`citation_ids=[]`)

  ## 回答前的内部判断(不输出)

  在生成 answer 之前,先在心里判断:
  1. 证据清单里有没有能直接回答这个问题的具体证据?
  2. 如果有,引用哪几个 source_id?
  3. 如果没有,confidence 设 low,citation_ids 留空,answer 走 E 类模板

  这步是**内部判断**,**不要**在 answer 字段输出"我先判断..."这种思维过程;直接给最终答案。
```

**禁用措辞(D6)**:
- ❌ "让我们一步步分析"(暴露思维链)
- ❌ "首先...其次...最后..."(显式思维链结构)
- ❌ "希望对您有帮助"(寒暄)
- ❌ "可能""或许""大概"满天飞(05 § 0.3 反模式)

### 2. `core/prompts/glossary.yaml` v0.1 结构(D3 + D4)

```yaml
# core/prompts/glossary.yaml
# 国内电气 / 自动化 / 控制 / 通信专业核心术语对照表
# 用途:reference;主要消费方式是 qa_with_context.yaml v0.2-rc 内嵌快照(D3 c 方案)
# 维护:扩词条不需要改 qa_with_context.yaml(快照通过 PR review 同步)
#
# ★ 双维护风险声明(GPT R2 其他建议 3 修订):
# 本文件与 qa_with_context.yaml system 段 "## 国内教材术语对齐" 内嵌快照 两份。
# **修改本文件后必须同步 qa_with_context.yaml 快照**;否则 LLM 实际看到的是旧术语,本文件 reference 失效。
# 同步检查:每次本文件 PR 必须含 qa_with_context.yaml 对应改动;反之亦然。
# Phase 2 候选:_prompt_builder.py 动态注入(消除双维护);MCS 阶段不做。

version: "v0.1"
description: "国内工科教材术语对照,MCS v0.1 = 40 条核心词(5 大方向);Phase 2 可扩"

# 分类组织,方便维护
control_theory:
  state_space: 状态空间
  feedback_loop: 反馈回路
  closed_loop: 闭环
  open_loop: 开环
  bode_plot: 伯德图
  root_locus: 根轨迹
  nyquist_plot: 奈奎斯特图
  gain_margin: 增益裕度
  phase_margin: 相位裕度
  transfer_function: 传递函数
  pole: 极点
  zero: 零点

motor_control:
  park_transform: Park 变换
  clarke_transform: Clarke 变换
  foc: 矢量控制(FOC)
  dtc: 直接转矩控制(DTC)
  pmsm: 永磁同步电机(PMSM)
  bldc: 无刷直流电机(BLDC)
  rotor_flux_orientation: 转子磁链定向
  field_weakening: 弱磁控制

power_electronics:
  pwm: 脉宽调制(PWM)
  svpwm: 空间矢量脉宽调制(SVPWM)
  spwm: 正弦波脉宽调制(SPWM)
  rectifier: 整流器
  inverter: 逆变器
  buck: 降压斩波(Buck)
  boost: 升压斩波(Boost)

signal_processing:
  fourier_transform: 傅里叶变换
  dft: 离散傅里叶变换(DFT)
  fft: 快速傅里叶变换(FFT)
  convolution: 卷积
  z_transform: Z 变换
  laplace_transform: 拉普拉斯变换

# GPT R2 P2 修订:D4 承诺覆盖通信,补此小类
communication:
  modulation: 调制
  demodulation: 解调
  carrier: 载波
  bandwidth: 带宽
  snr: 信噪比
  bit_error_rate: 误码率
  qam: 正交幅度调制(QAM)

# (本草稿先列 40 条,GPT R2 后含 communication 7 条;裁定终稿不超过 50)
```

**词条选择原则**(D4):
- **优先**:国内主流教材高频词 + 学生易混淆词(如 "波德图" vs "伯德图")
- **包含**:壁垒 4 评测集所属专业的核心术语(电气 / 自动化 / 控制 / 通信)
- **排除**:过度专业的细分术语(如 STATCOM / UPFC 等电力系统专用,Phase 2 视客户结构再加)
- **格式**:每条 `english_lower_snake: 中文教材标准词`,**不**含解释 / 同义词列表(那是百科;LLM 已知)

### 3. `docs/eval/qa_eval_design.md` 结构(D8)

```markdown
# 工程问答评测题型设计 v0.1

> **本文档是评测体系长期 reference**,由 TASK-305 产出,TASK-306 消费,后续 prompt 回归 / dashboard 复用。
> 本文档**不含**可执行评测脚本 / 真实评测题集 / baseline CSV,这些由 TASK-306 落地。

> **目录分工**(GPT R1 次要建议):
> - `docs/eval/` = **长期设计文档**(题型设计 / 评分维度 / 评测体系 reference,本文档归此)
> - `eval/` = **可执行 cases / results / scripts**(TASK-306 落地;`eval/cases/*.json` 真实题集、`eval/results/*.csv` baseline / 对照、`eval/run_eval.py` 脚本)
> - 后续路径不再摇摆

## 1. 评测目的

(参照 03 索引 line 211-228 + 05 § 10)

- 验证 v0.2-rc prompt 相比 v0.1 baseline 是否提升
- 验证向量 RAG(HybridRetriever)相比粗 RAG(KeywordRetriever)是否提升(03 索引 line 231 硬指标)
- 验证 8 类 source_type 教学化说明是否帮助 LLM 正确引用
- 验证 glossary 快照是否提升中文术语对齐分

## 2. 题型分类(每工程 15 题)

| 类型 | 题数 | 描述 | 期望 `citation_ids` 类型(LLM 输出层) |
|---|:-:|---|---|
| **总体问题** | 5 | "这个工程在做什么?" / "主入口是哪个?" | overview / file / function |
| **模块问题** | 5 | "这个 block / 函数干什么?" / "SpeedLoop 子系统怎么工作?" | block / subsystem / function |
| **参数问题** | 3 | "这个参数为什么这么设?" / "Kp 设 5.0 合理吗?" | block / function / param |
| **修改问题** | 2 | "我要改速度环响应,应该动哪里?" | block / function |

**字段命名约定**(GPT R1 P2-4 守门):
- **LLM 输出层**:`citation_ids: ["S1", "S3"]`(source_id 字符串列表;ChatLLMResponse schema)
- **服务端展开后**:`citations: list[SourceRef]`(SourceRef 列表;ChatAnswer / ChatResponse schema)
- **本文档评测维度的"引用"主要评 LLM 输出层是否正确给 source_id**,故用 `citation_ids`
- "期望 citation_ids 类型"列指**该 source_id 对应 RetrievalHit.source_type 在 8 类中的哪类**

## 3. 评分维度(每题 100 分)

(参照 03 索引 line 219-227)

| 维度 | 分值 | 评分要点 |
|---|:-:|---|
| 事实正确 | 30 | 答案符合工程实际配置;不编造文件 / block / 函数名 |
| 引用完整 | 20 | LLM 输出 `citation_ids` 字段含 ≥ 1 个有效 source_id;source_id 真实存在于「证据清单」 |
| 教学性 | 20 | 像老师讲,不像 ChatGPT 背书;无寒暄;先结论后依据 |
| 可操作 | 20 | 指明学生下一步看哪 / 改哪;不写"先理解基础概念"空话 |
| 不编造 | 10 | 证据不足时主动走 E 类(confidence=low,`citation_ids=[]`) |

**通过线**:平均分 ≥ 70 才能升 v0.2 final(03 索引 line 228 硬约束)。

## 4. 每类题型典型样例(2-3 个 / 类,中文)

> **GPT R1 P2-5 守门**:样例中的"引用 / 依据"措辞**不暗示具体行号**;当前 `source_block` 渲染仅含 `source_id + source_type + snippet`,LLM 拿不到 `SourceRef.line_range`(`_prompt_builder.py` 实地核查)。若 v0.3+ 需要让 LLM 引用行号,要改 `source_block` 渲染(超 305 范围,触发 R2 ④)。

### 4.1 总体问题

**样例 1**:
- 问:"这个工程是做什么的?"
- 期望答(摘要):"这是一个 PMSM 矢量控制仿真工程,顶层模型 pmsm_foc.slx 实现速度环 + 电流环闭环,主入口 run_simulation.m..."
- 期望 `citation_ids` 类型:`[overview]` 或 `[overview, file]`
- 评分预期:事实正确 30 / 引用 20 / 教学性 18-20 / 可操作 0-10(总体问题不强求可操作)/ 不编造 10

**样例 2**:
- 问:"主入口是哪个文件?为什么?"
- 期望答(摘要):"主入口是 run_simulation.m。从 ProjectGraph 看它调用 sim('pmsm_foc.slx') 启动仿真,且其他 .m 文件(init_params.m / plot_results.m)都通过它串起..."
- 期望 `citation_ids` 类型:`[file]` 或 `[file, function]`

### 4.2 模块问题

**样例 1**(电机控制方向):
- 问:"SpeedLoop 子系统怎么工作?"
- 期望答(摘要):"SpeedLoop 子系统接收速度参考 ω_ref 和实测速度 ω,做差后通过 PI 控制器输出 Iq_ref 给电流环。PI 参数 Kp=5.0, Ki=100..."
- 期望 `citation_ids` 类型:`[subsystem, block]` 或 `[subsystem, block, file]`

**样例 2**(通信 / 信号处理方向,GPT R2 其他建议 4 修订:防评测样例偏 PMSM):
- 问:"这个工程里的 FFT 模块怎么用的?"
- 期望答(摘要):"FFT 函数 fft_analysis.m 接收时域信号,输出频谱。从函数定义看,采样频率 fs 用作输入参数,N 点 FFT 默认 1024 点。你想分析频谱时调这个函数,把信号数组传进去..."
- 期望 `citation_ids` 类型:`[function, file]` 或 `[block]`(若 Simulink FFT block)
- **覆盖说明**:若 306 评测集含信号处理 / 通信工程,本样例的术语对齐(FFT / 采样频率 / N 点)用得上 glossary 中的通信小类

### 4.3 参数问题

**样例 1**:
- 问:"速度环 Kp 设 5.0 是为什么?"
- 期望答(摘要):"从 init_params.m 的参数定义看 Kp=5.0,这是 PMSM 速度环常见经验起点 —— Kp 决定响应速度。如果你想调,先小幅改 Kp(±20%)观察转速曲线..."
- 期望 `citation_ids` 类型:`[file, block]`(参数本身在 .m 文件,使用在 Simulink block)
- **P2-5 守门**:答案**不**写"第 15 行";`source_block` 不渲染 line_range,LLM 看不到具体行号

### 4.4 修改问题

**样例 1**:
- 问:"我想让速度响应更快,应该改哪里?"
- 期望答(摘要):"主要改速度环 PI 参数:先小幅增大 init_params.m 里的 Kp,改完跑一次仿真看转速曲线。不要同时动 Ki..."
- 期望 `citation_ids` 类型:`[file, block]`

## 5. 边界 case(故意诱导出 E 类回答)

(每工程额外 1-2 个,用于验证证据强制器 / E 类降级是否正常)

- "这个工程跑出来的转速峰值是多少?"(需运行仿真;期望 E 类,confidence=low,`citation_ids=[]`)
- "Kp 设到多少最好?"(无证据的具体建议;期望 E 类,不许编造)
- "为什么作者选了这个控制方案而不是 DTC?"(超出工程文件能回答的范围;期望 E 类)

## 6. 评分流程(给 TASK-306 参考)

(由 TASK-306 落地;本文档**不含**脚本)

1. 选 5 个测试工程(03 索引 Week 0 验收 10 个的子集)
2. 每工程 15 题 × 5 工程 = 75 题
3. 跑 v0.1 baseline + v0.2-rc 对照各 1 轮(75 × 2 = 150 次 LLM 调用)
4. 每题人工评分(PM + 二审过)按 § 3 的 5 维打分
5. 输出 CSV:`eval/results/qa_v0.1_baseline_<date>.csv` + `eval/results/qa_v0.2_rc_<date>.csv`
6. v0.2-rc 平均分 - v0.1 平均分 ≥ 5 分(且 ≥ 70 分)→ PM 拍板升 v0.2 final
7. 不达标 → 305 v0.3 草稿(由 PM 单独派活)

## 7. 不在本文档范围

- ❌ 评测脚本 `eval/run_eval.py`(TASK-306)
- ❌ 真实评测题集 `eval/cases/*.json`(TASK-306)
- ❌ baseline CSV(TASK-306)
- ❌ 人工评分细则模板(TASK-306,本设计文档仅给维度 + 分值)
- ❌ 评测 dashboard(Phase 2)
- ❌ 自动化打分(LLM-as-judge;Phase 2 候选,需独立评估对齐)
```

---

## 决策日志

### D1 — A 档范围锁定:只动 `qa_with_context.yaml` + 新建 2 个文件

**理由**(PM 2026-06-07 拍板):
- B / C 类 prompt yaml(`slx_block_explain.yaml` / `m_code_explain.yaml`)**当前无调用方**(03 索引 Week 4 前端 TASK-402 / 403 没列 block / .m 文件讲解端点,02 § 3 yaml 规划但未启用)
- 升 `project_overview.yaml` 会让 TASK-306 评测**同时跑两条独立 prompt 链路**;v0.2-rc 分数变化反推不出问题在 overview prompt 还是 qa prompt
- MCS 4 周收尾,集中火力在用户付费时高频触发的 D 类问答 prompt 最划算

**替代方案**:
- A. B 档(本任决策)。**理由见上**。
- B. B 档(+ overview prompt)。**为何不选**:306 评测变量爆炸。
- C. C 档(+ 全 prompt)。**为何不选**:B / C 类无调用方,改了上不了线。

### D2 — `version: "v0.2-rc"` 候选标记

**理由**:
- 候选驱动语义需要文件层面可识别(PM 2026-06-07 拍板)
- `-rc` 后缀符合通用版本号惯例(release candidate)
- 305 完工时 prompt 文件入 main HEAD,**v0.2-rc 会在运行时生效**(因为 yaml 不是 db 版本切换,文件即生效);**但不视为 v0.2 final 正式定版**(GPT R2 其他建议 1 修订:统一上线语义,产品/工程/评测三方不打架)
- 但 305 不承诺 v0.2-rc 优于 v0.1;**承诺**走完 TASK-306 评测后由 PM 拍板是否升 v0.2 final
- 05 § 9.2 "正式上线"语义解释:**v0.2-rc 运行时生效但非正式定版**;**v0.2 final** 才是"PR review + 评测通过的正式版本";v0.2-rc → v0.2 final 是去 -rc 后缀 + 文档同步,**不是**重新合并

**替代方案**:
- A. `"v0.2"` 直接升正式。**为何不选**:违 05 § 9.2(每次 prompt 升版本必须跑评测才能上线);MCS 4 周节奏不留时间走完整 PR review。
- B. 不改 version 字段(v0.2-rc 改 system 段但 version 保 v0.1)。**为何不选**:违 05 § 9.2(改 prompt 必须升版本)+ 评测 CSV 无法区分。
- C. `"v0.2-beta"` / `"v0.2-draft"` / 其他后缀。**为何不选**:`-rc` 是 Python / 开源界最普及的语义,Codex / 二审一眼懂。

### D3 — glossary 静态内嵌(c 方案)

**理由**(PM 2026-06-07 拍板):
- 不改 `_prompt_builder.py`(避免触发 R2 升级触发器 ④)
- 不引入动态注入(Phase 2 候选;MCS 阶段简单写死最稳)
- `glossary.yaml` 作为独立可维护文件,后续扩词条不需要改 prompt 文件;但**当前快照**通过手工 sync 到 system prompt 内
- v0.2-rc 入 main 时,`qa_with_context.yaml` system 段内嵌 40 条快照副本;若 Phase 2 扩 glossary,**v0.3 时再 sync**(不是动态注入)

**替代方案**:
- A. `_prompt_builder.py` 全量塞 glossary。**为何不选**:触发 R2 ④。
- B. 检索时动态注入。**为何不选**:需新代码 + 性能开销(MCS 单次 < 8s 预算紧);Phase 2 候选。
- C. **本任决策**(静态内嵌)。**为何选**:最小改动 + 不撞触发器 + 后续 Phase 2 可平滑升级到 (b)。

### D4 — glossary 规模 40 条草案(R2 后含通信,最多 50)

**理由**(PM 2026-06-07 拍板):
- 40 条草案覆盖电气 / 自动化 / 控制 / 通信 / 信号处理 **5 大方向**核心术语(GPT R2 + R3 修订后含通信小类),够帮 LLM 稳定口吻
- 超 50 条进入"挤占 LLM 注意力"区间(token 预算 + LLM 注意力衰减)
- v0.1 草稿先列 40 条 5 大方向(本任 § 7.2),R1-R4 期间裁定终稿;最多裁到 50 条

**替代方案**:
- A. < 30 条。**为何不选**:覆盖不全,壁垒 2 效果弱。
- B. > 50 条。**为何不选**:边际收益递减 + token 挤占。
- C. **本任决策**(40 条 5 大方向,最多 50)。

### D5 — 8 类 RetrievalHit.source_type 教学化说明

**理由**(TASK-304 + PM 2026-06-07 拍板):
- TASK-304 把 SourceType 从 6 类扩到 8 类(加 `subsystem` / `overview`),但 TASK-205 v0.1 prompt 设计时不知道
- LLM 看到 `[S1] subsystem: 子系统 SpeedLoop 在 pmsm_foc.slx...` 标签会困惑("subsystem 是什么?")
- 教学化说明同时承担 R12 sentinel 软消解:告诉 LLM "overview 类型的来源是项目总览,不要把 `__project_overview__` 当文件名"
- **强调 LLM 视角(8 类)而非 chunk 视角(7 类含 reserved)**,避免后续读者混淆

**替代方案**:
- A. 不说明,让 LLM 自行揣度。**为何不选**:实测可能编造 source_type 含义;且 R12 sentinel 软消解机会失去。
- B. 说明但简化(只说新增 2 类)。**为何不选**:6 类原有也未在 v0.1 说明,LLM 也可能误解;一次性 8 类全说明最稳。
- C. **本任决策**(8 类全说明 + R12 软消解告知)。

### D6 — 教学口吻强化 + 1-2 个短负例,不引入 CoT

**理由**(PM 2026-06-07 拍板):
- 05 § 8 + 05 § 0.3 反模式已明示"像老师不像 ChatGPT" / "不寒暄" / "不'可能或许大概'满天飞"
- 但 v0.1 system prompt 是**抽象规则**,LLM 可能合规但偏移;**具体负例 + 正例对照** 比规则更有约束力
- **允许**"先判断证据是否足够,再组织回答" 措辞(让 LLM 内部做证据判断,提升 E 类降级精度)
- **不允许**显式输出思维链("让我们一步步分析" / "首先...其次..."):暴露思维链占 answer 字段 token + 学生看起来啰嗦 + 无客观证据 CoT 在本场景显著提分(MCS 阶段 token 预算紧)

**替代方案**:
- A. 不加负例,只强化规则。**为何不选**:v0.1 已有规则,效果待评测验证。
- B. 加 5+ 负例。**为何不选**:挤占 token;1-2 个典型负例 + 1 个正例对照已够。
- C. 加 CoT。**为何不选**:PM 明示不引入 + token 预算紧 + 显式 CoT 让 answer 字段变啰嗦。
- D. **本任决策**(1-2 负例 + 允许"先判断证据"措辞,不引入显式 CoT)。

### D7 — R12 sentinel 不承接 + 明示去向(反例 31 KPI 兑现)

**理由**(TASK-304 R12 + PM 2026-06-07 拍板):
- TASK-304 R12 技术债:`__project_overview__` 哨兵在 E 类 fallback(`_short_hit_label` 函数)字面泄露
- **305 是 prompt 层,不动 backend Python 代码**(D9)
- TASK-307 证据强制器**只解决** citation 强类型识别(`source_type == "overview"` 而非 `file_path` 字面匹配),**不解决** backend 文案泄露
- **不写**"留给 TASK-307 修"(反例 31 转嫁同源)
- **明示去向**:消解落到 backend `ChatService` / `_chat_persist.py`,由 PM 另开**独立 backend chore**(预估 5-10 行 + 1 单测,半天活)
- 305 prompt 内的"教学化说明"是**软消解**(告诉 LLM 别把 `__project_overview__` 当文件名),不是硬消解(backend 替换字面);Week 4 内测前 backend chore 必须完成

**替代方案**:
- A. 305 承接 backend chore。**为何不选**:违 D9 + 触发 R2 ③ + 305 范围混乱。
- B. 写"留给 TASK-307 修"。**为何不选**:反例 31 转嫁;307 不解决文案泄露。
- C. **本任决策**(不承接 + 明示去向)。

### D8 — 评测题型设计放 `docs/eval/qa_eval_design.md`

**理由**(PM 2026-06-07 拍板 + GPT R1 次要建议):
- 评测体系长期 reference,不属于 305 附件(放 `docs/tasks/task-305-supplements/` 显得是临时产物)
- 后续 prompt regression / TASK-306 / Phase 2 dashboard 都消费这份设计
- `docs/eval/` 目录若不存在,本任新建
- 305 产出**设计文档**;306 产出**评测脚本 + 真实题集 + baseline CSV**
- 文档明示"不在本文档范围"清单(§ 3 末尾)防 306 边界漂移
- **GPT R1 次要建议**:`docs/eval/` 与仓库已有顶层 `eval/` 并存的目录分工:
  - `docs/eval/` = **长期设计文档**(题型设计 / 评分维度 / 评测体系 reference,本任产出)
  - `eval/` = **可执行 cases / results / scripts**(TASK-306 落地;`eval/cases/*.json` 真实题集、`eval/results/*.csv` baseline / 对照、`eval/run_eval.py` 脚本)
  - 此边界写进本任 `docs/eval/qa_eval_design.md` 首段 + `eval/README.md`(若存在;Stage 0 #7 兜底)

**替代方案**:
- A. 放 `docs/tasks/task-305-supplements/`。**为何不选**:305 完工后被人当临时文档清掉。
- B. 放 `eval/design.md`。**为何不选**:`eval/` 目录留给可执行脚本 + 真实题集,设计文档归 docs。
- C. **本任决策**(`docs/eval/qa_eval_design.md`)。

### D9 — 生产 Python 代码零变更 + 允许 tests 断言机械同步(R2 升级守门;GPT R1 P1-1 修订)

**理由**:
- A 档边界关键护栏:任一**生产** Python 代码改动 → 自动升 R2(触发器 ①-④)
- 维护本任审批级别"GPT 一审 R1"语义(若改生产 Python 代码,本任复杂度等同 TASK-205 / 304,必须二审)
- **GPT R1 P1-1 修订**:`tests/features/chat/test_prompt_loader.py` 等含 `template.version == "v0.1"` 字面断言的测试,本任升 `version` → `"v0.2-rc"` 后**测试必挂**;**强制留 v0.1 字面 = 测试与代码漂移**(反例 24 同源)→ 边界改成"测试断言机械同步**允许**,且**不**触发 R2"
- 测试改动硬约束:**仅允许** v0.1 → v0.2-rc 字面同步;**不允许**新增 assert / 新增 test function / 改测试逻辑(任一触发 R2 ④)
- Codex 实施时若发现 prompt 改动**触发**其他测试断言失败(不只是 version 字面)→ **停手报 PM**,**不**自行扩范围改测试逻辑

**严守不动清单**(生产 Python):
1. `features/chat/_prompt_builder.py`
2. `features/chat/_prompt_loader.py`(GPT R1 P1-2 实地核查发现:`load_prompt_template()` 在此文件,不是 `_prompt_builder.py`)
3. `features/chat/chat_service.py`
4. `features/chat/_chat_persist.py`
5. `features/chat/_retriever.py`(TASK-304 main freeze)
6. `features/chat/chat_schemas.py`(若存在)
7. 任何 Pydantic schema
8. `core/domain/*`
9. `core/interfaces/*`
10. `adapters/*`
11. `app/config.py` / `.env.example`(D10 同源)

**允许 tests 改动清单**(仅字面机械同步):
- `tests/features/chat/test_prompt_loader.py`(已知含 `template.version == "v0.1"` 断言,本任升 `"v0.2-rc"` 后同步;GPT R1 P1-1 实地核查发现)
- 其他 `tests/features/chat/test_*.py` 中含 `"v0.1"` 字面断言(若存在;Stage 0 #3' 兜底核查)

**替代方案**:
- A. 允许微调 `_prompt_builder.py` / `_prompt_loader.py`(如读取 glossary.yaml)。**为何不选**:触发 R2 ④ + 引入新代码路径风险。
- B. 允许微调 ChatService(如 R12 软消解)。**为何不选**:触发 R2 ③ + 反例 31 同源(转嫁本应另开 chore)。
- C. 强制留 v0.1 字面在测试中(让 prod 升 v0.2-rc 但 test 仍 v0.1)。**为何不选**:测试与代码字面漂移(反例 24 同源)+ make check 必挂 + 强迫 Codex 派活循环。
- D. **本任决策**(生产严守 + 测试机械同步,不触发 R2)。

### D10 — 零配置增量

**理由**:
- glossary 静态内嵌(D3 c 方案),不需新 AppSettings 字段
- 8 类 source_type 教学化说明在 prompt 内消化,不需 settings
- pyyaml 已是项目依赖(TASK-205 已加),glossary.yaml 沿用 `safe_load`
- 维护本任"零代码侵入"边界

**替代方案**:
- A. 加 `prompt_glossary_path` AppSettings 字段允许动态切换 glossary 文件。**为何不选**:违 D9 + Phase 2 候选。
- B. **本任决策**(零增量)。

---

## 风险与注意

### R1 — main HEAD `qa_with_context.yaml` v0.1 实际形态与设计稿可能有出入

**风险**:架构师无 repo(反例 28),设计稿(`task-205-v0.2.md § 7.5`)与 main HEAD 入库形态可能微差(YAML 字段顺序 / 缩进 / 注释)。Codex 第一棒 Stage 0 必须实地核查 + 报告差异。

**应对**:
- Stage 0 #1 / #2 必跑(核查 yaml 字段集 + 版本号 + 4 个 system 段标题)
- v0.2-rc 改动用 **grep 锚点**(`version:` / `description:` / `## 输出协议` / `## 证据规则` / `## 教学口吻` / `## 安全约束` 等章节标题)定位,**不**假设 v0.1 完整字面
- 若 Stage 0 发现 v0.1 实际入库形态与设计稿严重不符(如缺失某段 / 字段名变化)→ Codex 停手报 PM(决策 09 纪律 1)

### R2 — system prompt 总长 token 预算

**风险**(GPT R2 其他建议 2 修订):v0.2-rc 追加 4 段:
- 8 类 source_type 说明 ~300 字
- glossary 快照 **40 条**(含通信)~700-800 字
- 教学口吻反例 ~300 字
- 回答前的内部判断 ~150 字

总追加 **~1450-1550 字**。v0.1 system 段估 ~800 字,**v0.2-rc 总长 ~2300-2400 字**(约 1700-2000 tokens for DeepSeek tokenizer)。**逼近 3000 字硬上限**(GPT R2 抓:补通信后 token 余量明显变紧)。

**应对**:
- **Codex 实施时术语快照写成压缩列表**(GPT R2 其他建议 2 修订):每行多个术语,**不**逐条解释(`PWM(脉宽调制)/ SVPWM(空间矢量脉宽调制)/ ...`),不浪费 token 在术语自解释上
- DeepSeek V4-Flash 上下文窗口 32K~64K tokens,2300 tokens system prompt 不挤压用户 context
- 但 LLM **注意力衰减**:system prompt > 3000 字时尾部段落可能被忽略
- 验收 #4 + #8 加守门:`yaml safe_load` 后 system 段字符数 ≤ 3000(防超规)
- 若评测 306 发现尾部段(教学口吻反例 / 内部判断)未被遵守 → v0.3 时把核心规则前置
- **Codex 若实测 system 段超 3000 字**:停手报 PM;**不**自行裁删教学口吻 / glossary(那是 PM 拍板范围)

### R3 — R12 sentinel UX 泄露在 backend chore 落地前的内测窗口

**风险**:305 不动 backend,`_short_hit_label` 仍把 `__project_overview__` 漏到 E 类 fallback 文案。Week 4 内测开始前若 backend chore 未落,5-10 个内测用户偶尔(只在 E 类触发路径)会撞见。

**应对**:
- D7 已明示去向(backend chore,5-10 行 + 1 单测,半天活)
- PM 在 305 merge 前后开 backend chore Task 卡(建议命名 TASK-308 或独立 chore 编号)
- 305 prompt 内的"教学化说明"作为软消解:告诉 LLM 别把 `__project_overview__` 当文件名 → 减轻 D / B / C 类回答里的泄露(E 类 fallback 是 backend 硬拼,prompt 帮不上)
- Week 4 内测前 backend chore 必须完成(PM 排期硬约束)

### R4 — 评测题型设计可能不准

**风险**:305 题型设计是架构师 + PM 单方面拍,306 真实评测时可能发现某些题型不可评分(如"修改问题"过于主观,人工打分一致性差)。

**应对**:
- 题型设计 § 4 给每类 2-3 个**带评分预期**的样例,306 实施前 PM + 二审过目
- 306 PR 允许微调题型 / 评分维度细则(本任设计文档预留调整接口);**重大调整**(如改 5 维变 6 维)→ 反推 305 v0.2-rc system prompt 更新

### R5 — TASK-304 Stage 0 #10 hot-patch 实测状态依赖

**风险**:TASK-304 Stage 0 #10 留给 Codex 第二棒实测:`qa_with_context.yaml` 是否含 6 类 source_type 枚举字面集合?

- PASS(预期):v0.1 prompt 不含枚举字面 → TASK-304 不动 prompt → 本任 305 主动加 8 类说明(D5)
- 触发 hot-patch:TASK-304 已加 `subsystem` / `overview` 描述 → 本任 D5 与 TASK-304 已落形态冲突

**应对**:
- Stage 0 #4 必跑:核查 main HEAD `qa_with_context.yaml` 是否已含"subsystem" / "overview" 描述(TASK-304 hot-patch 痕迹)
- 若 hot-patch 已落:本任 D5 改为"在 TASK-304 已加的 8 类描述基础上,**强化教学化口吻** + 增加 R12 sentinel 软消解"(非新增 / 替换)
- 若 hot-patch 未触发:本任 D5 按设计稿落地(全新追加段)

### R6 — v0.2-rc 候选 vs v0.1 上线状态混淆

**风险**:305 PR merge 后,`qa_with_context.yaml` 文件 `version: "v0.2-rc"` 进 main;**v0.2-rc 会在运行时生效**(ChatService 加载 yaml 即生效),**但不视为 v0.2 final 正式定版**(GPT R2 其他建议 1 修订)。若 306 评测发现 v0.2-rc 不如 v0.1,**回滚需要新 PR**(不是改 db / 切配置)。

**应对**:
- D2 已明示"v0.2-rc 运行时生效但非正式定版"
- 若评测显著退步 → 回滚 PR(Codex 改 `version: "v0.2-rc" → "v0.1"`,删追加 3 段)
- 若评测显著提升 → v0.2 final PR(Codex 改 `version: "v0.2-rc" → "v0.2"` + 文档同步)
- 若评测部分维度提升部分退步 → v0.3 草稿(由 PM 派活)
- **不在 305 范围**:回滚 / 升 final / v0.3 全由 PM 在 306 评测后另拍

### R7 — glossary 词条选择主观性

**风险**:40 条术语选择由架构师 + PM 主观拍,可能漏掉某些工程的高频术语(如评测集中有信号处理工程,但 glossary 偏控制 / 电机)。

**应对**:
- v0.1 草稿 40 条覆盖 5 大方向(控制 12 + 电机 8 + 电力电子 7 + 信号处理 6 + 通信 7,本任 § 7.2 草案;GPT R2 补通信)
- GPT R1 / R2 期间二审过目;306 评测中发现"中文术语对齐"维度低分 → v0.3 扩 glossary
- 词条选择记入文档,后续可追溯调整

### R8 — glossary 双维护漂移(GPT R2 其他建议 3 修订)

**风险**:D3 c 方案 = `glossary.yaml`(独立文件)+ `qa_with_context.yaml` system 段内嵌快照(同份内容)。**两份内容容易漂移**:扩 glossary 时忘了同步 prompt 快照,导致:
- LLM 实际看到的术语 = 旧 prompt 快照
- glossary.yaml 作为 reference 失效
- 学生看到的术语口径与文档承诺漂移

**应对**:
- `glossary.yaml` 文件头加同步要求注释(本任 § 7.2 已落)
- 每次 glossary 改动 PR 必须含 `qa_with_context.yaml` 对应改动(PR review checklist)
- Phase 2 候选:`_prompt_builder.py` 动态注入(消除双维护)— MCS 阶段触发 R2 ④,不做

### R9 — 执行环境假设(GPT R3 P1-1 + P1-2 修订)

**风险**:架构师无 repo,Stage 0 / 验收 / CI 命令凭印象写默认 bash + 默认 Python + 默认 PATH 工具链,但 Codex 实施环境可能是:
- Windows PowerShell(grep / bash / cat 不可用;`rg` 可用)
- 系统 Python F:\python\python.exe(无 yaml / sentence_transformers)
- PATH 上的 Anaconda 工具(pytest / ruff / mypy 来自 Anaconda 不是项目 venv)

任一环境假设错位 = Codex 第一棒命令跑挂 → 阻断实施 → 派活循环 → Week 3 进度延后。

**应对**:
- § Stage 0 开头加 **Shell 工具链约定**:Codex 实施前**必报告 shell + Python + PATH 工具可用性**
- 命令等价对照表(bash / PowerShell / 跨平台 rg)
- 验收 #22 / #23 强制用项目 venv 显式路径或激活
- 任一命令"找不到工具" → Codex **停手报 PM,不自行替换工具**(防反例 25 同源)
- Phase 2 候选:写跨平台 `scripts/stage0_runner.py`(Python 实现所有 Stage 0 核查),消除 shell 假设;MCS 阶段架构师明示 + Codex 报告兜底

---

## Stage 0 实地核查清单(给 Codex 第一棒)

> **反例 28 KPI 兑现**:架构师无 repo,以下 10 项核查项(含 #3' 兜底)**必须由 Codex 实地跑**;任一项异常 → 停手报 PM(决策 09 纪律 1 + 反例 24 同源)。

### Shell 工具链约定(GPT R3 P1-1 + R4 P1-1 + P2-3 修订)

> **架构师无 repo,凭印象写 bash 命令未核查 Codex 实施环境**。PM 实测 Windows workspace 默认 shell = PowerShell;`grep` / `bash` / `cat` 不可用,**但** `rg`(ripgrep)workspace 已有,跨平台可用。
>
> **GPT R4 P1-1 修订**:旧版"默认 bash + 不可用就停手"会让 Codex 在 PowerShell 下"明明有 rg 备选却被要求停手"。改为**实施前选定一套工具链 + 全程统一,只在选定工具链工具不可用时停手**。

**Codex 第一棒实施前必做(三步)**:

1. **选定工具链**(**推荐**:PowerShell + `rg` + `.venv\Scripts\python.exe`;Linux / macOS 可选 bash + `rg` + `.venv/bin/python`)
2. **报告工具可用性**(用选定工具链):
   - PowerShell:`Get-Command rg, python` + `.venv\Scripts\python.exe --version` + `.venv\Scripts\python.exe -c "import yaml; print(yaml.__version__)"`
   - bash:`which rg python` + `.venv/bin/python --version` + `.venv/bin/python -c "import yaml; print(yaml.__version__)"`
3. **报告 Codex 文件读取能力**:Codex 自身有 `view` 工具直接读文件(`view <path>`),**不**走 shell;`view` 报告"非 shell 命令"标识

**命令等价对照**(下文 Stage 0 / 验收命令默认 bash 风格;PowerShell 用右列;`rg` 跨平台首选):

| 默认 bash | PowerShell 等价(GPT R4 P2-3 实测可用) | 跨平台备选 |
|---|---|---|
| `grep -nE 'pat' file` | `Select-String -Pattern 'pat' file` | `rg -n 'pat' file`(**推荐**;workspace 已有) |
| `grep -cE 'pat' file` | `(Select-String -Pattern 'pat' file).Count` | `rg -c 'pat' file` |
| `grep -rn 'pat' dir/` | `Get-ChildItem -Recurse -File dir/ \| Select-String -Pattern 'pat'`(R4 P2-3 修订:`-Recurse` 在 Select-String 不支持,改用 Get-ChildItem pipeline) | `rg -n 'pat' dir/`(默认递归) |
| `cat file` | `Get-Content file` | `rg . file --no-line-number` |
| `ls dir 2>&1 \|\| echo NOT` | `if (-not (Test-Path dir)) { "NOT_EXIST" }`(R4 P2-3 修订:`$?` 是命令成功标志非路径存在,改用 `-not (Test-Path)`) | Codex `view dir`(非 shell)|
| `head -20 file` | `Get-Content file -TotalCount 20` | `rg . file -m 20 --no-line-number` |
| `wc -l file` | `(Get-Content file).Count` | Codex `view file`(非 shell,直接报行数)|
| `view file`(Codex 工具,非 shell)| 同左 — Codex `view` 工具不走 shell | 同左 |

**Codex 报告硬约束**(R4 P1-1 修订):
- 每个 Stage 0 命令报告时含"我选了哪套工具链 + 命令字面 + 输出"
- **选定工具链确认可用后**(步骤 1-3 PASS),后续命令**全程统一用该工具链**;不来回切换
- **只在选定工具链工具不可用时停手报 PM**(如 `rg` 没装 / `.venv` 没建);不**因为另一套工具链不可用而停手**(防 R3 P1-1 同源)
- **不**自行更换工具或自行替换命令(防反例 25 同源)

### #1 — main HEAD `qa_with_context.yaml` 真实形态

```bash
cat core/prompts/qa_with_context.yaml
```

**Codex 报告**:
- 完整文件内容(全文)
- 版本号 / description 字段字面
- system 段 4 章核心标题是否存在("## 输出协议" / "## 证据规则" / "## 教学口吻" / "## 安全约束")
- user 段 4 个模板变量字面(`{project_name}` / `{project_type}` / `{source_block}` / `{question}`)是否齐备

**PASS 条件**:4 核心章节 + 4 模板变量都在;`version: "v0.1"` 字面存在。

### #2 — yaml safe_load 解析(GPT R2 P2 修订:用项目 Python 环境)

> **GPT R2 P2 修订**:必须用**项目 Python 环境**(`.venv` / poetry / 项目级 venv),系统 Python 可能没装 pyyaml(实测 Windows F:\python\python.exe 无 yaml,`.venv\Scripts\python.exe` 有 yaml 6.0.2);**反例 27 同源**("工具默认行为"陈述前必须实地核查)。

**命令**(Codex 实施时按平台选项目 Python 环境):

```bash
# 选项 1:bash + venv(Linux / macOS / Git Bash)
.venv/bin/python -c "import yaml; d = yaml.safe_load(open('core/prompts/qa_with_context.yaml')); print('version:', d.get('version')); print('system chars:', len(d.get('system', '')))"

# 选项 2:Windows cmd / PowerShell
.venv\Scripts\python.exe -c "import yaml; d = yaml.safe_load(open('core/prompts/qa_with_context.yaml')); print('version:', d.get('version')); print('system chars:', len(d.get('system', '')))"

# 选项 3:poetry run(若项目用 poetry)
poetry run python -c "import yaml; d = yaml.safe_load(open('core/prompts/qa_with_context.yaml')); print('version:', d.get('version')); print('system chars:', len(d.get('system', '')))"
```

**Codex 报告**:用了哪种 Python 环境 + 输出实际 version 值 + system 段字符数

**PASS 条件**:`version: v0.1` + system 字符数 < 3000(为 v0.2-rc 预留空间)

### #3 — `_prompt_loader.py::load_prompt_template()` 函数签名 + yaml 字段引用(GPT R1 P1-2 修订)

> **GPT R1 P1-2 修订**:v0.1 写 `_load_qa_template()`,实地核查发现实际是 `features/chat/_prompt_loader.py::load_prompt_template()`,由 `features/chat/_prompt_builder.py::ChatPromptBuilder` 类调用。**反例 28 大命中**:架构师无 repo,task-205-v0.2 设计稿 § 7.4 与 main HEAD 实际入库形态有差异(文件拆分 + 函数名变化)。本节按实际核查写。

**核查方式**(GPT R4 P2-4 修订:`view` 是 Codex 文件读取工具,**不是** shell 命令,不放进 code block):
- 用 Codex 自身 `view` 工具读取 `features/chat/_prompt_loader.py` 和 `features/chat/_prompt_builder.py`(等价 PowerShell `Get-Content` / bash `cat` / `rg . <file> --no-line-number`)

**Codex 报告**:
- `load_prompt_template()` 函数(在 `_prompt_loader.py`)存在 + 签名 + 读取 yaml 哪几个字段(system / user / version / description / 其他?)
- `ChatPromptBuilder` 类(在 `_prompt_builder.py`)是否存在 + 是否调用 `load_prompt_template()`
- `ChatPromptBuilder.build_messages(...)` 方法签名是否含 `source_entries: list[SourceEntry]`(TASK-205 R2 P1-5 锁)
- `source_block` 渲染语义(GPT R2 P2 修订):**仅含** `source_id + source_type + snippet`(snippet 可经 `_truncate(snippet, MAX_SNIPPET_CHARS)` 截断);**不含** `line_range`(关键守门项)
- `source_block` 是否含 `line_range` 渲染(应**不含**;GPT R1 P2-5 守门:LLM 看不到行号)

**PASS 条件**:
- `load_prompt_template()` 在 `_prompt_loader.py`,读取字段不超过 `system / user / version / description` 4 个
- `ChatPromptBuilder.build_messages(...)` 签名符合 TASK-205 R2 P1-5
- `source_block` 渲染**仅含** `source_id + source_type + snippet`,**不含** `line_range`(P2-5 守门:确认 LLM 拿不到行号,避免编造)

### #3' — `tests/features/chat/test_prompt_loader.py` 字面断言核查(GPT R1 P1-1 兜底)

```bash
grep -nE 'template\.version|"v0\.1"|"v0\.2' tests/features/chat/test_prompt_loader.py 2>&1
grep -rnE '"v0\.1"|"v0\.2"' tests/features/chat/ 2>&1
```

**Codex 报告**:命中行 + 内容;列出所有含 `"v0.1"` 字面断言的测试

**PASS 条件**:
- `test_prompt_loader.py` 含 `template.version == "v0.1"` 字面(或类似断言)→ 本任 D9 允许的字面同步范围 = 这条 + 其他 grep 命中的同类断言
- 命中 0 → 不需要 tests 同步(Codex 报 PM 决定是否仍允许 D9 例外打开)

### #4 — TASK-304 Stage 0 #10 hot-patch 实测状态(R5 应对)

```bash
grep -nE "subsystem|overview|file/function/block/subsystem|项目总览" core/prompts/qa_with_context.yaml | head -20
```

**Codex 报告**:命中行号 + 内容

**判断**:
- 0 命中(prompt 不含 subsystem / overview 字面) → PASS,本任 D5 按设计稿全新追加
- ≥ 1 命中(TASK-304 hot-patch 已落) → **触发 R5 应对**:Codex 报告完整命中段;本任 D5 改"在已有基础上强化 + 加 R12 软消解",**不替换**已落段

### #5 — `chat_schemas.py` 是否存在 + 字段集守门

```bash
ls features/chat/chat_schemas.py
grep -nE "class (ChatLLMResponse|ChatAnswer|ChatResponse)" features/chat/chat_schemas.py
```

**Codex 报告**:文件是否存在 + 3 个 class 是否在 + 字段集(列每个 class 的字段名)

**PASS 条件**:3 个 class 都在;字段集符合 TASK-205 § 8 锁(`answer / confidence / citation_ids / follow_up_suggestions` + `is_fallback / fallback_reason`)

### #6 — `core/prompts/` 目录现有 yaml 清单

```bash
ls core/prompts/*.yaml
```

**Codex 报告**:实际 yaml 文件清单

**PASS 条件**:`qa_with_context.yaml` 在;`glossary.yaml` **不在**(本任新建);若 `project_overview.yaml` 在 → D1 不动该文件守门

### #7 — `docs/eval/` 目录是否存在

```bash
ls docs/eval/ 2>&1 || echo "DIR_NOT_EXIST"
```

**Codex 报告**:目录存在 / 不存在

**应对**:
- 不存在 → 本任新建 `docs/eval/` + `qa_eval_design.md`
- 存在 → 本任仅加 `qa_eval_design.md`(不动既有内容)

### #8 — `version: "v0.2-rc"` / "v0.2" 字面在 main 是否已出现(防 D2 提前落地)

```bash
grep -rn 'version: "v0.2' core/prompts/ 2>&1 | head -5
```

**Codex 报告**:命中行 + 内容

**PASS 条件**:0 命中(防止某个 yaml 已被人提前升 v0.2 触发字面冲突);非 0 → 停手报 PM

### #9 — 03 索引 TASK-305 行字面(搭车 chore)

```bash
grep -nE "^\| TASK-305" docs/03_TASK_INDEX.md
```

**Codex 报告**:命中行 + 内容

**PASS 条件**:
- 已落 TASK-304 merge 搭车 chore(line 339 `4/7` + line 342 `22/32` + line 349 `启动 TASK-305`)→ TASK-305 行字面应是 `🔲`,本任搭车 chore 改 `🔲 → 🔍`
- 未落 chore → 停手报 PM(305 起稿前 PM 必须先落 304 merge chore;依赖反例 29 跨段一致性)

---

## 验收标准(Codex 实施完成后)

### 文件层守门

- [ ] **#1** `core/prompts/glossary.yaml` 新建,40 条术语(`grep -cE "^[[:space:]]+[a-z_]+:" core/prompts/glossary.yaml` ∈ [30, 50])
- [ ] **#2** `core/prompts/glossary.yaml` 含 `version: "v0.1"` 字面
- [ ] **#3** `docs/eval/qa_eval_design.md` 新建,含 § 1-7 段(`grep -cE "^## " docs/eval/qa_eval_design.md` ≥ 7)
- [ ] **#4** `core/prompts/qa_with_context.yaml` `version` 字段:`grep -nE '^version: "v0\.2-rc"' core/prompts/qa_with_context.yaml` 命中 1 行
- [ ] **#5** `core/prompts/qa_with_context.yaml` v0.1 原 4 章核心标题保留:`grep -cE "## (输出协议|证据规则|教学口吻|安全约束)" core/prompts/qa_with_context.yaml` ≥ 4
- [ ] **#6** `core/prompts/qa_with_context.yaml` v0.2-rc 追加 3-4 段:`grep -cE "## (证据类型说明|国内教材术语对齐|教学口吻反例|回答前的内部判断)" core/prompts/qa_with_context.yaml` ≥ 3
- [ ] **#7** `core/prompts/qa_with_context.yaml` user 段 4 模板变量字面保留:`grep -cE "\{(project_name|project_type|source_block|question)\}" core/prompts/qa_with_context.yaml` ≥ 4
- [ ] **#8** `core/prompts/qa_with_context.yaml` system 段总长 ≤ 3000 字(yaml safe_load 后 `len(d["system"])` 检验,Python 一行守门)

### yaml 解析守门

- [ ] **#9** 使用项目 Python 环境(`.venv/bin/python` / `.venv\Scripts\python.exe` / `poetry run python`,**不**用系统 `python`;GPT R2 P2 修订):`<项目 python> -c "import yaml; yaml.safe_load(open('core/prompts/qa_with_context.yaml'))"` 无异常
- [ ] **#10** 同 #9:`<项目 python> -c "import yaml; yaml.safe_load(open('core/prompts/glossary.yaml'))"` 无异常

### 不动文件守门(D9 + D10)

- [ ] **#11** **生产** Python 代码零变更:`git diff --name-only main -- '*.py' ':!tests/'` 应空(GPT R1 P1-3 修订:本任改 `core/prompts/*.yaml` 必让 `core/` 非空,**只**核查 .py 文件 + 排除 tests/ 路径)
- [ ] **#11'** tests Python 改动仅限字面同步(GPT R1 P1-1 + R3 P3-5 兜底):
  - **机械守门(辅助)**:`git diff main -- 'tests/**/*.py'` 若有命中,**每个 hunk 应仅是** `"v0.1"` → `"v0.2-rc"` 字面替换
  - **bash 自动检查**:`git diff main -- 'tests/**/*.py' | grep -E '^[-+]' | grep -v -E '"v0\.(1|2-rc)"|^---|^\+\+\+'` 应空(只保留字面替换 hunk,无其他改动行)
  - **PM 人工 review 兜底**(GPT R3 P3-5 修订:机械守门偏弱,只能辅助):PM 在 305 PR review 时**逐行核查** tests/ diff 仅含 `"v0.1"` → `"v0.2-rc"` 字面替换;**不**含新增 assert / 新增 import / 新增 test function / 改测试逻辑
  - **Phase 2 候选**:写 Python 校验脚本(`scripts/check_tests_literal_sync.py`)严格证明"仅一处字符串替换";MCS 阶段人工 review 足够
- [ ] **#12** Pydantic schema 零变更:`git diff main -- features/chat/chat_schemas.py 2>&1 | head -5` 应空 + `git diff main -- core/domain/*.py 2>&1 | head -5` 应空
- [ ] **#13** AppSettings 零增量:`git diff main -- app/config.py .env.example 2>&1 | head -5` 应空
- [ ] **#14** prompt_builder 零变更:`git diff main -- features/chat/_prompt_builder.py 2>&1 | head -5` 应空
- [ ] **#15** ChatService 零变更:`git diff main -- features/chat/chat_service.py features/chat/_chat_persist.py 2>&1 | head -5` 应空
- [ ] **#16** project_overview.yaml 零变更:`git diff main -- core/prompts/project_overview.yaml 2>&1 | head -5` 应空(D1 严守)
- [ ] **#17** 没新建 B / C 类 prompt yaml:`ls core/prompts/slx_block_explain.yaml core/prompts/m_code_explain.yaml 2>&1` 应输出"No such file"(D1 严守)

### Prompt injection 防御段守门

- [ ] **#18** v0.1 防御段核心语义保留:`grep -cE "(prompt injection|忽略系统提示|切换角色|数据.*不是指令)" core/prompts/qa_with_context.yaml` ≥ 2(原 v0.1 安全约束段不应被改弱)

### 03 索引搭车 chore(决策 07 边界)

- [ ] **#19** TASK-305 行从 🔲 改 🔍:`grep -nE "^\| TASK-305" docs/03_TASK_INDEX.md` 命中行应含 🔍(不是 🔲 / ✅ / ❌)
- [ ] **#20** 进度条 / 总计 / 当前状态字面零变更:`git diff main -- docs/03_TASK_INDEX.md | grep -E "^[-+].*[0-9]/[0-9]|当前状态"` 应空(本任不动这 3 处;由 PM merge 后另改)

### Stage 0 #4 hot-patch 状态对应守门(R5)

- [ ] **#21** 若 Stage 0 #4 PASS(prompt 不含 subsystem / overview 字面):验收要求 `grep -nE "(subsystem|overview)" core/prompts/qa_with_context.yaml` 命中 ≥ 4 行(本任 D5 落地)
- [ ] **#21'** 若 Stage 0 #4 触发 hot-patch(已含字面):验收要求 v0.2-rc diff 在已有基础上**强化**(grep "项目总览|不要把.*当文件名" 命中 ≥ 1),**不替换** 已落段

### CI hygiene + format(决策 09 纪律 7 + 反例 26 + GPT R3 P1-2 修订)

> **GPT R3 P1-2 修订**:`make check` 调 PATH 上的 python/pytest/ruff/mypy,Windows 实测 PATH 里是系统 Python / Anaconda,**不是项目 .venv**,裸 pytest 跑 chat 测试会缺 `sentence_transformers`;`bash scripts/check_repo_hygiene.sh` 在 PowerShell 不可用,**但** `make hygiene` 走 `scripts/check_repo_hygiene.py` 跨平台可用。

- [ ] **#22** **CI 全管道,使用项目 Python 环境**(GPT R3 P1-2 + R4 P1-2 修订:对齐 Makefile `check` target 完整 step):
  - **首选(等价 `make check`,完整管道)**:**先激活 venv 再跑 `make check`**(`source .venv/bin/activate` 或 `.venv\Scripts\activate.ps1`)→ `make check`
  - 备选(venv 激活不可用 + 必须**等价** Makefile `check` 完整 step,**不是**降级):
    - `.venv/bin/python -m pytest -v` 或 `.venv\Scripts\python.exe -m pytest -v`(**全测试,不只 chat**;对齐 Makefile)
    - `.venv/bin/ruff check .` 或 `.venv\Scripts\ruff.exe check .`
    - `.venv/bin/ruff format --check .` 或 `.venv\Scripts\ruff.exe format --check .`(R4 P1-2 补:漏的 step)
    - `.venv/bin/mypy core/ adapters/ features/ api/` 或 `.venv\Scripts\mypy.exe core/ adapters/ features/ api/`(R4 P1-2 补:Makefile 跑 4 目录,不只 features/)
    - `make hygiene` 或 `.venv/bin/python scripts/check_repo_hygiene.py`(由 #23 守门)
  - **核查重点**:`tests/features/chat/` 现有 prompt 相关测试不应因 yaml 改动失败(允许 #11' 字面同步;不允许新 assert)
  - **本任不引入 Python 代码**,主要核查既有测试 / lint / type-check 不挂
  - **若使用备选必须跑全 5 步**(对齐 Makefile `check`),漏任一 step = #22 FAIL
- [ ] **#23** Hygiene 守门(GPT R3 P1-2 修订:**用 `make hygiene` 或 `<项目 python> scripts/check_repo_hygiene.py`,不用裸 bash**):
  - 选项 A:`make hygiene` PASS(走 `scripts/check_repo_hygiene.py` 跨平台,实测 PM 确认可用)
  - 选项 B:`.venv/bin/python scripts/check_repo_hygiene.py` 或 `.venv\Scripts\python.exe scripts/check_repo_hygiene.py` PASS
  - **不用** `bash scripts/check_repo_hygiene.sh`(PowerShell 不可用)

---

## 给 Codex 的提示

### 范围严守

- **只动 3 + 1 个交付文件**:`core/prompts/qa_with_context.yaml`(修改)+ `core/prompts/glossary.yaml`(新建)+ `docs/eval/qa_eval_design.md`(新建)+ `docs/03_TASK_INDEX.md`(305 自己的搭车 chore 改 🔲 → 🔍)
- **额外允许 1 个 tests 字面同步**(D9 + GPT R2 P1 修订):`tests/features/chat/test_prompt_loader.py` 等含 `template.version == "v0.1"` 字面断言的测试,**允许**改 `"v0.1"` → `"v0.2-rc"` 字面同步;**不允许**新增 assert / 新增 test function / 改测试逻辑
- **生产 Python 代码严守不动**(D9 严守);若发现 yaml 改动会触发**生产** Python 代码变更(如 yaml schema 不兼容)→ **停手报 PM**

### Stage 0 必跑

- **10 项 Stage 0 全跑**(含 #3' 兜底);任一异常停手报 PM
- 重点:#1 报告 `qa_with_context.yaml` 全文 + #4 报告 hot-patch 状态 + #9 报告 03 索引 TASK-305 行字面

### yaml 写法

- 用 yaml block scalar(`|`)写 system 段 / user 段,**不**用单行字符串
- 中文标点保留原样(参考 v0.1 既有标点风格;ASCII `:` / `,` + 中文 `。`,反例 24 + 反例 28 同源)
- 缩进用空格,**不**用 Tab
- yaml safe_load 测试通过

### glossary.yaml 词条选择

- **优先**:国内主流教材高频词(胡寿松《自动控制原理》/ 郑君里《信号与系统》/ 樊昌信《通信原理》/ 刘和平《微机原理》)
- **避免**:过度专业细分术语(如电力系统的 STATCOM / UPFC,Phase 2 视客户结构再加)
- 40 条覆盖控制 / 电机 / 电力电子 / 信号处理 / **通信** **5 大方向**(本任 § 7.2 草案 40 条供参考;GPT R2 P2-c + R3 P2-4 修订;最多 50 条)
- **格式**:`english_lower_snake: 中文教材标准词`,**不**含解释 / 同义词列表

### v0.2-rc 追加 3 段措辞

- 参照本文档 § 7.1 v0.2-rc 追加段示例;**保留**核心结构 + 措辞,**允许**微调具体术语 / 负例措辞
- "证据类型说明"段:8 类 source_type 全列(LLM 视角,不是 chunk 视角)
- "国内教材术语对齐"段:内嵌 glossary.yaml 当前快照(40 条)
- "教学口吻反例"段:1-2 个负例 + 1 个正例对照
- "回答前的内部判断"段:允许"先判断证据是否足够,再组织回答"措辞;**不要求** LLM 输出思维过程

### 03 索引搭车 chore

- 仅改 TASK-305 行 `🔲 → 🔍`(line ~181 附近,具体行号 Codex 实测)
- **不动**进度条 / 总计 / 当前状态字面(那 3 处由 PM 在 305 merge 后另改 ✅)
- 不写"TASK-305 完成,启动 TASK-306"(那是 merge 后状态)

### 完工三件套(决策 08)

- PR 标题:`TASK-305: 教学 Prompt 优化(候选驱动 v0.2-rc + glossary v0.1 + 评测设计)`
- PR 正文:对照 § 验收 #1-#23(+ #11' + #21' 兜底)逐条勾选;说明每条做了什么
- commit 拆分:建议 **5 commits**(304 merge bookkeeping 已走独立 chore PR `f0ad469`,本任**不重复**;tests 字面同步独立 commit 让 review 注意力清晰)
  1. `feat(prompts): add glossary.yaml v0.1 with 40 terms (5 directions)`
  2. `feat(prompts): qa_with_context.yaml v0.1 -> v0.2-rc (candidate)`
  3. `test(prompts): sync test_prompt_loader.py version assertions to v0.2-rc`(GPT R2 P1 修订,字面同步)
  4. `docs: add docs/eval/qa_eval_design.md for TASK-306 consumption`
  5. `chore: mark TASK-305 as reviewing in TASK_INDEX`

---

## 关联文档 / 决策 / 反例

### 关联宪法

- 01 § 8 line 311(prompt 在 yaml,不写死代码)
- 01 § 11 line 364(单次问答 < 8s)
- 05 § 0 / § 5 / § 6 / § 8 / § 8.2 / § 9.2(教学风格 + glossary + 版本号)
- 03 索引 line 181 / 211-228(TASK-305 行 + 评测维度)

### 关联 Task

- **上游**:TASK-203(`project_overview.yaml` v0.1,本任不动)/ TASK-205(`qa_with_context.yaml` v0.1 + `_prompt_builder.py` + chat_schemas)/ TASK-303(7 类 chunk source_text 模板;chunk 视角)/ TASK-304(8 类 RetrievalHit.source_type;LLM 视角 + R12 sentinel)
- **下游**:TASK-306(消费 v0.2-rc + glossary + qa_eval_design.md 跑评测)/ TASK-307(证据强制器,与本任 D7 R12 软消解互补;不接 sentinel 修复)/ TASK-403(前端展示文案受 LLM 输出风格影响)
- **平行 chore**:R12 sentinel backend chore(D7 推 PM 另开)

### 关联决策

- 决策 06(Codex 可读仓库文件)— Stage 0 实地核查依赖
- 决策 07(03 索引更新边界)— 搭车 chore 沿用
- 决策 08(PM 验 git + 字节级)— commit 三件套
- 决策 09(架构师必须实地核查)— 反例 28 KPI;架构师无 repo,Stage 0 转 Codex
- 决策 11(async + logger 双不变量)— 本任不引入新 async / 新日志,但勿动既有

### 关联反例

- 反例 18(审批级别 5 维评估)— § 状态段兑现
- 反例 24(凭印象写)— Stage 0 全 Codex 实地核查兜底
- 反例 28(架构师无 repo)— Stage 0 转 PM / Codex 兜底
- 反例 29 / 30(跨段一致性)— § 输出 + § 接口 + § 验收 grep 关键字 1:1 对齐
- 反例 31(决策回避 / 转嫁)— D7 R12 不写"留给 307 修",明示去向 backend chore

---

## Checklist(精简)

**实施前**(Codex 第一棒):
- [ ] 读 5 核心文档(01 / 02 / 03 / 04 / 05)
- [ ] 读决策 06 / 07 / 08 / 09 / 11
- [ ] 读 task-205-v0.2.md § 7.5(qa_with_context.yaml v0.1 设计稿)+ task-304-vector-rag-v0.5.md(SourceType 8 类 + R12)
- [ ] 读 task-303-chunk-strategy-v0.5.md(chunk 7 类 source_type 与 LLM 8 类对照)
- [ ] 跑 Stage 0 10 项(含 #3' 兜底),报告 PASS / FAIL + 异常细节

**实施中**:
- [ ] 只动 3 + 1 个交付文件 + 可选 1 个 tests 字面同步文件(yaml × 2 / 设计文档 × 1 / 03 索引 305 自己的搭车 chore × 1 / test_prompt_loader.py 字面同步 × 1)
- [ ] 任一**生产** Python 代码改动 → 停手报 PM;tests 改动**仅限** v0.1 → v0.2-rc 字面同步,不允许新增 assert / 改测试逻辑
- [ ] yaml safe_load 解析通过 + system 段 ≤ 3000 字
- [ ] glossary 40 条 + 格式 `english_lower_snake: 中文`
- [ ] 03 索引 TASK-305 行改 🔍

**完工前**:
- [ ] 验收 #1-#23 全过(含 #11' tests 同步守门 + #21' hot-patch 对应守门)
- [ ] commit 拆 5(glossary / qa v0.2-rc / test 字面同步 / eval design / 305 行 🔲→🔍 搭车 chore;304 bookkeeping 已独立 PR `f0ad469`,**不重复**)
- [ ] commit subject 单行无 body(反例 17)
- [ ] PR 标题 + 正文按本任模板
- [ ] 完工三件套(决策 08:git log + git diff --stat + git status clean)

---

**版本**:v0.1.4(2026-06-07 起稿 → GPT R1 5 + R2 8 + R3 5 + R4 5 = 22 条全采纳)
**作者**:Claude(架构师,第二十一任)
**关联宪法版本**:v2.1(冻结,不修改)
**前置 commit**:main HEAD `chore: bookkeeping for TASK-304 merge in TASK_INDEX`(commit `f0ad469`,304 merge 后 bookkeeping 独立 PR;第二十一任接手并落)
**审批历史**:v0.1 起稿 → R1 / 5 → v0.1.1 → R2 / 8 + 次要 → v0.1.2 → R3 / 5 → v0.1.3 → R4 / 5(PM 拍板不进行 R5)→ v0.1.4 = **最终版**(2026-06-07)→ PM 入仓 + Codex 一口气执行 task + 完工
**审批级别**:GPT 四审已过(R1 + R2 + R3 + R4 全采纳;若 5 触发器任一命中 → 自动升 R5,**但 PM 拍板不进行**;Codex 实施期触发 → 停手报 PM)
**完工后 PM 单独 chore**:升仪决策 09 反例 32 三条 KPI(KPI-A / KPI-B / KPI-C,详 § R4 台账)
