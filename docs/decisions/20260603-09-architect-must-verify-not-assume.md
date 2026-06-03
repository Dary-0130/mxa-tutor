# 20260603-09 — 架构师写文档前必须实地核查,不凭印象做假设

## 状态

冻结(v2.1 兼容)。本决策与决策 04-08 并行生效,不冲突。

---

## 触发原因

TASK-104(项目第一个攻击面 P0 Task)的设计 / 修订 / review 全过程,架构师**连续 8 次因"凭印象做假设"被 Codex / PM / CI 抓住**。每次都没有进入 main(协作流程纪律的胜利),但累计延误项目约 2-3 个工作日,且暴露了一类系统性反模式:

**架构师在写文档 / 修订指令 / review 命令时,把"我以为是这样"等同于"事实是这样",而不去实地核查。**

这一类错误的特征是 GPT 二审看不到(只能审材料看不到仓库),Codex 实施时按文档干会被强制对齐(踩坑后才能被抓住),Step B PM 核查只能事后补救。**唯一可持续的解法是把核查纳入架构师的写作流程**。

8 次踩坑账本(项目历史完整记录,见末尾"反例集")。

---

## 决策

架构师在以下任一场景,**不能凭印象**做关于"仓库实际状态"或"文档内部一致性"的判断,必须实地核查或精确数数:

### 纪律 1 — 写新 Task 文档的"前置依赖"段时

凡引用其他 Task 的产物("已建文件 / 已定字段 / 已建配置"),必须 `view` 实地核查那个 Task 的实际产物。

**不可凭印象写**:"TASK-XXX 已建 `foo/bar.py`"。
**必须实地核查**:`view /mnt/project/task-XXX-*.md`,看其"输出(交付物)/ 新增文件"段实际列了什么。

### 纪律 2 — 写文档修订指令时

凡涉及"目标文件当前内容"的 before 文本,必须实地 `view` / `cat` 核查,**不能**凭"我之前写过应该是这样"假设。

**反例**:patch_task104.py 修订 3 用多行 Python 字符串字面量(LF)匹配 task-104.md CRLF 内容,assert 失败。

**正例**:写 patch 脚本前先 `cat <file>` 看实际行尾,或用 `git ls-files --eol <file>` 确认 i/lf w/lf,然后字符串字面量与文件实际编码对齐。

### 纪律 3 — 写字节级 Python 替换脚本时

多行匹配必须用 `\r?\n` regex 兼容 CRLF/LF,或用 `splitlines()` 后逐行处理。**禁止**用 Python `'''...'''` 多行字符串字面量直接匹配文件内容(LF/CRLF 不兼容)。

错误消息**必须**用纯 ASCII,避免 Windows Git Bash codepage 导致中文乱码挡视线。

### 纪律 4 — 文档内部数值描述时

文档自身的"字段数 / 行数 / 索引 / 总计"等数值,必须**实际数过**,不能凭"加法应该是这样"。

**反例**:task-108 § 7.1 代码骨架有 16 字段(1 必填 + 15 带默认),但架构师把"1 + 15"误算为"1 + 16 = 17",在 § 4 / § 7.1 末尾 / § 8 验收 4 三处把"16"写成"17"。

**正例**:写"字段总数 N"前,实际跑 `grep -cE "^\s+[a-z_]+:" <文档内的代码骨架抽出来>` 数一次。

### 纪律 5 — 二审采纳建议时

采纳 GPT 二审建议涉及多处出现的事实(扩展名清单 / 字段名 / 数字计数 / 文件路径等),**必须 grep 全文核查所有引用点同步更新**,不能只改局部。

**反例**:GPT round-2 建议把 `.gif` 加进 ALLOW_EXTS / `.bin` 加进 DENY_EXTS,架构师采纳时只改了 § 7.4 名单,**忘了同步** § 5 / § 8 里"用 .gif 做灰名单测试样例"和 § 7.6 "fixture 7 用 .bin 数据"的字面。Codex 实施时分别抓住两处。

**正例**:采纳后立即 `grep -n "<被改的字面>" <task文档>`,看所有引用点是否需要同步。

### 纪律 6 — 判断 CI 行为时

判断"CI 会装哪些依赖 / 跑哪些步骤",必须 `view .github/workflows/ci.yml` 看实际 `run:` 命令,**不能**凭 `requirements*.txt` 内容或 Makefile target 名假设。

**反例 1**:TASK-108 加 `pydantic-settings` 到 `requirements.txt`,架构师凭印象信"CI 会装它",实际 CI workflow 只跑 `pip install -r requirements-dev.txt`,且 `requirements-dev.txt` 没传递引用 `-r requirements.txt`,导致 CI ModuleNotFoundError。

