# TASK-516:MATLAB run-state 采集 + 通道契约(v0.3-b / b3-1)

## 状态
🔲 **v0.4 封板派单稿(三门全齐,✅ 可派 Codex 建)**(2026-06-24)。
**三门全齐**:① 两拍契约方向 —— **PM 已拍**;② **R1(GPT)定向复审 = ACK(P0=0 / P1=0)**;③ **R6(Codex)= ACK 可派建**(无遗留 P0/P1、无须二次 spike、实测数字落地准确)。前序方向(DP-6/DP-7、波形 union、32KB、fingerprint、深不可变、decision 13 扩充)与 v0.3 闭合的两项(波形算法契约化、单位/状态-容器跨字段)R1/R6 均已确认。
本 v0.4 = v0.3 双 ACK 基础上**并入两审给的非阻断实现注记**(MATLAB 1-based 入桶式 / 单点 series 不发 / 单位映射 / `rel_tol` 实测固定),**不改已 ACK 契约语义,无须再审**。decision 13 全清单实现期 Codex 照做。**可派单。**

---

## 编号与拆分
- **TASK-516**(Codex 已核:`origin/main` 现 `4b96277`,TASK-516/517/518/519 **未占号**;TASK-515 不在主干/索引,仅本地未跟踪卡)。
- v0.3-b `T0 → b1 ∥ b2-0 → b2-1 → b3`;b3 实现期再拆 `b3-1 → b3-2 → b3-3`。**本卡 = b3-1**(run-state 采集 + 通道契约方向落定,无持久化、无 LLM)。**b3-2(持久化 + 跨轮状态机 + 迭代循环 + run-state 解释)、b3-3(评测/质量总门)另卡。**
- **定义来源**:TASK-515 v0.4 + roadmap §5 + 本卡 §实测地基(实测自 `origin/main 4b96277`)+ Codex R2026a spike。

---

## 背景与定位
- **b3-1 做一件事**:把"程序自动读到的 run-state(跑完的结果)"经客户端抽成**有界、脱敏、用户每轮确认过的快照**,经**一根独立新通道**送到服务端**校验、回执**。沿用块 B(TASK-514)的客户端采集 + 脱敏 + 强制确认 + 不可变快照 + 数据边界零件,采集对象从"一条报错文本"换成"run-state 结构化数值"。
- **run-state = 三部分**(PM 已拍):(1) 状态/元数据(必带);(2) 有界指标摘要(必带);(3) 有界降采样波形(PM 选带)。
- **b3-1 明确不做**:不碰持久化 / 跨轮状态机 enforcement / run-state 的 LLM 解释(b3-2);不碰质量总门(b3-3);**不改、不碰 `/diagnostic`、`/explanation` 契约语义**;**不拓宽 `MatlabEngineProvider`、服务端不跑/不采集用户模型**;**不动 route 固定守序与 32KB `MAX_BRIDGE_BODY_BYTES`**。
- **b3-1 验收门 = 机制 + 确定性护栏**:采集→确认→送→校验→回执机制对 + 所有边界/拒绝/脱敏/fail-closed 护栏成立。run-state 解释质量随 b3-3 seam(不变量 14)。

---

## 架构站位(R1 一审已确认方向;采集器边界本版收紧)
- **采集在客户端**:Add-on 在用户本机 MATLAB **进程内**经**固定、审计过的 run-result adapter** 读 run-state,**不调任何服务端 Engine API**;客户端白名单提取 + 脱敏 + 有界截断/降采样 + 冻结 canonical JSON + **强制用户确认** + **字节预检**,再经 HTTPS 发新端点。
- **服务端不跑用户模型 / 不接收原始文件**:只收有界脱敏快照;不反序列化任意原始 .slx/.mat/.csv。
- **服务端 Engine(TASK-512/513)= dev/test,非 b3-1 采集路径**;`MatlabEngineProvider` 仅 `health_probe()`,**b3-1 不拓宽**。
- **独立新通道、不碰现有两端点**:`POST /api/v1/bridge/run-state`(提议)复用 `MatlabBridgeRoute` 守序 + 守门 + 传输,另起 `BridgeRunStateRequest` 契约 + 独立 `protocol_version`。
- **信任边界(R1 P1-5,Codex 实测确认)**:服务端结构校验**只能限规模与形态,不能证明数值真来自波形**;真正信任边界是客户端采集器。故 adapter **写死白名单**(见 §采集器白名单)。
- **请 R1 复审**:DP-6/DP-7 改后是否 ACK;采集器白名单是否够。

---

## 实测地基(`origin/main 4b96277`,Codex Stage-0 复核;R1 无 repo,以下自包含)
> Codex 一审 Stage-0:HEAD 已从 v0.1 所记 `29df60a` 前进到 `4b96277`,**新增提交仅改 `docs/03_TASK_INDEX.md`**;按 `4b96277` 复核,A–G 代码地基仍成立。**真开工必须从最新 `origin/main` 新建分支**(本地 main 实测 ahead/behind 各 1 + 未跟踪 TASK-515)。

