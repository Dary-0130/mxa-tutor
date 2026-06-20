# TASK-500:paper-to-model 开门 chore(5 项前置硬门槛一锅炖)

## 状态

🔲 **v0.2.2**(2026-06-20 微补丁:fixture 数据自洽 + R2 真值源事实表 + 文档说明同步,因 TASK-503 v0.2.4 派单期发现 fixture 命名 / FIG caption 糊 / 缺 R2 真值源 5 类缺口 reopen;v0.2.1 主体已合并入仓,本版仅 surgical 追加门槛 5 内 5 类改动 + 1 类新增子段,**不动 4 项已交付门槛主体 + 不改 06 / 04 既有字面**)

- v0.1:架构师起稿,2 个 challenge 点待 PM 拍板。
- v0.1.1:PM 拍板两项 challenge,架构师自审补 2 个漏点。
- v0.2:GPT R1 一审 reject(3 P0 + 8 P1 + 4 P2);架构师全部采纳。
- v0.2.1:GPT R1 复审 conditional pass(0 P0 + 3 P1 + 3 P2);架构师全部采纳。**v0.2.1 主体已 PR #93 合并入仓(决策 22 配套)**。
- v0.2.2:TASK-503 v0.2.4 派单期取证 16 实测发现 5 类 fixture / 文档缺口:
  - **C1**:MISS-006 在 `expected_missing_prompts.json` 与 `user_supplied_params.json` parameter_name 长 / 短版冲突,production merge 会因 `parameter_name_mismatch` 崩(取证 16 § A2/A3)
  - **C2**:`expected_updated_plan.json` 6 条 user_supplied paper_param_name 带"(用户补充)"前缀,与 production merge 行为(replace 不加前缀)不齐,actual_updated_plan 与 golden 必然 diff(取证 16 § A4)
  - **C3**:FIG-01 caption 提"p 极对数"但 expected_missing_prompts 未列;FIG-02 caption 写糊"完整参数"未列具体三项(变比 / X_T / 接线方式)(取证 16 § A1)
  - **C4**:无 R2 真值源事实表(冲突型 / 幻觉型误报无判分依据;TASK-503 v0.2.4 R1a/R2 死规则判分前置)
  - **C5**:`scoring_template.md` line 71/151/152/186-187 + `case_README.md` missing line 16/40/51/106/110-111 + `verification_method.md` line 39/43 仍写"固定 6 个 missing prompts" / "B1/B2 recall/precision" / "E2 集合相等"等口径,与 TASK-503 v0.2.4 R1a/R2/R3/R4/R5 死规则判分方向冲突

---

## 上下文(v0.2.2 增量)

> v0.2.1 上下文(决策 22 § 10.4 锁定 5 项前置硬门槛、不拆 chore、PM 拍 2026-06-15 五项一锅炖、产出 = 文档与规范层不写功能代码)保留不变。

**v0.2.2 触发**(2026-06-20):

- TASK-503 v0.2.4(原 v0.2.3 升级)起草期发现 missing_param case 当前 fixture + 文档说明与新口径(R1a/R2/R3/R4/R5 死规则判分 + 5D 双轴状态)字面不齐
- 取证 15(2026-06-19)+ 取证 16(2026-06-20)逐字摘出 5 类缺口
- 决策 12 v0.4 R2 公开 challenge:PM 拍板范围归属 ABAA(fixture 数据 + R2 真值源 + 文档口径 ∈ TASK-500 v0.2.2 微补丁;判分代码改造 + 双轴 + per-case scorer ∈ TASK-503 v0.2.4;长期 decision = 新建 25)
- 依赖顺序:**TASK-500 v0.2.2 先合 → TASK-503 v0.2.4 rebase**(单向前置,违 = TASK-503 R6 真跑 fixture 命名 merge 崩)

---

## 5 项门槛拆解

> 门槛 1-4 主体 v0.2.1 已交付,本版不动字面;门槛 5 内追加 v0.2.2 子段 "5.2 数据自洽 + R2 真值源 + 文档口径同步(v0.2.2)"。

### 门槛 1(v0.2.1 完工,本版不动)

06 契约新增三套 schema(PaperSpec / ModelGenerationPlan / TuningSuggestion):**已交付,v0.2.2 不动字面**。

