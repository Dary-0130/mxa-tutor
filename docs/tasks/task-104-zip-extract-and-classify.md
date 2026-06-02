# TASK-104: 工程压缩包安全解压 + 文件分类(含沙箱)

## 状态

🔲 未开始

---

## 上下文

这是 Week 1 的第四个 Task,也是**项目第一个攻击面 P0 Task**。

`docs/01_PROJECT_CONSTITUTION.md` 第 5 节"何时找 AI 二审复审"明确列出的核心 Task 清单(`101 / 102 / 104 / 107 / 205 / 304`)中,TASK-104 在列。本 Task 文档已走 **GPT 二审 2 轮**(round-1 抓到 13 项必采 + 5 项部分采纳;round-2 把 Q1-Q7 全部细化到可直接抄入代码骨架),v1.0 是采纳后的收口版本。

宪法层面有 4 条硬约束直指本 Task:

- 宪法 § 8.1:**绝对不执行用户上传的任何代码**(只读 + 静态解析)
- 宪法 § 9 数据隐私:学生上传 24 小时后自动删除、日志不记录原文、不用于模型训练
- 04 § 8 整章上传安全与文件沙箱
- 02 § 4.6 业务异常体系(`UploadError` 子类已由 TASK-101 建好)

本 Task 实现两件事:

1. **`adapters/parser/zip_extractor.py`** — 安全解压用户上传的 zip 字节流到指定临时目录,过 7 道 metadata 闸 + 在 30 秒 deadline 内的手动分块解压 loop,失败抛 `UploadError` 子类或 `ProjectTooLargeError`
2. **`adapters/parser/file_classifier.py`** — 解压完成后,遍历目录按扩展名做**粗分类**(白名单 / 黑名单 / 灰名单三档),返回 `list[FileInfo]`,**不读文件内容**,**不调** `MParserImpl` / `SlxParserImpl`

下游依赖与边界:

- **TASK-105**(文件依赖关系分析):消费 `list[FileInfo]`,自己读 `.m` 内容
- **TASK-107**(ProjectGraph 构建器):消费 `MFile.file_role` 做 `.m` 细分类(`script` / `function` / `class`),**不**依赖 104
- **TASK-202**(上传 + 解析 API):把请求体字节流喂给 `safe_extract`,把 dest_dir 拼到 `./data/uploads/<uuid>/`;TASK-104 不实现 API 路由

**本 Task 是粗分类**:TASK-104 仅按扩展名归类(`FileInfo.file_type ∈ {".m", ".slx", ".mat", ".prj", "other", ...}`),**不**跨 Task 调用 `MParserImpl` 做 `.m` 文件细分类。这一点与 TASK-101 契约 `FileInfo.file_type: str` 一致(注释取值已经是字面扩展名),细分类延迟到 TASK-105 / TASK-107 消费 `MFile.file_role` 时做。

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架,已合并 commit `01413a7`)
- ✅ TASK-002(开发环境 + CI,已合并 commit `64d337d`):工具链已就绪
- ✅ **TASK-108(app/config.py + pydantic-settings 配置层基建桥接)**:本 Task 直接消费 `AppSettings`,**不再修改 `app/config.py` 字段**
- ✅ TASK-003(4 个真实 MATLAB demo 测试集,已合并 commit `6bbea80`,位于 `tests/fixtures/slx_samples/`):**辅助验收**(走"合法 zip 不被沙箱误拒"反衬测试,策略 B 白名单扩展后的语义)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并 commit `bf50aba`):**直接契约依赖**,本 Task 用 `FileInfo` / `UploadError` 系列异常 / `ProjectTooLargeError`
- ✅ TASK-102(.slx XML 解析器,已合并 commit `2317bb6`):间接依赖,本 Task 在 `tests/adapters/parser/conftest.py` 里**扩展**(不覆盖)TASK-102 已建的 fixture
- ✅ TASK-103(.m 文件解析器,已合并 commit `0714ff7`):间接依赖,**与本 Task 解耦**;TASK-104 不调用 `MParserImpl`(粗分类纪律)

### 必须存在的文件 / 状态

- `main` 分支处于 commit `9edef50` 或之后
- 以下文件由 TASK-108 建好,本 Task **直接 import 使用**(契约不变):
  - `app/config.py` — `AppSettings` 含 `max_extraction_seconds` / `max_total_uncompressed_mb` / `max_entries_per_project` 三个 TASK-104 需要的配置字段
- 以下 `core/` 文件由 TASK-101 建好,本 Task **直接 import 使用**(契约不变):
  - `core/domain/project.py` — `FileInfo` dataclass
  - `core/domain/exceptions.py` — `UploadError` / `ZipBombError` / `ZipSlipError` / `FileTypeNotAllowedError` / `ProjectTooLargeError` / `ProjectError` / `MxaError`
- 以下 TASK-102 / TASK-103 产出文件**已存在**,本 Task 不动:
  - `adapters/parser/slx_parser.py` 等 5 个 `.slx` 解析模块
  - `adapters/parser/m_parser.py` 等 4 个 `.m` 解析模块
  - `tests/adapters/parser/conftest.py`(本 Task **追加** `malicious_zip_dir` fixture,不重写)
  - `adapters/parser/__init__.py`(本 Task **追加**导出 `safe_extract` / `classify_files`)
- `main` 分支保护已开,所有改动走 PR + CI 全绿 + Squash

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,**特别第 5 节核心 Task 二审清单 / 第 8 节工程规则 / 第 8 节"禁止执行用户上传代码" / 第 9 节数据隐私**)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,**特别第 4.1 节 `FileInfo` 契约 / 第 4.6 节 `UploadError` 异常体系 / 第 7 节配置 / 第 9 节错误翻译表 / 第 11 节性能预算**)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,**特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范 / 第 8 节上传安全与文件沙箱(整章) / 第 10 节异常处理**)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(本 Task **不直接产出**讲解输出,但需理解下游使用场景)
- `docs/decisions/20260601-04-understanding-not-top-level-feature.md`(架构理解中间层归属)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(静态扫描规范)
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(Codex 能读仓库文件,Task 文档可使用路径引用)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(`docs/` 改动语义)
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(**Codex 完工报告必须含 git 三件套**;**改已有文件必须用编辑器或 Python 字节级操作**,禁用 `read_text` / `write_text` / `sed -i`)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(契约源,本 Task 严格依赖其定义的 `FileInfo` / `UploadError` 字段)
- `docs/tasks/task-102-slx-xml-parser.md`(实施风格参考,本 Task 在 `adapters/parser/` / `tests/adapters/parser/` 目录复用 TASK-102 / 103 已建的目录结构与 conftest 模式)
- `docs/tasks/task-103-m-parser.md`(实施风格参考)
- `tests/fixtures/slx_samples/README.md`(测试集清单,本 Task 反衬测试依据)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

`adapters/parser/` 下:

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `zip_extractor.py` | **主入口**,定义 `safe_extract(zip_bytes, dest_dir, config) -> Path`,7 道 metadata 闸 + 手动分块解压 loop + 30 秒 deadline | 200-280 |
| `file_classifier.py` | 定义 `classify_files(extracted_root, project_root) -> list[FileInfo]`,白/黑/灰三档分类,**不读**文件内容 | 80-150 |
| `_zip_paths.py` | 路径规范化与跨平台不安全名检测工具(POSIX + Windows ADS / UNC / reserved names / 尾随点空格 / drive letter) | 80-120 |
| `_zip_policy.py` | 共享扩展名策略 `classify_extension(ext) -> Literal["allow","deny","other"]`,内嵌白/黑名单 frozenset | 100-150 |

下划线前缀模块为 `zip_extractor.py` / `file_classifier.py` 的内部协作模块,**不暴露**到 `adapters/parser/__init__.py`(只导出 `safe_extract` / `classify_files`)。

`tests/adapters/parser/` 下(目录由 TASK-102 / 103 已建,本 Task 仅新增以下 4 个测试文件 + 扩展 conftest.py):

| 文件 | 职责 |
|------|------|
| `test_zip_extractor_unit.py` | 7 道闸单元测试,用内存构造的 `io.BytesIO` zip(每道闸正反 2 个测试) |
| `test_zip_extractor_real.py` | 4 个真实 zip 在沙箱下应通过(策略 B 验证:`.png/.svg/.ssc` 不再被误拒) |
| `test_zip_extractor_errors.py` | 7 个恶意 zip 风险族全部被正确拒绝 + Windows 不安全路径参数化变体 + 超时路径 |
| `test_file_classifier.py` | classifier 三档分类正确性(白/黑/灰) + classify_extension 共享函数单测 |

`tests/fixtures/malicious_zips/` 下(**新建目录**):

| 文件 | 职责 |
|------|------|
| `build_fixtures.py` | 构造脚本,运行时生成 7 个风险族 zip(详见"接口契约"小节 7.6) |
| `__init__.py` | 空文件 |
| `README.md` | 7 个 fixture 的精确构造目标矩阵 + 重新生成命令 |

### 修改文件

- **`adapters/parser/__init__.py`** — TASK-102 / 103 已建,本 Task **追加**两行:
  ```python
  from adapters.parser.zip_extractor import safe_extract
  from adapters.parser.file_classifier import classify_files
  ```
  并把 `__all__` 扩展为 `['SlxParserImpl', 'MParserImpl', 'safe_extract', 'classify_files']`
- **`adapters/parser/README.md`** — TASK-102 / 103 已建,本 Task **追加**一段说明新增的 4 个模块各自的一句话职责,以及 `safe_extract` + `classify_files` 的对外用法 2-3 行示例
- **`app/config.py`** — TASK-108 已建完整 `AppSettings`(含 `max_extraction_seconds=30` / `max_total_uncompressed_mb=200` / `max_entries_per_project=200` 三字段),**本 Task 不再修改**,只 `from app.config import AppSettings` 消费
- **`.env.example`** — TASK-002 已建,本 Task **新增 3 行**:
  ```
  MAX_EXTRACTION_SECONDS=30
  MAX_TOTAL_UNCOMPRESSED_MB=200
  MAX_ENTRIES_PER_PROJECT=200
  ```
- **`tests/adapters/parser/conftest.py`** — TASK-102 / 103 已建 `extracted_slx_projects` / `extracted_m_files` fixture,本 Task **追加** `malicious_zip_dir` fixture(session scope,首次跑 `build_fixtures.py` 在 `tmp_path_factory` 临时目录生成 7 个 fixture zip,返回 `dict[risk_family_name, Path]`)
- **`docs/03_TASK_INDEX.md`** — 把 TASK-104 行状态从 🔲 改为 🔍,Week 1 进度条 `[✅✅✅⬜⬜⬜⬜]` → `[✅✅✅🔍⬜⬜⬜]`(4/7 数字不变,Codex 推 🔍 后)。**必须用字节级 Python 操作(决策 08)**,详见"风险与注意点"风险 1