### A. 现有 bridge 解释契约(**不动**,仅对照)
`BridgeExplanationRequest`(`core/domain/bridge_explanation.py` + Pydantic + `schemas/bridge_explanation_request.schema.json`):`protocol_version Literal["0.3-b1"]` / `request_id UUID` / `diagnostic_kind Literal["manual_error","auto_captured_error"]` / `matlab_release`(`^R20[0-9]{2}[ab]$`)/ `client_version`(`^[A-Za-z0-9.\-]{1,32}$`)/ `error_text`(1–4096)/ `llm_processing_consent_confirmed bool`。**b3-1 不改。**
### B. route + guards(**复用,不动**)
`MatlabBridgeRoute` 固定顺序:loopback(403)→ `application/json`(415)→ `body_with_limit`(413,`MAX_BRIDGE_BODY_BYTES = 32*1024`)→ replay → handler。现挂 `/diagnostic`、`/explanation`。红线写在 `docs/06 §13.4` + 任务文档(代码无字面"固定顺序")。**Codex 确认:新 `/run-state` 挂同一 `route_class` 可干净跑通,守序 + flag/dev-test 守门照继承。**
### C. 认证/守门(**复用**)
`app_environment` 默认 `production`;`matlab_bridge_enabled=False`;非 dev/test 启用即 `RuntimeError`;router 仅 enabled 时 include。**b3-1 新端点同挂,seam 前不上 production(不变量 14)。**
### D. 客户端传输(**复用**)
`postDiagnostic`/`postExplanation` 用 `webwrite`。新增 `postRunState`。**Codex 实测:`webwrite(char(jsonencode(payload)), MediaType="application/json")` 收到的 body 即原 JSON UTF-8 字节**(支撑逐字节冻结)。
### E. Engine 接口面(**不动**)
`MatlabEngineProvider` 仅 `health_probe()`。**b3-1 不拓宽。**
### F. decision 13 同步面(**本版按 Codex 实测订正**)
导出脚本 `scripts/export_bridge_schemas.py` 现导 6 个 bridge schema。**Codex 订正:现有 `test_exported_bridge_schemas_do_not_drift` 只覆盖 explanation 三个 schema;六个 bridge schema 全漂移主要靠 `Makefile verify-schema`(line 39)。** 故 b3-1 新增 run-state schema 须**同时**纳入导出脚本、`verify-schema` 闸,并补 run-state 专属 freeze 测试。
### G. 块 B 可复用零件
客户端不可变快照顺序、白名单采集、客户端 + 服务端二次脱敏、`SENSITIVE_EXTRA_FIELDS` 拒额外敏感字段、隐私 fail-closed、fail-closed 触发面、日志只元数据。**b3-1 沿用,数据对象换 run-state。**
### H. 台账(**已由 Codex 确认**)
块 B index 收尾 PR 已落,索引中 **TASK-514 = ✅**,总任务行仍 45。

---

## Stage 0 — 取证/基线检查(强制,decision 15)
```bash
git fetch origin
git status --short                 # 须空(可白名单本卡未跟踪路径);否则停手报 PM
git rev-parse origin/main          # 期望 4b96277 或其后裔
git show origin/main:docs/03_TASK_INDEX.md | grep -n "TASK-51[6789]"   # 确认 516 空
git switch -c task/TASK-516-run-state-collection origin/main           # 必从最新 origin/main 切
```
**若 main 与 §实测地基(A–G)不符 → 停手报 PM(decision 15)。**

---

## 新契约 `BridgeRunStateRequest`(v0.2 核心;数字 = Codex R2026a 实测后定)
独立 `protocol_version: Literal["0.3-b3"]`;新端点 `POST /api/v1/bridge/run-state`;三层(domain dataclass(frozen,**嵌套用 tuple 深不可变**)+ Pydantic(`extra="forbid"` + strict 数值)+ 导出 JSON schema)。

### 标识与同意
| 字段 | 类型 / 约束 | 备注 |
|---|---|---|
| `protocol_version` | `Literal["0.3-b3"]` | 独立版本 |
| `request_id` | `UUID` | **每个 HTTP 尝试一个** |
| `session_id` | `UUID` | 会话 scope 锚;**只是请求体输入,非鉴权证明**(b3-2 持久化前由 scoped-token claim 校验一致) |
| `run_id` | `UUID` | **一个逻辑不可变快照一个;重试沿用同一个**(规则 2) |
| `run_sequence` | `int`,`0 ≤ x ≤ 1_000_000` | 会话内单调;跨语言安全上界;StrictInt 拒 bool/字符串 |
| `matlab_release` / `client_version` | 同块 B pattern | 复用 |
| `run_state_sharing_consent_confirmed` | `StrictBool` 须 `True` | **更名**(R1 P2-2):b3-1 不调 LLM,不沿用 `llm_processing_consent_confirmed`;每一轮确认 |