### 门槛 2(v0.2.1 完工,本版不动)

MissingParameterPrompt + EvidenceSource + PaperEvidenceEntry 双源契约:**已交付,v0.2.2 不动字面**。

### 门槛 3(v0.2.1 完工,本版不动)

04 文档上传安全 § 8.6(7 子项):**已交付,v0.2.2 不动字面**。

### 门槛 4(v0.2.1 完工,本版不动)

v0.1 对外口径(前端 / 销售 / API / README):**已交付,v0.2.2 不动字面**。

### 门槛 5(v0.2.1 完工 + v0.2.2 增量补丁)

#### 5.1 v0.2.1 已交付(本版不动)

- `eval/cases/paper_to_model/README.md`
- `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/`(input / golden / case_README)
- `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/`(input / user_input / golden / case_README)
- `eval/cases/paper_to_model/scoring_template.md`
- `eval/cases/paper_to_model/verification_method.md`

#### 5.2 v0.2.2 数据自洽 + R2 真值源 + 文档口径同步(本版增量)

> **改动范围**:仅 missing_param case fixture + 公共文档(scoring_template + verification_method);**不动 material_to_plan case fixture**(取证 16 § A8:material `case_README.md` grep `E2|user_supplied` 无命中,无字面需改)。

##### 5.2.1 改动项(7 文件 surgical 改 + 2 文件新增)

| 编号 | 文件 | 改动 | 锚点 |
|---|---|---|---|
| (a) C3.1 | `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/source_doc_stripped.md` | FIG-01 caption 微删"p 极对数"(只留 H / F 与 expected_missing_prompts 一致) | line 73(取证 16 § A1 实测) |
| (b) C3.2 | 同上 | FIG-02 caption 补具体三项:**变压器变比 / 漏阻抗 X_T / 接线方式(连接组别)**(替代糊语"完整参数") | line 77 |
| (c) C1 | `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/expected_missing_prompts.json` | MISS-006 `parameter_name` 改短版 `"电机初相角 α0"`;长说明搬 paper_reference.excerpt(已含 `"根据电机初始化工具的截图可得,定子侧电流 a 相滞后电压 -4.43°"`,不动) | MISS-006 entry |
| (d) C2 | `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/golden/expected_updated_plan.json` | 6 条 `source: user_supplied` 的 `paper_param_name` 改长版去"(用户补充)"前缀,与 expected_missing_prompts 端 parameter_name 逐字一致 | parameter_mapping 中 line 119-124(取证 16 § A4 实测) |
| (e) C5.1 | `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/case_README.md` | 改死规则口径(删 B1/B2 / 删"固定 6 个 missing prompts" / 加降级注:`expected_missing_prompts.json` + `expected_updated_plan.json` 降级为参考样例);降级注简短,引用 `verification_method.md` 详细说明 | line 16 / 40 / 51 / 106 / 110-111(取证 16 § A5 实测确认) |
| (f) C5.2 | `eval/cases/paper_to_model/scoring_template.md` | 改死规则口径:删 B1/B2 recall/precision 描述 + 删"6 个固定 missing prompts"口径 + 加 R1a-pre/R1a-post/R2/R3/R4/R5 死规则评分流程(missing case);material case 评分流程不动(material 仍人工 + 自动) | line 71 / 151 / 152 / 186-187(取证 16 § A6 实测确认) |
| (g) C5.3 | `eval/cases/paper_to_model/verification_method.md` | 改死规则口径:missing case 全自动(R1a/R2/R3/R4/R5 五条死规则);material case 仍人工 + 自动 | line 39 / 43(取证 16 § A7 实测确认) |
| (h) C4.1 | `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/r2_truth_source/document_facts.json` | **新增**:R2 真值源事实表(15 项 `document_given_values` + 0 项 `document_not_mentioned` 初始空白);locator 单源 source_doc markdown 标题 + 行号(missing case 无 `expected_paper_spec.json`,无 PaperSpec section_id 双源) | 新建文件 |
| (i) C4.2 | `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/r2_truth_source/README.md` | **新增**:R2 真值源用途说明(评测专用 / actor 不读 / 与 expected_missing_prompts 区别 / 维护责任 = 架构师起草 + PM 核审) | 新建文件 |