**反例 2**:TASK-104 完工 review 时,架构师让 PM 跑 `make check`(本地全过),实际 CI 多跑一步 `ruff format --check`,Codex 本地的 Makefile lint target 没含这步,CI 挂在 format 检查。

**正例**:写 Task 文档"验收标准"或 review 命令清单前,先 `view .github/workflows/ci.yml`,逐条对齐 CI 实际执行的所有 `run:` 命令。

### 纪律 7 — Step B review 命令清单时

PM 跑的 Step B review 命令(决策 08 第 2 条)必须**对齐 CI 实际执行的所有步骤**,不能信任 `make check` 完整覆盖 CI。

Makefile target 与 ci.yml steps 经常漂移(实施时一方更新另一方未更新),review 时必须用 CI 实际命令做最终兜底。

### 纪律 8 — 架构师自我反思

每次架构师踩坑被 Codex / PM / CI 抓住后,**必须在当次 review 回复中明示反思**(踩坑序号 / 根因 / 应固化的纪律候选),不能默默修复。

这是为了:① 让 PM 看到协作流程在工作;② 累积证据决定何时固化新决策;③ 给后续架构师交接时留可追溯证据。

---

## 工程影响

**对架构师**:写文档时间增加约 15-30%(需要 view / cat / grep),但减少 Codex 踩坑后的派活循环时间(每次 30 分钟-2 小时)。**净时间为负**(节省项目时间)。

**对 PM**:Step B review 命令清单必须包含"对齐 CI 实际执行步骤"的核查,不再只跑 `make check`。

**对 Codex**:无影响。Codex"看见冲突就停手"纪律继续保持(决策 08 第 2 条),它是本决策的最终兜底。

**对 GPT 二审**:无影响。本决策针对 GPT 看不到的"仓库实际状态"维度,GPT 二审仍负责审材料层面的合理性。

---

## 反例集 — 8 次踩坑账本(TASK-104 历史完整记录)