> **`snapshot_fingerprint` 已删(R1 P1-3)**:幂等/冲突真值不由客户端定;b3-2 持久化时由**服务端**对"校验 + 规范化 + 二次脱敏后的语义快照"计算指纹,日志不记指纹。客户端只负责 canonical JSON 字节冻结(预览 = 发送,见 §不可变快照)。

### 状态(必带,容器恒在;R1 P1-2)
| 字段 | 类型 / 约束 | 备注 |
|---|---|---|
| `run_status` | `Literal["completed","stopped","execution_error","unknown"]` | **消歧**(R1 P1-2):`execution_error`=仿真执行抛诊断错(R2026a `StopEvent='DiagnosticError'`);`completed`=跑到设定停止(`ReachedStopTime`);`stopped`=提前停且非错;删除模糊的 `failed`/`error` 二义 |
| `convergence_status` | `Literal["converged","not_converged","not_applicable","unknown"]` | **Codex 实测:R2026a 无通用收敛字段**;v1 默认 `not_applicable`(一般 Simulink 仿真)或 `unknown`;`converged`/`not_converged` 仅识别到白名单结果对象时填,且**仅当 `run_status="completed"`**(合法组合规则) |
| `stop_reason` | `str?`,≤160 chars **且 ≤480 UTF-8 bytes**,脱敏 | 非可信文本→数据非指令;缺失=null |
| `solver` | `str?`,≤32 chars **且 ≤96 UTF-8 bytes**,脱敏 | 缺失=null |
| `metrics_status` | `Literal["available","unavailable","not_applicable","unknown"]` | 容器恒在,失败运行用空数组 + 状态,不靠省略猜 |
| `series_status` | `Literal["available","unavailable","not_applicable","unknown"]` | 同上 |

**状态–容器跨字段校验(双向,R1 P1-2)**:`metrics_status="available" ⟺ metrics 非空`;其余三状态 ⟺ `metrics` 为空。`series_status` 与 `series` 同理。四组双向 validator 均须校验并测(见 G-2)。

### 指标(必带容器,≤16 项;Codex 实测收紧)
每项:`name`(`str` ≤32 chars 且 ≤96 bytes,脱敏,**列表内去重**)+ `value`(`StrictFloat` **有限**,拒 bool/字符串/NaN/Inf/null)+ `unit_status`(`Literal["known","unknown","not_applicable"]`;R1 P1-2)+ `unit?`(`str` ≤16 chars 且 ≤48 bytes,**当且仅当 `unit_status="known"` 时存在**,不用 null 混淆"未知/无量纲/不适用")。

### 波形(PM 选带;**v1 删 LTTB,两判别表示 + 降采样算法契约化**,R1 P0-1/P1-1 + Codex 实测)
`series[]` ≤4 条,均为**均匀时间轴**(诚实,不伪造峰值时间)。

**源序列前置(客户端,fail-closed at series 粒度;R1 P1-1)**:候选 series 的 `Time` 必须**有限实数 + 严格递增**(无重复、无倒序);不满足 → **该 series 不发出**(只记元数据日志),**不修补、不重排、不插值、不填值**。

**均匀判定(固定容差;R1 P1-1)**:令 `d = diff(Time)`;`uniform ⟺ median(d) > 0 且 max(|d − median(d)|) ≤ rel_tol × median(d)`,`rel_tol` 固定 **= 1e-6**(Codex R6 已核:对 fixed-step / default sine / ode45 51 点均判 uniform,且把手工非均匀 Dataset 判 non-uniform;**最终常量由实现固定并纳确定性 golden test**)。**非均匀序列 v1 不表示 → 该 series 不发出**(显式 x 留后续卡);**因此不会产生空桶。**

- **`identity_uniform_v1`**(均匀且 `2 ≤ source_point_count ≤ 192`):`t_start`(= Time[0])+ `t_step`(= median(d),>0)+ `time_unit` + `y[]`(`StrictFloat` 有限,长度 = `source_point_count`,**2–192**);不选点、完整保留原点。**单点 series(`diff(Time)` 为空)v1 不发**(Codex 实现注:`y` 最小长度收成 2)。
- **`min_max_envelope_uniform_v1`**(均匀且 `source_point_count > 192`):`t_start`(= Time[0])+ `bucket_width`(>0)+ `time_unit` + `y_min[]` + `y_max[]`(等长,`y_min[i] ≤ y_max[i]`)。**桶规则(确定性,R1 P1-1)**:`bucket_count = 96`;`bucket_width = (Time[end] − Time[0]) / 96`;样本入桶(0-based 语义)`min(95, floor((Time[j] − t_start)/bucket_width))`(**末桶右闭、含 Time[end]**,其余左闭右开);**Codex 实现注:MATLAB 1-based 写 `idx = min(96, floor((t − t_start)/bucket_width) + 1)`,末点落 97 被 `min` 收进末桶**;因源均匀且 `96 ≤ source_point_count`,**每桶必非空**(无空桶、无 mask 需求);`y_min[i]/y_max[i]` = 桶 i 内 Data 的 min/max。