##### 5.2.2 d 项命名统一表(C2 改动)

| 旧字面(expected_updated_plan paper_param_name) | 新字面(逐字与 expected_missing_prompts parameter_name 一致) |
|---|---|
| `(用户补充) 同步机惯性时间常数 H` | `同步发电机惯性时间常数 H` |
| `(用户补充) 同步机摩擦因数 F` | `同步发电机摩擦因数 F` |
| `(用户补充) 变压器变比` | `变压器变比(原边/副边电压比)` |
| `(用户补充) 变压器漏阻抗 X_T` | `变压器漏阻抗 X_T` |
| `(用户补充) 变压器接线` | `变压器接线方式(原边 / 副边连接组别)` |
| `(用户补充) 电机初相角 α0` | `电机初相角 α0`(短版,同 c 项 MISS-006 统一) |

##### 5.2.3 b 项 FIG-02 caption 改写(C3.2)

旧字面(取证 16 § A1 line 77):

```text
> **[FIG-02:变压器参数图]**(v0.1 系统无 OCR,图片信息丢失;论文在此提供 Three-Phase Transformer 完整参数,文字未给出任何变压器具体数值。系统应识别为缺失参数,等待用户补充。)
```

新字面:

```text
> **[FIG-02:变压器参数图]**(v0.1 系统无 OCR,图片信息丢失;论文在此提供 Three-Phase Transformer 参数 — 包括 **变压器变比(原边/副边电压比)** / **变压器漏阻抗 X_T** / **变压器接线方式(原边 / 副边连接组别)** 三项,文字未给出任何变压器具体数值。系统应识别这三项为缺失参数,等待用户补充。)
```

##### 5.2.4 a 项 FIG-01 caption 微调(C3.1)

旧字面(取证 16 § A1 line 73):

```text
...可能含本文档第 2 节文字之外的额外参数如 H 惯性时间常数 / F 摩擦因数 / p 极对数等...
```

新字面:

```text
...可能含本文档第 2 节文字之外的额外参数如 H 惯性时间常数 / F 摩擦因数 等(系统应识别这两项为缺失参数,等待用户补充)...
```

> 删 "p 极对数" 是为保 FIG-01 caption ↔ expected_missing_prompts MISS-001/MISS-002 字面一致(后者只列 H/F,不含 p)。SUT 漏报 p 在新 R2 口径下不算冲突 / 不算幻觉(p 不在 document_facts.json),R2 不判错;但 caption 暗示 p 而 prompts 没列会让 v0.2 多 case judge 产生不必要 noise,本版微调消除该不一致。

##### 5.2.5 e/f/g 项文档口径改造方向(C5.1/2/3)

> Codex 实施时 view 三文件,逐 line 实测字面,执行 str_replace。本表给改动方向 + 锚点,**不给逐字 old_str / new_str**(避免取证摘字面有遗漏导致 str_replace 失败,Codex 应以 main 实测字面为真值源)。

| 文件 | 锚点 line | 当前口径(取证 16 印象确认) | 新口径(v0.2.2 改造方向) |
|---|---|---|---|
| `case_README.md` missing | 16 / 40 / 51 / 106 / 110-111 | "6 个固定 missing prompts" / "B1 recall + B2 precision" / "E2 集合相等" | "R1a-pre/R1a-post 死规则 + R2 真值源(冲突 / 幻觉)+ R3 一票否决(来源真实性)+ R4 一对一基数 + R5 全链 canonical name 一致";数量不约束;**降级注**:`expected_missing_prompts.json` + `expected_updated_plan.json` 降级为参考样例,evaluator 不读,详见 `verification_method.md` |
| `scoring_template.md` | 71 / 151 / 152 / 186-187 | "B1/B2 + 固定 6 个" missing 评分流程 | missing case = R1a/R2/R3/R4/R5 五条死规则全自动(无人工 / 无 partial / 无 ✅ 🟡 维度);material case 评分流程 = R1a 不适用 / R2 不适用 / R3 = 无 user_supplied mapping(原 E2 material 分支改名,行为不变)/ 其余 metrics 不动(A1 / C2 / C3 / D1 + 人工 A2 / C1 保留) |
| `verification_method.md` | 39 / 43 | "本 chore 阶段 = 人工对照;TASK-501 落地后 = 自动对比 actual vs golden" | missing case = TASK-503 v0.2.4 evaluator 五条死规则全自动(R1a/R2/R3/R4/R5);material case = TASK-503 v0.2.4 evaluator 自动 metrics(A1 / C2 / C3 / D1 / E1 / R3 替代旧 E2)+ 保留人工 A2 / C1 |

