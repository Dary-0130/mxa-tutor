# 20260602-08:PM 验收 Task 必须先确认 git 状态;改文本文件必须保留原始字节

## 状态
✅ 决议

## 背景

TASK-101 实施过程中,PM 和架构师踩到两个独立的坑,**都和"自检覆盖盲区"有关**,值得固化成规则,避免未来 27 个 Task 重复触发。

### 坑 1:Codex 完工虚报,实际 git 操作整段漏掉

TASK-101 实施时,Codex 给 PM 的完工报告**看起来非常完整**:

- 修改文件清单
- 本地 `make check` 全绿输出
- 验收清单 11 项逐条勾选 + 说明
- PR 标题 + 完整 PR 正文

PM 也基于这份报告做了 5 分钟"代码层抽查",6 条全过。准备让 PM 走"创建 PR + 合并"流程时,**让 PM 顺手跑了一下 `git status` 兜底**,才发现:

- Codex 新建的 11 个 `core/` 文件、11 个 `tests/core/` 文件**全部是 Untracked**(从未 `git add`)
- 改动的两个 README 和 `docs/03_TASK_INDEX.md` 全部是 **Changes not staged**(改了但没 commit)
- 分支 HEAD 仍指向 Week 0 末尾的 commit,与 `main` / `origin/main` 完全一致
- **没有任何 TASK-101 相关的 commit,更没有 push 到远端**

也就是说:Codex 把代码写了、测试跑了,**但完全跳过了 `git add` / `git commit` / `git push` 这三步**。它的自检 (`make check`) 看的是工作区(文件系统),git 状态它根本没查。

**Codex 自检对此完全无感**——它甚至准备好了 PR 标题和正文,但仓库里根本没有可以提的 PR。

补救成本:让 Codex 按 Task 文档建议的 commit 拆分逐步 `git add` + `git commit`,push 后才进入正常 review 流程。**多花了 30 分钟**,主要是来回确认状态。

### 坑 2:用 Python `write_text` 改 markdown,行尾被规范化

TASK-101 收尾时,PM 需要改 `docs/03_TASK_INDEX.md` 中的两处字符(状态符号 🔍 → ✅,进度条 0/7 → 1/7)。

PM 不直接编辑 markdown 文件,架构师给了一条 Python 命令:

```python
text = path.read_text(encoding='utf-8')
text = text.replace(old, new)
path.write_text(text, encoding='utf-8')
```

替换字符**确实成功**了(grep 验证两处都改成了 ✅ / 1/7)。但 `git commit` 出来的 diff 是:

```
docs/03_TASK_INDEX.md | 722 ++++++++++++++++++--------------
1 file changed, 1194 insertions(+), 361 deletions(-)
```

文件总长 361 行,**Git 显示每一行都被改了**。原因:`pathlib.Path.write_text()` 默认按系统行尾习惯写文件,而仓库里这份 markdown 是 CRLF 行尾(Windows 默认)。Python 在 Git Bash 环境下走的是某种 Unix-like 路径,**把整个文件的行尾从 CRLF 规范化成了 LF**。

对功能没有影响(内容字面值仍正确),但:
- PR diff 视觉上一片红绿,**review 不可能进行**
- 污染 `git blame`(以后追溯这两行改动会看到"作者改了整个文件")
- 浪费 PM 时间(诊断 + 回滚 + 重做)

补救成本:`git reset --soft HEAD~1` 撤销 commit,`git checkout --` 恢复文件,用 `read_bytes` + `bytes.replace` + `write_bytes` 字节级操作重做。**多花了 20 分钟**。

### 两个坑的共同性

- Codex 或工具的"成功输出"**不等于** git 状态正确
- 都发生在"PM 信任自动化报告" → "实际操作埋了雷"的链路上
- 都可以通过"PM 在合并前多跑一条命令"100% 拦截

## 决策

### 1. PM 验收 Task 必须先确认 git 状态

收到 Codex 完工报告后,**PM 在做任何代码层 review 之前**,必须先确认 git 状态,流程如下:

**Step A**:Codex 完工报告里**必须**包含以下信息(如果没有,PM 退回让 Codex 补):

- `git status` 输出(应显示"working tree clean")
- `git log --oneline main..HEAD` 完整输出(应显示本 Task 的全部 commit)
- `git push` 输出(应显示分支已推送到远端,有形如 `xxxxxx..yyyyyy  task/xxx -> task/xxx` 的行)

**Step B**:PM 在自己的本地仓库**复查**(不依赖 Codex 报告的截图):

```bash
git fetch origin
git checkout <task-branch>
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD
```

预期:
- 第一条命令输出本 Task 的完整 commit 列表,**非空**
- 第二条命令输出文件级 diff 摘要,**所有数字看起来合理**(不应有"明明改 2 行却显示 700+ 行变化"这种异常)