每条公共字段:`series_id`(`^[A-Za-z0-9._\-]{1,32}$`,稳定、**列表内去重**)+ `label`(≤32/≤96,脱敏,非可信)+ `time_unit`(`Literal["s","ms","us","unknown"]`,缺失=`unknown`)+ `value_unit_status`(`Literal["known","unknown","not_applicable"]`;R1 P1-2)+ `value_unit?`(`str` ≤16/≤48,**当且仅当 `value_unit_status="known"` 时存在**)+ `sample_order`(`Literal["chronological"]`,固定)+ `source_point_count`(`StrictInt ≥0`,降采样前原始点数)。

> **说明**:两表示的时间轴**按构造即均匀**,"未知单位"经 `time_unit="unknown"` / `value_unit_status` 承载,**不靠 null 混淆"未知/无量纲/不适用"**。v1 **不带显式 x 轴、不接受选点型 LTTB、不接受非均匀源**;**降采样确定可复现,实现期附确定性 golden tests**(R1 P1-1)。

### 硬拒绝(schema 级)
`additionalProperties:false` / `extra="forbid"`;拒 opaque blob / base64 / 压缩 / 归档 / 任意嵌套 MAT·JSON 对象 / 字符串伪装数值 / **bool 当数字** / 隐式字符串→数值;数值必须是 JSON number 且有限(**Codex 实测 `jsonencode(NaN/Inf)→null`,故客户端编码前递归拒非有限,服务端再拒 numeric=null**);敏感字段拒绝 = `SENSITIVE_EXTRA_FIELDS` **超集**(块 B 集 + `mat_path/csv_path/raw_mat/raw_csv/base64/blob/compressed/archive/model_content/...`,Codex P2);**所有字符串字段** Unicode 规范化 + 拒 NUL/控制符/双向文本控制符(R1 P1-5)。

### 字节预算(Codex 实测定;R1 P1-1)
旧 4×256+32metrics 实测中文满载 `39839` bytes **超 32KB**。v1 上限:`series ≤4` / `identity.y ≤192` / `envelope 桶 ≤96` / `metrics ≤16` / 字符串按上表 char + UTF-8 byte **双限**。**客户端 `jsonencode` 一次后按真实 UTF-8 bytes 预检,阈值 `28*1024`,超限 fail-closed;服务端 route 仍 32KB。**(满载实测:identity 192 中文 `24867`、envelope 96 中文 `24979`,留合理余量。)

### 回执 `BridgeRunStateReceipt`(domain frozen)+ `...Model`(R1 P2-1)
`status: Literal["validated"]` + `mode: Literal["ephemeral_validation"]` + `durable: Literal[false]` + 回显 `request_id`/`run_id`/`run_sequence`;**不回显任何 run-state 内容**。docs/06 须注明:200 = 通过校验并被本次请求消费,**不代表已保存/可恢复/可查询/已进跨轮状态**。

---

## 采集器白名单(R1 P1-5 写死 + Codex R2026a 实测)
- 输入**必须是 `Simulink.SimulationOutput`**。
- **运行状态**:经 `CaptureErrors="on"` + `SimulationMetadata.ExecutionInfo`(`StopEvent`/`StopEventTime`/是否有 `ErrorDiagnostic`)→ 映射 `run_status`;wall-clock 来自 `TimingInfo`。
- **指标**:用 `out.who` 枚举(有上限)、`out.get(name)` 只接受**有限数值标量** → metric。通用可取:运行是否返回、`StopEvent`、模型 start/stop time、`TimingInfo`、solver type/name/max-step(若 `ModelInfo.SolverInfo` 存在)。**不可通用假设**:收敛、残差、迭代次数、步数、业务/控制指标。
- **波形**:`out.get(name)` 的 `timeseries`(`Time/Data` 为**有限实数单通道向量**)或 `Simulink.SimulationData.Dataset` 的 `Signal.Values(timeseries)` 子集 → 逐条 `diff(Time)` 判均匀 → identity 或 envelope。
- **单位映射(Codex 实现注;不猜)**:`TimeInfo.Units='seconds'` → `time_unit='s'`(同理 ms/us);`DataInfo.Units` **为空时填 `value_unit_status="unknown"`,不猜无量纲**;仅当 adapter 白名单自知是计数/无量纲时才填 `not_applicable`;`time_unit` 无法确定时填 `unknown`。
- **明确禁止**(Codex 实测敏感面):整体上传 `ModelInfo`(含 `UserID`/`MachineName`/`ModelFilePath`)、整体 JSON 化 `MSLDiagnostic`、base workspace 浏览、`eval`、任意 object→JSON、任意字段递归、MAT/CSV/raw workspace dump、`getReport` 全文。
- **服务端只验规模/形态,不能证明来源真实**;adapter 是唯一信任边界(R1 P1-5)。