### 不动文件

- `core/domain/*.py` 和 `core/interfaces/*.py`(TASK-101 已建,**契约不许动**;尤其**不允许**新增 `FileType` enum 或修改 `FileInfo.file_type` 字段类型;如发现需要调整,**停手问 PM**,走宪法修订流程,不能在本 Task 顺带改)
- `adapters/parser/slx_parser.py` / `_slx_*.py`(TASK-102 已建,**与本 Task 解耦**,不允许修改)
- `adapters/parser/m_parser.py` / `_m_*.py`(TASK-103 已建,**与本 Task 解耦**,不允许修改;**且本 Task 不调用** `MParserImpl`)
- `requirements.txt` / `requirements-dev.txt`(本 Task **不引入任何新依赖**)
- `pyproject.toml` / `Makefile` / `.github/workflows/ci.yml` / `scripts/check_repo_hygiene.sh`(TASK-002 已配,本 Task 不调)
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(详见决策 07)
- `tests/fixtures/slx_samples/*.zip` 和 `tests/fixtures/slx_samples/README.md`(TASK-003 已建,**只读**)
- `tests/adapters/parser/test_slx_parser_*.py` 和 `test_m_parser_*.py`(TASK-102 / 103 已建,**与本 Task 解耦**,不允许修改)
- `core/prompts/` / `eval/` / `api/` / `features/` / `web/` 下任何文件
- 其他 Task 的代码与测试

### 新增依赖

**无**。本 Task 全部使用 Python 3.11 标准库:`zipfile` / `pathlib` / `io` / `os` / `time` / `stat` / `re` / `unicodedata` / `uuid` / `concurrent.futures` / `typing`。

### 新增配置项

3 个,见上方"修改文件 · `app/config.py`"。语义说明:

- `max_extraction_seconds`:整个 `safe_extract` 的 cooperative deadline,默认 30 秒(对齐 02 § 11"上传响应硬上限 30s")。Codex 实施完成跑 fixture 时若发现 50MB 真实 zip 接近 30 秒,允许**单独**走 chore PR 上调到 60 秒,**不**在 TASK-104 范围内预先调
- `max_total_uncompressed_mb`:总解压后大小硬上限,默认 200。防止 `200 文件 × 20MB = 4GB` 隐式攻击面。**v1.0 暂定 200**,Codex 实施完成跑 fixture 时若发现 200MB 上限对真实工程不够,允许**在 TASK-104 PR 内**顺手把默认调到合理值,并在"风险与注意点"补一笔(这是本 Task 内的自由度)
- `max_entries_per_project`:zip 内 entry 数硬上限(目录 + 文件都计数),默认 200。与 `max_files_per_project=200`(02 § 7 已定义)**同值不同语义**:前者防目录 entry 膨胀拖慢扫描,后者是业务文件数限制。两个都查

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-104-zip-extract-and-classify`
- [ ] **依赖结构理解**:实施前**第一件事**,unzip 4 个测试 zip 看实际内容结构(`unzip -l tests/fixtures/slx_samples/01_pmsm_foc_c2000.zip` 等),确认 `.png` / `.svg` / `.ssc` 这些扩展确实存在 —— 策略 B 白名单扩展的合理性在此**实地验证**,若实际看到的扩展名与本 Task 文档"接口契约"小节"7.4 扩展名分类策略"不符,**停手抛冲突给 PM**
- [ ] **`safe_extract` 主入口**(`adapters/parser/zip_extractor.py`):
  - [ ] 接受 `zip_bytes: bytes` + `dest_dir: Path` + `config: AppSettings`,返回 `Path`(最终解压根)
  - [ ] 失败时抛 `ProjectTooLargeError` / `ZipBombError` / `ZipSlipError` / `FileTypeNotAllowedError`,错误消息**中文**(详见"接口契约"小节 7.7)
  - [ ] 外层用**非 context-manager** `ThreadPoolExecutor` + `Future.result(timeout=N)` + `shutdown(wait=False, cancel_futures=True)`,严禁 `with ThreadPoolExecutor(...)` 写法(round-1 GPT 二审实锤事实 bug,详见风险 R02)
  - [ ] 内层 `_do_extract(zip_bytes, dest_dir, config, deadline)` 走 7 道 metadata 闸 + 手动分块解压 loop + chmod
  - [ ] **严禁** `zf.extractall()` 和 `zf.testzip()`(详见风险 R03 / R10)
- [ ] **7 道 metadata 闸**(详见"接口契约"小节 7.1,严格按顺序):
  - [ ] 闸 1:上传包外壳检查(字节长度 + dest_dir 元数据)
  - [ ] 闸 2:zip 容器结构检查(`ZipFile(BytesIO)` 可打开 + `infolist()`,**不**调 `testzip()`)
  - [ ] 闸 3:entry 数量检查(`max_entries_per_project` + `max_files_per_project` + 空 zip 拒)
  - [ ] 闸 4:entry 标志与类型检查(加密 / 压缩方法 / symlink / 非普通文件)
  - [ ] 闸 5:路径规范化检查(NFC + 反斜杠 + 绝对路径 + `..` + Windows 不安全名 + commonpath)
  - [ ] 闸 6:重名与碰撞检查(原始 / NFC / casefold 三层去重)
  - [ ] 闸 7:大小与扩展名策略检查(单文件 / 总解压 / 压缩比 / `classify_extension` 黑名单)
- [ ] **实际解压 loop**(7 道闸全过后,**在 deadline 框架内**):
  - [ ] 遍历 `infolist`,**每个 entry 用 `zf.open(info)` + 1MB chunk read + write 到 `target.open("xb")`**
  - [ ] 每读一个 chunk 后累计 `actual_file` / `actual_total`,超限立即抛 `ProjectTooLargeError` / `ZipBombError`
  - [ ] 每读一个 chunk 后查 `time.monotonic() > deadline`,超时抛 `ProjectTooLargeError`
  - [ ] 写完后比对 `actual_file == info.file_size`(metadata 与实际一致性 defense-in-depth,详见接口契约 7.2 注释 ②)
  - [ ] chmod:目录 `0o700`,文件 `0o600`(Windows 上 noop,详见 Q7 跨平台陷阱表 / 风险 R12 中的 Windows 行为)
  - [ ] 解压完成后再做一次 `os.walk(..., followlinks=False)` + `Path.is_symlink()` 复查(defense-in-depth,主防线是解压前 `external_attr` 闸 4)
- [ ] **`classify_files` 实现**(`adapters/parser/file_classifier.py`):
  - [ ] 接受 `extracted_root: Path` + `project_root: Path`,返回 `list[FileInfo]`
  - [ ] 遍历 `extracted_root`,**不递归 symlink**(walk 时 `followlinks=False`)
  - [ ] 对每个文件:
    - [ ] `relative_path` 用 POSIX 风格(强制 `/`,即使在 Windows 上)
    - [ ] `file_type`:走 `classify_extension(ext)`,allow → `ext`(带前导点小写),other → `"other"`,deny → 抛 `FileTypeNotAllowedError`(defense-in-depth,正常情况下不应到达)
    - [ ] `size_bytes` 用 `path.stat().st_size`
    - [ ] `description = None`
  - [ ] 跳过目录条目(`FileInfo` 只记文件)
- [ ] **共享扩展名策略**(`adapters/parser/_zip_policy.py`):
  - [ ] 实现 `ALLOW_EXTS` / `DENY_EXTS` 两个 `frozenset[str]`(完整清单见"接口契约"小节 7.4)
  - [ ] 实现 `classify_extension(ext: str) -> Literal["allow","deny","other"]`,调用方传**带前导点的小写**字符串,函数内不做规范化
  - [ ] **唯一权威清单**,extractor 闸 7 和 classifier 都调用此函数,**不允许两套清单**(round-2 已经把这条列为必采)
- [ ] **路径检测工具**(`adapters/parser/_zip_paths.py`):
  - [ ] 实现 `_is_windows_unsafe_name(name: str) -> tuple[bool, str]`(完整代码见"接口契约"小节 7.3),覆盖 drive letter / UNC / ADS / reserved names / 尾随点空格
  - [ ] 实现 `_normalize_zip_path(name: str) -> str`(NFC + 拒绝 NUL / 控制字符 / 反斜杠 / 绝对路径 / `..` / `.`)
  - [ ] 实现 `_compute_target_within_dest(name: str, dest_root: Path) -> Path`(用 `os.path.commonpath` 判断路径落在 `dest_root` 内,跨 drive `ValueError` → `ZipSlipError`)
- [ ] **dest_dir 契约加严**(在闸 1 内检查):
  - [ ] 必须已存在
  - [ ] 必须是目录,不能是文件
  - [ ] 必须**不是 symlink**(`Path.is_symlink()` 检查)
  - [ ] `dest_dir.resolve()` 必须在 `config.upload_dir` 的 `Path.resolve()` 子树内
  - [ ] **不强制要求是空目录**(测试用 pytest `tmp_path` 通常已经是空;生产环境由 TASK-202 用 UUID 路径保证)
- [ ] **失败隔离边界明示**:
  - [ ] 闸 1-7 任何一道失败 → 抛对应异常,**整工程拒绝**
  - [ ] `classify_files` 内**遇 deny 仍然抛**(defense-in-depth),**遇灰名单走 "other"**,**不抛**
  - [ ] 解压期间的临时目录**清理由调用方负责**(TASK-202 ingest service);本 Task `safe_extract` **不**做 `rmtree`(成功路径不清理,失败路径也不清理,只往外抛)
- [ ] **构造 7 个风险族 fixture**(`tests/fixtures/malicious_zips/build_fixtures.py`):
  - [ ] 7 族:`zip_bomb_ratio` / `zip_slip_paths` / `symlink_chain` / `duplicate_collision` / `forbidden_type` / `encrypted_or_bad_method` / `total_uncompressed_exceeds_cap`
  - [ ] 每族构造要点见"接口契约"小节 7.6
  - [ ] 脚本**可重复运行**(不依赖外部状态,UUID 命名靠 pytest tmp_path,fixture 文件名固定)
  - [ ] **fixture 7 不真实生成 200MB**,测试时通过局部 config 覆盖把 `max_total_uncompressed_mb=1` 触发即可
- [ ] **单元测试**(`test_zip_extractor_unit.py`):7 道闸每道闸正反 2 个测试(详见"验收标准")
- [ ] **真实工程反衬测试**(`test_zip_extractor_real.py`):**4 个真实 zip 在策略 B 下全部通过沙箱**,且 `classify_files` 输出 `list[FileInfo]` 含 `.png` / `.svg` / `.ssc` 等扩展(file_type 为对应扩展或 `"other"`)
- [ ] **恶意 zip 集成测试**(`test_zip_extractor_errors.py`):**7 个 fixture 各被对应异常拒绝**;Windows 不安全路径参数化覆盖 13+ 变体;超时路径单测(局部 config 把 `max_extraction_seconds=0.1` + 构造 hang 的解压)
- [ ] **classifier 测试**(`test_file_classifier.py`):
  - [ ] 在 `tmp_path` 手造 `.m` / `.exe` / `.gif` 三类文件,断言:`.m` → `file_type=".m"`;`.exe` → 抛 `FileTypeNotAllowedError`;`.gif` → `file_type="other"`(灰名单)
  - [ ] `classify_extension` 单测:每个边界值(空字符串、无点、大小写、白名单成员、黑名单成员、灰名单成员)
- [ ] **`adapters/parser/__init__.py` 扩展**:追加 `safe_extract` / `classify_files` 到 `__all__`
- [ ] **`adapters/parser/README.md` 更新**:追加 4 个新模块的一句话职责 + 用法示例
- [ ] **`tests/adapters/parser/conftest.py` 扩展**:追加 `malicious_zip_dir` session-scope fixture
- [ ] **`app/config.py` 扩展**:新增 3 个字段
- [ ] **`.env.example` 扩展**:新增 3 行
- [ ] **本地全检通过**:`make check` 全绿(lint / type-check / pytest / hygiene)
- [ ] **改 `docs/03_TASK_INDEX.md`**:
  - 把 TASK-104 状态从 🔲 改为 🔍,Week 1 进度条第 4 位 ⬜ 改为 🔍
  - **必须用字节级 Python 操作**(`read_bytes` + `bytes.replace` + `write_bytes`),详见"风险与注意点"风险 1
- [ ] **本 Task 最后一个 commit**:`docs: mark TASK-104 as in-review in task index`
- [ ] **完工报告必须含 git 三件套**(决策 08):`git status`(working tree clean)/ `git log --oneline main..HEAD`(完整 commit 列表)/ `git push`(推送成功输出)
- [ ] **提 PR**(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)

---

## 不做(明确排除)

### v0.1 范围明确不做(`docs/01_PROJECT_CONSTITUTION.md` 第 3 节)

- ❌ **运行 / 执行用户工程**(宪法 § 8.1 / 04 § 8.1 硬约束):本 Task 严格静态解压 + 按扩展名分类,**不**调 `subprocess` / `exec` / `eval` / MATLAB 等任何代码执行路径
- ❌ **递归解压嵌套 zip**:zip 内含 `.zip` 文件视为普通灰名单文件(`file_type="other"`),**不**展开
- ❌ **`.mat` 文件读取**:仅识别扩展名,**不**读 `.mat` 内容(Phase 2 范围)
- ❌ **`.prj` 文件解析**:仅识别扩展名,**不**读 `.prj` 内容(那是 TASK-202 / 203 范围,可能也推迟到 Phase 2)
- ❌ **`.slx` / `.m` 内容解析**:TASK-102 / 103 已建,本 Task **不**调用 `SlxParserImpl` / `MParserImpl`
- ❌ **跨文件依赖分析**:本 Task 一次只处理**单个** zip;跨文件依赖是 TASK-105 范围
- ❌ **项目类型识别**:不调 LLM,不调 `classify_project` prompt;那是 TASK-203 范围

### 工程范围排除

- ❌ **不实现 ProjectIngestService**(`features/ingest/service.py` 保持 TASK-001 占位现状,TASK-202 / 203 实现)
- ❌ **不实现 API 路由**(`api/routes/upload.py` 是 TASK-202)
- ❌ **不实现定时清理脚本** `scripts/cleanup_expired_uploads.py`(独立 chore 或 TASK-202 时做)
- ❌ **不实现 staging 目录**(`.extracting-<uuid>` 半成品隔离机制):round-2 GPT 建议有道理但属于 ingest service 层职责,推迟到 TASK-202;本 Task `safe_extract` 失败时**调用方** `rmtree(ignore_errors=True)`,extractor 不擦屁股
- ❌ **不拦截 `.git` / `.env` / `.ssh` / 私钥**:round-2 GPT 标记为风险 R16,但 PM 拍板"本 Task 不做,推迟到 TASK-202"。理由:产品策略层(隐私 vs 友好,加上路径检查也防不住用户主动把私钥扔进 `.m` 文件)。本 Task 只在风险清单提一笔
- ❌ **不实现下游展示安全**:SVG / PDF / XML 若被前端 inline 渲染会形成 stored XSS / 主动内容风险(round-2 R15),**不**在 104 解决,只在风险清单提醒下游"前端不得 inline 用户上传文件"
- ❌ **不引入第三方依赖**(包括但不限于 `defusedxml` / `python-magic` / `pyzipper`;Python 3.11 标准库够用)
- ❌ **不修改 TASK-101 契约**(尤其**不引入** `FileType` enum,**不**改 `FileInfo.file_type` 字段类型;改了停手问 PM)
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md`)

