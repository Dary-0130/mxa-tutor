# TASK-523:PDF 中文抽取乱码 pdfplumber fallback · v0.3(定稿)

> **归属**:paper-to-model 线 TASK-523(v0.1 TASK-312 编号复议改正——`PdfParser` 由 TASK-501 引入,commit `2eb29b8`)。**修复卡**,不占论文线完工计数,进度维持 21/22 · 52/55。
> **状态**:**v0.3 定稿 · 四阈值已按真样本实测校准 + 三样本判定验证全对 · Stage 0 全绿 · 可进实现**。
> **性质**:后端修复卡(改 `adapters/parser/pdf_parser.py` 加 pdfplumber fallback + 新增依赖)。不改对外 schema、不加路由、不碰业务逻辑、无前端。走合并前亲核真 diff + 后端真测试(挂既有 `tests/adapters/parser/test_pdf_parser.py`)+ 依赖 review + 真论文验证。
> **基线**:R6 @ live `origin/main` `5ab0f49` 实证(Codex 干净 detached worktree 两轮复核)。
>
> **★ v0.2 → v0.3 收敛(R6 实测校准,条件可落 → 定稿)**:
> - **★ 关键修正:predicate 条件 (b) `cjk_count==0` → CJK 比率**。R6 实测失败篇 pypdf **CJK 不是 0、是 1**(一个 `U+3DA7`,乱码偶发命中)。写死 `==0` 会漏触发这个真样本。采纳 R1 P2-1 已给的 `cjk_ratio` 方案:`cjk_count / 非空白数 <= FALLBACK_MAX_PYPDF_CJK_RATIO`(§4.1)。
> - **四阈值实测定死**(§4.1):`FALLBACK_MIN_CHARS=100` / `FALLBACK_MAX_PYPDF_CJK_RATIO=0.01` / `FALLBACK_CORRUPTION_RATIO=0.005` / `FALLBACK_MIN_RECOVERY_CJK=50`。
> - **corruption 字符集定案 = 核心层 `Cc(减\t\n\r\f\v)∪U+FFFD`**。R6 codepoint probe:失败篇坏字符是 149 个 Cc(`U+0001`×144 主导)+ 无 U+FFFD/无 PUA(Co)/无 `(cid:)`。**R1 P1-2 担心的 Co/CID 实测对触发零贡献,不启用**(保留为将来扩展点,§7)。
> - **三样本判定验证全对**(§4.4):失败篇 触发+采用→救回 3772 中文;正常中文 条件 b 挡下→pypdf 原样;正常英文 条件 c 挡下→pypdf 原样。margin 63x/4.7x/75x。
> - **依赖 review 过**(§3.5):pdfplumber 0.11.10 装通、链路解析、许可证 permissive、Linux manylinux wheel 下载验证通过(真运行靠 CI);**建议显式 pin `Pillow==12.2.0`**。
> - **Stage 0 §6 全绿**:1/2/6 早已过,本轮补齐 3/4/5 → **可进实现**。
>
> **v0.1 → v0.2 收敛(仍有效)**:编号复议 312→523;并入 R1 P1-1(护栏"有意义中文恢复")/P1-2(corruption 分层 + 非空白分母)/P1-3(fail-open 边界:Python 异常 fail-open、资源硬杀 sandbox 兜)/P2-1(已知漏判)/P2-2(诊断计数)。

---

## 1. 这张卡是什么 / 不是什么

**是**:给 `PdfParser` 加一条 **pdfplumber fallback**——当现有 pypdf 主路抽出的文本呈现「抽取损坏」信号(文本量不短、几乎零中文、且控制字符占比够高)时,改用 pdfplumber 重抽整篇;**仅当 pdfplumber 显著救回中文且坏率下降**才采用它,否则保留 pypdf。**pypdf 主路对正常文档一字节不动**。