---

## 不可变快照顺序(Codex 实测 canonical JSON 字节冻结)
```
读一次 run-state(adapter 白名单)→ 提取(状态/指标/序列)→ 客户端脱敏(所有字符串字段)→ 有界截断 + 降采样(identity/envelope,均匀时间轴)→ 生成 run_id → 固定字段顺序构造 → frozen_json = jsonencode → frozen_bytes = unicode2native(frozen_json,"UTF-8")→ 按 UTF-8 字节预检(≤28KB,超则 fail-closed)→ 向用户预览这份 frozen JSON → 用户确认 → 发送同一份 char(frozen_json)
```
验收须断言:**取消确认 = 零网络**;发送字节 = 预览/确认的 frozen_bytes **逐字节一致**;确认后 MATLAB 状态变化不改待发。

---

## 运行不变量(R1 P1-2 操作化进契约)
- **数值语义**:`time_unit` / `unit_status` / `value_unit_status` / 各 `*_status` 以**枚举 + 容器恒在**承载;单位缺失即显式 `unknown`(或 `not_applicable`),**不用 null 混淆"未知/无量纲/不适用"**;失败运行用空数组 + 状态,不靠省略;LLM 不得推断。
- **降采样语义**:仅 `identity_uniform_v1` | `min_max_envelope_uniform_v1`(确定、可复现);**删 LTTB**;包络明确表达桶内极值,不伪装单点。
- **载荷形态**:禁止原始二进制/base64/压缩/嵌套 MAT 对象借结构化字段绕过。
- **非可信文本**:所有字符串字段限长(char + UTF-8 byte 双限)+ 脱敏 + Unicode 规范化,作为数据非指令。

---

## 设计点裁决(R1 一审裁决已并入)
| DP | 裁决 / 提议 |
|---|---|
| DP-1 新通道 vs 改旧 | **独立新端点 + 新契约**(PM 第二拍);复用 route 守序/守门/传输。 |
| DP-2 表示层 | 状态(必带)+ 指标(必带)+ 波形(带)= identity/envelope 两表示。 |
| DP-3 体积 | 整 payload 卡 32KB route 内、客户端 28KB 字节预检 fail-closed;**不动 `MAX_BRIDGE_BODY_BYTES`**。 |
| DP-4 受控数值通道护栏 | 沿用块 B 四护栏 + run-state 特化(见 §硬拒绝 + §采集器白名单)。 |
| DP-5 采集机制 | 固定审计 adapter 白名单(见 §采集器白名单);禁通用 workspace/eval/object→JSON。 |
| **DP-6 b3-1/b3-2 范围线** | **R1 ACK:画得对。** b3-1 = 无状态 ingress 切片(契约 + 采集 + 接收/校验/拒绝/脱敏/fail-closed/最小回执),**不含持久化**;持久化 + 跨轮状态机 → b3-2(一旦写盘就须同时落 token scope/TTL/删除/隔离/幂等冲突/过期拒写,不再是"基础持久化")。 |
| **DP-7 token scoping(R1 P1-4 改硬前置)** | b3-1 **不实现 scoped token**,仅 dev/test loopback,**且不持久化、不调 LLM、production 不可启动**。**b3-2 在写入任何快照/派生状态之前,必须先落 scoped-token 校验**(claim 绑 user/project/session/capability=`run_state:write`,并校验 body `session_id` 与 claim 一致);**该前置未完成,b3-2 不得派单。** |

---

## decision 13 同步清单(R1 P1-6 + Codex 订正后扩充;缺一项 = 未完工)
```text
□ core/domain/bridge_run_state.py(新)              — BridgeRunStateRequest + BridgeRunStateReceipt 两个 domain(frozen;嵌套 metrics/series/y 用 tuple 深不可变)
□ features/matlab_bridge/bridge_run_state_schemas.py(新) — Pydantic Request/Receipt + 枚举 + 边界 + extra=forbid + strict 数值 + to_domain/from_domain
□ schemas/bridge_run_state_request.schema.json(新)   — export 生成
□ schemas/bridge_run_state_receipt.schema.json(新)   — export 生成
□ scripts/export_bridge_schemas.py(改)             — 纳入两个新 schema(6 → 8)
□ Makefile verify-schema(改/确认)                  — 把 run-state 两 schema 纳入全漂移闸(现六-schema drift 主靠此,§F)
□ tests/.../test_bridge_run_state_schema_freeze.py(新) — 两新 schema freeze + drift(注:现有 do_not_drift 仅覆盖 explanation 三个,本卡补 run-state 专属)
□ tests/.../test_bridge_run_state_schemas.py(新)     — 边界/拒绝/round-trip(见验收门)
□ request.to_domain / receipt.from_domain round-trip — 两向均成立
□ core/domain 不 import Pydantic                     — 断言
□ OpenAPI:feature 开时 /run-state 声明 200/403/413/415/422;关时 path 不存在
□ /run-state route 回归:32768/32769 字节、loopback、Content-Type
□ MATLAB 生成 payload → Python schema 跨语言 golden fixture
□ docs/06_OUTPUT_CONTRACTS.md(改)                  — 新增 run-state 契约段 + 新端点守序红线 + "200=已校验非已存"说明
□ 现有 6 schema 确认零漂移(本次仅 run-state 两个为"新增")
```
**不涉 `project_type`,不触 `core/prompts/*.yaml` / `docs/05`**(run-state 的 LLM 解释 + 文案是 b3-2)。b3-1 无 LLM 调用。