### v1.0 偏离 04 § 8.2 字面规范的说明(策略 B)

- ⚠️ **白名单扩展**:04 § 8.2 字面写了 11 个扩展(`.m` `.mlx` `.slx` `.mdl` `.mat` `.prj` `.txt` `.md` `.csv` `.json` `.xml`),本 Task 局部扩展到 29 项(加 `.ssc` `.fig` `.sldd` `.mldatx` `.slreqx` `.sltx` `.yaml` `.yml` `.png` `.jpg` `.jpeg` `.svg` `.pdf` `.bmp` `.gif` `.tif` `.tiff` `.webp`)。理由:测试集 4 个真实 zip 全部含非 04 字面白名单的扩展(`.png` / `.svg` / `.ssc`),严格策略下无真实 zip 可作通过测试;学生工程含教材插图是合理常见情况
- ⚠️ **新增黑名单兜底**:04 § 8.2 字面是"白名单 + 拒绝其他",本 Task 局部改为"白名单 + 黑名单 + 灰名单(归 `other`)"。理由:已知威胁(可执行 / 脚本 / 动态库)用黑名单更精准且不阻塞合法图像
- ⚠️ **新增 1 个配置项** `max_total_uncompressed_mb`(04 § 8.2 没定义总解压大小上限,只有压缩比 + 单文件)。理由:`200 × 20MB = 4GB` 隐式攻击面,round-1 GPT 二审 R06 必采
- ⚠️ **新增 1 个配置项** `max_entries_per_project`(目录也计数)。理由:目录 entry 膨胀拖慢扫描,round-2 R11

**不修订 04 文档**,以上偏离作为本 Task 局部决策记录在此。**未来若发现需要把这些偏离固化进 04**,由 PM 走宪法/规范修订流程,**不在 TASK-104 PR 内顺手改 04**。

---

## 接口契约

### 7.1 安全沙箱七道闸(顺序严格)

| 闸号 | 检查内容 | 失败时抛 | 一句话理由 |
|------|---------|---------|----------|
| 闸 1 | 上传包外壳检查:`len(zip_bytes) <= max_upload_size_mb * 1024 * 1024`;`dest_dir` 必须已存在、是目录、**不是 symlink**;`dest_dir.resolve()` 必须位于 `config.upload_dir` 的 `Path.resolve()` 子树内 | `ProjectTooLargeError` / `ZipSlipError` | 先用最便宜的字节长度和目标目录元数据拒绝明显越界输入,避免后续打开 zip 或写入不可信目录 |
| 闸 2 | zip 容器结构检查:仅用 `zipfile.ZipFile(io.BytesIO(zip_bytes))` 打开并读取 central directory / `infolist()`;捕获 `BadZipFile`、`LargeZipFile`、`RuntimeError`;**严禁** `testzip()` | `ZipBombError` | 只确认"这是可读 zip 元数据",不调用 `testzip()`(等同读一遍整包,把廉价 metadata 闸变昂贵),不读取 entry 数据 |
| 闸 3 | entry 数量检查:`len(infos) <= config.max_entries_per_project`(目录也计数);实际文件数 `<= config.max_files_per_project`;空 zip(`len(infos) == 0`)拒绝 | `ProjectTooLargeError` / `ZipBombError` | 防止用大量目录、空文件或 central directory 膨胀拖慢扫描和创建目录 |
| 闸 4 | entry 标志与类型检查:拒绝加密 entry(`info.flag_bits & 0x1`);压缩方法只允 `ZIP_STORED` / `ZIP_DEFLATED`(`info.compress_type` 检查);根据 `external_attr >> 16` 经 `stat.S_ISLNK` 拒绝 symlink、device、FIFO 等非普通文件 / 非目录 entry | `ZipSlipError` / `ZipBombError` | 在任何写文件前拒绝 symlink 链式逃逸、密码包和高 CPU 压缩方法 |
| 闸 5 | 路径规范化检查:`unicodedata.normalize("NFC", info.filename)`;拒绝 NUL、控制字符(`\x00-\x1f`)、反斜杠、绝对路径(POSIX `/` 开头 + Windows drive)、`..`、`.`、`_is_windows_unsafe_name()` 命中(详见 7.3);最终目标路径用 `os.path.commonpath([str(dest_root), str(target_parent)]) == str(dest_root)` 验证仍在 `dest_dir.resolve()` 内,跨 drive 抛 `ValueError` 时转 `ZipSlipError` | `ZipSlipError` | 路径安全是写文件前的硬边界,必须同时覆盖 POSIX、Windows、Unicode 和混合分隔符 |
| 闸 6 | 重名与碰撞检查:对规范化后的相对路径做三层去重:原始路径(NFC 前)、NFC 路径、casefold 路径;任一重复或碰撞都拒绝 | `ZipSlipError` | 防止 Linux 上看似不同、Windows/macOS 上可能覆盖的路径绕过扩展名或内容检查 |
| 闸 7 | 大小与扩展名策略检查:单文件**声明**解压大小 `<= max_single_file_mb * 1024 * 1024`;总**声明**解压大小 `<= max_total_uncompressed_mb * 1024 * 1024`;压缩比 `total_uncompressed / total_compressed <= max_compression_ratio`(`total_compressed > 0` 时);扩展名经 `classify_extension(Path(name).suffix.lower())` 命中 deny 时拒绝 | `ProjectTooLargeError` / `ZipBombError` / `FileTypeNotAllowedError` | 最后用 metadata 一次性确认资源预算和文件类型策略,仍不读取 entry 数据 |

**实际解压步骤不属于七道 metadata 闸**,见 7.2。

### 7.2 实际解压 loop(7 道闸全过后,在 `deadline` 框架内)