**★ 范围收口**:本卡是**针对已实测「整篇 mis-decode(控制字符型)」失败模式的外科式 fallback**,**不是「中文乱码全覆盖检测器」**。已知漏判(纯 printable-glyph 无控制字符的乱码 / 局部页损坏)见 §7。

**动机**:PM 真实第一篇中文论文,pypdf 抽出的是控制字符 + 异常 glyph 的乱码流(实测 chars=8767 / 非空白 6277 / CJK=1 / 控制字符 149 个),内容「进来了却读错了」→ 下游 PaperSpec 抽取吃到垃圾。pdfplumber 交叉验证同篇能正常抽出 3772 个中文。TASK-311 修好后大论文能进 sandbox,但这类中文论文进来仍是乱码,paper-to-model 对它是空转。非通病——特定字体/CMap 编码的 pypdf 兼容问题。

**根因位置**:`pdf_parser.py` 的抽取库(pypdf),与 TASK-311 修的 `_sandbox.py` 传输死锁是两处不同代码。

**不是**:
- ①**不整体换成 pdfplumber**:pypdf 对绝大多数文档读得对;整体换会牵动英文/正常中文 PDF 的空白、换行、页切分、equation locator 输出与耗时。只在坏信号命中时 fallback。
- ②**不改 pypdf 主路的任何抽取/后处理逻辑**:逐页 `extract_text()` + `[S{n}]` + `\n\n` 拼 + `.strip()` + equation locator + `document_text_too_short` 闸,一律不动。
- ③**不只看「零中文」触发**:正常英文也零中文(实测 CJK=0)。必须叠加控制字符损坏信号(§4.1 条件 c)。
- ④**不碰 DocxParser**(§3.6)。
- ⑤**不碰 sandbox 传输机制**:pdfplumber 在 TASK-311 现有 sandbox 子进程内跑,**不新开进程、不绕过、不削弱隔离/资源上限**(TASK-311 as-built 不回退)。
- ⑥**不做扫描件 OCR**:走既有 `document_text_too_short`。
- ⑦**不碰对外 schema / 路由 / 前端 / 业务逻辑**。

---

## 2. 产品 / 隐私边界(本卡不重开)

- **无产品决定点**:纯技术修复。用户可见变化仅一个:这类中文论文从「读出乱码」变成「读对、抽得出参数」。不是新功能。
- **隐私不变**:pdfplumber 失败/异常时不落原始文本 / filename / 堆栈(decision 11);fallback 判定、诊断计数、日志**只落固定码 + 数值指标**(§4.3)。filename 仅展示不落日志(多文件线已锁),沿用。
- **新增依赖**:pdfplumber + 传递依赖(§3.5),许可证全 permissive;pypdfium2、cryptography 是二进制 wheel,依赖 review 按**目标部署环境**验证(不只本地 pip)。

---

## 3. 现状基线(R6 @ live `origin/main` `5ab0f49` 实证)

### 3.1 PdfParser 主路(本卡只在其后加 fallback 分支,主路不动)— ✅ 已核一致
```python
reader = pypdf.PdfReader(..., strict=False)              # pdf_parser.py:49(全仓库唯一 PDF 抽取点)
for index, page in enumerate(reader.pages, start=1):
    section_id = f"S{index}"
    section_ids.append(section_id)
    text = (page.extract_text() or "").strip()
    if text:
        page_texts.append(f"[{section_id}]\n{text}")
raw_text = "\n\n".join(page_texts).strip()
# 之后:equation locator regex → raw_text < 100 → document_text_too_short → 组 ParsedDocument
```

