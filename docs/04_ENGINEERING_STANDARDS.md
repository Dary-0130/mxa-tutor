# 工程规范 · ENGINEERING STANDARDS

> **本文是工程层面的硬性规范**,补充 `01_PROJECT_CONSTITUTION.md` 中的概述。
> **Codex / Cursor 在写任何代码前,必须先读本文**。
> 与本文冲突的产出,一律打回返工。
> **版本:v2.1(冻结)**

---

## 1. Git 仓库与分支

### 仓库
- **名称**:`mxa-tutor`(GitHub Private)
- **默认分支**:`main`(永远保持可运行、可部署)
- **保护规则**:
  - 不允许直接 push 到 `main`
  - 所有合并必须通过 PR + review
  - PR 必须 CI 全绿才能合并

### 分支命名
```
task/TASK-NNN-<slug>     ← 每个 Task 一个分支
fix/<issue-slug>          ← bug 修复
docs/<doc-slug>           ← 纯文档更新
chore/<purpose>           ← 杂项(依赖升级、配置等)
```

### 分支生命周期
1. 从 `main` 切出新分支
2. 开发 + 测试
3. 提 PR → review → 合并
4. **合并后立即删除分支**

### Git 工作流实操纪律(反例归档)

**硬规则**(架构师起任何 git 操作前):