**注释 ①**:`safe_extract` 主体在 `try:` 之外做闸 1 的字节长度检查,闸 1 之后 `try:` 才开始打开 ZipFile。这个流程是有意的(便宜检查先,贵检查后),不要把闸 1 也包进 try。

**注释 ②**:`actual_file != info.file_size` 是 **defense-in-depth 一致性比对**(metadata 闸 7 已经查过 `info.file_size` 的声明值,actual loop 也累计了实际值,最后还比对)。**不要**误以为冗余删掉。理由:zip header 可被伪造,metadata 声明 1KB 但实际数据 20MB 的情况虽然 actual loop 中途已经抛超限,但 ≤ 20MB 的虚假声明可以漏过闸 7,留到 loop 结束才发现实际 ≠ 声明 —— 这道兜底拦的就是这种 "刚好不超限但与声明不符" 的可疑包。

**代码骨架**(可直接抄,但 metadata 闸的 7 道扫描在 `...` 处省略,Codex 实施时按 7.1 表格补上):

```python
from __future__ import annotations

import io
import os
import stat
import time
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

from app.config import AppSettings
from core.domain.exceptions import (
    FileTypeNotAllowedError,
    ProjectTooLargeError,
    ZipBombError,
    ZipSlipError,
)


CHUNK_SIZE = 1024 * 1024


def safe_extract(zip_bytes: bytes, dest_dir: Path, config: AppSettings) -> Path:
    """安全解压 zip 到 dest_dir,失败时抛 UploadError / ProjectError 子类。

    本函数**不**清理 dest_dir,失败时清理由调用方在 try/finally 负责。

    Args:
        zip_bytes: 原始 zip 字节流
        dest_dir: 必须已存在的目录,通常是 ./data/uploads/<uuid>/
        config: 包含 max_upload_size_mb / max_files_per_project /
                max_entries_per_project / max_single_file_mb /
                max_compression_ratio / max_total_uncompressed_mb /
                max_extraction_seconds / upload_dir 字段

    Returns:
        实际解压根路径(== dest_dir.resolve())

    Raises:
        ProjectTooLargeError: zip 总字节超限 / entry 数超限 / 文件数超限 /
                              单文件超限 / 总解压超限 / 解压超时
        ZipBombError: zip 结构非法 / 加密 / 不支持的压缩方法 / 压缩比超限 /
                      读取内容失败
        ZipSlipError: 路径穿越(绝对路径 / `..` / 反斜杠 / Windows 不安全名 /
                      symlink / 重名碰撞 / dest_dir 元数据非法)
        FileTypeNotAllowedError: 命中黑名单扩展名
    """
    timeout_seconds = config.max_extraction_seconds
    deadline = time.monotonic() + timeout_seconds

    # 注释 ①:闸 1 在 try 之外,因为字节长度检查 + dest_dir 元数据是免费的,
    # 在打开 ZipFile 之前拒绝越界输入。
    _check_outer_envelope(zip_bytes, dest_dir, config)

    # 非 context-manager:context-manager 会在退出时 shutdown(wait=True),
    # 导致超时路径仍等 worker 跑完。round-1 GPT 二审实锤的事实 bug。
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="zip-extract")
    future = executor.submit(_do_extract, zip_bytes, dest_dir, config, deadline)

    try:
        result = future.result(timeout=timeout_seconds)
    except FuturesTimeout as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise ProjectTooLargeError("解压超时,工程过大或异常") from exc
    except BaseException:
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True, cancel_futures=True)
        return result


def _check_outer_envelope(zip_bytes: bytes, dest_dir: Path, config: AppSettings) -> None:
    """闸 1:上传包外壳 + dest_dir 元数据"""
    max_upload = config.max_upload_size_mb * 1024 * 1024
    if len(zip_bytes) > max_upload:
        raise ProjectTooLargeError(f"上传压缩包过大,超过 {config.max_upload_size_mb}MB 上限")

    if not dest_dir.exists() or not dest_dir.is_dir():
        raise ZipSlipError("解压目标目录不存在或不是目录")
    if dest_dir.is_symlink():
        raise ZipSlipError("解压目标目录不能是符号链接")

    dest_root = dest_dir.resolve()
    upload_root = Path(config.upload_dir).resolve()
    try:
        if os.path.commonpath([str(upload_root), str(dest_root)]) != str(upload_root):
            raise ZipSlipError("解压目标目录不在 upload_dir 子树内")
    except ValueError as exc:
        # 跨 drive 情况(Windows)
        raise ZipSlipError("解压目标目录与 upload_dir 跨 drive") from exc


def _do_extract(
    zip_bytes: bytes,
    dest_dir: Path,
    config: AppSettings,
    deadline: float,
) -> Path:
    """执行闸 2-7 的 metadata 检查和分块解压。禁止使用 extractall。"""
    _raise_if_timeout(deadline)

    dest_root = dest_dir.resolve()

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            infos = zf.infolist()

            # 闸 2-7:在这里执行 metadata 扫描。
            # 推荐让 metadata 扫描产出 target_by_name: dict[str, Path],
            # 这样 actual loop 不需要重新做复杂路径判断。
            #
            # - 闸 2:已通过(ZipFile 打开 + infolist 读取成功)
            # - 闸 3:entry 数 / 文件数 / 空 zip
            # - 闸 4:加密 / 压缩方法 / symlink 与非普通文件
            # - 闸 5:路径规范化 + Windows 不安全名 + commonpath
            # - 闸 6:原始 / NFC / casefold 三层碰撞
            # - 闸 7:单文件 / 总声明 / 压缩比 / 扩展名 deny
            target_by_name: dict[str, Path] = ...
            directory_names: set[str] = ...

            max_single = config.max_single_file_mb * 1024 * 1024
            max_total = config.max_total_uncompressed_mb * 1024 * 1024
            actual_total = 0

            for info in infos:
                _raise_if_timeout(deadline)

                target = target_by_name[info.filename]

                if info.filename in directory_names or info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    # Windows 上 chmod 仅支持只读位,这里作为 best-effort。
                    try:
                        os.chmod(target, 0o700)
                    except OSError:
                        pass
                    continue

                # 即使闸 5 已检查,这里再做一次 commonpath defense-in-depth。
                target_parent = target.parent.resolve()
                try:
                    if os.path.commonpath([str(dest_root), str(target_parent)]) != str(dest_root):
                        raise ZipSlipError("zip 路径穿越,文件将写出解压目录")
                except ValueError as exc:
                    raise ZipSlipError("zip 路径跨 drive") from exc

                target.parent.mkdir(parents=True, exist_ok=True)

                actual_file = 0
                try:
                    with zf.open(info, "r") as src, target.open("xb") as dst:
                        while True:
                            _raise_if_timeout(deadline)
                            chunk = src.read(CHUNK_SIZE)
                            if not chunk:
                                break

                            actual_file += len(chunk)
                            actual_total += len(chunk)

                            if actual_file > max_single:
                                raise ProjectTooLargeError(
                                    f"单个文件解压后过大: {info.filename}"
                                )
                            if actual_total > max_total:
                                raise ZipBombError("工程解压后总大小超限,疑似 zip bomb")

                            dst.write(chunk)
                except FileExistsError as exc:
                    raise ZipSlipError("zip 内存在重复路径或路径碰撞") from exc
                except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
                    raise ZipBombError("zip 内容读取失败或格式非法") from exc

                # 注释 ②:metadata 声明大小与实际读取大小一致性 defense-in-depth。
                # 不要误以为冗余删掉。zip header 可被伪造,虚假声明 1KB 但实际数据
                # 远超的情况,actual loop 中途会抛超限;但刚好不超限但与声明不符的
                # 可疑包,需要这道兜底。
                if actual_file != info.file_size:
                    raise ZipBombError("zip 文件大小元数据与实际读取结果不一致")

                try:
                    os.chmod(target, 0o600)
                except OSError:
                    pass

    except zipfile.LargeZipFile as exc:
        raise ZipBombError("zip64 结构超出当前处理范围") from exc
    except zipfile.BadZipFile as exc:
        raise ZipBombError("zip 格式非法,无法读取压缩包") from exc

    _reject_symlink_after_extract(dest_root)
    return dest_root


def _raise_if_timeout(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ProjectTooLargeError("解压超时,工程过大或异常")


def _reject_symlink_after_extract(dest_root: Path) -> None:
    """defense-in-depth:主防线是解压前 external_attr 闸 4。"""
    for root, dirs, files in os.walk(dest_root, followlinks=False):
        root_path = Path(root)
        for name in [*dirs, *files]:
            if (root_path / name).is_symlink():
                raise ZipSlipError("解压结果包含符号链接")
```

**实施约束**:
- `target_by_name` 必须由闸 2-7 metadata 扫描生成,**不要**在 actual loop 里临时拼接未经校验的路径
- `ZipFile.open()` 用 `ZipInfo` 或文件名都行,推荐传 `ZipInfo`(精确)
- chmod 用 `try/except OSError: pass` 包,Windows 上对 `0o600` / `0o700` 的支持仅限只读位,失败不影响功能
- 文件长度超 280 行,主动拆分:把 metadata 扫描的 7 道闸抽到 `_zip_extractor_gates.py` 内部模块,`zip_extractor.py` 只做 `safe_extract` + `_do_extract` 编排

### 7.3 Windows 不安全路径检测(`_zip_paths.py`)

```python
import re
from pathlib import Path


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_UNC_RE = re.compile(r"^(?:\\\\|//)[^\\/]+[\\/][^\\/]+")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$",
    re.IGNORECASE,
)


def _is_windows_unsafe_name(name: str) -> tuple[bool, str]:
    """检查 zip entry name 是否包含 Windows 特有的不安全路径形态。

    覆盖:
    - drive letter: C:foo / C:\\foo
    - UNC: \\\\server\\share / //server/share
    - NTFS ADS: file.txt:ads
    - reserved names: CON / NUL / PRN / AUX / COM1-9 / LPT1-9,含扩展名
    - 路径段尾随空格或点号

    Returns:
        (是否不安全, 不安全理由的简短中文描述)
    """
    if not name:
        return True, "路径名为空"

    if _WINDOWS_DRIVE_RE.match(name):
        return True, "包含 Windows drive letter"

    if _WINDOWS_UNC_RE.match(name) or name.startswith(("\\\\", "//")):
        return True, "包含 Windows UNC 路径"

    # drive letter 已在前面处理;剩余任何冒号都按 ADS 或非法路径处理。
    if ":" in name:
        return True, "包含 Windows ADS 冒号或非法冒号"

    parts = re.split(r"[\\/]+", name)
    for part in parts:
        if part in {"", ".", ".."}:
            continue

        if part.endswith((" ", ".")):
            return True, "路径段尾随空格或点号"

        # Windows reserved name 带扩展名也非法,如 CON.txt / COM1.log。
        trimmed = part.rstrip(" .")
        if _WINDOWS_RESERVED_RE.match(trimmed):
            return True, "包含 Windows 保留设备名"

        stem = trimmed.split(".", 1)[0]
        if _WINDOWS_RESERVED_RE.match(stem):
            return True, "包含 Windows 保留设备名"

    return False, ""
```