##### 5.2.6 h 项 r2_truth_source/document_facts.json schema 与字段

详 配套数据文件 `r2_truth_source-document_facts-v0_2_2.json`。15 项 `document_given_values` 字面取自取证 16 § A1 line 27-41 实测,逐字摘录;`document_not_mentioned` 初始空白(`[]`),开放世界白名单留 case 增加时按需补。

##### 5.2.7 i 项 r2_truth_source/README.md

详 配套文件 `r2_truth_source-README-v0_2_2.md`。约 30 行,简短说明:用途 / 与 expected_missing_prompts 区别 / actor 不读保证 / 维护责任 / locator 单源原因。

---

## 不做(v0.2.2 增量)

> v0.2.1 不做项(不落 paper_*.py domain / 不写 features/paper/ 代码 / 不写 PDF/docx 解析器 / 不引依赖 / 不写 PaperPlanService / 不动 features/overview/ + features/explanation/ / 不动 project_overview 三件套)保留不变。

v0.2.2 新增不做:

- ❌ **不动 material_to_plan case fixture**(取证 16 § A8 实测 `case_README.md` grep `E2|user_supplied|user-supplied` 无命中,无字面需改)
- ❌ **不动 material `case_README.md`**(同上)
- ❌ **不动 06 § 12 三套 schema 字段表**(v0.2.1 已交付)
- ❌ **不动 04 § 8.6 7 子项**(v0.2.1 已交付)
- ❌ **不动 README + 前端 / API 对外口径**(v0.2.1 已交付)
- ❌ **不写 evaluator 代码**(留 TASK-503 v0.2.4;TASK-500 v0.2.2 只动 fixture 数据 + 文档说明)
- ❌ **不动 `eval/_paper_eval_metrics.py` / `_paper_eval_csv.py` / `run_paper_eval.py`**(同上)
- ❌ **不改 03 索引 TASK-500 状态字面**(v0.2.2 是 reopen 微补丁,合并后 PM 决定是否补 03 索引 v0.2.2 备注)

---

## 红线(v0.2.1 + v0.2.2)

> v0.2.1 红线(features/overview/ + features/explanation/ + project_overview 三件套 + EvidencePack 既有字段 + 不引依赖 + paper feature 不 import overview/explanation 私有结构 + 决策 22 § 5.2 配套红线)保留不变。

v0.2.2 新增红线:

- ❌ **不在 `eval/cases/paper_to_model/material_to_plan/` 任何文件改字面 / 改 schema**
- ❌ **不删 / 不改 `expected_missing_prompts.json` 与 `expected_updated_plan.json` 文件本身**(只降级为参考样例,文件本身字面不动 — 除 c 项 MISS-006 短版 + d 项 paper_param_name 去前缀两类必改;case_README 写降级注)
- ❌ **不在 `r2_truth_source/` 下放任何 actor 输入路径文件**(防答案泄漏)
- ❌ **不修 `paper_user_supply_service.py` 或其他 production code**(归 TASK-503 v0.2.4)

---

## 验收标准(v0.2.2 增量)

> v0.2.1 主体验收已 PR #93 通过,本版只新增 v0.2.2 改动项 checkbox。