1. 必须 `git log --oneline -10` 实测前任 commit history,确认工作流模式(PR # 编号 / squash merge / commit message 格式),**不许凭"通用直觉"假设**
2. 任何 push 到 `main` 的尝试都应被 branch protection 拒推;若意外在 `main` 本地有 commit,立刻 `git reset --hard origin/main` + 重开 feature branch
3. 架构师写派单 prompt 时,必须在前置约束段明示"分支:从 `<base-commit>` 开 `task/TASK-NNN-<slug>`;禁在 main 操作"

**反例归档**(2026-06-14 / 第 38 任):后端架构师从 TASK-310 立项起全程在 main 直接 file 操作 + commit,push 被 GitHub branch protection 拒推时,凭印象写出"本项目 = single-developer 直推 main"反例自抓。PM 实测 `git log` 立即识破:前任所有 commit 都带 PR 号(#88 / #87 / ...),工作流是 feature branch + PR + squash merge。

**预防协议**:决策 12 v0.4 KPI 14 自查清单加 v0.5 候选第 4 项(架构师起任何 git 操作前必须 `git log --oneline -10` 实测前任工作流;待下任正式起 v0.5 task 立项)。

---

## 2. Commit 规范(Conventional Commits)

### 格式

```
<type>(<scope>): <subject>

<body>(可选)

<footer>(可选,关联 issue / task)
```

### Type 取值

| Type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | bug 修复 |
| `docs` | 文档变更 |
| `test` | 测试相关 |
| `refactor` | 重构(不改变外部行为) |
| `chore` | 构建 / 工具链 / 依赖 |
| `style` | 代码格式(不影响行为) |
| `perf` | 性能优化 |

### 例

```
feat(slx): add block diagram XML parser

实现 .slx 文件解压 + blockdiagram.xml 解析,提取 blocks 和 lines。
支持嵌套 subsystem 递归遍历。

Refs: TASK-102
```

### 禁止
- ❌ `update`、`fix bug`、`修改`、`wip` 这种没信息的 commit
- ❌ 一个 commit 包含多个无关改动
- ❌ commit 信息为英文之外的语言(中文项目名等专有名词除外)

---

## 3. PR 规范

### PR 标题格式

```
TASK-NNN: <Task 标题简述>
```

### PR 描述模板

```markdown
## 关联 Task
TASK-NNN

## 变更摘要
(3-5 句话讲清楚做了什么)

## 主要变更文件
- `path/to/file1.py`:...
- `tests/...`:新增 N 个测试用例

## 验收清单
(从 Task 文档复制验收清单,逐条勾选并说明)

- [x] 验收项 1:做了 XXX,跑了 YYY,见测试 ZZZ
- [ ] 验收项 2:**未完成,原因:...**

## 测试结果

```bash
$ pytest tests/...
============= N passed in X.XXs =============
```

## 风险与注意

(如有破坏性变更、性能风险、未覆盖的边界情况)
```

### 合并规则

1. **CI 必须全绿**(测试 + lint + 类型检查)
2. **Claude 必须 review 通过**
3. **没合并就别开新 Task**(一次一个,串行)

---

## 4. 代码风格

### 语言:Python 3.11

### 强制工具
- **格式化**:`ruff format`
- **lint**:`ruff check`
- **类型检查**:`mypy`(strict mode 渐进式启用)
- **导入排序**:`ruff` 自带

### 配置文件:`pyproject.toml`

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = false
warn_unused_ignores = true
disallow_untyped_defs = false
```

### 命名规范

| 类型 | 规范 | 例 |
|------|------|---|
| 文件名 | `snake_case` | `slx_parser.py` |
| 类名 | `PascalCase` | `SlxParser` |
| 函数 / 方法 | `snake_case` | `parse_blocks()` |
| 变量 | `snake_case` | `block_count` |
| 常量 | `UPPER_SNAKE` | `MAX_FILE_SIZE` |
| 私有 | 前缀 `_` | `_internal_method` |
| 接口类 | 以角色结尾 | `TextProvider`, `SlxParser`, `Builder` |

### 类型注解

- **公开函数 / 方法必须有类型注解**
- **dataclass 字段必须有类型**
- **私有函数推荐**

### 文档字符串

- **每个公开类、函数必须有 docstring**
- **使用 Google 风格**

### 行长 / 缩进
- **每行 ≤ 100 字符**
- **缩进 4 空格,不用 Tab**
- **每文件 ≤ 300 行**(超过强制拆分)

### 禁止
- ❌ `print()` 调试(用 `loguru`)
- ❌ 裸 `except:`(必须指定异常类型)
- ❌ 全局可变状态
- ❌ 循环 import(按分层依赖)
- ❌ `from x import *`
- ❌ 中文变量名 / 函数名

---

## 5. 测试规范

### 框架:pytest

### 目录组织

```
tests/
├── core/                 # core 层单元测试
├── adapters/             # adapter 层(LLM 必须 mock)
├── features/             # feature 层(完整业务测试)
├── api/                  # API 集成测试
├── fixtures/             # 测试数据
│   ├── slx_samples/      # 真实 .slx 文件
│   ├── m_samples/        # 真实 .m 文件
│   ├── projects/         # 完整工程
│   └── malicious_zips/   # 恶意 zip 测试(zip bomb / slip 等) ⭐
└── conftest.py           # 公共 fixture
```

### 测试文件命名
- 测试文件:`test_<被测模块>.py`
- 测试函数:`test_<被测行为>`,描述性命名

### Mock 规则

**所有外部依赖必须 mock**:

| 类型 | 做法 |
|------|------|
| LLM API 调用 | 用 `FakeProvider` 或 `pytest-mock` |
| 数据库 | 用内存 SQLite(`:memory:`) |
| 文件系统 | 用 `tmp_path` fixture |
| 网络 | 用 `responses` 库 mock |
| 时间 | 用 `freezegun` |

### 测试覆盖原则

**必须有测试的部分**:
- 核心解析逻辑(.slx / .m 解析)
- 业务 service 的关键分支
- 数据序列化 / 反序列化
- 错误处理路径
- **上传安全(zip bomb / zip slip / 白名单)** ⭐
- **证据引用强制(citations 缺失降级)** ⭐

**可以不测的部分**:
- 纯 UI 渲染逻辑
- 简单 getter/setter
- FastAPI 路由的胶水代码

### 测试性能
- **整个测试套件运行 < 30 秒**
- 慢测试(> 1s 的)标记 `@pytest.mark.slow`,CI 默认跳过

### 集成测试
- 真实调用 LLM 的测试标记 `@pytest.mark.integration`
- 默认跳过,本地手动跑(`pytest -m integration`)

---

## 6. 依赖管理

### 主依赖文件:`requirements.txt`

格式:**必须指定版本**

```
# requirements.txt
fastapi==0.115.4
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.6.1
openai==1.55.3
aiosqlite==0.20.0
loguru==0.7.2
sentence-transformers==3.3.0
scipy==1.14.1
```

### 开发依赖:`requirements-dev.txt`

```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
ruff==0.7.0
mypy==1.13.0
```

### 添加新依赖的流程

1. 在 PR 中说明:**为什么必须加这个依赖**
2. 评估替代方案
3. Claude review 批准
4. 加进 `requirements.txt`

**禁止**:Codex 自己 `pip install` 然后不写进文件。

---

## 7. 配置与密钥

### 配置文件
- **开发**:`.env`(`.gitignore` 中,不提交)
- **生产**:服务器环境变量
- **模板**:`.env.example`(提交到仓库,不含真实值)

### `.env.example` 模板

```bash
# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Database
DB_PATH=./data/mxa.db

# Storage
UPLOAD_DIR=./data/uploads
UPLOAD_TTL_HOURS=24

# Limits
MAX_UPLOAD_SIZE_MB=50
MAX_SINGLE_FILE_MB=20
MAX_FILES_PER_PROJECT=200
MAX_COMPRESSION_RATIO=100
FREE_QUESTION_PER_PROJECT=3
SINGLE_PACK_QUOTA=100
MONTHLY_QUOTA=300

# Logging
LOG_LEVEL=INFO
```

### 禁止行为

- ❌ API Key 写在代码里(任何位置)
- ❌ API Key 提交到 Git(检查 `.gitignore`)
- ❌ API Key 出现在测试 fixture
- ❌ API Key 暴露到前端
- ❌ API Key 出现在日志中

### Git 安全

`.gitignore` 必须包含:

```
.env
.env.local
.env.*.local
*.key
*.pem
data/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
node_modules/
dist/
build/
*.egg-info/
```

---

## 8. 上传安全与文件沙箱 ⭐ v2.1 新增

### 8.1 总原则

**绝对不执行用户上传的任何代码**。

具体:
- ❌ 不允许 `exec()` 用户上传的 .m 内容
- ❌ 不允许 `import` 用户上传的 .py(本项目用户不会传 .py,但兜底约束)
- ❌ 不允许调用 MATLAB 运行用户工程
- ❌ 不允许把用户文件路径作为可执行文件路径
- ✅ 只做**静态解析**(读 + 解析,不执行)

### 8.2 zip 解压安全

解压前必须检查:

```python
# adapters/parser/zip_extractor.py 必须实现以下检查

from pathlib import Path
import zipfile

def safe_extract(zip_bytes: bytes, dest_dir: Path, config: AppSettings) -> Path:
    """安全解压 zip。失败时抛 UploadError 子类。"""
    
    # 1. 总大小检查
    if len(zip_bytes) > config.max_upload_size_mb * 1024 * 1024:
        raise ProjectTooLargeError(...)
    
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # 2. 文件数量检查
        if len(zf.namelist()) > config.max_files_per_project:
            raise ProjectTooLargeError(...)
        
        # 3. 压缩比检查(防 zip bomb)
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        total_compressed = sum(info.compress_size for info in zf.infolist())
        if total_compressed > 0 and total_uncompressed / total_compressed > config.max_compression_ratio:
            raise ZipBombError("压缩比异常,疑似 zip bomb")
        
        # 4. 单文件大小检查
        for info in zf.infolist():
            if info.file_size > config.max_single_file_mb * 1024 * 1024:
                raise ZipBombError(f"单文件过大: {info.filename}")
        
        # 5. 路径穿越检查(防 zip slip)
        for name in zf.namelist():
            # 禁止绝对路径
            if Path(name).is_absolute() or name.startswith("/"):
                raise ZipSlipError(f"非法绝对路径: {name}")
            # 禁止 ../
            normalized = Path(name).resolve()
            if not str(normalized).startswith(str(dest_dir.resolve())):
                raise ZipSlipError(f"路径穿越: {name}")
            # Windows 反斜杠也要查
            if ".." in name or "\\" in name:
                raise ZipSlipError(f"非法路径片段: {name}")
        
        # 6. 扩展名白名单
        ALLOWED_EXTS = {".m", ".mlx", ".slx", ".mdl", ".mat", ".prj", 
                        ".txt", ".md", ".csv", ".json", ".xml"}
        for name in zf.namelist():
            if name.endswith("/"):  # 目录跳过
                continue
            ext = Path(name).suffix.lower()
            if ext not in ALLOWED_EXTS:
                raise FileTypeNotAllowedError(f"不支持的文件类型: {ext}")
        
        # 7. 实际解压到临时目录
        zf.extractall(dest_dir)
    
    return dest_dir
```

### 8.3 临时目录策略

- 每次上传 → 一个独立临时目录(UUID 命名)
- 解析完成 → 数据入库 → 临时目录删除
- 异常情况 → 也要清理(用 `try/finally` 或 `contextlib`)
- TTL 24 小时,**定时任务清理过期目录**(`scripts/cleanup_expired_uploads.py`)

### 8.4 失败隔离

- 单个文件解析失败 **不能让整个工程失败**
- 失败的文件标记为 `parse_warnings`,继续处理其他文件
- 在 ProjectGraph 里保留 `unresolved_symbols` 字段

### 8.5 测试要求

`tests/fixtures/malicious_zips/` 必须包含:

- `zip_bomb_small.zip`:高压缩比 zip
- `zip_slip_relative.zip`:含 `../` 路径
- `zip_slip_absolute.zip`:含绝对路径
- `oversized_file.zip`:含 50MB 单文件
- `too_many_files.zip`:含 300+ 文件
- `bad_extension.zip`:含 .exe / .py / .sh

每个都必须有对应的测试:**确认被正确拒绝**。

---

## 9. 日志规范

### 工具:loguru

### 配置(`app/logger.py`)

```python
from loguru import logger
import sys

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
    level="INFO",
)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
)
```

### 日志级别

| 级别 | 用途 |
|------|------|
| `DEBUG` | 调试细节,生产关闭 |
| `INFO` | 关键流程节点(请求开始、解析完成、LLM 调用) |
| `WARNING` | 异常但不致命(重试、降级、citation 缺失) |
| `ERROR` | 失败的请求 / 操作 |
| `CRITICAL` | 服务级故障(数据库挂、API 全失败) |

### 日志内容

**必须记录**:
- 请求路径 + 用户 ID + 耗时
- LLM 调用 + token 消耗 + 延迟
- 异常 + 堆栈
- **上传安全拦截事件**(zip bomb / zip slip / 非法扩展名) ⭐

**禁止记录**:
- 用户上传的工程内容(原文)
- 学生问题原文 + 回答原文
- API Key / 密码 / 任何敏感凭证
- 文件名中可能含敏感信息的部分(用 hash 替代)

例:

```python
# ✓ 推荐
logger.info(f"Project ingest started: user={user_id}, size={file_size}, hash={project_hash}")
logger.info(f"LLM call: model=deepseek-v4-flash, tokens_in=1200, tokens_out=350, latency_ms=2300")
logger.warning(f"Citation missing in chat response: user={user_id}, question_hash={q_hash}")

