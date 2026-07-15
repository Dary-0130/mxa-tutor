# TASK-537-A:m_script 判死解耦 + 重生成谓词语义修正(v0_1)

> **★ 建卡进仓(勿漏,与 529/530/531 同模式)**:本文即规格卡 `docs/tasks/task-537-a-mscript-fate-decoupling-v0_1.md` 的正文(路径复数 `tasks/`、版本 `v0_1` 下划线)。请**把本文作为该卡文件、随本次实施代码 PR 一起提交进仓**。索引挂行(`docs/03_TASK_INDEX.md` 加 TASK-537-A)走 PM 网页侧单独 closeout PR、不进本代码 PR(决策 07)。

**性质**:修 bug + 对齐宪法。不是新功能。R1(设计审)+ R6(可落核)双审已过。

**背景一句**:.m 脚本骨架在宪法里是「尽力交付」,前端不渲染、下游不消费。但首次生成路径上,它一失败就 raise、整轮 plan 判死(build_steps / guidance 都不跑,用户什么都拿不到)。重生成路径早就不这么干了(失败只保持 None、不阻断 build_steps)。本卡把首次生成掰回来。

## Stage 0:前置核实(核不过就停手回报,不许带着假设施工)

S0-1. 重生成端点是不是 guidance-only 恢复的唯一入口?即:build_steps 已存在、guidance 缺失/失败,今天用户靠什么恢复 guidance?若靠本端点(且靠 m_script 恰好为 null 才进得去)→ 停手回报,C2 需要重新设计谓词。

S0-2. mscript 分支在抛错前,有没有对共享可变状态做写入?(改 plan / 写持久化 / 更新公共 evidence / 改动 build_steps 依赖的上下文)有 → 停手回报,仅把返回值置 None 会留半写状态。

S0-3. `eval/run_paper_pdf_smoke.py` 里那份生产编排的镜像逻辑,具体镜像了哪些行为?C1 改动后,哪些镜像点必须同步?列清单。

## 范围

### C1 后端首次生成路径

mscript 失败 → 降级为 None,不杀整轮,继续跑 build_steps + guidance。

- 降级必须封装在 mscript 叶子任务内部,不许在 gather 结果外层写宽泛 catch。
- `asyncio.CancelledError` / `KeyboardInterrupt` / `SystemExit` 等原样传播,不降级。
- plan_composer 失败仍整轮判死。禁止抽象出对多个分支共用的“把 `BaseException` 降级成空值”的 helper。
- 降级发生在 mscript 自身重试耗尽之后,不许第一次异常就降级。
- 降级的失败类别(全部降级,不扩大为整轮死亡):瞬时 provider 错 / 输出截断 / JSON 不可解析 / schema 不过 / 命中冲突参数红线 / 叶子内未预料的普通 Exception。
- 冲突参数红线不放宽:脚本照样拒,只是拒的范围止于 mscript。

### C2 重生成谓词,前后端原子同步

谓词去掉 `m_script` 项,只看 `build_steps` 与 active corrections。

- 明确取消「只重试 m_script」这个旧能力(合法 null 与失败 null 无法区分,不为它建状态面)。
- 前端用精确 null 判断(`structuredSteps == null`),不用 `!structuredSteps` 的 truthiness。
- 静态搜索全仓所有「m_script null = 有活没干完」的派生判断,一并清掉。
- 这是对外行为收窄:`build_steps` 有值 + `m_script` null + 无纠错 → 400 `regenerate_nothing_to_do`。历史数据不迁移,但要有固定测试。

### C3 可观测,禁静默丢弃(决策 27 §4)

内部保留三态 outcome,对外仍折叠为 `string|null`:

- `generated`(值为字符串,无子码)
- `returned_null`(合法终局,无子码)
- `degraded`(值 None,子码必填)

约束:

- 三态必须结构化保留,不许靠事后从 `m_script_skeleton is None` 反推。
- 子码是受控枚举。不落 LLM 原文 / 异常 message / traceback / 论文原文 / 参数值(决策 11)。
- mscript 降级是正交诊断轴:不覆盖 plan/build_steps/guidance 的主失败码。(mscript 降级 + build_steps 随后失败 → 主失败仍是 build_steps)
- telemetry / summary 写入失败不得抛回业务编排,不许诊断器重新获得整轮否决权。

### C4 评测跑道同源(决策 28「测量通道与生产同构」)

按 S0-3 的清单同步 eval 镜像逻辑,并加测试锁住「评测侧 mscript 降级行为 == 生产侧」。

plan 层评测编排镜像 = 已知同源缺口,焊死方案本卡不做,写进 as-built 记账。

## 明确不做

- 不动任何 prompt、不瘦身输入(归后续卡)。
- 不抬 max_tokens。
- 不删 m_script 生成(去留是独立产品决策,PM 未拍)。
- 不加公开 `m_script` + `_status` 字段(R1 裁决:不划算)。
- 不改 D1 指标定义(新 summary 字段只解释 null,不参与打分;历史 summary 缺字段用兼容默认值,不得伪装成 `returned_null`)。
- 不重写并发架构(本卡只保证「不判死」,不保证「不拖延」;延迟隔离归后续,记风险)。

## 验收

确定性测试为主;真机复跑只作支持性观察,不作正确性证明。

### A. 首次生成 mscript 定向 fake

角色定向 FakeProvider,固定其余角色为合法输出,只变 mscript:

- A1 合法字符串 → 保留,outcome=`generated`。
- A2 合法返回 null → None,outcome=`returned_null`,无子码。
- A3 provider timeout 重试耗尽 → None + `timeout` 子码。
- A4 瞬时错最终失败 → None + `transient` 子码。
- A5 截断 JSON → None + `truncated` / `unparseable` 子码。
- A6 JSON 完整但 schema 错 → None + `schema-invalid` 子码。
- A7 命中冲突参数红线 → None + `conflict-guard` 子码。
- A8 叶子抛普通 RuntimeError → None + `internal-error` 子码。
- A9 抛 CancelledError → 不返回成功 plan,取消原样传播。

