# 20260601-07:更新 `docs/03_TASK_INDEX.md` 状态不算"动 `docs/`",是 Codex 必选并发动作

## 状态
✅ 决议

## 背景

TASK-002 启动后,Codex 第一时间停手抛了一个治理冲突:

- `docs/01_PROJECT_CONSTITUTION.md` 第 5 节明确写:**Codex 干完每个 Task 必须更新 `TASK_INDEX.md` 状态**
- 但 TASK-002 文档"不做"清单明确写:**不动 `docs/`**
- 而 PM 给 Codex 的开场白也强调:**不动 `docs/`**

这两条彼此矛盾。Codex 守住了"发现冲突停手问 PM"的纪律,把球踢回 PM,由架构师裁决。

裁决结果:**TASK-002 豁免动一次 `docs/03_TASK_INDEX.md`**(也仅限这一文件、仅限更新对应 Task 状态)。

这次裁决是个案处理,但根本问题是:**Task 文档模板里"不动 `docs/`"的措辞太粗**,把"维护索引"这种记账动作也一刀切了。需要一条决策从语义上把两类改动剥开,避免每个 Task 都要重复裁决一次。

## 决策

### 1. "不动 `docs/`" 的语义重新定义

未来所有 Task 文档里写"不动 `docs/`"或"`docs/` 已冻结",**自动等价于**:

**禁止改动**:
- ❌ `docs/01_PROJECT_CONSTITUTION.md`
- ❌ `docs/02_ARCHITECTURE_OVERVIEW.md`
- ❌ `docs/04_ENGINEERING_STANDARDS.md`
- ❌ `docs/05_EXPLANATION_STYLE_GUIDE.md`
- ❌ `docs/decisions/` 下所有已存在文件(新增决策日志另算,见第 3 条)
- ❌ `docs/api/` 下文件(自动生成)
- ❌ 当前 Task 自身文档以外的 `docs/tasks/` 文件

**允许且必选**(无需 PM 单独裁决):
- ✅ 更新 `docs/03_TASK_INDEX.md` 中**当前 Task 那一行**的状态(从 🔲 → 🔍)
- ✅ 同步更新 `docs/03_TASK_INDEX.md` 底部"当前进度"那个进度条,把当前 Task 对应方块也改为 🔍

### 2. 状态语义与 Codex / PM 分工

| 状态 | 含义 | 谁改 | 何时改 |
|------|------|------|------|
| 🔲 未开始 | 默认 | (无,PM 写 Task 文档时已是此状态) | — |
| 🟡 进行中 | Codex 在干 | Codex(可选) | 切分支后立即 commit,可与 Task 第一个 commit 合并;**Codex 觉得没必要也可以直接跳到 🔍** |
| 🔍 等待验收 | Codex 干完提了 PR | **Codex(必选)** | push 到分支前的最后一个 commit |
| ✅ 已通过 | Claude review 通过且已合并 main | **PM(必选)** | PR squash 合并后,新开一个小 PR 改索引 |
| ❌ 打回返工 | review 不过 | Claude / PM | review 时由 PM 改,或交给 Codex 改后再 push |
| ⏸ 暂停 / 冻结 | 战略调整 | PM | 极少用 |

**关键**:Codex 只把状态推到 🔍,不写 ✅。这避免"Codex 自审自批"。

### 3. 新增决策日志的处理

如果 Codex 在 Task 实施中**发现需要新增一条决策日志**(例如踩到一个值得长期记录的坑),原则上:

- **小坑**:写进当前 Task 的 PR 描述"风险与注意"段,**不**新增决策日志,避免 PR 范围扩张
- **大坑**(影响多个未来 Task / 改写工程规范):**停手问 PM**,由 PM 决定是单独走文档 PR 加决策日志,还是在当前 PR 顺带加

不允许 Codex 在 Task 实施 PR 里悄悄塞决策日志。

### 4. Task 文档作者(Claude)的写作规范

未来 Claude 写 Task 文档时:

- **不再在"不做"清单里写"不动 `docs/`"**,因为本决策已经定义清楚边界
- 取而代之,写"`docs/` 核心文档冻结(详见决策 07)"或干脆省略,默认按本决策执行
- 如果某个 Task **确实需要改 `docs/` 核心文档**(例如修订宪法、升级架构),那是宪法修订流程,**不能塞进普通 Task**,必须由 PM 单独走"宪法修订 PR",打新 git tag

### 5. PM 开场白模板的相应修订

下次 PM 派活给 Codex 的开场白,把"不动 `docs/`"那一条改成:

> 不动 `docs/` 核心文档(01/02/04/05、decisions、api、其他 tasks),但**必须**把当前 Task 在 `docs/03_TASK_INDEX.md` 的状态从 🔲 改为 🔍(见决策 07)

或者更简洁:

> `docs/` 改动按决策 07 执行

(因为决策 06 已说明 Codex 能读仓库文件,这种引用方式可靠。)

## 理由

1. **避免每个 Task 都重复裁决一次**:TASK-002 这次裁决花了 5 分钟,后续 30+ 个 Task 如果每次都问一次,累计成本太高
2. **澄清"改 docs 的两种语义"**:改规范 / 改架构 vs 改状态 / 改记账,是两件事,合并管理只会越管越乱
3. **保持 Codex 的"看见冲突就停手"纪律**:不放松这个原则,只是减少触发频率
4. **状态机和分工同时落地**:🟡 / 🔍 / ✅ 各自谁动,清清楚楚
5. **PM 仍然守住 ✅ 的最终签字权**:Codex 推到 🔍,PM 在合并后改 ✅,审批权不丢

## 影响范围

- Claude 写 Task 文档的措辞规范
- PM 派活给 Codex 的开场白模板
- Codex 操作 `docs/03_TASK_INDEX.md` 的边界
- 架构师交接文档(下次新 Claude 接手时,本决策也要纳入交接清单)

## 是否可逆

✅ 完全可逆。如果未来发现 Codex 不靠谱(比如改状态时把别的行改坏了),可改回"任何 docs/ 改动都需 PM 裁决"的严苛模式,只是流程更慢。

## 关联

- TASK-002 启动时的裁决记录(本对话)
- `docs/01_PROJECT_CONSTITUTION.md` 第 5 节
- `docs/03_TASK_INDEX.md` 状态约定章节
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(Codex 能读取的前提,本决策据此简化引用)

---

**决策日期**:2026-06-01
**决策人**:PM + Claude(架构),源于 TASK-002 启动时 Codex 抛出的治理冲突