| # | 触发位置 | 踩坑 | 根因纪律 | Codex/PM/CI 抓住方式 |
|---|---|---|---|---|
| 1 | task-104 v1.0 § 3 输入 | 假设 TASK-002 已建 `app/config.py`,实际未建 | 纪律 1 | Codex 实地 `ls app/` 发现只有 `__init__.py / README.md` |
| 2 | patch_task104.py 修订 3 | 多行 Python 字符串字面量(LF)匹配 CRLF 失败 | 纪律 2 + 3 | 脚本 assert 失败 |
| 3 | v3 修订辅助材料 | 假设 task-104.md 是 CRLF,实际 LF | 纪律 2 | Codex `git ls-files --eol` 报告 i/lf w/lf |
| 4 | task-108.md 三处 | 字段总数算成 17(实为 16) | 纪律 4 | Codex 数 § 7.1 骨架字段 |
| 5 | task-108 加 `requirements.txt` | 没核查 CI 是否装 runtime,实际只装 dev | 纪律 6 | CI failed: ModuleNotFoundError |
| 6 | task-104 v1.0 § 5 / § 8 | `.gif` 一处 ALLOW 一处灰名单,4 处描述 | 纪律 5 | Codex 写 classifier 测试时矛盾 |
| 7 | task-104 v1.0 § 7.6 fixture 7 | `.bin` 蓝图与 DENY 黑名单冲突 | 纪律 5 | Codex 写 fixture 7 测试时矛盾 |
| 8 | TASK-104 review 命令 | 用 `make check` 替代 CI 实际步骤,漏 `ruff format --check` | 纪律 7 | CI failed: 3 files would be reformatted |
| 9 | 第七任交接文案"当前进度"段 | 凭印象写"TASK-002 状态是 🔍",未 view 03 索引 | 纪律 1 + 8 | 第七任 onboard 实地核查时抓住 |
| 10 | task-106 v1.1 line 117 / 04 § 6 line 267 | 选 `openai==1.54.0` 凭 04 § 6 工程规范模板,没核查与 transitive deps(httpx 0.28.x)兼容性。模板本身锁定的版本号在写时已过期 1.5 年(openai 1.55.3 已修复 proxies bug) | 纪律 6 | Codex 实施时抓:`OpenAI()` 初始化抛 `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`(冲突 2) |
| 11 | task-106 v1.1 § 5 line 188-190 | 改 § 7.1 构造函数签名为 `api_key: str` 必填后,没全文 grep 同步 § 5 测试 case 描述,三处仍写 `DeepSeekTextProvider()` / `DeepSeekTextProvider(model=...)` 无 api_key | 纪律 5 | Codex 派活时抓(冲突 1) |
| 12 | task-106 v1.1 § 5 line 170 / § 7.1 line 249 | 写"用 loguru 记录元数据"时,凭 04 § 6 模板假设 loguru 已在仓库,实际 TASK-001 / 002 / 101 / 102 / 103 / 104 / 105 / 108 全部没人加;同根因反例 10(凭 04 § 6 模板做"已加"假设) | 纪律 1 / 6 同源 | Codex 实施时抓:`ModuleNotFoundError: No module named 'loguru'`(冲突 3) |
| 13 | 第八任 onboarding 开场白第 99-103 行 | 凭 Task 名字面 "ProjectGraph + TeachingUnit 基础构建器" 描述 TASK-107 范围,没核查 03 索引 line 99-103 验收点只列 ProjectGraph;与 02 § 2 "TeachingUnit 才用 LLM" + 03 索引 "本 Task 不调用 LLM" 三处约束的唯一一致解读是仅做 ProjectGraph | 纪律 1 | 第八任 onboard 自审抓(实地核查 03 索引时发现) |
| 14 | TASK-107 设计阶段 disambiguate 策略 | 凭印象认为 task-105 暴露多候选 `dict[name, list[relpath]]` 可供 TASK-107 消费做函数级 disambiguate,实际是 `dependency_analyzer.py::_build_function_name_map` 私有 helper(`_` 前缀),跨边界访问违反决策 06(adapter 模块封装) | 纪律 1 | GPT 一审抓(指出 v0.1 料源不支持 function symbol 级,只能文件级 CALLS) |
| 15 | TASK-107 设计阶段 SUBSYSTEM 节点 | 没核查 `SlxModel.subsystems` 与 `SlxModel.blocks` 的语义重叠 — `block_type == "SubSystem"` 时同一实体同时出现在 `blocks` 列表 + `subsystems` 字典 key。若分别建 BLOCK + SUBSYSTEM 节点会导致 LLM 召回 / RAG 链路上同一实体重复 | 纪律 1 | GPT 一审抓(指出 Subsystem 与 Block 不应双重建模) |
| 16 | task-107.md § 输出 line 138 | 凭直觉列 `tests/features/__init__.py` 为必须文件,实际 pytest 默认 `--import-mode=prepend` 不需要 namespace package 显式 init。Codex 实施时漏建反而是更简洁的实现,但报告 17 个文件不含此项让 Step B 核查触发疑问 | 纪律 4 | Step B PM 核查发现(`git diff main --stat` 比对 task 文档预期清单) |
| 17 | 第八任 chore-pr-execution-plan.md § 2 / § 3 / commit 5 | 凭印象写"反例 12-18"假设编号,同时方案另处给了"按 last_n+1 灵活编号"规则,两套指令矛盾;且 `openai==1.54.0` 实际 10 处误数为 9 处 | 纪律 5 / 纪律 4 同源 | Codex 实地 grep 抓住停手抛冲突 |

**共同特征**:每次架构师**有机会**实地核查(view / cat / grep / git ls-files / 看 ci.yml)就能避免,**但没做**。这 8 次踩坑没有任何一次是"知识缺失",全部是"流程缺失"。

---

## 与其他决策的关系

- **决策 04**(理解不是顶层 feature):无关
- **决策 05**(静态扫描排除 venv/git):本决策的纪律 5 grep 全文核查时必须遵守
- **决策 06**(Codex 可读仓库文件):本决策的纪律 1 / 2 利用 Codex 读取能力做"实地核查"是一个低成本工具
- **决策 07**(03 索引更新边界):无关
- **决策 08**(PM 验 git 三件套 + 字节级操作):**本决策是决策 08 在架构师维度的延伸**。决策 08 是 PM 不再信任 Codex 自检;决策 09 是架构师不再信任自己印象

---

## 终止条件

当以下三项**同时**满足时,可考虑废除本决策或降级为"建议"而非"强制":

1. 架构师团队连续 3 个核心 Task(宪法 § 5 二审清单成员)实施过程**零"凭印象假设"被抓住**
2. 协作纪律已经稳定到 Codex / PM / CI 抓住的全部是知识层错误,而非流程层错误
3. 项目已进入 Phase 2 阶段,核心 Task 已基本就位

---

## 一句话总结

**架构师写文档前,凡涉及"仓库现状 / 文档自洽性 / CI 行为 / 二审采纳同步" 的任何描述,必须实地核查或精确数数 — 凭印象写的代价由整个团队承担**。

---

**版本**:v1.0
**日期**:2026-06-03
**作者**:Claude(架构师,第六任)
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(决策 08 在架构师维度的延伸)
**触发 Task**:TASK-104(项目第一个攻击面 P0 Task,实施过程 8 次架构师踩坑,Codex 全部抓住,代价由架构师承担反思 + 固化本决策)
