# TASK-524:build_steps 红线机检 `parameter_value_leak` 误报修复(display_text 退扫 + context-aware 裸值收紧)

**版本**:v0.3(R1 双审 + R6 现状核 + Stage 0 已执行 + 架构师并意见/撤回定稿;**待 Codex 在干净基线实现**)
**所属线**:paper-to-model(decision 22 5xx;**修复卡,不占 paper-to-model 完工计数**,与 TASK-523 / TASK-311 一致)
**前置**:TASK-507-B(build_steps 生成 + 11 条校验 + 红线机检 + 证据双源,已合并 main PR #136 / `2ae688a`)已在;507-A 契约在;508 前端在
**现状基线**:诊断取证 + Stage 0 @ live `origin/main` HEAD `68c36e6`(现状全部逐字实测通过,见「现状事实」+「Stage 0 执行结果」节);**实现前 Codex 复核最新 HEAD**
**卡号**:live `origin/main` 已含 523、**524 未被占**(Stage 0 已核)

---

## 状态
🔲 v0.3(双审 + Stage 0 + 并意见定稿;待 Codex 在干净 origin/main 基线实现)

## 本版改动(v0.2 → v0.3,Stage 0 结果 + 架构师并意见/撤回)
- **[撤回并意见 B]** 原「冲突守门与主修一致不扫 display_text」**撤回**。Codex Stage 0 反例证伪原推理:`target='0'` + `setting_name='05'` 经 config 派生(`.` 连接)→ display_text `Configure: 0.05`,单扫原始字段各为孤立短整数不命中、拼接后现高特异值。⇒ **冲突守门保留扫 display_text**(回到 R1 Q3 原判断)。
- **[冲突守门坍缩为零改动]** Stage 0 证冲突守门现状已独立:source = `spec.parameter_conflicts`、不复用普通红线裸 unit token。本卡主修仅移除**普通红线**对 display_text 的扫描,**不波及**独立冲突守门。⇒ **本卡对冲突守门零改动**;v0.2 §4「若耦合则独立化」条件分支坍缩(不耦合、source 已独立)。
- **[跨字段拼接缺口具体化]** R1 已裁决的「跨字段拆分泄漏接受不抓」补实例:`0`+`05`→`0.05` 这种,普通红线(不扫 display_text)接受不抓(普通值场景);冲突值场景由冲突守门扫 display_text 兜。config-redline **不**加拼接检查(否则回扫 display_text、重引伪命中)。不对称有意为之(冲突场景更严)。
- **[新缺口记档归后继]** 冲突守门只扫 display_text、不扫 `instruction`(instruction 不进 display_text 派生)⇒ instruction 里的冲突值漏抓 = 既有正交漏检缺口,与 `library_path` 并列归后继,**不在本卡补**。
- Stage 0 现状核实结果并入(全部通过);实现门 Stage 0 简化为「复核最新 HEAD + 工作区干净基线」。

## 上下文

TASK-523 端到端 E2E 照出一个**下游、与 523 无关**的问题:build_steps 结构化步骤生成,在**正常中文 / 英文论文上也系统性触发降级**(`reason_code=parameter_value_leak`)→ 整份 `build_steps` 丢 `None` → 退回 legacy 纯文字步骤。正常论文几乎每次降级 = 507-B / 508 结构化步骤功能**在真实中文语料上等于没生效**,前端永远只拿到 legacy 文字版。砸「能不能用」。

本卡走完「诊断先于修」(decision 15):取证定位 → R1 设计审 + 复审 + R6 现状核 + Stage 0 + 架构师并意见/撤回。**只改 507-B 红线机检口径(对内),不碰对外契约。**

## 诊断结论(取证已坐实)

红线机检(507-B)防 AI 在步骤文字塞无出处值 / 替填 / 调参数字。**live 三子规则**:(a) 参数名+完整值 40 字符窗口邻近 → `parameter_value_leak`;(b) 裸数字 / unit token 裸出现 → `parameter_value_leak`;(c) 倍率/调参 → `tuning_value_leak`。受检字段:`title`/`intent`/`block_refs[*].purpose`/`connection_hints[*].signal_meaning`/`configuration_hints[*].instruction` + 派生 `display_text`。

**病灶**:两中文样本首个命中都是 (b) 的 **unit token**,撞**单字符 ASCII 单位**(中文电机论文单位多单字母,步骤文字满是英文如 `A 相`/`s 域` → 必撞);命中都在 **display_text**(拼接组合出命中面);英文 Attention(无单位参数)不触发 → 反证病根是单字母单位非数字。**后果非真丢**:退回 legacy 文字版(非空、数量对齐)。

## 现状事实(R6 live @ `68c36e6` 逐字实测,本卡地基)

1. **主修地基成立**:`_derive_display_text(self, step)` 只接收 `step`、无 mapping 入参/闭包,只拼白名单字段,不 dereference `parameter_mapping.value/unit`、不引 evidence excerpt / LLM raw、`library_path` 未拼进。
2. **block_type / 参数名派生前兜底**:规则 3(`parameter_refs` 复合键 exact-match)/ 规则 5(`block_refs` normalized exact-match)在 `_derive_display_text` 之前 fail-fast。
3. **config `target`+`setting_name` 无兜底**:仅非空 string、无 enum / exact-match reject;`solver/powergui/simulation` 仅在 `_is_allowed_config_hint()` 当 instruction 例外判定;红线现只扫 `instruction`。

## Stage 0 执行结果(Codex @ `68c36e6`,全部通过 / 记两缺口)
- HEAD `68c36e6`(live)、524 未占、origin/main 已含 523。
- 现状事实 1/2/3 全部复核成立(主修命根成立)。
- **冲突守门现状**:source = `spec.parameter_conflicts`(独立、不复用普通红线裸 unit token);**扫 `step.display_text`**、**不扫** raw `title/intent/purpose/signal_meaning/target/setting_name`。⇒ 本卡零改动(见修复方案 §4)。
- **跨字段拼接反例**(证伪原「预期无绕过路径」):`target='0'`+`setting_name='05'` → display_text `Configure: 0.05`。裁决见 §4 + 风险节。
- **`library_path`**:LLM 自由字段、schema 仅非空可 null、不进 display_text、不被红线扫、规则 5 exact-match 只看 block_type/purpose ⇒ 本卡外独立漏检缺口,归后继不改。
- 红线纯 Python 对内、不需动 schema / `paperTypes.ts` / exporter。
- **实现门阻塞(环境,非设计)**:Codex 当前 checkout 在旧分支 `codex/task-311-sandbox-deadlock-fix`(upstream gone,HEAD `be7af88` ≠ live main),工作区有 311 v0_4 / 523 卡 / decision-26 等未提交尾巴 → 不满足干净基线,正确停手。**实现前须切干净 live origin/main 基线**(派单指令另述:worktree 隔离或 stash,**不销毁 311 分支未提交内容**、保住 524 预放卡)。

## 本卡做什么(一句话)

**主修**:`display_text` 退出 **普通红线**参数值扫描。**次修**:(b) 改 context-aware——unit 不单独裸检(b-unit)、短整数不单独裸检(b-number)、b1 全局 identifier-aware。**config 补扫**:`target`+`setting_name` 走 config-redline 窄 profile。**冲突守门**:**零改动**(现状已独立、扫 display_text 是其正确行为、主修不波及)。**边界**:不碰对外契约 / 509 / tuning (c) / legacy / 523 / 311;`library_path` 与「冲突守门不扫 instruction」两缺口归后继不做。

## 输入(前置依赖)
- 507-B 红线机检本体(`features/paper/paper_plan_helpers.py`)+ 507-A 契约,frozen 在 main。
- 锁:立法目的(防无出处值/替填/调参倍率);有出处值只在 `parameter_mapping` 带出处、`parameter_refs` 指过去;`TuningSuggestion` 只给方向;双源不互伪(decision 21);改对外契约走 decision 13 全清单+PM+R1。
- 必读:01/02/04/05/06 §12 / decision 08/11/13/15/21/22/25;506 v0.3 红线节 / 507-B §5。

## 修复方案(定稿)

### 1. 主修复(根治):`display_text` 退出**普通红线**参数值扫描
从**普通红线**受检字段移除 `display_text`。卡面结论(R1 复审措辞):
> 在 `_derive_display_text` 仍纯白名单派生、且 `target/setting_name` 已补进原字段红线后,`display_text` 不再参与**普通**参数值红线扫描;这不产生 display_text 层新增漏检。若 assembler 引入未经红线单扫字段(含 `library_path`/`value/unit`/evidence excerpt/LLM raw),主修不得上。
- 完全不动对 LLM 原始字段的红线强度。
- **注**:冲突守门是独立 guard(§4),**继续扫 display_text**,不受本主修影响。
- **主修完整性论证(R1 核准逐字段覆盖)**:step_id 机器生成无泄漏面;title/intent/purpose/signal_meaning 原字段红线单扫;block_type / 参数名 规则 5/3 派生前 fail-fast;config target/setting_name 本卡补扫 → 全覆盖。

### 2. 普通文本字段红线(context-aware 收紧)
受检:`title`/`intent`/`block_refs[*].purpose`/`connection_hints[*].signal_meaning`/`configuration_hints[*].instruction`。
- **a**:参数名+完整值同字段窗口邻近 → `parameter_value_leak`
- **b1**:高特异完整值裸出现 → `parameter_value_leak`。**全局 standalone / identifier-aware(并意见 A)**:数字类命中(小数/科学计数/≥3位整数/结构化 literal)**只对 standalone numeric token**(前后 word boundary)生效,**不从 alphanumeric 标识符/型号/求解器名内部拆数字**。不判:`ode113`/`ode15s`/`R2026a`/`C99`;判:`512`/`0.05`/`1e-3`/`2*pi/3`。
- **b2**:数字+单位 composite → `parameter_value_leak`(`3A`/`3 A`/`50 Hz`/`0.05Ω`)。
- **b3**:短整数(0-99)裸 token **仅在**参数名/别名上下文或数字+单位上下文中 → `parameter_value_leak`。孤立短整数不判。
- **b-unit**:unit token **不再单独裸检**,只作 b2 上下文增强。
- **c**:倍率/调参 → `tuning_value_leak`,**不动**。

### 3. config 标识符字段红线(config-redline 窄 profile)
受检(补扫):`configuration_hints[*].target` + `setting_name`。规则:
```
启用:a | b1(standalone/整字段值;identifier 内部数字不拆)| b2
禁用:unit-only | b3 | 配置动词+短整数 | 从 CamelCase/snake_case/连续标识符内部拆数字
```
- 不吃 instruction 的 config 例外(target/setting_name 是标识符不该含值)。
- **不加拼接检查**(§4 反例的 `0`+`05`→`0.05` 属跨字段,不回扫 display_text 解决,见风险节)。
- PASS:`StopTime`/`SolverName`/`ModelReferenceMinAlgLoopOccurrences`/`R2026aCompatibilityMode`/`solver`;FAIL:`512`/`Rs=3`/`0.05 Ω`/`1e-3`。

### 4. 冲突参数守门(零改动)
- **本卡不改冲突守门。** Stage 0 已证其现状即满足独立性:source = `spec.parameter_conflicts`(非 `parameter_mapping`)、不复用普通红线裸 unit token、扫 `step.display_text`。
- 主修仅移除**普通红线**对 display_text 的扫描;冲突守门是**独立 guard**,继续扫 display_text —— 这正是它抓「跨字段拼接产生的冲突值」(如 `0`+`05`→`0.05`)的必要能力,**保留**(撤回 v0.2 并意见 B「冲突守门不扫 display_text」)。
- **既有缺口(归后继,不本卡补)**:冲突守门不扫 `instruction`(instruction 不进 display_text 派生),故 instruction 内冲突值漏抓。与 `library_path` 并列归后继。
- 实现约束:本卡改动(普通红线受检字段增删 / (b) 重构 / config 补扫)**不得波及**冲突守门代码路径;Codex 实现后贴冲突守门 RAW 前后对比,证其逐字未动。

### 5. 受检字段总表(修复后)
```
普通红线(a/b1/b2/b3/c):
- title / intent / block_refs[*].purpose / connection_hints[*].signal_meaning / configuration_hints[*].instruction

config-redline 窄 profile(a/b1-standalone/b2):
- configuration_hints[*].target        ← 新增
- configuration_hints[*].setting_name  ← 新增

普通红线不扫:display_text（主修移除）
冲突守门扫:display_text（独立 guard，零改动，保留）
```

## 不做(明确排除)
- ❌ 不改对外契约/枚举/`schema.json`/`paperTypes.ts`(纯对内;非改不可=边界错,停手报架构师)。
- ❌ 不动 verdict/golden/roundtrip/`_paper_eval_rules.py`(509)。
- ❌ 不动 tuning (c) / `TuningSuggestion`。
- ❌ 不动 legacy `_llm_subsystem_plan`/`paper_plan_subsystem.yaml`。
- ❌ **不改冲突守门**(零改动;仅确保本卡改动不波及)。
- ❌ 不碰 TASK-523 / TASK-311。
- ❌ 不处理 `json_decode_failed`。
- ❌ **不补 `library_path` 红线覆盖**(独立漏检缺口,归后继)。
- ❌ **不补「冲突守门扫 instruction」**(既有正交漏检缺口,归后继)。
- ❌ 不给 config-redline 加跨字段拼接检查(不回扫 display_text)。
- ❌ 不改生成 prompt 红线措辞(除非 R1 判定须同步,另议)。

## 接口契约 / 落点
- **会碰**:`features/paper/paper_plan_helpers.py`(普通红线 `_validate_redlines`/`_validate_text_for_redline`/裸 token 提取含 b1 standalone 改造 / `_is_allowed_config_hint` 配合 / 受检字段列举 / config-redline profile)+ 对应测试。
- **不碰**:冲突守门代码路径 / 对外 schema / `paperTypes.ts` / exporter / verdict / golden / roundtrip / legacy / tuning。
- 红线纯 Python(不涉跨平台/MATLAB),单测 + `make check`(CI Linux)覆盖逻辑;真机验证靠本机 HTTP 上传链路(523 E2E 同款)。

## 测试矩阵(最少)
**普通红线 PASS**:`display_text` 出现 `A`/`s`/`V`/`第 3 步`;原始字段 `连接 A 相信号`/`三相输入`/`包含 2 个端口`/`在 s 域观察响应`/`使用 ode113 求解器`(内部数字不拆)。
**普通红线 FAIL `parameter_value_leak`**:`0.05Ω`/`0.05 Ω`/`1e-3`/`512`/`H 设为 3`(参数名邻近)/`电流设为 3 A`(数字+单位)。
**config-redline PASS**:`setting_name=StopTime`/`SolverName`/`ModelReferenceMinAlgLoopOccurrences`/`R2026aCompatibilityMode`(内部数字不拆)/`target=solver`。
**config-redline FAIL**:`setting_name=512`/`Rs=3`;`target=0.05 Ω`/`1e-3`。
**tuning FAIL(不动,回归)**:`增大 2 倍`/`提高 20%`。
**冲突守门(零改动,回归不破)**:回归现有冲突守门用例;`target='0'`+`setting_name='05'`→display_text `0.05` 若 0.05 是冲突候选值 → 冲突守门仍命中(证扫 display_text 能力保留)。
**display_text assembler sentinel(证不 dereference,高信号 sentinel,禁 `A`/`s`)**:value=`__LEAK_VALUE_0_0523__` / unit=`__LEAK_UNIT_OHM__` / excerpt=`__LEAK_EXCERPT__` 均不入 display_text;display_text 仅白名单字段组成。
**端到端(真实语料)**:523 三篇 + 尽量多真实中文电机论文:正常论文 build_steps **非空、不再 parameter_value_leak 降级**;真泄漏样本仍 fail-closed。

## 诊断日志(脱敏,decision 11)
只记 field_path / reason_code / rule / token_class,不记原文/值/filename。例:`field_path=configuration_hints[1].setting_name reason_code=parameter_value_leak rule=standalone_specific_value token_class=specific_numeric`。

## 实现门 Stage 0(现状已核过,实现前复核 + 干净基线)
1. **切干净基线**:实现须在 live `origin/main`(`git fetch` 后)干净工作树进行;**不得**在旧分支 `codex/task-311-...` 上做;**不销毁**该分支未提交内容(worktree 隔离 或 stash,保住 524 预放卡)。
2. `git rev-parse origin/main` 复核 HEAD(≥ `68c36e6`,允许 main 合法前进);核 524 仍未占。
3. 复核现状事实 1(P0 主修命根:`_derive_display_text` 仍纯白名单、library_path 未拼进);2/3 仍在。
4. 工作树:除预放本卡 + `*-dev.log` 外干净。
任一不符停手报架构师。

## 验收标准
- [ ] 主修:普通红线受检字段不含 display_text;assembler sentinel 4 测试过。
- [ ] 次修:b-unit/b-number context-aware + b1 全局 standalone(`ode113`/`R2026a` 不误报);普通红线 PASS 不判、FAIL 判。
- [ ] config-redline 窄 profile:标识符含数字不误报、塞值抓、不吃 instruction 例外。
- [ ] **冲突守门逐字未动**:贴前后 RAW 对比证零改动;冲突守门回归用例不破(含 display_text 扫描能力保留)。
- [ ] tuning (c) 未动、回归过。
- [ ] 端到端:523 三篇正常论文 build_steps 非空、不再降级;真泄漏样本仍 fail-closed 退 legacy(绝不 `[]`/半截 list)。
- [ ] **对外契约零变更守门**:`python -m scripts.export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json` 无变更 + `cd web && pnpm typecheck` 绿。
- [ ] `make check` 全绿;golden/roundtrip/verdict 未改、eval 不回归。
- [ ] 日志脱敏;decision 13 同步面 diff 贴完工报告;`library_path` + 冲突守门 instruction 两缺口结论已记(归后继,本卡不改)。
- [ ] 完工三件套(decision 08:git status/log/push 三命令;改已有文件字节级保留原始字节,禁 `read_text`/`write_text`/`sed -i`)。

## 风险与注意点
- **主修前置硬门(P0)**:display_text 派生一旦引入未经扫字段(含 library_path),主修不得上。实现前复核最新 HEAD。
- **跨字段拆分泄漏缺口(R1 裁决可接受,含具体实例)**:去 display_text 普通红线扫描后,`0`+`05`→`0.05` 这类跨字段拼接,普通红线**接受不抓**(普通值场景;原始字段单扫为孤立短整数不命中;不回扫 display_text 解决 = 避免重引伪命中)。**冲突值场景**由独立冲突守门扫 display_text 兜。不对称有意为之(冲突场景更严)。
- **b1 standalone 是防误报关键**:从标识符内部拆数字会误伤求解器名/版本号(`ode113`/`R2026a`),回退本轮同类误报。测试守门。
- **冲突守门零改动、勿波及**:本卡改动限普通红线 + config-redline;严禁顺手动冲突守门。贴前后 RAW 证。
- **两个归后继缺口勿顺手补**:`library_path` 漏检 / 冲突守门不扫 instruction —— 都是本卡外正交漏检,记档归后继,范围纪律,严禁在本卡碰。
- **高危泄漏必命中**:`0.05Ω`/`1e-3`/`512`/`Rs=3`/`3 A`/`增大 2 倍` 必抓(FAIL 段守门)。
- **行尾/日志**:decision 08/11。

## 给 Codex 的提示
- 肉在「普通红线受检字段增删 + (b) 重构 context-aware(b1 standalone/identifier-aware + b2 数字单位 + b3 短整数上下文)+ config-redline 窄 profile + 测试矩阵」;**冲突守门零改动、对外契约不动**。
- 没 `grep`:用 `git grep`/`rg`/`Select-String`。
- 改已有文件保留原始字节(decision 08);完工给 git status/log/push 三命令。
- paper schema/前端验收不在 `make check` 里,显式跑。
- 真机端到端验证走本机 HTTP 上传链路(523 E2E 同款);Docker/WSL 起不来无碍。
- `library_path` + 冲突守门 instruction 缺口:**只记不改**。
- 别越界:不动冲突守门 / 对外契约 / 509 / tuning / legacy / 523 / 311。

## 本卡双审 + Stage 0 记录
- **R1(GPT)**:设计审骨架条件通过 → 复审收窄两处(零漏措辞 / config 窄 profile,查 MathWorks 文档佐证);Q3 判冲突守门可扫 display_text。
- **R6(Codex)**:坐实三现状事实;Stage 0 反例证伪「冲突值预期无绕过路径」(`0`+`05`→`0.05`)+ 证冲突守门 source 已独立 + library_path 缺口确认 + 卡号 + 实现门阻塞(旧分支/脏工作树)。
- **架构师并意见/撤回**:b1 全局 identifier-aware(A,保留)/ **撤回 B**(冲突守门保留扫 display_text)/ library_path 归后继(C)/ 冲突守门 instruction 缺口归后继(新)/ 冲突守门坍缩为零改动。
- 派单:切干净 origin/main 基线;代码 PR 与索引/文档收尾 PR 分开走、squash 合、live 核 HEAD;修复卡不占完工计数。