### 3.2 ★ 失败 fingerprint + codepoint probe(R6 实测,真样本仓库外)
样本目录 `E:\桌面\样例\异步电机定子匝间短路仿真模型\` 下:
- **PDF-2 失败篇** = `_感应电机定子匝间短路故障建模与仿真研究.pdf`
- **PDF-1 正常中文** = `_异步电机定子匝间短路故障建模及检测研究.pdf`

pypdf 测量(核心层 corruption = `(Cc 减 \t\n\r\f\v)∪U+FFFD` / 非空白数):
```
样本            chars   非空白   CJK    core corruption ratio
PDF-2 失败篇     8767    6277     1      0.023737
PDF-1 正常中文   14706   11372    3762   0
正常英文         53339   43774    0      0
```
**★ PDF-2 CJK=1(非 0)**:那 1 个是 `U+3DA7`,乱码偶发命中 → predicate 条件 b 必须用比率、不能写死 `==0`(§4.1)。

**PDF-2 坏字符类别分布(分母 6277 非空白)**:
```
类别              数量    占比        备注
Cc 控制字符        149     0.023737   codepoint: U+0001×144 / U+0010×4 / U+000E×1
U+FFFD             0       0
Co (PUA)           0       0          ← R1 P1-2 担心的私用区,实测无
(cid:\d+)          0       0          ← CMap 失败强信号,实测无
其余非ASCII非CJK   1386    0.220806   Lo443/Sm234/Ll212/Cn110/Mn108/Lu88/Mc74/Nd48/Po40…(中文被映射成的杂字符,非损坏 marker)
```
**结论**:失败篇靠 `Cc∪U+FFFD` 已把 corruption_ratio 拉到 0.0237(正常样本为 0),**核心层足够、Co/CID 不启用**。「其余非 ASCII 非 CJK」占 22% 是乱码主体,但**不作判据**(正常数学/物理英文论文也含大量希腊字母/数学符号,会误伤——R1)。

### 3.3 pdfplumber 在现有 sandbox 内可行性(R6 实测,已复跑确认)
```
现有 run_in_sandbox + pdfplumber 子进程 import/抽取: 跑通
失败篇 PDF-2 pdfplumber: chars=11091  非空白=9100  CJK=3772  core_ratio=0  (< 80000)
```
限制(R6):本机 Windows,非 Linux `_apply_resource_limits` 直接 return,证不了 Linux `RLIMIT_AS=512MB` 是否够;早前 probe 峰值工作集 ≈96MB(宽松指示,非等价测量)。Linux 侧靠 CI + TASK-311 既有 sandbox 保护兜(§4.3)。

### 3.4 下游 — ✅ 已核一致
`run_in_sandbox → ParsedDocument → len(raw_text) <= 80000 → build_messages → LLM`。pdfplumber 输出走同一下游;失败篇 pdfplumber chars=11091 < 80000,可直接进 prompt(80k 闸本卡不动)。

### 3.5 依赖 review(R6 实测,已过)
```
pdfplumber==0.11.10 装通;链路:pdfminer.six==20260107 / pypdfium2==5.11.0 / cryptography==49.0.0
                     / cffi==2.0.0 / charset-normalizer==3.4.7 / pycparser==3.0 / Pillow>=12.2.0
现有 requirements 仅 pypdf==6.13.2,无直接冲突。
Linux manylinux cp313 wheel(含 pypdfium2/cryptography 二进制)下载验证通过;Ubuntu 真运行靠 CI(本机 Docker/WSL 起不来)。
许可证:MIT / BSD-3-Clause / Apache-2.0 组合,均 permissive。
```
**★ 要求**:requirements 显式钉死 pdfplumber==0.11.10 + 其传递依赖;**显式 pin `Pillow==12.2.0`**(否则 resolver 拉更新版)。

### 3.6 范围:DocxParser 不受影响
DOCX 走 `python-docx`,不涉 pypdf/pdfplumber;只共享 sandbox 传输层(TASK-311 已修)。

---

## 4. 范围(必须做)

### 4.1 ★ 核心:fallback 判定 + 采用护栏 + 调用位置(阈值已实测定死)

**判定 predicate**(`_pypdf_text_looks_corrupted(text) -> bool`;命中才 fallback):
```python
nonws  = sum(1 for ch in text if not ch.isspace())          # 非空白字符数(公共分母)
cjk    = cjk_count(text)
corrupt = sum(1 for ch in text
               if (unicodedata.category(ch) == "Cc" and ch not in "\t\n\r\f\v")
               or ch == "\uFFFD")

