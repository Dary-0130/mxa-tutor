# 20260601-05:静态扫描命令必须排除 `.venv` / `.git`

## 状态
✅ 决议

## 背景

TASK-001 验收时,Claude 给 PM 的 TODO 残留检查命令为:

```bash
grep -rn -l "TODO\|FIXME\|XXX" --include="*.py" .
```

结果命中了 `.venv/Lib/site-packages/` 下大量第三方包(mypy / pytest / pip 自身代码),触发误报。

## 决策

**所有静态扫描类命令(`grep` / `find` / 自定义脚本)必须显式排除 `.venv` 和 `.git`**,无论本地手跑还是 CI 跑。

### 规范模板

`grep` 类:
```bash
grep -rn ... --exclude-dir=".venv" --exclude-dir=".git" ...
```

`find` 类:
```bash
find . -path './.venv' -prune -o -path './.git' -prune -o ... -print
```

Python 脚本类:遍历前显式跳过 `.venv` / `.git` / `__pycache__` / `node_modules`。

### 落地位置

- **TASK-001 task 文档的验收清单**:已写过的命令算历史,不追改,但本决策记录在案
- **TASK-002 CI 配置**:`ci.yml` 中所有静态扫描步骤必须遵守
- **TASK-002 同时新增 `scripts/check_repo_hygiene.sh`**(或同名 `.py`):统一收纳骨架级 grep 检查,避免下次 Task 又裸写
- **`Makefile`**:如新增扫描类 target,同样遵守

### 不影响

- `ruff` / `mypy` / `pytest`:这三个工具**自带**忽略 `.venv` 等,无需额外配置(`pyproject.toml` 已配 `target-version`,工具会读 git 配置或默认排除 venv)
- 业务代码扫描(如未来 LLM citation 校验扫工程文件):本决策不适用,业务扫描在 `data/uploads/` 下,与开发期扫描不同

## 理由

1. **避免 CI 在 PM 提 PR 时误报**:CI 跑 `grep TODO` 扫到 mypy 源码里的 TODO,会让无辜 PR 红;一旦 PM 习惯无视红 CI,真正的问题也会被无视
2. **降低 review 成本**:PM 在本地核对时,误报会让人怀疑代码,白白追问 Codex
3. **命令模板可复用**:统一规范后,所有 Task 文档都可直接抄

## 影响范围

- 所有未来 Task 的验收命令模板
- TASK-002 的 CI 工作流
- 任何新加的"仓库卫生检查"脚本

## 是否可逆

✅ 完全可逆,只是规范升级,不动代码。

---

**决策日期**:2026-06-01
**决策人**:Claude(架构) + PM,源于 TASK-001 实战发现
**关联**:TASK-001 验收日志、TASK-002 CI 配置