**Unit test 参数化必须覆盖以下变体**:

```python
UNSAFE = [
    "C:foo",          # drive letter without backslash
    "c:\\foo",        # drive letter with backslash
    "\\\\server\\share\\x.m",  # UNC backslash
    "//server/share/x.m",       # UNC forward slash
    "file.txt:ads",   # NTFS ADS
    "dir/CON.txt",    # reserved name with extension
    "NUL",            # bare reserved name
    "COM1.log",       # COM1 with extension
    "LPT9",           # LPT9
    "evil.exe.",      # trailing dot
    "evil.exe ",      # trailing space
]
SAFE = [
    "model.slx",
    "dir/file.m",
    "COM10.txt",      # COM10 not reserved
    "normal.name.txt",
]
```

### 7.4 扩展名分类策略(`_zip_policy.py`)

**唯一权威清单**,extractor 闸 7 和 classifier 都调用 `classify_extension`,**禁止两套清单**。

```python
from typing import Literal


ALLOW_EXTS: frozenset[str] = frozenset(
    {
        # MATLAB / Simulink core
        ".m",
        ".mlx",
        ".slx",
        ".mdl",
        ".mat",
        ".prj",
        ".ssc",
        ".fig",
        ".sldd",
        ".mldatx",
        ".slreqx",
        ".sltx",
        # Text / config / data
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        # Images / documents
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".pdf",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
        ".webp",
    }
)

DENY_EXTS: frozenset[str] = frozenset(
    {
        # Windows executables / native libraries
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".msi",
        ".dll",
        ".cpl",
        ".sys",
        ".drv",
        ".ocx",
        # Unix / macOS executables / native libraries
        ".so",
        ".dylib",
        ".sh",
        ".bash",
        ".zsh",
        ".command",
        ".app",
        ".dmg",
        ".pkg",
        ".run",
        ".bin",
        ".elf",
        ".out",
        ".appimage",
        # Python / scripts
        ".py",
        ".pyc",
        ".pyo",
        ".pyd",
        ".ps1",
        ".vbs",
        ".js",
        # MATLAB native / installable / protected artifacts
        ".mex",
        ".mexw64",
        ".mexa64",
        ".mexmaci64",
        ".p",
        ".mlappinstall",
        ".mlpkginstall",
        ".ctf",
        # Windows launchers / registry / script hosts
        ".lnk",
        ".url",
        ".scf",
        ".hta",
        ".wsf",
        ".wsh",
        ".jse",
        ".vbe",
        ".psm1",
        ".reg",
        ".inf",
        # Office macro containers
        ".docm",
        ".xlsm",
        ".pptm",
        ".xlam",
        ".xlsb",
        # Other runtimes / bytecode / packaged apps
        ".class",
        ".jar",
        ".war",
        ".ear",
        ".wasm",
        ".mjs",
        ".cjs",
    }
)


def classify_extension(ext: str) -> Literal["allow", "deny", "other"]:
    """按扩展名返回 allow / deny / other(本 Task 唯一权威策略函数)。

    Args:
        ext: 已由调用方规范化后的扩展名。约定:
            - 必须是小写
            - 带前导点,例如 ".m"
            - 本函数内不再做大小写或路径规范化

    Returns:
        "allow": 白名单扩展,可进入 FileInfo.file_type = ext
        "deny": 黑名单扩展,拒绝整个工程
        "other": 灰名单扩展,可进入 FileInfo.file_type = "other"

    Notes:
        - 空字符串 "" 归 other(无扩展名)。
        - 无点扩展,如裸 "Makefile",归 other(调用方应传 ""。Path.suffix 对
          "Makefile" 返回 "")。
        - ".slxc" / ".html" / ".htm" 不在白名单(MCS 阶段不需要;.slxc 是 cache
          产物对教学解析价值低;.html/.htm 若被前端 inline 是 stored XSS 风险)。
        - ".ts" / ".tsx" / ".jsx" / ".php" / ".pl" / ".rb" / ".lua" / ".r"
          不在黑名单精简版,按 PM round-2 锚点归 other(后端不执行前端不渲染)。
    """
    if ext in ALLOW_EXTS:
        return "allow"
    if ext in DENY_EXTS:
        return "deny"
    return "other"
```

### 7.5 异常分类调用方指引(给 TASK-202 用)

`ProjectTooLargeError` 继承自 `ProjectError`,**不是** `UploadError`。调用方必须同时 catch 两个基类:

```python
import shutil
from core.domain.exceptions import UploadError, ProjectError

try:
    extracted = safe_extract(zip_bytes, dest_dir, config)
    files = classify_files(extracted, extracted)
except (UploadError, ProjectError) as exc:
    # 必须 catch 两个基类才能完整捕获:
    # - UploadError: ZipBombError, ZipSlipError, FileTypeNotAllowedError
    # - ProjectError: ProjectTooLargeError
    shutil.rmtree(dest_dir, ignore_errors=True)
    raise
```

只 catch `UploadError` 会让 `ProjectTooLargeError` 漏到 API 层,被 02 § 9 错误翻译表的"未知异常"兜底("出了点问题,我们已经记录...")—— 这是错的,应该走 `ProjectTooLargeError` 的"工程过大,请压缩到 50MB 以内"中文消息。

### 7.6 7 个风险族 fixture 构造要点

`tests/fixtures/malicious_zips/build_fixtures.py` 实施蓝图。每族给伪代码 + 预期触发的闸。

#### Fixture 1: `zip_bomb_ratio.zip`

```python
out = fixture_dir / "zip_bomb_ratio.zip"
payload = b"0" * (2 * 1024 * 1024)  # 高度可压缩
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    zf.writestr("model.m", payload)
# 预期触发: 闸 7 压缩比 > 100
# 预期抛: ZipBombError("压缩比异常...")
```

#### Fixture 2: `zip_slip_paths.zip`

```python
out = fixture_dir / "zip_slip_paths.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("../escape.m", "disp('escape');")
    zf.writestr("safe/model.m", "disp('safe');")
# 预期触发: 闸 5 路径包含 ".."
# 预期抛: ZipSlipError
# 其他路径变体(绝对路径 / 反斜杠 / UNC / drive letter)走 unit test 参数化
```

#### Fixture 3: `symlink_chain.zip`

```python
out = fixture_dir / "symlink_chain.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    link = zipfile.ZipInfo("linkdir")
    link.create_system = 3  # Unix
    link.external_attr = ((stat.S_IFLNK | 0o777) << 16)
    zf.writestr(link, "/tmp/outside-target")
    zf.writestr("linkdir/payload.m", "disp('should not be written');")
# 预期触发: 闸 4 external_attr 闸识别 linkdir 是 symlink
# 预期抛: ZipSlipError
```

**实施提示**:`stat.S_IFLNK` 即 `0o120000`。`external_attr` 高 16 位是 Unix 模式位。`zipfile.ZipInfo` 直接构造,`writestr` 传 ZipInfo + 数据。这是 round-2 GPT 标记的难点。

#### Fixture 4: `duplicate_collision.zip`

```python
out = fixture_dir / "duplicate_collision.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("dup/a.m", "disp(1);")
    zf.writestr("dup/a.m", "disp(2);")           # 原始重复
    zf.writestr("unicode/e\u0301.m", "disp(1);")  # NFD
    zf.writestr("unicode/é.m", "disp(2);")        # NFC 后碰撞
    zf.writestr("case/A.m", "disp(1);")
    zf.writestr("case/a.m", "disp(2);")           # casefold 后碰撞
# 预期触发: 闸 6 三层去重任一命中
# 预期抛: ZipSlipError
```

#### Fixture 5: `forbidden_type.zip`

```python
out = fixture_dir / "forbidden_type.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("model.m", "disp('ok');")
    zf.writestr("native/evil.mexw64", b"MZ fake binary")
# 预期触发: 闸 7 classify_extension(".mexw64") == "deny"
# 预期抛: FileTypeNotAllowedError
```

#### Fixture 6: `encrypted_or_bad_method.zip`

```python
out = fixture_dir / "encrypted_or_bad_method.zip"
with zipfile.ZipFile(out, "w") as zf:
    zf.writestr(
        "bad_method/model.m",
        "disp('bzip2');",
        compress_type=zipfile.ZIP_BZIP2,
    )
# 预期触发: 闸 4 compress_type 不在 {ZIP_STORED, ZIP_DEFLATED}
# 预期抛: ZipBombError
# 说明: Python stdlib zipfile 不适合写加密 zip;本 fixture 用 BZIP2 覆盖该风险族
```

#### Fixture 7: `total_uncompressed_exceeds_cap.zip`

```python
out = fixture_dir / "total_uncompressed_exceeds_cap.zip"
chunk = os.urandom(64 * 1024)  # 避免压缩比闸先触发
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
    for i in range(24):
        zf.writestr(f"data/part_{i:03d}.bin", chunk)
# 测试时把 config.max_total_uncompressed_mb 覆盖为 1
# 单文件 64KB 远小于 20MB(不触发单文件闸)
# 总解压 ~1.5MB 超过 1MB cap(触发总解压闸)
# 压缩比因为 urandom 接近 1(不触发压缩比闸)
# 预期抛: ZipBombError("工程解压后总大小超限...")
```

**Fixture 7 关键**:**不真实生成 200MB+ 文件**(污染仓库 + 测试慢)。fixture 自身小型化,测试时用 `pytest.MonkeyPatch` 或 `dataclasses.replace` 局部覆盖 config 阈值到 1MB 触发即可。

### 7.7 错误消息中文化清单