# ✗ 不接受
logger.info(f"User asked: {question}")  # 不记录原文
logger.debug(f"API key: {api_key}")     # 严重违规
logger.info(f"Filename: {filename}")    # 文件名可能含敏感信息
```

---

## 10. 异常处理

### 三层异常体系

```python
# core/domain/exceptions.py
class MxaError(Exception):
    """所有业务异常的基类"""
    pass

class LLMError(MxaError): pass
class ParseError(MxaError): pass
class ProjectError(MxaError): pass
class UploadError(MxaError): pass       # ⭐ v2.1 新增
class QuotaError(MxaError): pass
class EvidenceMissingError(MxaError): pass  # ⭐ v2.1 新增
```

### 异常翻译

- **adapter 层**:捕获原始 SDK 异常 → 翻译成业务异常
- **feature 层**:接收业务异常,可能加上业务上下文重新抛
- **api 层**:统一捕获 `MxaError` → 翻译成 HTTP 响应 + 中文消息

```python
# api/middleware/error_handler.py
# 实际形态（TASK-206 实施）是 tuple of (Exception, status, machine_code, message)，
# 由 register_error_handlers() 循环 app.add_exception_handler 注册。
# 此处仅列高频示例；完整 21 handler 表见 docs/tasks/task-206-error-handling-and-i18n.md。
error_handlers: tuple[tuple[type[Exception], int, str, str], ...] = (
    (ZipBombError, 400, "zip_bomb", "压缩文件异常，请检查后重新上传"),
    (ZipSlipError, 400, "zip_slip", "压缩包内含非法路径，请重新打包后上传"),
    (FileTypeNotAllowedError, 400, "file_type_not_allowed", "包含不支持的文件类型"),
    (ProjectTooLargeError, 413, "project_too_large", "工程过大，请压缩到 50MB 以内"),
    (LLMAuthError, 503, "llm_auth", "服务暂时不可用，请稍后重试"),
    (LLMRateLimitError, 429, "llm_rate_limit", "请求太频繁，稍等一下"),
    (LLMTimeoutError, 504, "llm_timeout", "网络较慢，正在重试..."),
    (SlxParseError, 400, "slx_parse", "Simulink 模型解析失败，可能版本过老或损坏"),
    (QuotaExhaustedError, 402, "quota_exhausted", "已达到合理使用上限，可联系加量"),
    # ... 共 21 条，详见 TASK-206 实施文档
)
```

---

## 11. 代码 Review 检查清单

Claude 在 review PR 时,**按这个清单逐条核对**:

### 工程合规
- [ ] PR 标题格式正确(`TASK-NNN: ...`)
- [ ] PR 描述完整(摘要、验收清单勾选、测试结果)
- [ ] CI 全绿(测试 + lint + 类型检查)
- [ ] Commit 信息符合 Conventional Commits

### 范围合规
- [ ] 改动严格在 Task 范围内,没有"顺便修了别的"
- [ ] 没有未经讨论的新依赖
- [ ] 没有违反架构分层(UI 不直接调 adapter 等)
- [ ] 没有违反"教学理解中间层"原则(LLM 不直接面对原始 parser 输出)

### 代码质量
- [ ] 命名清晰
- [ ] 公开 API 有类型注解 + docstring
- [ ] 没有 `print` / 裸 `except` / 全局可变状态
- [ ] 每文件 ≤ 300 行
- [ ] 没有 API Key / 敏感信息

### 安全合规 ⭐
- [ ] 上传相关代码符合第 8 章沙箱规范
- [ ] 没有执行用户上传代码的路径
- [ ] 涉及临时文件的有清理逻辑(try/finally)
- [ ] 日志不记录敏感内容

### 教学输出 ⭐
- [ ] 涉及讲解输出的符合 `05_EXPLANATION_STYLE_GUIDE.md`
- [ ] LLM 回答必须带 `citations`
- [ ] 无证据的回答降级为"不确定"

### 测试质量
- [ ] 核心逻辑有测试
- [ ] LLM / 外部依赖全部 mock
- [ ] 测试运行 < 30 秒
- [ ] 测试名字描述行为

### 文档质量
- [ ] 新增模块有 README
- [ ] 复杂逻辑有注释
- [ ] 关键决策记录到 `docs/decisions/`

---

## 12. CI 配置(`.github/workflows/ci.yml`)

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
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy core/ adapters/ features/
      - run: pytest -v --tb=short
```