---

## 验收门(机制 + 确定性护栏;质量留 b3-3 seam)
- [ ] **G-1 契约 freeze/drift**:run-state request/receipt 两 schema freeze 生成绿 + 纳 `verify-schema` 闸;现有 6 schema 零漂移。[CI]
- [ ] **G-2 边界拒绝 + 跨字段**:超 series/点/桶/metrics/字符串(char + UTF-8 byte 双限)、NaN/Inf/null、bool 当数字、字符串伪装数值、base64/blob/压缩/嵌套对象/敏感超集字段、未知枚举/`protocol_version` → 全拒;**跨字段双向 validator**:`converged/not_converged` 仅配 `run_status="completed"`、`metrics_status`/`series_status` ⟺ 容器空/非空(四组)、`unit`/`value_unit` 存在 ⟺ 对应 `*_status="known"`;`series_id`/metric name 列表内碰撞 → 拒。[单测]
- [ ] **G-3 客户端采集 + 确认 + 降采样确定性**:adapter 白名单读 → 脱敏(所有字符串)+ 降采样(identity/envelope)+ 冻结 → **强制确认才发**;采集/脱敏/降采样/预检失败或未确认 → **fail-closed**;**降采样确定性 golden tests**(R1 P1-1):`Time` 非严格递增 / 非均匀源 → 该 series 不发、不修补;identity 与 envelope 桶规则(固定 96 桶、`bucket_width=(t_end−t_start)/96`、末桶右闭、无空桶)对固定输入产出固定输出。[本机 + 单测]
- [ ] **G-4 不可变快照 + 字节预检**:取消 = 零网络;发送字节 = 预览 frozen_bytes 逐字节一致;UTF-8 字节 >28KB → 不发;确认后状态变化不改待发。[本机]
- [ ] **G-5 脱敏 + 隐私 fail-closed**:**所有字符串字段**(label/series_id 除外的文本 + `metrics[].name/unit`/`series[].label/value_unit`/`stop_reason`/`solver`)客户端 + 服务端二次脱敏 + Unicode 规范化;回执 + 日志不含未脱敏文本;泄漏语料含嵌入式敏感(路径/变量值/连接串/用户目录/源码/`ModelInfo` 字段)。[单测]
- [ ] **G-6 体积**:整 payload ≤32KB route 成立、客户端 28KB 预检;**不动 `MAX_BRIDGE_BODY_BYTES` 与守序**;现有两端点无回归。[单测 + 本机]
- [ ] **G-7 端到端 + 跨语言**:Add-on 读 run-state → `/run-state` → `validated/ephemeral/durable=false` 回执;MATLAB→Python golden fixture 通过;现有 manual/auto explanation E2E 保留。[本机 e2e]
- [ ] **G-8 CI 卫生**:ruff / format / mypy / 全 pytest(fake provider)/ hygiene 全绿;b1/b2-0/b2-1(块 A+B)无回归。[CI + 本机]
- [ ] **G-9 日志限制**:客户端 + 服务端日志只元数据(大小/类型/点数/状态码/请求 id);**不记指纹**(避免跨请求关联)。[单测]
- [ ] **G-10 深不可变 + 边界**:domain round-trip 两向成立;嵌套 tuple 深不可变;core/domain 不 import Pydantic;OpenAPI feature 开/关行为对。[单测]

---

## 不做(明确排除)
- ❌ 持久化 + TTL/scoped 存储 + 跨轮状态机 enforcement + run-state 的 LLM 解释(**b3-2**)。
- ❌ 质量总门 / 评测语料(**b3-3**)。
- ❌ 改/碰 `/diagnostic`、`/explanation` 契约语义。
- ❌ 拓宽 `MatlabEngineProvider` / 服务端跑或采集用户模型。
- ❌ 动 route 固定守序与 `MAX_BRIDGE_BODY_BYTES`。
- ❌ 上传原始 .slx/.mat/.csv / 完整 workspace / 整体 `ModelInfo` / 整体 `MSLDiagnostic`。
- ❌ 选点型 LTTB / 非均匀显式 x 轴 / >4 series / identity >192 点 / envelope >96 桶(留后续卡)。
- ❌ 跨 MATLAB 版本(R2026a 起步)。
- ❌ seam 前上 production / 作能力宣传(不变量 14)。