| 异常 + 触发场景 | 标准错误消息 |
|---|---|
| `ProjectTooLargeError` 闸 1 字节超限 | "上传压缩包过大,超过 {N}MB 上限" |
| `ProjectTooLargeError` 闸 3 entry / 文件数超限 | "工程文件数过多,超过 {N} 个" |
| `ProjectTooLargeError` actual loop 单文件超限 | "单个文件解压后过大: {filename}" |
| `ProjectTooLargeError` 超时 | "解压超时,工程过大或异常" |
| `ZipBombError` 闸 2 zip 结构非法 | "zip 格式非法,无法读取压缩包" |
| `ZipBombError` 闸 4 加密 | "压缩包含加密文件,暂不支持" |
| `ZipBombError` 闸 4 压缩方法 | "压缩方法不支持,仅允许 stored / deflated" |
| `ZipBombError` 闸 7 压缩比 | "压缩比异常,疑似 zip bomb" |
| `ZipBombError` actual loop 总解压超限 | "工程解压后总大小超限,疑似 zip bomb" |
| `ZipBombError` 大小一致性 | "zip 文件大小元数据与实际读取结果不一致" |
| `ZipSlipError` 闸 1 dest_dir 非法 | "解压目标目录不存在或不是目录" / "解压目标目录不能是符号链接" / "解压目标目录不在 upload_dir 子树内" |
| `ZipSlipError` 闸 4 symlink | "zip 内含符号链接或非普通文件" |
| `ZipSlipError` 闸 5 路径 | "zip 内含非法路径片段: {name}" / "zip 路径穿越,文件将写出解压目录" |
| `ZipSlipError` 闸 5 Windows 不安全名 | "zip 内含 Windows 不安全路径名: {reason}" |
| `ZipSlipError` 闸 6 重名 | "zip 内存在重复路径或路径碰撞" |
| `ZipSlipError` 解压后 walk | "解压结果包含符号链接" |
| `FileTypeNotAllowedError` 闸 7 黑名单 | "包含不支持的文件类型: {ext}" |
| `FileTypeNotAllowedError` classifier defense-in-depth | "包含不支持的文件类型: {ext}" |

错误消息**严格中文**,**禁止**英文(02 § 9 错误翻译表已为这些异常给出中文用户提示,后端异常消息也应中文以便日志和测试断言)。

---

## 验收标准

> **以下每条都给出 PM 可在 Git Bash 跑出来的命令**。
> 命令在仓库根目录(`F:\mxa-tutor`)下执行,且已 `source .venv/Scripts/activate`。

### 1. 文件全部创建

```bash
ls adapters/parser/zip_extractor.py adapters/parser/file_classifier.py \
   adapters/parser/_zip_paths.py adapters/parser/_zip_policy.py \
   tests/adapters/parser/test_zip_extractor_unit.py \
   tests/adapters/parser/test_zip_extractor_real.py \
   tests/adapters/parser/test_zip_extractor_errors.py \
   tests/adapters/parser/test_file_classifier.py \
   tests/fixtures/malicious_zips/build_fixtures.py \
   tests/fixtures/malicious_zips/__init__.py \
   tests/fixtures/malicious_zips/README.md
```

期望:11 个文件全部存在,无 "No such file" 报错。

### 2. 不应被创建的文件确实没创建

```bash
ls features/ingest/service.py 2>&1 | grep -v 'No such' && echo FAIL || echo OK
ls api/routes/upload.py 2>&1 | grep -v 'No such' && echo FAIL || echo OK
ls scripts/cleanup_expired_uploads.py 2>&1 | grep -v 'No such' && echo FAIL || echo OK
```

期望:三条都输出 `OK`(本 Task 不实现 API / ingest service / 清理脚本)。

### 3. 不引入第三方依赖

```bash
git fetch origin main
git diff origin/main..HEAD --name-only -- requirements.txt requirements-dev.txt pyproject.toml
```

期望:无输出。

### 4. 不修改 TASK-101 契约

```bash
git diff origin/main..HEAD --stat -- core/domain/ core/interfaces/
```

期望:无输出(核心契约纹丝不动)。

### 5. 不修改 TASK-102 / 103 产物

```bash
git diff origin/main..HEAD --stat -- \
   adapters/parser/slx_parser.py adapters/parser/_slx_*.py \
   adapters/parser/m_parser.py adapters/parser/_m_*.py \
   tests/adapters/parser/test_slx_parser_*.py tests/adapters/parser/test_m_parser_*.py
```

期望:无输出(除 `__init__.py` 和 `conftest.py` 之外,102/103 文件不动)。

### 6. `adapters/parser/__init__.py` 已扩展

```bash
grep -E "safe_extract|classify_files" adapters/parser/__init__.py
```

期望:看到 2 行 import + 在 `__all__` 中出现这两个符号。

### 7. 配置项已扩展

```bash
grep -E "max_extraction_seconds|max_total_uncompressed_mb|max_entries_per_project" app/config.py
grep -E "MAX_EXTRACTION_SECONDS|MAX_TOTAL_UNCOMPRESSED_MB|MAX_ENTRIES_PER_PROJECT" .env.example
```

期望:两个文件各看到 3 行。

### 8. 静态扫描:domain 和 interfaces 内部不 import 任何外部库

```bash
grep -rn "^import\|^from" adapters/parser/zip_extractor.py adapters/parser/file_classifier.py \
   adapters/parser/_zip_paths.py adapters/parser/_zip_policy.py \
   --exclude-dir=".venv" --exclude-dir=".git" \
   | grep -vE "(import|from) (re|os|io|stat|time|unicodedata|zipfile|pathlib|concurrent|typing)"
```

期望:除业务模块 import(`core.domain.exceptions` / `app.config`)外无输出。本 Task **零第三方依赖**。

按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 强制要求加 `--exclude-dir`。

### 9. 7 道闸单元测试全绿(`test_zip_extractor_unit.py`)

```bash
pytest tests/adapters/parser/test_zip_extractor_unit.py -v
```

期望:**每道闸正反 2 个测试**,合计 14+ 个测试通过,运行 < 3 秒。最低覆盖清单:

- 闸 1:刚好 50MB 通过 / 51MB 拒绝;dest_dir 不存在拒绝;dest_dir 是 symlink 拒绝;dest_dir 不在 upload_dir 下拒绝
- 闸 2:正常 zip 通过;BadZipFile 拒绝;非 zip 字节(纯文本)拒绝
- 闸 3:200 entry 刚好通过 / 201 拒绝;空 zip 拒绝
- 闸 4:加密 entry 拒绝;BZIP2 entry 拒绝;symlink entry 拒绝(用 ZipInfo + external_attr 构造)
- 闸 5:`../foo` 拒绝;`/abs/path` 拒绝;`C:\foo` 拒绝;`file:ads` 拒绝;`CON.txt` 拒绝;`evil.exe.` 拒绝(尾随点)
- 闸 6:`a.m` 重复 2 次拒绝;NFC 碰撞拒绝;casefold 碰撞拒绝
- 闸 7:20MB 单文件通过 / 21MB 拒绝;压缩比 100 通过 / 101 拒绝;`.exe` 拒绝;`.gif` 通过为 "other"

### 10. 7 个恶意 zip 集成测试全绿(`test_zip_extractor_errors.py`)

```bash
pytest tests/adapters/parser/test_zip_extractor_errors.py -v
```

期望:7 个 fixture 各被对应异常正确拒绝;Windows 不安全路径参数化 11+ 变体全过;超时路径测试通过(用 `monkeypatch` 把 `max_extraction_seconds=0.1` + 构造 hang 的解压)。

### 11. 4 个真实 zip 反衬测试通过(`test_zip_extractor_real.py`)

```bash
pytest tests/adapters/parser/test_zip_extractor_real.py -v
```

期望:`01_pmsm_foc_c2000.zip` / `02_buck_voltage_control.zip` / `03_pid_antiwindup.zip` / `04_lms_noise_cancel.zip` **全部通过沙箱**(策略 B 验证),`classify_files` 返回的 `list[FileInfo]` 含:

- `01_*` 中应有 `.png` (8 个,白名单 allow)
- `02_*` 中应有 `.ssc` (1 个,白名单 allow)、`.svg` (1 个,白名单 allow)
- 全部 4 个工程的 `.m` / `.slx` 应分类为对应扩展名

### 12. classifier 测试全绿(`test_file_classifier.py`)

```bash
pytest tests/adapters/parser/test_file_classifier.py -v
```

期望:三档分类正确性 + `classify_extension` 边界值 + defense-in-depth(classifier 遇黑名单仍抛)。

### 13. 全套测试 < 30 秒

```bash
time pytest tests/adapters/parser/ -v
```

期望:整个 `tests/adapters/parser/` 测试套件运行 < 30 秒(04 § 5 测试规范)。

### 14. lint 和 type-check 全绿

```bash
make lint        # ruff check
make type-check  # mypy adapters/parser/ core/ app/
```

两者都应 0 error。

### 15. 每文件 ≤ 300 行

```bash
wc -l adapters/parser/zip_extractor.py adapters/parser/file_classifier.py \
      adapters/parser/_zip_paths.py adapters/parser/_zip_policy.py | sort -n
```

期望:最长的文件 ≤ 300 行(04 § 4 节硬规定)。若 `zip_extractor.py` 接近 280 行,**主动**抽 `_zip_extractor_gates.py`(把 7 道 metadata 闸扫描拆出来)。

### 16. README 已更新

```bash
cat adapters/parser/README.md
cat tests/fixtures/malicious_zips/README.md
```

期望:`adapters/parser/README.md` 列出 4 个新模块各自的一句话职责 + 2-3 行用法示例;`tests/fixtures/malicious_zips/README.md` 列出 7 个 fixture 的精确构造目标矩阵 + 重新生成命令。

### 17. TASK_INDEX 状态已更新

```bash
grep -n "TASK-104" docs/03_TASK_INDEX.md
```

期望:看到 TASK-104 那一行状态变成 🔍,Week 1 进度条第 4 位变成 🔍。改动用字节级 Python 操作(详见风险 1),`git diff docs/03_TASK_INDEX.md` 应只显示 4 行左右改动,**不**是几百行红绿。

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md` 第 1 条,本 Task **只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件**,不动其他任何 docs 核心文档或决策日志或 task 文档。

### 18. 一键全检

```bash
make check
```

应输出 "All checks passed!"。

### 19. PR 元信息

- PR 标题:`TASK-104: 工程压缩包安全解压 + 文件分类(含沙箱)`
- 分支名:`task/TASK-104-zip-extract-and-classify`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-18 项**并简述每项做了什么

### 20. 完工报告含 git 三件套(决策 08)

完工时必须给 PM:

- 修改的文件清单
- 本地 `make check` 完整输出
- **`git status`(显示 working tree clean)**
- **`git log --oneline main..HEAD`(显示本 Task 完整 commit 列表,非空)**
- **`git push` 完整输出(显示 `xxxxxx..yyyyyy  task/TASK-104-zip-extract-and-classify -> task/TASK-104-zip-extract-and-classify`)**
- 验收清单 1-19 项逐条勾选 + 说明
- PR 标题 + PR 正文

**不附三件套 = 没完工**,PM 退回让 Codex 补。

---

## 风险与注意点

### 风险 1:改 `docs/03_TASK_INDEX.md` 必须按决策 08 字节级操作

**这是本 Task 收尾时最容易踩的坑**(TASK-101 收尾时实测踩过)。

`docs/03_TASK_INDEX.md` 在仓库里是 CRLF 行尾(Windows 默认)。**禁用**:

- ❌ `pathlib.Path.read_text() + write_text()`(默认按系统行尾习惯写,Git Bash 下会规范化为 LF,整文件红绿)
- ❌ `open(path, 'w').write(...)`(同上,默认文本模式)
- ❌ `sed -i`(Git Bash 下对中文 + emoji 的处理不稳定,TASK-101 实测踩坑)
- ❌ `python -c "..."` 中混用文本模式读写

**只允许**方式 A 编辑器(VS Code / Notepad++ / Codex 内置编辑工具)或方式 B Python 字节级:

```python
import pathlib

