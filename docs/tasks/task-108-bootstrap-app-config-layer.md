# TASK-108: app/config.py + pydantic-settings 配置层(基建桥接)

## 状态

🔲 未开始

---

## 上下文

**这是 TASK-104 实施前补的基建桥接 Task**。

背景:`docs/02_ARCHITECTURE_OVERVIEW.md` 第 7 节定义了 `AppSettings` 配置层骨架,但 TASK-001 / 002 / 101 / 102 / 103 全部范围之外,没有任何前置 Task 实施它。TASK-104 是项目**第一个真正消费配置**的 Task,Codex 在 TASK-104 派活后实地核查发现 `app/config.py` 不存在,按决策 08"看见冲突就停手"纪律抛冲突给 PM。

架构师 + PM 协商后拍板:走方案 B,先单独走一个基建桥接 Task 把配置层建好,再回 TASK-104。理由:

1. 配置层是项目级基建,TASK-104 / 201 / 202 / 204 / 304 / 405 都会消费 `AppSettings`,独立成 Task 让其他 Task 干净 import
2. TASK-104 是攻击面 P0,绑配置层基建会污染本 Task 审计边界
3. 现在 Codex 还没动 TASK-104 任何文件,修复成本最低

**本 Task 属于 Week 1**,但**编号 108 不代表实施顺序**(宪法 § 8 节命名规范:NN 是"该周内序号",按加入索引的次序)。实施顺序是 **108 → 104 → 105 / 106 / 107**。

**架构师自我反思**(决策 09 候选):写新 Task 文档时,凡前置依赖里引用其他 Task 的产物,**必须 view 实地核查那个 Task 的"输出 / 新增文件"清单**,不能凭印象写。task-104 v1.0 漏掉这一步,GPT 二审两轮也没抓到(GPT 只看材料看不到仓库实地状态),Codex 抓到了,因为它在分支上实地操作。是否值得固化为决策 09 由 PM 在本 Task 合并后决定。

上下游依赖:

- **上游**:TASK-002(已合并 commit `64d337d`):基础工具链(`pyproject.toml` / `requirements-dev.txt` / `Makefile`)已就位
- **下游**:TASK-104(沙箱)/ TASK-201(FastAPI 框架)/ TASK-204(SQLite 存储)/ TASK-304(向量 RAG)等所有未来 Task,都通过 `from app.config import AppSettings` 消费

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架,已合并 commit `01413a7`):`app/` 目录已存在,内含 `__init__.py` + `README.md` 占位
- ✅ TASK-002(开发环境 + CI,已合并 commit `64d337d`):`requirements.txt` / `requirements-dev.txt` / `pyproject.toml` / `Makefile` 已配置
- ✅ TASK-003 / 101 / 102 / 103(已合并到 commit `4733417`):本 Task 不直接依赖,但 main 应处于 4733417 或之后

### 必须存在的文件 / 状态

- `main` 分支处于 commit `4733417` 或之后(task-104 v1.0 + task-108 文档已入仓的 docs PR 已合并)
- `app/` 目录已存在,内含 `__init__.py` + `README.md`(TASK-001 建)
- `app/config.py` **不存在**(本 Task 创建)
- `requirements.txt` 当前为空或 0 行(TASK-001 / 002 范围内未填,因为没有 runtime 依赖)
- `.env.example` 已含 7+ 字段(TASK-002 hygiene 强制),本 Task **扩展**

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,**特别第 7 节技术架构原则 / 第 8 节配置走 pydantic + YAML**)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,**特别第 7 节配置管理 `AppSettings` 代码骨架**)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,**特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范 / 第 6 节依赖管理 / 第 7 节配置与密钥**)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(静态扫描规范)
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(Codex 能读仓库文件)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(`docs/` 改动语义)
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(**git 三件套 + 字节级操作**)
- `docs/tasks/task-104-zip-extract-and-classify.md`(**下游消费者,理解为什么要建本 Task**)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `app/config.py` | `AppSettings` 配置类(pydantic-settings),含 17 个字段 | 50-90 |
| `tests/app/__init__.py` | 空文件,模块标记 | — |
| `tests/app/test_config.py` | `AppSettings` 单元测试(默认值 + 环境变量覆盖 + 必填字段缺失 + 类型转换) | 60-100 |