---

## 实施约束(全程)
- **decision 11**:同步实现 + async 侧一处 `to_thread`;禁 `logger.exception`;日志/异常/对外结果不含原始序列/路径/源码。
- **decision 13**:新契约列清单贴 diff(见上)。
- **decision 15**:main 与本卡不符 → 停手报 PM。
- **decision 21**:b3-1 在 `features/matlab_bridge/` 内,不 import `features/explanation/` 私有结构;跨 feature 共享只在 `core/` 公开 contract。
- **不变量 14**:seam 前不上 production;确定性护栏只降低已枚举危险概率。
- **不重开已锁**:v0.3-a freeze / b1 / b2-0 / b2-1 块 A+B / TASK-515 v0.4 的 run/session 8 规则 + 总门 + 「独立通道≠原始上传」。
- **行尾**:照 `20260602-08`(非 decision 18)。
- **git**:**从最新 `origin/main`(`4b96277` 或后裔)新建** `task/TASK-516-run-state-collection`;`git diff --stat origin/main` 与 §文件清单一致;完工 03 索引新增 TASK-516 行(🔲→🔍),PM 合并后 → ✅。

---

## 文件清单(草案,Codex 以 Stage 0 复核)
**生产(契约)**:`core/domain/bridge_run_state.py`(新)、`features/matlab_bridge/bridge_run_state_schemas.py`(新)、`schemas/bridge_run_state_request.schema.json`(新)、`schemas/bridge_run_state_receipt.schema.json`(新)、`scripts/export_bridge_schemas.py`(改)、`Makefile`(改/确认 `verify-schema`)、`api/routes/matlab_bridge.py`(改:加 `/run-state` + 复用 `route_class`,**不动守序/32KB/现有两端点**)、`docs/06_OUTPUT_CONTRACTS.md`(改)。
**生产(服务)**:`features/matlab_bridge/bridge_run_state_service.py`(新:接收/校验/脱敏/回执,**无持久化、无 LLM**)、`api/dependencies.py`(改:注入)。
**客户端**:`clients/matlab_bridge/app/+mxa/+bridge/`(改/增:固定 adapter 读 run-state + 白名单 + 脱敏 + identity/envelope 降采样 + canonical JSON 冻结 + 字节预检 + 快照确认 + `postRunState`)。
**测试**:run-state schema freeze/边界 + 跨语言 golden(新)、run-state 服务测试(新)、客户端采集单测 + 本机 e2e。
**任务卡/索引**:本卡(PM 预放 `docs/tasks/` 或 Codex `create_file`);完工新增 `docs/03_TASK_INDEX.md` TASK-516 行(🔲→🔍)。

---

## v0.2 变更对照(给两边定向复审:逐条对应一审意见)
| 一审项 | 源 | v0.2 处理 |
|---|---|---|
| 波形静默改时间语义 | R1 P0-1 / Codex 波形 | **删 LTTB**;改 `identity_uniform_v1` \| `min_max_envelope_uniform_v1` 两均匀时间轴表示;删 `peaks_preserved`(表示自身保极值) |
| 32KB 预算未闭合 | R1 P1-1 / Codex 字节 | 按实测收紧(series≤4 / identity≤192 / envelope≤96 / metrics≤16 / 字符串 char+byte 双限);客户端 28KB UTF-8 预检 fail-closed;route 仍 32KB |
| unknown 未进契约 | R1 P1-2 | `time_unit` 枚举含 `unknown`;`metrics_status`/`series_status`/`run_status`/`convergence_status` 枚举 + 容器恒在;`run_status` `failed/error` 消歧为 `execution_error`;合法组合规则 |
| fingerprint/重试/不可变 | R1 P1-3 | **删客户端 `snapshot_fingerprint`**(b3-2 服务端算语义指纹、日志不记);`run_id` 重试沿用 / `request_id` 每尝试一个;domain 嵌套用 tuple 深不可变;措辞改"摘要不直接含原文" |
| DP-7 改硬前置 | R1 P1-4 | b3-2 **持久化前必须**落 scoped-token 校验(claim 绑 user/project/session/`run_state:write` + 校验 session_id 一致),未完成不得派单 |
| 文本/数值/来源护栏 | R1 P1-5 | 脱敏扩至**所有字符串字段** + Unicode 规范化 + 拒控制/双向符;strict 数值拒 bool/字符串/隐式转换;`run_sequence` 上界;name/series_id 去重;**采集器白名单写死** + 信任边界说明 |
| decision 13 缺项 | R1 P1-6 / Codex §F | 补 receipt domain / round-trip / 深不可变 / core 不 import Pydantic / OpenAPI / route 回归 / 跨语言 golden;订正"drift 主靠 verify-schema、do_not_drift 仅覆盖 explanation 三" |
| 回执语义模糊 | R1 P2-1 | 回执 `validated`/`ephemeral_validation`/`durable=false` + docs/06 明示 |
| consent 命名 | R1 P2-2 | 更名 `run_state_sharing_consent_confirmed` |
| 稳定标识 + 诊断元数据 | R1 P2-3 | 加 `series_id`(受限稳定)+ `source_point_count`;表示自带算法版本(`*_v1`) |
| 敏感字段超集 / NaN / ModelInfo | Codex P2 / §1 | `SENSITIVE_EXTRA_FIELDS` 超集;客户端编码前拒非有限、服务端拒 numeric=null;禁整体 `ModelInfo`/`MSLDiagnostic` |
| HEAD/分支 | Codex Stage-0 | §实测地基记 `4b96277`;Stage 0 必从最新 origin/main 新建分支 |