p = pathlib.Path('docs/03_TASK_INDEX.md')
data = p.read_bytes()

# 改 TASK-104 状态行的两处:
old_status = '| TASK-104 | 工程压缩包安全解压 + 文件分类(含沙箱) | 🔲 | Codex | 101 |'.encode('utf-8')
new_status = '| TASK-104 | 工程压缩包安全解压 + 文件分类(含沙箱) | 🔍 | Codex | 101 |'.encode('utf-8')
assert old_status in data, 'TASK-104 状态行未找到'
data = data.replace(old_status, new_status)

# 改 Week 1 进度条:
old_bar = 'Week 1:  [✅✅✅⬜⬜⬜⬜]'.encode('utf-8')
new_bar = 'Week 1:  [✅✅✅🔍⬜⬜⬜]'.encode('utf-8')
assert old_bar in data, 'Week 1 进度条未找到'
data = data.replace(old_bar, new_bar)

p.write_bytes(data)
```

**改完后立即 `git diff docs/03_TASK_INDEX.md` 验证**。若 diff 显示几百行红绿,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销,换方式 A 用编辑器手改**。

**仅这一个文件**,不动其他任何 docs 核心文档或决策日志或 task 文档(决策 07 边界)。

### 风险 2-18:GPT 二审采纳的 17 条风险(R01-R17 分级表)

| 风险 ID | 等级 | 描述 | 缓解措施位置 |
|---|---|---|---|
| R01 | 🔴 高 | `ThreadPoolExecutor` 超时后正在运行的 worker 不能被强制 kill;若外层清理目录,Windows 上可能与写文件线程冲突 | 本 Task:非 context-manager + cooperative deadline;下游 TASK-202:失败后 `rmtree(ignore_errors=True)` |
| R02 | 🔴 高 | 用 `with ThreadPoolExecutor(...)` 会在退出 context 时等待 worker,导致"超时立即返回"失效(round-1 GPT 二审实锤事实 bug) | 本 Task:禁止 context-manager 写法,显式 `shutdown(wait=False, cancel_futures=True)` |
| R03 | 🔴 高 | `extractall()` 无法做分块累计、实际大小中途终止和精确 chmod,且不适合作为不可信 archive 的安全边界 | 本 Task:禁止 `extractall()`,改用 `zf.open(info)` + chunked copy |
| R04 | 🔴 高 | path traversal:`../` / 绝对路径 / 反斜杠 / Windows drive / UNC / ADS / reserved name / 尾随点空格都可能导致跨平台逃逸或覆盖异常 | 本 Task:路径闸 5 + `_is_windows_unsafe_name()` + `os.path.commonpath` |
| R05 | 🔴 高 | symlink 链式逃逸:先写 symlink,再写 symlink 下路径,可能写出沙箱(主防线必须在解压前) | 本 Task:解压前查 `external_attr` 拒绝 symlink / 非普通文件,解压后 walk 复查 |
| R06 | 🔴 高 | 总解压大小膨胀:200 文件 × 20MB 可形成理论 4GB 输出 | 本 Task:新增 `max_total_uncompressed_mb = 200`,metadata 声明值和 actual read 双重累计 |
| R07 | 🔴 高 | `info.file_size` / zip header 可被伪造,metadata 闸通过后实际读取可能超限 | 本 Task:actual loop 中累计 `actual_file` / `actual_total`,超限立即抛;loop 结束做一致性比对 |
| R08 | 🔴 高 | 多 entry 同名 / NFC vs NFD 碰撞 / 大小写碰撞可能导致覆盖或绕过扩展名策略 | 本 Task:原始路径 / NFC / casefold 三层去重 |
| R09 | 🔴 高 | 加密 zip 或 unsupported compression method 可能在读取阶段失败、消耗 CPU 或绕过预期错误分类 | 本 Task:metadata 闸 4 拒绝 `flag_bits & 0x1`,只允 `ZIP_STORED` / `ZIP_DEFLATED` |
| R10 | 🟡 中 | `zipfile.testzip()` 会读取所有文件,把廉价 metadata 闸变成昂贵数据读取 | 本 Task:**删除** `testzip()`,不放在任何闸位置 |
| R11 | 🟡 中 | 目录 entry / 空文件 entry 膨胀:攻击者可用大量目录拖慢扫描和创建目录 | 本 Task:新增 `max_entries_per_project`,目录也计数 |
| R12 | 🟡 中 | `dest_dir` 若不是新建空目录、本身是 symlink、或不在 `upload_dir` 下,会破坏沙箱边界 | 本 Task:闸 1 dest_dir 契约加严;下游 TASK-202 创建目录时也要遵守 |
| R13 | 🟡 中 | zip64 / 超大 central directory 兼容性和内存占用不可忽视 | 本 Task:捕获 `LargeZipFile`,限制上传总大小、entry 数、声明总大小 |
| R14 | 🟡 中 | 黑名单不是完整安全边界;灰名单默认通过可能放入未知可执行或主动内容 | 本 Task:黑名单精简版 + "不执行、不 import、不 inline 展示"风险说明;下游继续约束 |
| R15 | 🟡 中 | SVG / PDF / XML 未来若被前端 inline 展示,可能形成 stored XSS / 主动内容风险 | 下游 Task(前端 / API 静态资源服务):禁止 inline 原始用户文件。**本 Task 不做拦截**,仅记录 |
| R16 | 🟡 中 | `.git` / `.env` / 私钥等隐私文件会污染后续入库、prompt 或前端展示 | 下游 TASK-202:隐私拦截。**本 Task 不做拦截**,仅记录 |
| R17 | 🟢 低 | 临时目录 UUID 冲突概率极低,但测试 fixture 和 ingest 逻辑不应依赖外部状态 | 下游 TASK-202:目录创建用 exclusive mkdir;本 Task fixture 构造脚本可重复运行 |

### 风险 19:跨平台陷阱核对表

| 项 | Linux | Windows | macOS | Codex 测试建议 |
|---|---|---|---|---|
| `os.chmod` | POSIX 权限位按预期生效,`0o600` / `0o700` 可断言 | Python 3.11 文档说明 Windows 上 `chmod()` 只能设置只读标志,其他权限位会被忽略;**不要**断言 `0o600` 精确权限 | 类 POSIX | Linux/macOS 断言"无 executable bit";Windows 用 `try/except OSError: pass` 包,只断言调用不阻塞流程 |
| `os.mkdir(..., mode=0o700)` | 受 umask 影响,最终权限可能不是精确 `0o700` | Windows 对 `0o700` 有特殊 ACL 处理,其他 mode 被忽略 | 同 POSIX,受 umask 影响 | `dest_dir` 创建最好在 TASK-202 统一处理;104 只校验"不是 symlink、在 upload root 内" |
| `os.path.commonpath` | 对绝对路径列表可靠;比 `commonprefix` 安全 | 不同 drive、绝对/相对混合会抛 `ValueError`;应在调用前拒绝 drive / UNC / 反斜杠 | 同 POSIX | 包一层 `try/except ValueError`,转 `ZipSlipError`;不要用 `commonprefix` |
| 反斜杠 vs 正斜杠 | `\` 只是普通字符,若不拒绝可能绕过 Windows 语义 | `\` 是路径分隔符,`..\\foo` 会形成 traversal | `\` 通常是普通字符,但跨平台工程仍应拒绝 | metadata 闸 5 直接拒绝任何 `\`(PM 锚点保留) |
| `info.external_attr` | Unix zip 工具通常写 POSIX mode 到高 16 位;symlink fixture 用 `create_system=3` + `external_attr` 构造 | Windows 工具可能不写 POSIX mode,高 16 位不可靠 | macOS zip 通常携带 POSIX mode,但不同工具行为不一致 | 不要假设所有外部工具都保留 symlink bit;但只要 bit 显示为 symlink 就必须拒绝 |
| MATLAB R2026a 打包工具是否保留 symlink 属性 | 不作为本 Task 的正确性前提 | 同左 | 同左 | fixture 自己构造 symlink entry;真实 MATLAB 包如果不保留 symlink 属性,则不会触发 symlink metadata 测试,但 path / size / extension 闸仍生效 |
| `stat.S_ISLNK` | 在 mode int 上判断文件类型位,适合解析 `external_attr >> 16` | 同样可运行;问题是 zip 是否提供 POSIX mode | 同 Linux | 单元测试直接喂 `(stat.S_IFLNK \| 0o777) << 16`,不要依赖宿主 OS 创建真实 symlink |
| `Path.resolve()` | 消除 `..`,解析 symlink;`strict=False` 可解析不存在路径的已存在前缀 | 也会解析可解析的 reparse point / symlink;大小写规范化不要作为安全判断前提 | 解析 symlink;Unicode 文件名可能受文件系统 normalization 影响 | 路径比较前先做字符串级拒绝(NFC / 反斜杠 / 绝对路径 / Windows 不安全名),再用 `resolve()` + `commonpath` 兜底 |
| 解压后 symlink walk | `Path.is_symlink()` 可发现 symlink | Windows symlink / junction 行为受权限和 reparse point 影响,`is_symlink()` 不能覆盖全部 Windows reparse point 风险 | 可发现 symlink | 它只是复查,不是主防线。主防线是解压前 `external_attr` 闸 4 |

### 风险 20:测试集的反衬测试不等于生产保证

`test_zip_extractor_real.py` 验证 4 个真实 zip 在策略 B 下通过沙箱 —— 但这只代表 MathWorks R2026a 示例工程的样本。**真实学生上传的工程**可能含本 Task 未覆盖的扩展名(例如学生用了 NI LabVIEW 工具箱产物 `.vi`,或老师发的 `.docx` 教学文档)。

策略:这些都走灰名单 `"other"`(白名单不命中、黑名单不命中),**不阻塞**上传。Task 文档 § 6 "不做" 章节明示:超出已知白名单的合法扩展由灰名单兜底,**不**在 TASK-104 内动态扩白名单。若 MCS 上线后真实数据反馈"很多 `.docx` 教学文档没被识别成 doc 文件",再走单独 chore PR 加白名单,**不在 TASK-104 内预先做**。

### 风险 21:`max_total_uncompressed_mb` v1.0 暂定 200,允许 Codex 校准

PM 拍板:Codex 实施完成跑 4 个真实 zip + 7 个 fixture 后,若发现 200MB 上限对真实工程不够(例如某个工程展开后接近 200MB),**允许在 TASK-104 PR 内顺手把默认调到合理值**(例如 300 / 500),并在 PR 描述"风险与注意点"补一笔"实测 XX 工程需要 YY MB,默认上调至 ZZ"。

这是本 Task 内的自由度,不需要单独走 chore PR。

### 风险 22:`max_extraction_seconds` v1.0 锁 30 秒,实测过紧由 Codex 独立 chore 上调

PM 拍板:Codex 实施完成跑 fixture 时若发现 50MB 真实 zip 接近 30 秒,**允许独立 chore PR** 上调到 60 秒,**不在 TASK-104 范围内预先调**。本 Task 验收以 30 秒为基线;独立 chore PR 在 TASK-104 合并后单独走。

### 风险 23:Codex 看见冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / TASK-101 契约 的任何冲突,**停手问 PM**,不要默默偏离。

常见可能冲突场景:

- 发现 `FileInfo` 字段需要新增 / 修改(尤其想加 `FileType` enum)→ **不要改 TASK-101 已建的 dataclass**,问 PM 是否走宪法修订流程
- 发现 `core/domain/exceptions.py` 缺某种异常子类需要新增 → **不要在本 Task 顺带改 core**,问 PM
- 发现 4 个测试工程中某个工程实际格式与本 Task 文档"接口契约"小节 7.6 描述不同 → **不要硬扛**,告诉 PM 你看到的实际结构
- 发现 GPT round-2 的代码骨架与你实际写的有显著差异 → **告诉 PM**,不要默默"优化"代码骨架(round-2 内容是 PM + 架构师两轮采纳后的收口版本)

### 风险 24:静态扫描误报

任何 `grep` / `find` 检查必须按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。本 Task 验收清单已按规则给出命令,直接用。

---

## 估时

预估 **12-18 小时**(显著长于 TASK-102 / 103,因为安全测试覆盖更密集,且 fixture 构造脚本中的 symlink zip 是难点):

- 阅读 GPT round-1 + round-2 + 本 Task 文档:1 小时
- `_zip_paths.py`(Windows 不安全名)+ 单测:1-2 小时
- `_zip_policy.py`(白/黑名单)+ 单测:1 小时
- `zip_extractor.py` 主体(7 道闸 + actual loop + 超时):4-6 小时
- `file_classifier.py` + 单测:1 小时
- `build_fixtures.py` 7 个 fixture 构造(symlink zip 是难点):2-3 小时
- `test_zip_extractor_unit.py` 14 个正反测试:2 小时
- `test_zip_extractor_errors.py` 7 fixture 集成 + Windows 路径参数化 + 超时测试:1-2 小时
- `test_zip_extractor_real.py` 4 真实 zip 反衬:0.5 小时
- README / commit 拆分 / PR 描述 / 三件套确认 / 决策 08 字节级改索引:1 小时

---

## 给 Codex 的提示

### 1. 先看 4 个真实 zip 实际结构,再动手写代码

切分支后**第一件事**,unzip 4 个真实 zip 看扩展名分布,确认本 Task 文档 § 7.4 白名单 29 项的合理性:

```bash
unzip -l tests/fixtures/slx_samples/01_pmsm_foc_c2000.zip | awk '{print $NF}' | grep -oE '\.[^.]+$' | sort -u
unzip -l tests/fixtures/slx_samples/02_buck_voltage_control.zip | awk '{print $NF}' | grep -oE '\.[^.]+$' | sort -u
unzip -l tests/fixtures/slx_samples/03_pid_antiwindup.zip | awk '{print $NF}' | grep -oE '\.[^.]+$' | sort -u
unzip -l tests/fixtures/slx_samples/04_lms_noise_cancel.zip | awk '{print $NF}' | grep -oE '\.[^.]+$' | sort -u
```

预期看到的扩展名应该是 § 7.4 白名单子集(`.m` `.slx` `.png` `.ssc` `.svg` `.mat` `.prj` 等)。**若看到本 Task 文档未列出的扩展名**(例如 `.mp4` 教学视频),**停手抛冲突给 PM**,不要默默扩白名单。

### 2. 推荐实现顺序

按依赖关系从无到有:

1. **`_zip_policy.py`**(无依赖):`ALLOW_EXTS` / `DENY_EXTS` / `classify_extension`
2. **`_zip_paths.py`**(无依赖):`_is_windows_unsafe_name` + `_normalize_zip_path` 等
3. **`file_classifier.py`**(依赖 1-2):`classify_files`
4. **`zip_extractor.py`**(依赖 1-3):`safe_extract` + `_do_extract` + 7 道闸
5. **`build_fixtures.py`**(独立):构造 7 个 fixture zip
6. 测试文件,每个对应实现完成后立即写,逐步推进而非最后一起

**每个文件建完就立刻跑对应测试** —— 逐文件验证,避免一次性十几个错。

### 3. 先用 fixture 5 把"黑名单拒绝路径"调通

`forbidden_type.zip` 是 7 个 fixture 里**最简单的**(直接 `writestr` 一个 `.mexw64` 文件,触发闸 7 + `classify_extension` deny)。先把这个调通,7 道闸的"通过主路径 + 一道拒绝路径"就跑通了。然后逐个扩展到其他 fixture。

最难的是 `symlink_chain.zip`(fixture 3):需要手动构造 `ZipInfo` + `create_system=3` + `external_attr = ((stat.S_IFLNK | 0o777) << 16)`。建议最后做。

### 4. Commit 拆分建议(Conventional Commits)

```
feat(parser): add zip extension policy whitelist/blacklist
test(parser): add classify_extension unit tests
feat(parser): add zip path normalization and Windows unsafe name detection
test(parser): add zip path utility unit tests
feat(parser): add file classifier (3-tier extension policy)
test(parser): add file_classifier unit tests
feat(parser): add zip extractor with 7-gate sandbox and chunked extraction
test(parser): add zip extractor unit tests (7 gates)
test(parser): add malicious zip fixture builder (7 risk families)
test(parser): add zip extractor error handling tests on malicious fixtures
test(parser): add zip extractor reverse-validation on 4 real projects
docs(parser): update adapters/parser/README
docs: add tests/fixtures/malicious_zips/README
chore(config): add max_extraction_seconds / max_total_uncompressed_mb / max_entries_per_project
docs: mark TASK-104 as in-review in task index
```

每个 commit 单一职责,review 更轻松。**不要**单个超大 commit 提交全部代码。

### 5. 文件拆分纪律

04 § 4 节"每文件 ≤ 300 行"是硬规定。`zip_extractor.py` 估算 200-280 行偏紧,**主动**抽 `_zip_extractor_gates.py`(把 7 道 metadata 闸扫描拆出来,`zip_extractor.py` 只做 `safe_extract` + `_do_extract` 编排),不要写到 320 行才发现违规。

### 6. 错误消息严格中文

`ZipBombError("compression ratio too high")` ❌ — 英文不行。
`ZipBombError("压缩比异常,疑似 zip bomb")` ✅。

详见 § 7.7 错误消息中文化清单。

### 7. 不要"优化" GPT round-2 代码骨架

§ 7.2 的代码骨架是 PM + 架构师 + GPT 二审 2 轮(round-1 + round-2)收口后的版本,**Codex 实施时直接抄,不要自作主张优化**:

- **不**要把非 context-manager 改回 `with ThreadPoolExecutor(...)`(round-1 实锤 bug)
- **不**要用 `extractall()` 替代手动 chunked loop(round-1 必采)
- **不**要加 `testzip()` 调用(round-1 必采删除)
- **不**要省略 `actual_file != info.file_size` 一致性比对(注释 ②,defense-in-depth)
- **不**要省略解压后 `os.walk` 复查(defense-in-depth,主防线是闸 4)

若你在实施时**强烈认为**某条骨架应该优化,**停手问 PM**,不要默默偏离。

### 8. 内部模块的 import

```python
# adapters/parser/zip_extractor.py
from adapters.parser._zip_paths import _is_windows_unsafe_name, _normalize_zip_path
from adapters.parser._zip_policy import classify_extension
# ...