---

## 13. 常用命令(`Makefile`)

```makefile
.PHONY: install dev test lint format type-check clean

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn api.main:app --reload --port 8000

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .

type-check:
	mypy core/ adapters/ features/

check: lint type-check test
	@echo "All checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
```

---

## 14. 给 Codex 的"快速对齐咒语"

PM 在给 Codex 派活时,**贴这段开头**:

```
我是 mxa-tutor 项目的 PM。开工前请按顺序确认以下事项:

1. 你已读过(v2.1 版本):
   - 01_PROJECT_CONSTITUTION.md
   - 02_ARCHITECTURE_OVERVIEW.md
   - 04_ENGINEERING_STANDARDS.md(本文)
   - 05_EXPLANATION_STYLE_GUIDE.md(涉及讲解输出时)

2. 你将严格遵守:
   - 一次只做一个 Task
   - 不擅自扩张范围
   - 写代码 + 写测试 + 写 README
   - LLM 调用必须 mock
   - 每文件 ≤ 300 行
   - 不擅自加依赖
   - Commit 用 Conventional Commits
   - PR 标题 "TASK-NNN: ..."
   - 不执行用户上传代码
   - LLM 回答必须带 citations,无证据降级为"不确定"

3. 完成后,你将提供:
   - 修改的文件清单
   - 测试运行的截图或日志
   - 对 Task 验收清单的逐条勾选 + 说明

4. 如果发现 Task 描述和宪法 / 架构 / 规范冲突,**停手问我**,不要硬干。

确认后,这是当前 Task:

[贴 TASK-NNN 文档]
```

---

**版本**:v2.1(冻结)
**最后更新**:2026-06-01