**只有 Step A + B 都通过,PM 才开始走代码层抽查**。

### 2. 改任何已存在文本文件必须保留原始字节

无论 PM / 架构师 / Codex,**改任何已存在的文本文件**(markdown / yaml / json / python / 配置文件 / 其他),**只允许**用以下两种方式:

**方式 A:用编辑器手动改**

VS Code / Notepad++ / IntelliJ / 任何成熟编辑器,都默认保留原文件的行尾和编码。Codex 直接编辑也属于这类(它内置的工具会保留原编码)。

**方式 B:Python 字节级操作**

```python
import pathlib
p = pathlib.Path('xxx')
data = p.read_bytes()
old = '原字符串'.encode('utf-8')
new = '新字符串'.encode('utf-8')
assert old in data, 'old not found'
data = data.replace(old, new)
p.write_bytes(data)
```

**禁止**:
- ❌ `path.read_text() + path.write_text()`
- ❌ `open(path, 'w').write(...)`(默认文本模式,会规范化行尾)
- ❌ `sed -i`(Git Bash 下对中文 + emoji 的处理不稳定,行为不可预期,**实战已验证踩坑**)
- ❌ `python -c "..."` 中混用文本模式读写

**唯一例外**:创建全新文件(不是修改已存在文件)。这种情况新文件可以按当前系统默认行尾写,因为不存在"原始字节"的概念。

### 3. Codex 完工报告模板更新

PM 派活给 Codex 的开场白模板(详见决策 07 第 5 节),**新增一条要求**:

> 完工时给 PM:
> - 修改的文件清单
> - 本地 `make check` 输出
> - **`git status`、`git log --oneline main..HEAD`、`git push` 三条命令的完整输出**(决策 08)
> - 验收清单逐条勾选 + 说明
> - PR 标题 + PR 正文

不补这三条命令输出 = Codex 没完工。

### 4. 架构师写 Task 文档的措辞规范

未来 Claude 写 Task 文档时:

- "给 Codex 的提示"段落新增一条:"提交前确保 `git status` clean、`git log --oneline main..HEAD` 显示完整 commit 列表、`git push` 成功推送"
- "验收标准"段落如涉及"改已有文件",**必须**说明用方式 A 或方式 B,**不允许**用 `read_text` / `write_text` / `sed -i`

实际操作上,Task 文档不需要每次重复决策 08 全文,引用"按决策 08 执行"即可(决策 06 已经说明 Codex 能读仓库文件)。

## 理由

1. **TASK-101 双坑共耗 50 分钟,未来 27 个 Task 累计风险不可接受**:每次踩同样坑修一遍 = 20 多小时浪费,远超固化规则的成本
2. **PM 不写代码,只能靠"跑命令 + 看输出"做验收**,所以验收流程必须**给具体命令**,而不是"PM 自行核对"
3. **Codex 自检盲区是结构性的**:`make check` 看的是工作区,从不查 git 状态。固化规则后,PM 不再依赖 Codex 自检
4. **字节级操作不是过度工程**:`read_bytes` + `write_bytes` 写法本身 5 行代码,和 `read_text` + `write_text` 等价,但完全消除行尾问题
5. **`sed -i` 在 Git Bash 实战踩过坑**:中文 + emoji 替换静默失败(grep 显示文件未改,但命令退出码 0),无法依赖

## 影响范围

- **PM 验收流程**:每次 Task 合并前必须跑 Step A + B,大约多花 1 分钟
- **Codex 开场白模板**:多一条"必须给 git log / git status / git push 输出"
- **Claude 写 Task 文档时**:"给 Codex 的提示"和"验收标准"段落措辞更新
- **架构师交接文档**:下次新 Claude 接手时,本决策也要纳入交接清单
- **未来所有改已有文件的操作**:统一用方式 A 或方式 B

## 是否可逆

✅ 完全可逆。

如果未来发现 Codex 自检高度可靠(几十个 Task 都没漏过 git 操作),可放宽 Step A + B 的要求。但**字节级文件操作规则建议永久保留**,因为这是工具属性问题,不是 Codex 可靠性问题。

## 关联

- **坑 1 触发记录**:TASK-101 实施过程,Codex 第一次完工报告(本对话)
- **坑 2 触发记录**:TASK-101 收尾 PR 创建过程,Python 改 03 索引行尾被规范化(本对话)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(静态扫描排除 `.venv`,本决策的"工具属性问题"同类)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(Codex 完工动作约束,本决策第 3 条直接更新该决策的开场白模板)

---

**决策日期**:2026-06-02
**决策人**:PM + Claude(架构),源于 TASK-101 实施和收尾过程中实际踩到的两个独立坑
