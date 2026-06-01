# TASK-002: 开发环境 + CI 配置

## 状态
🔲 未开始

---

## 上下文

TASK-001 已建好骨架并合并到 `main`(commit `01413a7`),`main` 分支保护规则已生效(直接 push 被 GH013 拒,所有改动必须走 PR)。决策 05(静态扫描必须排除 `.venv` / `.git`,见 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`)与决策 06(Codex 能直接读取仓库文件,见 `docs/decisions/20260601-06-codex-can-read-repo-files.md`)也已就位。

本 Task 的目标是把 Week 0 验收的最后一块拼上:**让 GitHub CI 在每个 PR 上自动跑 `ruff` / `mypy` / `pytest`**,并把 PM 在 TASK-001 验收时手跑的"目录契约 / 字段契约 / TODO 残留 / key 泄露"等核对自动化成一个仓库卫生脚本。

完成本 Task 后,后续 Task 的 PR 不再需要 PM 手动跑一大堆命令——CI 红绿就是验收结论的第一道关。

---

## 输入(前置依赖)

- **必须已完成的 Task**:TASK-001(已合并)
- **必须存在的文件 / 状态**:
  - `main` 上有 TASK-001 的全部产物(目录树、`pyproject.toml`、`Makefile`、`requirements-dev.txt` 等)
  - `main` 分支保护已开(`Require PR before merging` + `Required approvals = 0` + `Block force pushes` + `Restrict deletions`)
  - 决策 05、决策 06 已在 `docs/decisions/`
  - `.github/workflows/` 目录已存在(目前只含 `.gitkeep`)
- **必须读过的文档**:
  - `docs/01_PROJECT_CONSTITUTION.md`(整篇)
  - `docs/04_ENGINEERING_STANDARDS.md`(整篇,**重点第 12 节 CI 模板、第 13 节 Makefile**)
  - `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(整篇,强制规范)
  - `docs/decisions/20260601-06-codex-can-read-repo-files.md`(整篇,确认你可以读仓库其他文件作为参考)
  - 当前 Task 文档:`docs/tasks/task-002-dev-env-and-ci.md`(本文)

---

## 输出(交付物)

### 新增 / 修改文件

**新增**:
- `.github/workflows/ci.yml` — GitHub Actions 工作流,在 `pull_request` 与 `push` 到 `main` 时跑 lint / type-check / test / hygiene
- `scripts/check_repo_hygiene.sh` — Bash 脚本,封装 TASK-001 验收时 PM 手跑的 6 条核对命令

**修改**:
- `Makefile` — 新增 `hygiene` target(本地一键跑 `scripts/check_repo_hygiene.sh`),并把 `check` target 扩展为同时跑 `hygiene`
- `scripts/README.md` — TASK-001 占位 README,需更新内容说明现有 / 未来脚本
- `README.md`(根)— 在"快速启动"章节追加一段:本仓库使用 GitHub Actions,所有 PR 必须 CI 全绿才能合并

**删除**:
- `.github/workflows/.gitkeep` — 一旦 `ci.yml` 存在,`.gitkeep` 没存在必要

### 新增依赖
无(`actions/checkout@v4` 与 `actions/setup-python@v5` 是 GitHub Actions 内置 action,不算 Python 依赖)。

### 新增配置项
无业务配置。仅 CI 工作流自身的 YAML 配置。

### 新增测试
不新增业务测试。`scripts/check_repo_hygiene.sh` 本身是验证脚本,不需要"测试的测试"。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-002-dev-env-and-ci`
- [ ] **创建 `.github/workflows/ci.yml`**,严格按 `docs/04_ENGINEERING_STANDARDS.md` 第 12 节模板,并叠加以下增强:
  - 触发条件 `pull_request: branches: [main]` + `push: branches: [main]`
  - Job 名称 `test`,`runs-on: ubuntu-latest`,Python `3.11`
  - 步骤顺序:`checkout` → `setup-python` → `pip install -r requirements-dev.txt` → `ruff check .` → `ruff format --check .` → `mypy core/ adapters/ features/` → `pytest -v --tb=short` → `bash scripts/check_repo_hygiene.sh`
  - **每一步显式 `name`**,失败时一眼看出卡在哪
  - 缓存 pip(用 `actions/setup-python@v5` 自带的 `cache: 'pip'` + `cache-dependency-path: requirements-dev.txt`),加速 CI
- [ ] **删除** `.github/workflows/.gitkeep`
- [ ] **创建 `scripts/check_repo_hygiene.sh`**,内容包含以下 6 条检查,全部按决策 05 加 `--exclude-dir=".venv" --exclude-dir=".git"`:
  1. `.gitignore` 必含 `.env` / `data/` / `__pycache__/` / `.venv/` 四项(任一缺失 → 退出非零)
  2. `.env.example` 必含 `DEEPSEEK_API_KEY` / `DB_PATH` / `UPLOAD_DIR` / `MAX_UPLOAD_SIZE_MB` / `FREE_QUESTION_PER_PROJECT` / `MONTHLY_QUOTA` / `LOG_LEVEL` 七字段
  3. **无真实 key 泄露**:`grep -rn "your-api-key\|sk-real\|sk-prod\|sk-live"` 在 `*.example` / `*.toml` 中无匹配
  4. **`.py` 文件中无 `TODO` / `FIXME` / `XXX`**(排除 `.venv` / `.git`)
  5. **无 `print(` 调用**(排除 `.venv` / `.git` / `tests/`,因 04 第 4 节明令禁止 `print` 调试)
  6. **无裸 `except:`**(排除 `.venv` / `.git`,因 04 第 4 节禁止)
  - 脚本头部 `set -euo pipefail`,任一条失败立即累积 FAILED(不要因一条失败就 short-circuit)
  - 每条检查输出 `PASS: <检查项>` 或 `FAIL: <检查项>: <详情>`
  - 最终统一输出 `All hygiene checks passed!` 或 `Hygiene check FAILED.`
- [ ] **更新 `Makefile`**:
  - 新增 target `hygiene`:`bash scripts/check_repo_hygiene.sh`
  - 修改 target `check`:从 `lint type-check test` 改为 `lint type-check test hygiene`(顺序保留,新增 hygiene)
  - `.PHONY` 行加上 `hygiene`
- [ ] **更新 `scripts/README.md`**:用 1-2 段说明 `scripts/` 目录目前包含什么(列出 `check_repo_hygiene.sh`),以及未来会包含什么(`init_db.py` / `dev_setup.py` 等占位)
- [ ] **更新根 `README.md`** "快速启动"章节:追加一段简短说明本仓库使用 GitHub Actions,所有 PR 必须 CI 全绿才能合并;追加 `make hygiene` 到本地命令清单
- [ ] **本地全套验证**(见"验收标准")
- [ ] **提 PR**,标题 `TASK-002: 开发环境 + CI 配置`,PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板
- [ ] **PR 提交后,本人观察 GitHub Actions 上 CI 实际运行结果**,在 PR 描述里贴 CI 跑通的截图或 Actions run 链接

---

## 不做(明确排除)

- ❌ **不加 Codecov / coverage 上传**(无业务代码,先备好基础设施,Week 1 真有测试时再加)
- ❌ **不加 `pre-commit` hooks**(MCS 阶段保持工具链最简)
- ❌ **不加 `dependabot.yml` / `renovate.json`**(依赖更新人工 review)
- ❌ **不加 `CODEOWNERS`**(单人项目)
- ❌ **不加 PR / Issue 模板文件**(PR 描述模板已在 `docs/04` 第 3 节,Codex 在 PR description 里手填即可)
- ❌ **不引入新 Python 依赖**(包括 `pytest-cov` / `pytest-mock` 等,等对应 Task 真需要时再加)
- ❌ **不创建 `scripts/dev_setup.py` / `scripts/init_db.py`**(等对应 Task)
- ❌ **不动 `pyproject.toml`**(TASK-001 已配好,本 Task 不调整 ruff / mypy / pytest 配置)
- ❌ **不动 `requirements.txt` / `requirements-dev.txt`**
- ❌ **不写 deployment workflow**(部署是 TASK-405)
- ❌ **不加 matrix 测多 Python 版本**(只跑 3.11)
- ❌ **不加 Windows / macOS runner**(只跑 ubuntu-latest)
- ❌ **不动 `docs/`**

---

## 接口契约

### `ci.yml` 关键结构

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: requirements-dev.txt

      - name: Install dev dependencies
        run: pip install -r requirements-dev.txt

      - name: Lint (ruff check)
        run: ruff check .

      - name: Format check (ruff format)
        run: ruff format --check .

      - name: Type check (mypy)
        run: mypy core/ adapters/ features/

      - name: Test (pytest)
        run: pytest -v --tb=short

      - name: Repo hygiene
        run: bash scripts/check_repo_hygiene.sh
```

允许微调注释、空行,但**步骤顺序、`name` 文本、命令**不许擅自改动。如果 Codex 觉得某条命令应改(例如 mypy 想加 `--strict`),**停手问 PM**,不要自己改。

### `check_repo_hygiene.sh` 关键骨架

```bash
#!/usr/bin/env bash
set -euo pipefail

FAILED=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1: $2"; FAILED=1; }

# 1. .gitignore must include core entries
# 2. .env.example must include required fields
# 3. No leaked real-looking API keys in *.example / *.toml
# 4. No TODO/FIXME/XXX in .py files (excluding .venv/.git)
# 5. No print( calls in .py files (excluding .venv/.git/tests)
# 6. No bare `except:` in .py files (excluding .venv/.git)

if [ $FAILED -eq 0 ]; then
    echo "All hygiene checks passed!"
    exit 0
else
    echo "Hygiene check FAILED."
    exit 1
fi
```

完整实现由 Codex 写,但**必须满足**:
- 所有 `grep -r` 必须带 `--exclude-dir=".venv" --exclude-dir=".git"`(决策 05)
- 每条检查独立判定,**不许因一条失败就 short-circuit 跳过后续**(用 `FAILED` 累积变量,最后统一 exit)
- 输出格式统一(`PASS: ...` / `FAIL: ...`),便于 CI 日志肉眼扫
- shebang 用 `#!/usr/bin/env bash`,**不用 `#!/bin/bash`**(可移植性)
- 文件权限 `chmod +x`,且**通过 `git update-index --chmod=+x` 把可执行位也提交进 git**(否则 Linux runner 上 `bash scripts/...` 仍可跑,但 `./scripts/...` 不能,稳妥起见加上)

### `Makefile` 变更

```makefile
# 原:
.PHONY: install dev test lint format type-check clean

check: lint type-check test
	@echo "All checks passed!"

# 改为:
.PHONY: install dev test lint format type-check hygiene check clean

hygiene:
	bash scripts/check_repo_hygiene.sh

check: lint type-check test hygiene
	@echo "All checks passed!"
```

---

## 验收标准

> 所有命令在仓库根目录、激活的 venv 内执行。Codex 在 PR 描述里贴每条命令的输出。

### 本地验证(Codex 提 PR 前自行确认)

- [ ] `git status` 在分支 `task/TASK-002-dev-env-and-ci` 上,干净
- [ ] `cat .github/workflows/ci.yml` 内容符合"接口契约"中的结构
- [ ] `test -f .github/workflows/.gitkeep && echo "BAD" || echo "OK"` 输出 `OK`(.gitkeep 已删)
- [ ] `test -x scripts/check_repo_hygiene.sh && echo "OK"` 输出 `OK`(脚本可执行)
- [ ] `bash scripts/check_repo_hygiene.sh` 输出 6 条 `PASS:` + `All hygiene checks passed!`,退出码 0
- [ ] `make hygiene` 同上
- [ ] `make check` 输出 lint / type-check / test / hygiene 全部通过 + `All checks passed!`
- [ ] `grep -n 'hygiene' Makefile | wc -l` 输出 ≥ 2(`.PHONY` 行和 target 行)
- [ ] `grep -n 'CI' README.md | wc -l` 输出 ≥ 1(README 已说明 CI 要求)

### GitHub CI 验证(PR 提交之后)

- [ ] PR 页面 **Checks 标签**显示 CI run **绿色 ✅**
- [ ] CI run 中能看到 8 个步骤名(`Checkout` / `Set up Python 3.11` / `Install dev dependencies` / `Lint (ruff check)` / `Format check (ruff format)` / `Type check (mypy)` / `Test (pytest)` / `Repo hygiene`)
- [ ] CI 总耗时 < 2 分钟(目标值,非硬卡)
- [ ] PR 描述底部贴 CI run 的链接(GitHub Actions 页面 URL)

### 分支保护互动验证(PM 与 Codex 协作)

- [ ] PR 在 CI 跑完之前,GitHub PR 页面显示 "Merging is blocked" 或类似提示(因 main 保护要求走 PR)
- [ ] CI 绿了之后,Merge 按钮可点(因 `Required approvals = 0`,无需别人 approve)

### PR 描述

- [ ] 标题:`TASK-002: 开发环境 + CI 配置`
- [ ] 按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板填写
- [ ] 贴上述本地验证 + GitHub CI 验证的输出 / 截图 / 链接

---

## 风险与注意点

### 1. Codex 易犯错误清单(review 时重点查)

| 易错点 | 期望行为 |
|--------|---------|
| CI 步骤里 `pip install -r requirements.txt`(注意是 dev 文件) | **只装 `requirements-dev.txt`**(runtime requirements.txt 当前为空) |
| `mypy` 步骤加 `api/` | 只查 `core/ adapters/ features/`(对齐 Makefile,避 FastAPI 类型噪音) |
| `pytest` 加 `-n auto` / `--cov` | 不加。MCS 阶段最简,等真有测试再优化 |
| `check_repo_hygiene.sh` 用 `find` 而非 `grep --exclude-dir` | 哪种都行,**但必须排除 `.venv` 和 `.git`**(决策 05) |
| 脚本里有 `cd` 改工作目录但没 `set -e` 兜底 | 必须 `set -euo pipefail` 在最顶 |
| `ci.yml` 在 `push` 任何分支都触发 | 仅 `push: branches: [main]` + `pull_request: branches: [main]` |
| 把 `.github/workflows/.gitkeep` 留着 | 必须删,只留 `ci.yml` |
| 在 `Makefile` 改 `mypy`/`pytest` 等其他 target | 只动 `hygiene` 和 `check` 两个 target |
| 把 README 写成完整 CI 文档 | 一段话即可,详细的在 04 第 12 节 |

### 2. CI 第一次跑可能踩的坑

- **`ruff format --check` 在 Linux runner 上行尾符判定**:Codex 本地在 Linux 没问题,但 PM 本地 Windows 改过文件,行尾符可能不一致。`.gitattributes` 没配。如果 CI 跑 `ruff format --check` 报错,先检查行尾符。**本 Task 不解决 .gitattributes**(超范围),如果踩坑就在 PR 描述里登记,留给后续。
- **`mypy` 在空目录上**:`mypy core/ adapters/ features/` 在只有 `__init__.py` 的目录上应输出 `Success: no issues found in 0 source files`,exit code 0。如果报错,看 `pyproject.toml` 配置。
- **缓存 key 失效**:第一次 CI run 没缓存,会装依赖 1-2 分钟;之后 PR 应在 30s 内装完。

### 3. PR 流程注意

- 本 Task 的 PR **本身就是分支保护规则的第一次实战检验**。Codex 提 PR 后,GitHub 会强制走完 PR 流程(无法 push 到 main、CI 必须跑过)。
- Codex 没有 GitHub 登录态(TASK-001 实战已确认),无法用 `gh pr create`。需要 **PM 协助**:Codex 把分支 push 到远端,PM 在 GitHub 网页上点 "New pull request" 创建,正文由 Codex 提供。

### 4. 不可逆操作警告

`main` 分支保护已开。Codex **绝对不要**尝试 `git push origin main`(会被 GH013 拒绝,且日志可见,白白增加 noise)。**所有改动只能 push 到 `task/TASK-002-*` 分支**,然后走 PR。

### 5. `print` 检查与 `tests/` 例外

仓库卫生第 5 条"无 `print(`"必须排除 `tests/`——pytest 测试里有时合理使用 `print` 调试断言,且 04 第 4 节禁令针对的是业务代码。脚本里的排除规则:`grep -rn "print(" --include="*.py" --exclude-dir=".venv" --exclude-dir=".git" --exclude-dir="tests"`。

---

## 估时

预估 2-3 小时(主要时间在调通 hygiene 脚本的 grep 表达式 + 等 CI 第一次跑)。

---

## 给 Codex 的提示

1. **先读决策 05 和 06**:`docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 和 `docs/decisions/20260601-06-codex-can-read-repo-files.md`。这两个决策直接影响本 Task 实现。

2. **操作顺序建议**:
   1. 切分支
   2. 先写 `scripts/check_repo_hygiene.sh`(本地能跑通 6 项 PASS)
   3. 再改 `Makefile`(加 `hygiene` target + 改 `check`),`make hygiene` 和 `make check` 都跑通
   4. 再写 `.github/workflows/ci.yml`,删 `.gitkeep`
   5. 改 `scripts/README.md` 和根 `README.md`
   6. 本地 `make check` 完整跑通 → commit → push 到远端分支
   7. PM 在 GitHub 网页创建 PR,贴标题和正文(Codex 提供)
   8. 观察 CI run,把链接补进 PR 描述

3. **Commit 粒度**(Conventional Commits):
   - `chore(ci): add github actions workflow`
   - `chore(scripts): add repo hygiene check`
   - `chore(make): add hygiene target and extend check`
   - `docs(readme): document CI requirement and local hygiene check`
   - 避免单个超大 commit。

4. **`check_repo_hygiene.sh` 的 grep 写法可参考**(Codex 可优化,但保留语义):

   ```bash
   # No TODO/FIXME/XXX in .py
   if hits=$(grep -rn -l "TODO\|FIXME\|XXX" --include="*.py" --exclude-dir=".venv" --exclude-dir=".git" . 2>/dev/null); then
       fail "no TODO/FIXME/XXX in .py" "$hits"
   else
       pass "no TODO/FIXME/XXX in .py"
   fi
   ```

5. **CI yml 缩进必须严格**:YAML 用 2 空格缩进,**绝对不要 Tab**。Codex 用 IDE 自动格式化前先确认编辑器设置。

6. **PR 创建协作**:Codex 完成本地 commit 并 push 后,在最终回复里**明确给出 PR 标题与正文**(按 04 第 3 节模板),PM 复制粘贴到 GitHub 网页创建 PR。Codex 不需要尝试 `gh pr create`。

7. **遇冲突先停手**:本 Task 明确禁止改 `pyproject.toml` / `requirements*.txt` / `docs/`。如果发现这些文件确实需要改才能完成任务,**停手问 PM**,不要自己拍板。

---

**版本**:Task 文档 v1.0
**作者**:Claude(架构师)
**日期**:2026-06-01
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-05-*.md`、`docs/decisions/20260601-06-*.md`