- [ ] (a) FIG-01 caption line 73 微删 "p 极对数" 完成,新字面如 5.2.4 节
- [ ] (b) FIG-02 caption line 77 补三项完成,新字面如 5.2.3 节
- [ ] (c) MISS-006 `parameter_name` 改短版 `"电机初相角 α0"` 完成
- [ ] (d) `expected_updated_plan.json` 6 条 user_supplied paper_param_name 改长版去前缀完成(命名统一表 5.2.2)
- [ ] (e) missing `case_README.md` line 16/40/51/106/110-111 死规则口径改造完成 + 降级注简短
- [ ] (f) `scoring_template.md` line 71/151/152/186-187 死规则口径改造完成
- [ ] (g) `verification_method.md` line 39/43 死规则口径改造完成
- [ ] (h) 新增 `r2_truth_source/document_facts.json`(15 项 + 0 项 not_mentioned + locator 单源)
- [ ] (i) 新增 `r2_truth_source/README.md`(简短说明)
- [ ] R6.2 验证(v0.2.2 增量):
  - `git grep -nE "B1|B2|6 个固定|MISS-001|MISS-002|MISS-003|MISS-004|MISS-005|MISS-006|blocked_known_defect" -- eval/cases/paper_to_model/missing_param/ eval/cases/paper_to_model/scoring_template.md eval/cases/paper_to_model/verification_method.md` 命中清单合理(MISS-00N 在 fixture json 中保留参考样例字面;`B1/B2/6 个固定/blocked_known_defect` 在 missing case 文档 + scoring_template + verification_method 中**应为 0 命中**)
  - `git grep -n "(用户补充)" -- eval/cases/paper_to_model/missing_param/case_01_missing_image_param/golden/expected_updated_plan.json` 应为 0 命中(d 项已去前缀)
  - `git grep -nE "电机初相角 α0\(初始化结果" -- eval/cases/paper_to_model/missing_param/` 应仅在 `expected_missing_prompts.json` 命中 1 次(其 `paper_reference.excerpt` 字面保留;`user_supplied_params.json` MISS-006 entry 已改短版,**应 0 命中**)
  - `git diff --name-only origin/main` 改动文件清单仅在以下 v0.2.2 范围内:
    - `docs/tasks/task-500-paper-to-model-open-door-chore.md`(改:版本号 v0.2.1 → v0.2.2 + 状态行 + 修订历史 + 新增 5.2 子段 + 验收标准 v0.2.2 增量 + 不做 / 红线 v0.2.2 增量)
    - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/source_doc_stripped.md`(改:a/b)
    - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/expected_missing_prompts.json`(改:c)
    - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/golden/expected_updated_plan.json`(改:d)
    - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/case_README.md`(改:e)
    - `eval/cases/paper_to_model/scoring_template.md`(改:f)
    - `eval/cases/paper_to_model/verification_method.md`(改:g)
    - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/r2_truth_source/document_facts.json`(新增:h)
    - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/r2_truth_source/README.md`(新增:i)
    - 任何范围外文件改动 → Codex 停手报 PM
  - **红线文件未动实测**(逐个跑):`git diff --name-only origin/main -- <redline_path>` 应为空输出
    - `eval/cases/paper_to_model/material_to_plan/`(整目录)
    - `eval/cases/paper_to_model/README.md`
    - `docs/06_OUTPUT_CONTRACTS.md`
    - `docs/04_ENGINEERING_STANDARDS.md`
    - `features/overview/` / `features/explanation/`
    - `eval/_paper_eval_metrics.py` / `eval/_paper_eval_csv.py` / `eval/run_paper_eval.py`

---

## 估时(v0.2.2 增量)

Codex 实施:**0.5 天**(纯 fixture + 文档改动,7 文件 surgical 改 + 2 文件新增,无功能代码)

R 轮:R6.2(Codex 完工实测自审)+ PM 兜底,**0.5 天**

总计:**1 天完工**

---

## 工艺(v0.2.1 + v0.2.2)

> v0.2.1 工艺(决策 12 v0.4 R1 + R6 + PM)保留不变。v0.2.2 微补丁因不动设计 / 不动契约 / 不动产品口径,**R1 GPT 审跳过**,直接 R6 实测 + PM 兜底。

- **本任审批级别(v0.2.2)**:**fixture / 文档修订类**,降级为 R6 + PM(无 R1)
- **R6.2**:Codex 完工实测(grep R6.2 列表 + git diff --name-only 范围 + 红线文件未动)
- **PM 兜底**:PM 直接 review v0.2.2 改动 + R6.2 报告
- **K_28a 自防**(架构师 v0.2.2 起稿期):取证 16 § A1-A10 + A8 grep + C1 decision 编号实测,所有 5 类改动方向均锚源码 / 锚行号 / 锚 grep 命中