# adapters/parser/file_classifier.py
from adapters.parser._zip_policy import classify_extension
```

用绝对路径 import,**不**用相对 import(`from ._zip_policy import ...`)。

### 9. fixture 构造脚本运行约定

`build_fixtures.py` 设计为"幂等可重复运行":

```python
# tests/fixtures/malicious_zips/build_fixtures.py
def build_all(out_dir: Path) -> None:
    """构造 7 个风险族 fixture 到 out_dir。out_dir 不存在则创建。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    build_zip_bomb_ratio(out_dir)
    build_zip_slip_paths(out_dir)
    build_symlink_chain(out_dir)
    # ...

if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./_built_fixtures")
    build_all(out)
```

`conftest.py` 的 `malicious_zip_dir` fixture 在 `tmp_path_factory` 下首次跑 `build_all`,返回 `dict[risk_family_name, Path]`,session scope。

### 10. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见风险 1 的脚本骨架。改完后 `git diff docs/03_TASK_INDEX.md` 确认只显示 4 行左右改动。**若 diff 显示几百行变化,立即 `git checkout --` 撤销,换方式 A 用编辑器手改**。

### 11. 完工报告必须含 git 三件套(决策 08)

完工时给 PM:

- 修改的文件清单
- 本地 `make check` 输出
- **`git status` / `git log --oneline main..HEAD` / `git push` 三条命令的完整输出**
- 验收清单 1-19 项逐条勾选 + 说明
- PR 标题:`TASK-104: 工程压缩包安全解压 + 文件分类(含沙箱)`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 12. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:

- PR 标题:`TASK-104: 工程压缩包安全解压 + 文件分类(含沙箱)`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

PM 在 GitHub 网页手动创建 PR。CI 自动触发,绿了之后 PM 把 Codex 产出 + CI 结果交给架构师 review。

---

**版本**:Task 文档 v1.0(GPT 二审 2 轮采纳后收口版)
**作者**:Claude(架构师,第六任)
**日期**:2026-06-02
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-04-*.md` / `20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md`
**关联 Task**:依赖 TASK-101(契约) / TASK-002(配置层) / TASK-003(测试集);下游 TASK-105 / TASK-202
**GPT 二审历史**:round-1 抓 13 项必采 + 5 项部分采纳;round-2 Q1-Q7 细化到代码骨架,无新发散,直接进 v1.0