(a) len(text.strip()) >= FALLBACK_MIN_CHARS                  # = 100
(b) cjk / max(1, nonws) <= FALLBACK_MAX_PYPDF_CJK_RATIO      # = 0.01(无有意义中文;失败篇 0.000159 命中,正常中文 0.3308 不命中)
(c) corrupt / max(1, nonws) >= FALLBACK_CORRUPTION_RATIO     # = 0.005(损坏;失败篇 0.0237 命中,正常 0 不命中)
返回 a and b and c
```
- **corruption 字符集 = 核心层 `Cc(减 \t\n\r\f\v)∪U+FFFD`**,分母 = 非空白数(不用全量 len,避免换行/`[S{n}]` 稀释)。**Co(PUA)/CID marker 实测零贡献,不启用**(§3.2);保留为将来扩展点(§7)。
- **条件 b 用比率不用 `==0`**(★ v0.3 关键):实测失败篇 CJK=1。比率把「乱码偶发命中几个中文」和「真有中文」分开(失败篇 0.000159 vs 正常中文 0.3308,63x/33x margin)。
- **✗ 不用「非 ASCII 比例高」当判据**(误伤含符号英文——R1)。

**★ 采用护栏 = "有意义中文恢复"**(`_pdfplumber_is_meaningful_recovery(pypdf_text, plumber_text) -> bool`):
```python
return (
    len(plumber_text.strip()) >= FALLBACK_MIN_CHARS                          # 100
    and cjk_count(plumber_text) >= FALLBACK_MIN_RECOVERY_CJK                 # 50(失败篇 pdfplumber 3772 命中,英文 0 不命中,75x margin)
    and cjk_count(plumber_text) > cjk_count(pypdf_text)                      # 比 pypdf 抽出更多中文
    and corruption_ratio(plumber_text) < corruption_ratio(pypdf_text)       # 坏率下降(失败篇 0 < 0.0237)
)
```
只有 pdfplumber **显著救回中文且坏率下降**才替换 pypdf,外科式限定在中文失败模式;否则 fail-open 回 pypdf。

**调用位置与顺序**(在 `PdfParser` 内,pypdf 抽完 raw_text 之后):
```
1. pypdf 逐页抽 → 组 pypdf_raw_text + pypdf_section_ids               # §3.1,主路不动
2. ★ if _pypdf_text_looks_corrupted(pypdf_raw_text):
       plumber_text, plumber_section_ids = _extract_with_pdfplumber(sandbox 内路径)
       if plumber_text is not None and _pdfplumber_is_meaningful_recovery(pypdf_raw_text, plumber_text):
           raw_text, section_ids = plumber_text, plumber_section_ids       # 采用 pdfplumber
       else:
           raw_text, section_ids = pypdf_raw_text, pypdf_section_ids       # fail-open,保留 pypdf
   else:
       raw_text, section_ids = pypdf_raw_text, pypdf_section_ids