---

## 给 Codex 的提示(v0.2.2)

按宪法 § 5 沟通模板。**v0.2.2 不需 Stage 0 摸底**(reopen 微补丁,基线已是 v0.2.1 合并入仓状态,无 schema 假设)。Codex 直接进 Stage 1 实施:

1. **Base commit 校验**:PM 派单时提供 base commit hash;Codex 验证 main 含 v0.2.1 PR #93 squash commit + TASK-503 v0.2.3 任务卡(若已入仓)。若漂移 → 停手报 PM
2. `git status` 工作树洁;有 untracked 报 PM 后再开工
3. **改动顺序自由,建议**:
   - a + b(FIG-01/02 caption 微调,1 文件 surgical 改)
   - c(MISS-006 短版)
   - d(expected_updated_plan paper_param_name 去前缀,6 条同时改)
   - e + f + g(文档口径改造,3 文件 surgical 改)
   - h + i(新增 r2_truth_source 子目录 + 2 文件)
4. 每个改动项完工 → `git diff --name-only origin/main` 自审范围 → 下一项
5. **str_replace 实施纪律**:每文件先 `view` 实测当前字面 + 行号,再执行 str_replace;**不许凭印象 / 转述写 old_str**(K_28a 防御)
6. **e/f/g 改造时不许整段重写**:逐 line surgical 改 / 加(防漂移)
7. 全部完工 → R6.2 完工实测三件套:
   - **范围实测**:`git diff --name-only origin/main` 输出在 5.2 表 + 验收标准 v0.2.2 范围清单内
   - **字面残留扫描**:验收标准 R6.2 验证段四个 grep 全跑 + 输出贴 PR
   - **红线文件未动实测**(逐个跑):`git diff --name-only origin/main -- <redline_path>` 应为空;命令输出贴 PR
8. PR 完工 report 必须按 R6.2 实证,不许凭主观范围声明(决策 12 v0.4 R6.1 沿用)

---

**版本**:v0.2.2(2026-06-20 微补丁,reopen v0.2.1 主体之上 surgical 追加 5 类改动 + 1 类新增子段)
**作者**:Claude(架构师,接手第 49 任)
**关联决策**:`docs/decisions/20260615-22-direction-pivot-paper-to-model.md` § 10.4;`docs/decisions/20260620-25-evaluator-dual-axis-and-per-case-scorer.md`(新长期 decision,本版同期入仓)
**关联宪法**:v3.0
**关联工艺**:决策 12 v0.4(R6 + PM;v0.2.2 跳 R1 因 fixture 修订类)
**入仓**:本版 patch 入仓与 TASK-503 v0.2.4 任务卡 + decision 25 同一 PR(由 PM 决定 PR 组合策略)

**修订历史(v0.2.2 增量条目)**:

- v0.1(2026-06-15):架构师起稿,2 challenge 待 PM 拍板
- v0.1.1(2026-06-15):PM 拍板 + 架构师自审补 2 漏点
- v0.2(2026-06-15):GPT R1 一审 reject 15 条全采纳
- v0.2.1(2026-06-15):GPT R1 复审 conditional pass + 6 条全采纳;**主体 PR #93 合并入仓**
- **v0.2.2(2026-06-20)**:TASK-503 v0.2.4 派单期取证 16 实测发现 5 类 fixture / 文档缺口(C1 MISS-006 长短版冲突 / C2 expected_updated_plan 前缀冲突 / C3 FIG-01/02 caption 不齐 / C4 缺 R2 真值源 / C5 文档口径仍写 B1/B2/6 个固定),架构师据 PM ABAA 范围拍板起 v0.2.2 微补丁(7 文件 surgical 改 + 2 文件新增;不动 v0.2.1 已交付 4 项门槛主体 + 不动 material case fixture)。**本任反例账(v0.2.2 +1)**:架构师设计稿 v1 凭交接包 § 4 转述写"12 项参数"(K_28a 同源,实测 15 项;取证 16 § A1 拦下)+ 凭印象写 decision 编号 23(K_28a 同源,项目知识库实测最大 24,正确为 25);均未流入 v0.2.2 实施