`tests/__init__.py` 由 TASK-001 / 002 已建,**不动**;`tests/app/` 目录新建。

### 修改文件

- **`requirements.txt`** — TASK-001 建,本 Task **新增 1 行** `pydantic-settings==2.6.1`(**项目第一个 runtime 依赖**)
- **`requirements-dev.txt`** — TASK-001 / 002 已建,**不动**(pydantic-settings 通过 `-r requirements.txt` 自动传递)
- **`.env.example`** — TASK-001 / 002 已建,本 Task **追加** 字段补齐 17 项配置(详见"接口契约"§ 7.3)
- **`app/README.md`** — TASK-001 占位,本 Task 更新:列出 `app/config.py` 的职责 + 用法示例(2-3 行)
- **`docs/03_TASK_INDEX.md`** — 本 Task 推 🔲 → 🔍,Week 1 进度条第 8 位 ⬜ → 🔍。**必须用字节级 Python 操作(决策 08)**,详见"风险与注意点"风险 1

### 不动文件

- `app/__init__.py`(TASK-001 已建空文件,本 Task 不动)
- `core/` / `adapters/` / `features/` / `api/` / `web/` 下所有文件
- `pyproject.toml` / `Makefile` / `.github/workflows/ci.yml` / `scripts/check_repo_hygiene.sh`(TASK-002 已配,本 Task 不调)
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(决策 07 边界;**特别注意**:本 Task 文档自身的修订、`task-104-zip-extract-and-classify.md` 的修订、03 索引"加 TASK-108 行 + 进度条 3/7→3/8"等改动,已由**架构师 + PM 在 docs PR** 提前完成,Codex 不需要也不允许在本 Task 内做这些"加行"动作)
- `tests/fixtures/` / `tests/core/` / `tests/adapters/`(已存在,与本 Task 解耦)
- 其他 Task 的代码与测试

### 新增依赖

**1 个,且是项目第一个 runtime 依赖**:

```
pydantic-settings==2.6.1
```

注意:pydantic-settings 内部依赖 `pydantic`(2.x),所以 `pip install -r requirements.txt` 会传递安装 pydantic。**PR 描述里必须明示**这是项目第一个 runtime 依赖,且 transitively 引入 pydantic。

### 新增配置项

17 个字段(完整清单见 § 7.1),已在 task-104 v1.0 范围说明里全部出现过。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-108-bootstrap-app-config-layer`
- [ ] **依赖结构理解**:实施前**第一件事**,`cat app/__init__.py app/README.md requirements.txt .env.example` 看实际内容,确认本 Task 文档"输入"小节描述的现状与实际一致。若 `.env.example` 现有字段顺序 / 名称与"接口契约"§ 7.3 描述不符,**停手抛冲突给 PM**
- [ ] **追加 `pydantic-settings==2.6.1` 到 `requirements.txt`**(单行追加,不动现有内容)
- [ ] **建 `app/config.py`**(详见"接口契约"§ 7.1 完整代码):
  - [ ] `from pydantic_settings import BaseSettings, SettingsConfigDict`(注意 pydantic-settings 2.x 用 `model_config = SettingsConfigDict(...)` 而非旧 `class Config`)
  - [ ] 定义 `AppSettings(BaseSettings)`,17 个字段,**严格对齐 § 7.1**
  - [ ] **必填字段**(无默认值):`deepseek_api_key: str`
  - [ ] **其他字段全部带默认值**,默认值与 § 7.1 完全一致
  - [ ] `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`
  - [ ] 类 docstring(简短一句话)
  - [ ] **不**实例化全局单例,**不**导出 `settings = AppSettings()`(那是 `app/container.py` 或调用方的事)
- [ ] **扩展 `.env.example`**:在现有字段之后追加缺失字段,确保 17 项全到位(详见"接口契约"§ 7.3)
- [ ] **更新 `app/README.md`**:列出 `app/config.py` 的职责 + 1-2 行用法示例(`from app.config import AppSettings; cfg = AppSettings()`)
- [ ] **建测试**(`tests/app/__init__.py` + `tests/app/test_config.py`):
  - [ ] `test_default_values`:用 `monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")` 后 `AppSettings()`,断言所有非必填字段的默认值正确
  - [ ] `test_env_override`:`monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "100")`,断言 `AppSettings().max_upload_size_mb == 100`(且类型是 int,验证 pydantic-settings 自动类型转换)
  - [ ] `test_missing_required_raises`:不设 `DEEPSEEK_API_KEY` 环境变量,`AppSettings()` 应抛 `pydantic.ValidationError`
  - [ ] `test_invalid_type_raises`:`monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "not-a-number")`,应抛 `ValidationError`
  - [ ] **测试用 `monkeypatch.delenv(..., raising=False)`** 清理可能污染的环境变量(尤其 `DEEPSEEK_API_KEY` 如果 PM 本地设了)
  - [ ] **不读真实 `.env` 文件**,所有测试用 monkeypatch + 临时变量;测试隔离