---

## v0.3 变更对照(R1 定向复审剩 2 项 P1)
| 一审项 | 源 | v0.3 处理 |
|---|---|---|
| 降采样算法未完全契约化 | R1 P1-1 | 加:`Time` 须有限 + 严格递增(否则该 series 不发、不修补);均匀判定固定容差(`rel_tol` 提议 1e-6,Codex 核);**非均匀源 v1 不表示→不发**(不产生空桶/插值/填值);envelope 桶规则确定化(固定 96 桶、`bucket_width=(t_end−t_start)/96`、末桶右闭、因源均匀必非空);实现期附确定性 golden tests |
| 单位 / 状态-容器跨字段未完成 | R1 P1-2 | 加 `unit_status`/`value_unit_status`(`known/unknown/not_applicable`),`unit`/`value_unit` **当且仅当 status=known 时存在**(不用 null 混淆);加四组双向 validator:`metrics_status`/`series_status` ⟺ 容器空/非空(并入 G-2) |
| `StrictFloat` 接受 JSON 整数 | Codex 实现期提醒 | 记录:`StrictFloat` 接受 JSON integer 转 float、拒 bool/string,**非阻断**;实现照此 |

## v0.4 并入(两审非阻断实现注记,不改契约语义,无须再审)
- envelope 入桶 MATLAB 用 1-based `idx = min(96, floor((t−t_start)/bucket_width)+1)`(= 0-based `min(95, floor(...))`);
- 单点 series 不发,`identity_uniform_v1.y` 最小长度 = 2;
- `rel_tol = 1e-6` 经 Codex 实测确认(fixed-step/sine/ode45 判 uniform、手工非均匀判 non-uniform),实现固定并纳 golden test;
- 单位映射:`TimeInfo.Units` → `time_unit`;`DataInfo.Units` 空 → `value_unit_status="unknown"`(不猜无量纲);`not_applicable` 仅 adapter 自知计数/无量纲时填。

---

## 关联决策
decision 11 / 12 v0.4(双审)/ **decision 13(本卡触发,新契约)** / decision 15 / **decision 21**(feature boundary)/ decision 25(评测双轴;随 b3-3)/ **`20260602-08`(保行尾;非 decision 18)** / **不变量 14** / **roadmap §5 + §10.3** / **TASK-515 v0.4** / **TASK-514 块 B**。

---

## 审查与派发
- **三门全齐(2026-06-24)**:两拍契约 = **PM 已拍**;**R1(GPT)定向复审 = ACK(P0=0/P1=0)**;**R6(Codex)= ACK 可派建**(无遗留 P0/P1、无须二次 spike)。v0.4 并入两审非阻断实现注记,不改契约语义。
- **下一步:派 Codex 建。** 派单注意:① Stage 0 必从最新 `origin/main`(`4b96277` 或后裔)新建 `task/TASK-516-run-state-collection`,`git status` 脏(除本卡未跟踪)即停手报 PM;② 本卡放 `docs/tasks/`(PM 预放或 Codex `create_file`,按 PM 定);③ **decision 13 全清单逐项贴 diff**(缺一项 = 未完工);④ `rel_tol` 最终常量纳 golden test;⑤ 完工补 `docs/03_TASK_INDEX.md` 新增 TASK-516 行(🔲→🔍);⑥ **完工 PM 看 diff + 验收门勾选后合并 → ✅**(契约 + 隐私护栏高风险,合并前架构师亲自取证复核 diff + 安全门,不只看绿勾)。
- **实现门**:两拍契约(**PM 已拍**)+ R1(**ACK**)+ R6(**ACK**)+ decision 13 全清单(实现期)。**全齐,可派单。**
- **brief**:§实测地基 = 自包含事实(实测自 `origin/main 4b96277`);R1 无 repo、无记忆,以本卡为准。