3. equation locator regex / too-short 闸 / 组 ParsedDocument           # §3.1,不动,跑最终 raw_text
```
- **`_extract_with_pdfplumber` 用与 pypdf 主路相同的组装约定**:逐页抽、非空页前插 `[S{n}]`、`\n\n` 拼、`section_ids` 按页生成——保持 `locator_index` 契约一致(两路都 6 页,section_ids 通常一致)。
- **★ pdfplumber 在现有 sandbox 子进程内运行**:`PdfParser` 本就由 `run_in_sandbox` 包在 spawn 子进程里跑,fallback 就地调 pdfplumber、不新开进程;spawn/cwd/env/临时目录/Linux RLIMIT_AS 照旧作用于它(R6 已证)。
- **`cjk_count` / `corruption_ratio` 抽成模块内小工具**,predicate 与 recovery guard 共用同一实现。

### 4.2 ★ 逐条保住现有语义(不得退步)
- **pypdf 主路一字节不动**:`PdfReader(strict=False)` / 逐页 `extract_text()` / `[S{n}]` / `\n\n` / `.strip()` / equation locator / too-short 闸,全不改。
- **sandbox 隔离不削弱**:pdfplumber 不新开进程、不改 spawn/cwd/env/临时目录/RLIMIT(TASK-311 as-built 不回退)。
- **DocxParser 不碰**;**80k 下游闸不动**;**equation locator 行为不变**(跑最终 raw_text)。

### 4.3 ★ 错误处理边界 + 内存兜底 + 诊断计数
- **Python 异常层 fail-open**:pdfplumber import 失败 / 抽取内部 raise / 返回文本未达 recovery guard → 保留 pypdf、不 raise、记固定码(`pdfplumber_fallback_failed`,无堆栈/路径/filename)。最坏退回 pypdf 乱码(= 现状,无回归)。
- **★ 资源级硬失败不同进程 fail-open**:pdfplumber 触发 sandbox wall timeout / OS SIGKILL / 硬 OOM 时子进程已被杀,带不回 pypdf 结果 → 走 TASK-311 既有分类(`document_parse_timeout` / `document_parse_failed`)。本卡**不承诺此类硬失败回 pypdf**(与「不新开进程」一致取舍)。失败篇实测 ~1s、远不触 30s,实际不会碰到。
- **可选加固(实施自决,非必须)**:`_extract_with_pdfplumber` 内 per-page 软预算(超预算 `return None` → fail-open),覆盖「整体慢但单页不挂」;覆盖不了单页 `extract_text` 卡死(靠 sandbox timeout)。
- **内存兜底靠 sandbox**:`RLIMIT_AS`(512MB,Linux)约束 pdfplumber;病态 PDF 撑爆 → sandbox 干净失败,非 crash。
- **★ metadata-only 诊断计数**:记 `pypdf_chars` / `pypdf_cjk_count` / `pypdf_corruption_ratio` / `fallback_attempted` / `fallback_adopted` / `plumber_cjk_count` / `plumber_corruption_ratio`。**只记数值,不落文本/filename/堆栈**(decision 11)。

### 4.4 ★ 验收测试(挂既有 `tests/adapters/parser/test_pdf_parser.py`,现有用例继续全绿)
**A. predicate / guard 单测(纯逻辑,synthetic 文本;阈值边界钉死)——必做**:
1. 失败形态命中:非空白 ~6000、CJK=1、Cc 占 ~2.4% 的 synthetic 串 → `_pypdf_text_looks_corrupted` True。
2. 正常英文不命中:干净 ASCII、CJK=0、Cc=0 → False(条件 c)。
3. 正常中文不命中:CJK 占比 ~33% → False(条件 b)。
4. 近空/扫描件不命中:短串/空串 → False(条件 a)。
5. **边界:长英文 + 少量杂散 Cc,但 Cc 比率 < 0.005 → False**(阈值不过敏,R1)。
6. U+FFFD 形态命中:CJK 比率极低 + 足量 U+FFFD → True。
7. **CJK 比率边界**:CJK 比率略高于 0.01 → 判「有中文」不命中;略低于 0.01 且 Cc 够 → 命中(钉死 v0.3 的比率改动)。

**B. fallback 调用测(mock pdfplumber)——必做**:
8. 命中 + mock 返回 CJK=3772 且坏率 0 → 采用 pdfplumber、section_ids 按其页重建、equation locator 跑新文本。
9. **命中 + mock 返回 CJK=1(< 50,未达 recovery)→ 不替换、保留 pypdf**(护栏钉死:偶发中文不推翻)。
10. **命中 + mock 返回高 CJK 但坏率未下降 → 不替换**。
11. 命中 + mock 抛异常 → fail-open 保留 pypdf、不 raise、记固定码。
12. predicate 不命中 → pdfplumber **根本不被调用**。

**C. 真论文验证(manual,合并前 Codex 跑;样本仓库外、不进 fixture)——必做,预期即 §3.2/§3.3 实测**:
```
样本            触发pdfplumber  采用pdfplumber  结果
PDF-2 失败篇     是              是              CJK 1→3772,走通 PaperSpec 抽取
PDF-1 正常中文   否(条件b挡)    —               pypdf 原样,CJK 3762 不变
正常英文         否(条件c挡)    —               pypdf 原样,输出不变
```

**D. 依赖 review**:版本钉死(含 pin Pillow==12.2.0);二进制 wheel 在 CI ubuntu 装/跑。

### 4.5 验证 checklist(合并前)
- `make check` 完整跑到「All checks passed!」。
- A/B 全部测试全绿;现有 parser 测试继续全绿。
- 无对外 schema 改动 → `make export-schema && make verify-schema` 零 drift(仍跑确认)。
- 无前端改动 → 无 pnpm/smoke/截图。
- Linux 靠 CI:新增测试 + pdfplumber 二进制 wheel 在 CI ubuntu 装/跑绿。
- C 真论文验证已跑(三样本结果如 §4.4 表),Codex 如实报。
- `git diff --check`/`--cached` 过;隐私 grep:无 `logger.exception`/`str(exc)`/`repr(exc)`/`exc_info`,无文本/路径/filename 落日志。
- 合并前亲核真 diff:改动**只在 `pdf_parser.py`**(+ 测试 + requirements),pypdf 主路逐字未动,fallback 只在坏信号命中时启动。

---

## 5. 反例 / 红线(不许这样修)

- **✗ 不许整体换 pdfplumber**;只加 fallback 分支。
- **✗ 条件 b 不许写死 `cjk_count==0`**:失败篇实测 CJK=1,必须用比率(§4.1)。
- **✗ 不许只看「无中文」触发**:必须叠加控制字符损坏信号(条件 c)。
- **✗ 替换护栏不许停在 `CJK>0`**:必须"有意义中文恢复"(≥50 + 坏率下降,§4.1)。
- **✗ corruption 不许扩到「非 ASCII 比例高」**:误伤含符号英文。核心层 `Cc∪U+FFFD` 已实测够用。
- **✗ 不许用 LLM / 启发式「猜乱码」**:纯确定性 predicate。
- **✗ 不许让 pdfplumber 绕过/新开 sandbox**:就地在现有 sandbox 内跑(TASK-311 as-built 不回退)。
- **✗ Python 异常必须 fail-open 回 pypdf、不 crash**;但**不许声称「所有 fallback 失败都回 pypdf」**——资源级硬杀由 sandbox 兜(§4.3)。
- **✗ 不许泄露文本/filename/堆栈**:fallback + 诊断计数只落固定码 + 数值。
- **✗ 不许动 pypdf 主路 / equation locator / too-short 闸 / 80k 下游闸**。
- **✗ 阈值不许改动**:四常量已按真样本校准(§4.1),实现照抄;若实测发现某样本判定与 §4.4 表不符,停手报架构师(说明基线变了)。

---

## 6. Stage 0 可落性 gate — ✅ 全绿(可进实现)

1. **✅** `PdfParser` 现状与 §3.1 一致。
2. **✅** 全仓库 PDF 抽取只 `pdf_parser.py:49` 一处。
3. **✅** 失败 fingerprint live 复现:PDF-2 pypdf chars=8767 / CJK=1 / Cc 149 个;corruption_ratio + codepoint 类别实测齐(§3.2)。
4. **✅** pdfplumber 在 live sandbox 内复跑通:失败篇 CJK=3772、chars<80000(§3.3)。
5. **✅** 依赖装通 + 许可证 permissive + Linux wheel 下载验证;真运行靠 CI(§3.5)。
6. **✅** 归属定案:PdfParser 由 TASK-501 引入 → 论文线、编号 523、修复卡不占计数。

**★ Stage 0 结论**:六项全绿,四阈值实测校准 + 三样本验证全对 → **可进实现**。

---

## 7. 明确不在本卡、单独排的后继

- **纯 printable-glyph 乱码(无 Cc/U+FFFD)**:若某坏法把中文映射成普通 Latin/希腊/符号且无控制字符 → corruption_ratio 不够、漏判。核心层覆盖当前失败篇(靠 149 个 Cc);全新坏法需新样本,再考虑启用 Co/CID 扩展层或别的确定性信号(**✗ 仍不用「非 ASCII 比例高」**)。
- **少量 CJK 残留(比率 > 1%)型乱码**:v0.3 条件 b 覆盖到 cjk_ratio ≤ 0.01;若某乱码残留中文比率更高(如 5%)会漏,届时调 `FALLBACK_MAX_PYPDF_CJK_RATIO` 或加别的信号。
- **局部单页 mis-decode**:整篇比率被正常页稀释 → 漏。本卡目标整篇;局部按页 fallback 排后。
- **扫描件 / 图片型 PDF OCR**:走既有 too-short;OCR 独立能力、不在此。
- 解析器抓图 / 公式渲染 / 逐行可点出处等升级(既有独立线)。

---

## 8. 双审结论 + Stage 0 结果

**R1(GPT 设计审)= 条件通过**,P1 已并入(P1-1 护栏"有意义中文恢复" / P1-2 corruption 分母 + 字符集待 probe / P1-3 fail-open 边界 / P2-1 已知漏判 / P2-2 诊断计数)。R1 P1-2 的"异常 glyph 可能是 PUA/CID"经 R6 probe 证否(实测 Co/CID 零贡献),核心层 `Cc∪U+FFFD` 即够。R1 P2-1 预警的"少量 CJK 残留"经 R6 实测确认存在(失败篇 CJK=1)、v0.3 已用比率修正。

**R6(Codex 可落核)= 条件可落 → 定稿**:
- ✅ §3.1 一致 / 全仓库 PDF 抽取一处 / 下游符合 / pdfplumber sandbox 复跑通 / 依赖装通。
- ✅ 归属定案(TASK-501 引入 → 523 论文线)。
- ✅ 真样本实测:失败篇 fingerprint + codepoint 类别分布 + 三样本 corruption/CJK 值全测(§3.2/§3.3/§3.5)。
- 提出并修正:失败篇 CJK=1(非 0)→ 条件 b 改比率。

**四阈值实测校准 + 三样本验证全对**(§4.4 表),**Stage 0 六项全绿** → **v0.3 定稿,进实现**。

---

**本卡版本**:v0.3 定稿(2026-07-04)
**作者**:Claude(架构师)
**归属**:paper-to-model 线 TASK-523;`adapters/parser/pdf_parser.py` 加 pdfplumber fallback(坏信号命中才启,采用护栏 = 有意义中文恢复;四阈值实测定死)+ 新增依赖(pin Pillow==12.2.0);pypdf 主路不动;DocxParser 不受影响;sandbox 隔离不削弱(TASK-311 as-built 不回退)。
**v0.2 → v0.3**:① 条件 b `cjk_count==0`→CJK 比率(实测失败篇 CJK=1)。② 四阈值实测定死(MIN_CHARS=100 / MAX_PYPDF_CJK_RATIO=0.01 / CORRUPTION_RATIO=0.005 / MIN_RECOVERY_CJK=50)。③ corruption 字符集定核心层 `Cc∪U+FFFD`(Co/CID 实测零贡献)。④ 依赖 review 过 + pin Pillow==12.2.0。⑤ 三样本判定验证全对、Stage 0 全绿、可进实现。