- [ ] **本地全检通过**:`make check` 全绿(lint / type-check / pytest / hygiene)
- [ ] **改 `docs/03_TASK_INDEX.md`**:
  - 把 TASK-108 状态从 🔲 改为 🔍
  - Week 1 进度条第 8 位 ⬜ 改为 🔍
  - **必须用字节级 Python 操作**(`read_bytes` + `bytes.replace` + `write_bytes`),详见"风险与注意点"风险 1
- [ ] **本 Task 最后一个 commit**:`docs: mark TASK-108 as in-review in task index`
- [ ] **完工报告必须含 git 三件套**(决策 08):`git status`(working tree clean)/ `git log --oneline main..HEAD`(完整 commit 列表)/ `git push`(推送成功输出)
- [ ] **提 PR**(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)

---

## 不做(明确排除)

- ❌ **不**实施任何业务逻辑(沙箱 / 解析 / LLM / 存储)
- ❌ **不**写 `app/logger.py` / `app/container.py`(02 § 3 目录结构提到,但本 Task 不实施,留给后续 chore 或 TASK-201)
- ❌ **不**在 `app/config.py` 实例化全局 `settings`(那是依赖注入容器的事,不属于本 Task)
- ❌ **不**用 `dotenv` / `python-dotenv` 等替代库(`pydantic-settings` 内置 `.env` 加载)
- ❌ **不**修改 TASK-101 已建的 `core/domain/` 数据结构(尤其不要试图把 `FileInfo.file_type` 改成 enum)
- ❌ **不**实施 `features/` / `adapters/` / `api/` 层的任何代码
- ❌ **不**调用 LLM / 加密码 / 加 secret manager 等高级特性(MCS 阶段简单 `.env` 够用)
- ❌ **不引入除 pydantic-settings 外的任何依赖**(pydantic 是 transitively 传递,**不要**显式加进 requirements.txt)
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md` 的 TASK-108 状态行 + Week 1 进度条第 8 位)

---

## 接口契约

### 7.1 `app/config.py` 完整代码

```python
"""项目全局配置(pydantic-settings 加载自 .env 或环境变量)。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """项目全局配置。下游通过 ``from app.config import AppSettings`` 消费。

    所有字段从环境变量或 .env 文件加载。字段名小写,环境变量名大写
    (例如 ``max_upload_size_mb`` 对应 ``MAX_UPLOAD_SIZE_MB``)。
    """

    # LLM
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"

    # Storage
    db_path: str = "./data/mxa.db"
    upload_dir: str = "./data/uploads"
    upload_ttl_hours: int = 24

    # Quota
    free_question_per_project: int = 3
    single_pack_quota: int = 100
    monthly_quota: int = 300

    # File limits(基础)
    max_upload_size_mb: int = 50
    max_files_per_project: int = 200
    max_single_file_mb: int = 20
    max_compression_ratio: int = 100

    # File limits(TASK-104 扩展)
    max_extraction_seconds: int = 30
    max_total_uncompressed_mb: int = 200
    max_entries_per_project: int = 200

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

**字段总数 17**(1 必填 + 16 带默认)。

**字段顺序约束**:对齐 02 § 7 配置块顺序 + task-104 扩展段在 File limits 末尾。**不要**按字母序重排;**不要**把 quota 类放到 LLM 段。

**默认值约束**:所有默认值与本契约 100% 一致。**不要**改任何默认值。若 Codex 强烈认为某默认值需要调整(例如 `max_total_uncompressed_mb=200` 太小),**停手问 PM**,不要默默改。

### 7.2 测试要点(`tests/app/test_config.py`)

```python
import pytest
from pydantic import ValidationError

from app.config import AppSettings


def _clean_env(monkeypatch):
    """清理可能污染的环境变量。"""
    keys = [
        "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL",
        "DB_PATH", "UPLOAD_DIR", "UPLOAD_TTL_HOURS",
        "FREE_QUESTION_PER_PROJECT", "SINGLE_PACK_QUOTA", "MONTHLY_QUOTA",
        "MAX_UPLOAD_SIZE_MB", "MAX_FILES_PER_PROJECT", "MAX_SINGLE_FILE_MB",
        "MAX_COMPRESSION_RATIO", "MAX_EXTRACTION_SECONDS",
        "MAX_TOTAL_UNCOMPRESSED_MB", "MAX_ENTRIES_PER_PROJECT",
        "LOG_LEVEL",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def test_default_values(monkeypatch, tmp_path):
    """默认值与契约一致。"""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.chdir(tmp_path)  # 避免读 PM 本地真实 .env

    cfg = AppSettings()
    assert cfg.deepseek_api_key == "sk-test"
    assert cfg.deepseek_base_url == "https://api.deepseek.com"
    assert cfg.max_upload_size_mb == 50
    assert cfg.max_files_per_project == 200
    assert cfg.max_single_file_mb == 20
    assert cfg.max_compression_ratio == 100
    assert cfg.max_extraction_seconds == 30
    assert cfg.max_total_uncompressed_mb == 200
    assert cfg.max_entries_per_project == 200
    assert cfg.upload_ttl_hours == 24
    assert cfg.log_level == "INFO"
    # ... 其他字段


def test_env_override_and_type_conversion(monkeypatch, tmp_path):
    """环境变量覆盖 + 字符串自动转 int。"""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "100")  # 字符串
    monkeypatch.chdir(tmp_path)

    cfg = AppSettings()
    assert cfg.max_upload_size_mb == 100
    assert isinstance(cfg.max_upload_size_mb, int)  # 验证 pydantic-settings 自动转换


def test_missing_required_raises(monkeypatch, tmp_path):
    """缺 DEEPSEEK_API_KEY 抛 ValidationError。"""
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()


def test_invalid_type_raises(monkeypatch, tmp_path):
    """字符串无法转 int 抛 ValidationError。"""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "not-a-number")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        AppSettings()
```

**测试隔离关键**:`monkeypatch.chdir(tmp_path)` 切到临时目录,避免 pydantic-settings 读 PM 本地真实 `.env` 文件污染测试。

### 7.3 `.env.example` 完整字段对齐

Codex 实施时先 `cat .env.example` 看当前内容,然后**追加缺失字段**。完整目标(对齐 04 § 7 模板 + task-104 扩展):

```bash
# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Database
DB_PATH=./data/mxa.db

# Storage
UPLOAD_DIR=./data/uploads
UPLOAD_TTL_HOURS=24

# Limits(基础)
MAX_UPLOAD_SIZE_MB=50
MAX_SINGLE_FILE_MB=20
MAX_FILES_PER_PROJECT=200
MAX_COMPRESSION_RATIO=100
FREE_QUESTION_PER_PROJECT=3
SINGLE_PACK_QUOTA=100
MONTHLY_QUOTA=300

# Limits(TASK-104 扩展)
MAX_EXTRACTION_SECONDS=30
MAX_TOTAL_UNCOMPRESSED_MB=200
MAX_ENTRIES_PER_PROJECT=200

# Logging
LOG_LEVEL=INFO
```

**追加策略**:不删现有字段,不改现有字段顺序,只在末尾或对应分组段末追加缺失项。若 Codex 看到现有 `.env.example` 与上面格式有显著差异(例如分组注释不同),**保留现有风格** + 追加缺失项即可,**不要**重写整个文件(否则 git diff 会变成全文红绿,违反决策 08 字节级精神,虽然 `.env.example` 不是 CRLF 文件但保守起见也按"最小改动"原则)。

### 7.4 错误处理

`AppSettings()` 实例化失败的两种场景:

- 缺必填字段 `deepseek_api_key` → `pydantic.ValidationError`,字段路径 `deepseek_api_key`,消息含"Field required"
- 类型转换失败(如 `MAX_UPLOAD_SIZE_MB=abc`)→ `pydantic.ValidationError`,字段路径 `max_upload_size_mb`,消息含"Input should be a valid integer"

下游调用方(TASK-104 等)**不应**try/except `ValidationError`,因为这是程序启动期错误(.env 配置不全等于部署事故),应让进程直接崩溃,运维通过 stderr 看到错误信息修复 `.env`。

---

## 验收标准

> **以下每条都给出 PM 可在 Git Bash 跑出来的命令**。
> 命令在仓库根目录(`F:\mxa-tutor`)下执行,且已 `source .venv/Scripts/activate`。

### 1. 文件全部创建

```bash
ls app/config.py tests/app/__init__.py tests/app/test_config.py
```

期望:3 个文件全部存在,无 "No such file" 报错。

### 2. `requirements.txt` 已扩展

```bash
grep -n "pydantic-settings" requirements.txt
```

期望:看到 `pydantic-settings==2.6.1`(版本号精确)。

### 3. `.env.example` 覆盖 17 字段

```bash
grep -cE "^(DEEPSEEK_API_KEY|DEEPSEEK_BASE_URL|DB_PATH|UPLOAD_DIR|UPLOAD_TTL_HOURS|FREE_QUESTION_PER_PROJECT|SINGLE_PACK_QUOTA|MONTHLY_QUOTA|MAX_UPLOAD_SIZE_MB|MAX_FILES_PER_PROJECT|MAX_SINGLE_FILE_MB|MAX_COMPRESSION_RATIO|MAX_EXTRACTION_SECONDS|MAX_TOTAL_UNCOMPRESSED_MB|MAX_ENTRIES_PER_PROJECT|LOG_LEVEL)=" .env.example
```

期望:输出 `16`(因为 `=` 后跟值,grep 计数 16 个匹配行 —— 注意 DEEPSEEK_API_KEY 后跟 `sk-xxx` 占位,所以也匹配)。

### 4. `app/config.py` 字段总数正确

```bash
grep -cE "^\s+[a-z_]+:" app/config.py
```

期望:输出 `17`(17 个字段声明)。

### 5. 不引入除 pydantic-settings 外的依赖

```bash
git fetch origin main
git diff origin/main..HEAD -- requirements.txt
```

期望:只看到 `+pydantic-settings==2.6.1` 一行(可能 +空行),无其他新增 / 删除。

### 6. 不修改 TASK-001-103 已建文件

```bash
git diff origin/main..HEAD --stat -- \
    core/ adapters/ features/ api/ web/ \
    pyproject.toml Makefile .github/ scripts/ \
    tests/core tests/adapters tests/fixtures
```

期望:无输出(本 Task 严格只动 `app/` + `tests/app/` + `requirements.txt` + `.env.example` + `app/README.md` + `docs/03_TASK_INDEX.md`)。

### 7. 单元测试全绿

```bash
pytest tests/app/ -v
```

期望:4 个测试通过,运行 < 1 秒。

### 8. lint 和 type-check 全绿

```bash
make lint        # ruff check
make type-check  # mypy core/ adapters/ features/
```

注意:本 Task **不**在 mypy 范围(`app/` 默认不在 04 § 13 节 Makefile 的 mypy target 列表)。这是有意的(配置层很简单,mypy strict 在 BaseSettings 子类上会噪音)。若 Codex 强烈认为应该把 `app/` 加进 mypy target,**停手问 PM**,不要自己改 Makefile。

### 9. 每文件 ≤ 300 行

```bash
wc -l app/config.py tests/app/test_config.py
```

期望:`app/config.py` ≤ 90 行;`test_config.py` ≤ 100 行。

### 10. README 已更新

```bash
cat app/README.md
```

期望:看到 `app/config.py` 的职责说明 + 1-2 行用法示例。

### 11. TASK_INDEX 状态已更新

```bash
grep -n "TASK-108" docs/03_TASK_INDEX.md
```

期望:看到 TASK-108 那一行状态变成 🔍,Week 1 进度条第 8 位变成 🔍。改动用字节级 Python 操作(详见风险 1),`git diff docs/03_TASK_INDEX.md` 应只显示 4 行左右改动。

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md` 第 1 条,本 Task **只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件**,不动其他任何 docs 核心文档或决策日志或 task 文档。

### 12. 一键全检

```bash
make check
```

应输出 "All checks passed!"。

### 13. PR 元信息

- PR 标题:`TASK-108: app/config.py + pydantic-settings 配置层(基建桥接)`
- 分支名:`task/TASK-108-bootstrap-app-config-layer`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-12 项**并简述每项做了什么,**且必须在"变更摘要"明示**:本 Task 引入项目**第一个 runtime 依赖** `pydantic-settings==2.6.1`,transitively 引入 `pydantic` 2.x

### 14. 完工报告含 git 三件套(决策 08)

完工时必须给 PM:

- 修改的文件清单
- 本地 `make check` 完整输出
- **`git status`(显示 working tree clean)**
- **`git log --oneline main..HEAD`(显示本 Task 完整 commit 列表,非空)**
- **`git push` 完整输出**
- 验收清单 1-13 项逐条勾选 + 说明
- PR 标题 + PR 正文

**不附三件套 = 没完工**,PM 退回让 Codex 补。

---

## 风险与注意点

### 风险 1:改 `docs/03_TASK_INDEX.md` 必须按决策 08 字节级操作

**这是本 Task 收尾时唯一容易踩的坑**。

`docs/03_TASK_INDEX.md` 在仓库里是 CRLF 行尾(Windows 默认)。**禁用**:

- ❌ `pathlib.Path.read_text() + write_text()`
- ❌ `open(path, 'w').write(...)`(默认文本模式,会规范化行尾)
- ❌ `sed -i`(Git Bash 下对中文 + emoji 处理不稳定)

**只允许**方式 A(编辑器手改)或方式 B(Python 字节级):

```python
import pathlib

p = pathlib.Path('docs/03_TASK_INDEX.md')
data = p.read_bytes()

# TASK-108 状态行(由 PM 在 docs PR 时新加入,初始 🔲):
old_status = '| TASK-108 | app/config.py + pydantic-settings 配置层(基建桥接) | 🔲 | Codex | 无 |'.encode('utf-8')
new_status = '| TASK-108 | app/config.py + pydantic-settings 配置层(基建桥接) | 🔍 | Codex | 无 |'.encode('utf-8')
assert old_status in data, 'TASK-108 状态行未找到(检查 PM 是否已在 docs PR 内加 TASK-108 行)'
data = data.replace(old_status, new_status)

# Week 1 进度条第 8 位(初始 🔲 → 🔍):
old_bar = 'Week 1:  [✅✅✅⬜⬜⬜⬜⬜]           3/8'.encode('utf-8')
new_bar = 'Week 1:  [✅✅✅⬜⬜⬜⬜🔍]           3/8'.encode('utf-8')
assert old_bar in data, 'Week 1 进度条未找到(检查 PM 在 docs PR 时是否已经把 3/7 改成 3/8 + 第 8 位 ⬜)'
data = data.replace(old_bar, new_bar)

p.write_bytes(data)
```

**改完后立即 `git diff docs/03_TASK_INDEX.md` 验证**。若 diff 显示几百行红绿,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销,换方式 A 用编辑器手改**。

**注意**:进度条第 8 位 ⬜ → 🔍 是 Codex 的事;TASK-108 表格行本身(包含状态 🔲)是 PM 在 docs PR 时**预先加入**的。若 Codex 看到 `docs/03_TASK_INDEX.md` 里没有 TASK-108 行,说明 PM 还没走 docs PR 把 TASK-108 索引化 —— **停手问 PM**,不要自己加行。

### 风险 2:pydantic-settings 2.x API 与 1.x 完全不同

pydantic-settings 2.x(对齐 pydantic 2.x)的写法:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    foo: str = "default"
    model_config = SettingsConfigDict(env_file=".env")
```

**不是**旧的 1.x 写法:

```python
# ❌ 错误(pydantic-settings 1.x / pydantic 1.x):
class AppSettings(BaseSettings):
    foo: str = "default"

    class Config:
        env_file = ".env"
```

Codex 如果搜到的网络教程是旧写法,**必须**改为 2.x。版本号 `pydantic-settings==2.6.1` 已经锁定,API 差异由本契约 § 7.1 代码骨架直接展示,**直接抄即可**。

### 风险 3:`monkeypatch.chdir(tmp_path)` 防 .env 污染

PM 本地若已有 `.env`(实际开发会有),`AppSettings()` 默认会读它,污染测试断言。所有测试**必须** `monkeypatch.chdir(tmp_path)`,把 cwd 切到临时目录,确保 pydantic-settings 找不到 `.env` 文件,所有值来自显式 `monkeypatch.setenv`。

### 风险 4:Codex 不要"优化"AppSettings 默认值

§ 7.1 代码骨架是架构师 + PM 严格对齐 02 § 7 + task-104 v1.0 的版本。Codex 实施时:

- ❌ **不**要改任何默认值(尤其 `max_total_uncompressed_mb=200` 是 task-104 v1.0 锁定)
- ❌ **不**要把可选字段改成必填
- ❌ **不**要新增 02 § 7 没列的字段(例如 redis_url / mysql_url 等都不要加)
- ❌ **不**要把字段类型从 int 改成 float / str
- ❌ **不**要导出 `settings = AppSettings()` 全局单例

**强烈认为某处应改,停手问 PM**。

### 风险 5:Codex 看见冲突就停手

本 Task 文档与 `docs/01/02/04` / 决策日志 / 03 索引 / task-104 文档 的任何冲突,**停手问 PM**,不要默默偏离。

常见可能冲突场景:

- 发现 `app/__init__.py` 已有内容(不是空文件)→ **不要**清空,告诉 PM 实际内容
- 发现 `requirements.txt` 已有其他依赖(本 Task 假设是空的)→ **不要**清空或动现有内容,只追加
- 发现 `.env.example` 字段名 / 顺序与 § 7.3 描述显著不符 → **告诉 PM**,不要默默重写
- 发现 03 索引里 TASK-108 行不存在(PM 还没走 docs PR)→ **停手问 PM**,不要自己加行

### 风险 6:静态扫描误报

任何 `grep` / `find` 检查必须按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。本 Task 验收清单已按规则给出命令,直接用。

---

## 估时

预估 **1.5-2.5 小时**(显著短于其他 Task,纯基建):

- 阅读本 Task 文档 + 04 § 6/7:0.5 小时
- 加依赖 + 建 `app/config.py`(直接抄 § 7.1):0.3 小时
- 改 `.env.example`(对齐 § 7.3 追加缺失字段):0.2 小时
- 写测试(4 个 test_*):0.5 小时
- 更新 `app/README.md`:0.1 小时
- 本地 `make check` + commit 拆分:0.3 小时
- 改 03 索引 + 三件套 + PR 描述:0.2 小时

---

## 给 Codex 的提示

### 1. 推荐实现顺序

按依赖关系:

1. 切分支 `task/TASK-108-bootstrap-app-config-layer`
2. `cat app/__init__.py app/README.md requirements.txt .env.example` 看现状
3. 追加 `pydantic-settings==2.6.1` 到 `requirements.txt`
4. `pip install -r requirements.txt` 把 pydantic-settings 装上(本地验证)
5. 写 `app/config.py`(直接抄 § 7.1)
6. 写 `tests/app/__init__.py`(空文件)+ `tests/app/test_config.py`(参考 § 7.2)
7. `pytest tests/app/ -v` 跑过
8. 更新 `.env.example`(追加缺失字段对齐 § 7.3)
9. 更新 `app/README.md`(1-2 行说明)
10. `make check` 全检
11. 改 03 索引(决策 08 字节级)
12. commit 拆分 + push + 三件套 + 提 PR

### 2. Commit 拆分建议(Conventional Commits)

```
chore(deps): add pydantic-settings 2.6.1 (project first runtime dep)
feat(app): add AppSettings configuration class
test(app): add AppSettings unit tests
docs(env): extend .env.example with all 16 settings fields
docs(app): update app/README.md with config usage
docs: mark TASK-108 as in-review in task index
```

不要单个超大 commit。

### 3. 改 `.env.example` 必须按决策 08

`.env.example` 虽然不是 CRLF 文件(Bash 脚本通常 LF),但保守起见也按"最小改动"原则:**只追加缺失字段**,不重写整个文件。验证:`git diff .env.example` 应只显示 `+` 行,基本无 `-` 行(除了可能改一两个分组注释)。

### 4. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见风险 1 的脚本骨架。改完后 `git diff docs/03_TASK_INDEX.md` 确认只显示 4 行左右改动。**若 diff 显示几百行变化,立即 `git checkout --` 撤销,换方式 A 用编辑器手改**。

### 5. 完工报告必须含 git 三件套(决策 08)

完工时给 PM:

- 修改的文件清单
- 本地 `make check` 输出
- **`git status` / `git log --oneline main..HEAD` / `git push` 三条命令的完整输出**
- 验收清单 1-13 项逐条勾选 + 说明
- PR 标题:`TASK-108: app/config.py + pydantic-settings 配置层(基建桥接)`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板;**变更摘要必须明示**"项目第一个 runtime 依赖")

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 6. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:

- PR 标题:`TASK-108: app/config.py + pydantic-settings 配置层(基建桥接)`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

PM 在 GitHub 网页手动创建 PR。CI 自动触发,绿了之后 PM 把 Codex 产出 + CI 结果交给架构师 review。

### 7. 遇冲突就停手

本 Task 文档与 `docs/01/02/04` / 决策日志 / 03 索引 / task-104 文档 / TASK-001-103 已建产物 的任何冲突,**停手问 PM**,不要默默偏离。

详见风险 5 的常见冲突场景。

---

**版本**:Task 文档 v1.0
**作者**:Claude(架构师,第六任)
**日期**:2026-06-02
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md`
**关联 Task**:依赖 TASK-001 / TASK-002(基础工具链);下游 TASK-104(直接消费者)/ TASK-201 / 202 / 204 / 304 / 405(未来消费者)
**触发原因**:TASK-104 派活时 Codex 实地核查发现 `app/config.py` 不存在,按决策 08 纪律抛冲突;PM + 架构师协商后拍板走方案 B 单独基建桥接 Task