A2 与 A3 必须分开测,这是本卡最关键的 null 语义测试。A1-A8 每条都断言:build_steps 恰好调一次、guidance 恰好调一次。

### B. 反向命门

- B1 plan_composer 单独失败 → 仍整轮判死,build_steps/guidance 不跑,不得被改写成 mscript 降级。
- B2 plan_composer 失败 + mscript 也失败 → 主失败是 plan_composer,mscript 子码只能是 secondary。
- B3 mscript 降级后 build_steps 失败 → 主失败是 build_steps 原码,不得重分类为 `mscript_*`。
- B4 telemetry sink 固定抛异常 → 不得杀掉已可交付的 plan,走 metadata-only fallback。

### C. 重生成谓词矩阵

- 纠错空 / build_steps 有 / mscript 有 → 400。
- 纠错空 / build_steps 有 / mscript null → 400。C2 核心契约,必测。
- 纠错空 / build_steps None / mscript 有 → 允许。
- 纠错空 / build_steps None / mscript null → 允许。
- 纠错非空 / build_steps 有 / mscript 任意 → 允许。
- 纠错非空 / build_steps None / mscript 任意 → 允许。

### D. 状态转移

- D1 首次生成 build_steps 成功 + mscript 失败 → plan 返回 → 前端不显示按钮 → 直接打端点返回 400 → 不产生第二轮 mscript 调用。
- D2 纠错/撤销 → build_steps 与 mscript 同时 None → 按钮显示 → 端点允许 → 重生成后 build_steps 恢复 → 按钮消失。

前端四态:`build_steps` 有值(mscript 有/无)→ 不显示按钮;`build_steps` null(mscript 有/无)→ 显示。

### E. 隐私哨兵(决策 11)

在 fake 异常 message 与 raw response 里放唯一哨兵串,断言 telemetry / eval summary / 业务日志 / API response 均不含该串。

### F. 契约与静态检查

- 公共 schema export 零 diff(不改 Pydantic Field/Literal,跑 export/verify 证明)。
- 不出现公开 `m_script` + `_status`;`m_script_skeleton` 仍是 `string | null`。
- 静态搜索:重生成资格判断中不再存在 mscript null 判断。
- 静态搜索:不存在对多个 gather 分支共用的“把 `BaseException` 降级成空值”的 helper。
- `make check` 全绿。

## 同步清单(决策 13,PR 里逐条勾)

- 后端谓词 + 单测。
- 路由级 400 集成测试。
- 前端 `hasRegenerationWork` + 按钮测试。
- `web/scripts/task522d1-smoke.mjs` 旧谓词断言。
- `docs/06_OUTPUT_CONTRACTS.md` §12.5.1 契约文字。
- eval 镜像逻辑 + 同源测试。
- `tests/features/paper/test_paper_plan_service.py` 里 `test_mscript_drafter_rejects_conflict_candidate_assignment` 的期望。
- 埋点或事件名(不许再叫「补齐 mscript」)。

## 效果口径(决策 28)

本卡不承诺抬高成品率。禁止拿单轮 generated 当「修好了」的证据。若报真机数字:N≥3,报分布,坏事件配机会数与分母,null ≠ 0。

## 索引

按决策 07,状态推到 🔍;索引挂行走 PM 单独 closeout PR,不进本代码 PR。

## As-built 记账

### Stage 0 核实

- S0-1:后端已有 `guidance_status_requires_regeneration("stale_pending_regeneration")` 放行重生成端点;因此 guidance stale 恢复并不依赖 `m_script_skeleton is None`。但前端旧按钮谓词不看 `guidance_status`,本卡仍按 C2 收窄按钮到 `structuredSteps == null`;对 `generation_failed` 的纯 guidance retry 入口不在本卡扩展范围。
- S0-2:`mscript_drafter` 失败前只做叶子本地 LLM 调用、JSON/字段/冲突守门与日志;未写持久化,未改 plan/evidence/build_steps 上下文。将返回值降级为 None 不会留下共享半写状态。
- S0-3:eval paired-full 镜像了生产的 plan+mscript 并行启动、plan structured retry 时复用已完成 mscript、missing+build_steps 并行、同一份 mscript 装配到每个 paired build-step arm、每个 arm 再独立校验并生成 guidance。C1 后必须同步 plan+mscript 并行处的 mscript outcome 降级与复用逻辑,并把三态 outcome 写入 summary。

### 本卡落点

- 首次生成新增内部 `MScriptDraftOutcome` 三态,对外仍只写 `m_script_skeleton: string | null`。
- mscript 普通失败降级在 mscript 叶子 wrapper 内完成;`CancelledError` / `KeyboardInterrupt` / `SystemExit` 原样传播;plan_composer 和 build_steps 主失败码不被 mscript 子码覆盖。
- 重生成资格去掉 `m_script_skeleton is None`;保留 active corrections、`build_steps is None`、`stale_pending_regeneration`。
- 前端按钮谓词同步为 `structuredSteps == null`;`build_steps` 有值且 `m_script_skeleton=null` 不再显示按钮。
- eval paired-full 镜像同步 mscript outcome,summary 新增 `mscript_outcome` / `mscript_degradation_code`;summary version bump 到 `paper_pdf_smoke_guidance_observability_v4`。
- 已知同源缺口:plan 层评测编排仍是复制镜像,未抽成生产同源函数;本卡只把 C1 触及的镜像点焊住。
