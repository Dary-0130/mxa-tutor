# TASK-517:run-state 写入 scoped-token 安全门 + 安全契约(v0.3-b / b3-2a)

## 状态
🔲 **v0.3 收一轮定向复审稿,待二轮定向复审**(2026-06-24)。一轮定向复审:**R1(GPT)剩 P0×1 / P1×1**(进程内撤销的多 worker 边界 + 标识规范化语义;**P0-7 两 PR review gate、P0-1 非生产 scope 门控制面、P0-3 撤销范围切法均已认可**,P0-3 待多 worker 边界条件闭合);**R6(Codex)P0=0,剩 P1×2 文案收紧**(进程代次失效机制 + endpoint 形态),并已 **ACK v0.2 形态**;实测 `origin/main df383c8` 仍一致,无 decision 15。三拆(a 安全门 / b 持久化+状态机 / c 编排+解释)+ 顺序 `a→b→c` 不重开。本 v0.3 仅收这几条(见 §二审变更对照),**不引入新 PM 决定**。

**关键结构变更(R1 P0-7;Codex 认同"一卡可压,拆只为审查负担")**:a **仍是单卡 TASK-517,不增卡**;但实现**分两个独立过审的 PR**——**517-A substrate**(建锁:token profile / 配置 / dev issuer·revoker / 撤销 store / 单测,**不开放 run-state 写路径**)→ **517-B enforcement**(装锁:route 级 enforcement + auth context + MATLAB 携带·刷新 + OpenAPI / docs / e2e)。**b(TASK-518)须 517-A、517-B 均合并后才派**。这是"审得安全"前提下最省的拆法:不增卡,只多一个 PR。

---

## 编号与拆分
- **TASK-517**(父卡;派单前 Codex grep 复核空号)。实现两 PR:517-A(substrate)→ 517-B(enforcement)。
- v0.3-b b3 拆 b3-1(TASK-516,**已合并 #118 / df383c8**)→ b3-2 → b3-3。b3-2 = a/b/c **三张卡**;本卡 = a(内部两 PR)。b(持久化+状态机,TASK-518 拟)、c(编排+解释,TASK-519 拟)另卡,顺序 `a→b→c`。
- **定义来源**:TASK-515 v0.4 + TASK-516 §硬前置 R1 P1-4 + 本卡 §实测地基(Codex R6 实测 df383c8)+ GPT R1 一审 + Codex R6 一审。

---

## 背景与定位
- **硬前置(b3-1 R1 P1-4)**:写入任何 run-state 快照 / 派生状态前,必须先落 scoped-token 校验(claim 绑 user/project/session/`capability=run_state:write` + 校验 body `session_id` 与 claim 一致);未完成,b/c 不得派。本卡 = 落这道前置。
- **a 做一件事**:给 run-state 写入路径建一道 **development/test 密码学 scope 门**(R1 P2-1:**非生产用户身份认证**,生产登录 / SSO 仍归 seam)——一套 dev/test 可签发、可校验、可撤销、客户端可携带刷新的 scoped token,并在 `/run-state` **任何 service 副作用之前**完成密码学校验 + claim 一致性 + 构造可信 auth context(供 b 消费)。
- **a 明确不做**:持久化 / 跨轮状态机 / TTL / 删除(b);run-state 的 LLM 解释 / 读历史 / 建议 / read·explain 能力(c);改 `/diagnostic`、`/explanation` 语义;动守序与 32KB;拓宽 `MatlabEngineProvider`;seam 前上 production(不变量 14);生产身份提供方 / 登录 / SSO / 长效 refresh token。
- **a 验收门 = 机制 + 确定性安全护栏**:合法 token 仍得 b3-1 既有临时回执(`durable=false` 不变);非法 / 伪造 / 过期 / `nbf` 未到 / 撤销 / 能力不符 / iss-aud 不符 token 在 service 副作用前 fail-closed;auth context 不可由外部字段直接构成;失败路径不记 token / claim / `jti` / header / 指纹 / 异常文本。

---

## 架构站位(R1/R6 一审定;v0.2 收紧)

### 控制面与信任(R1 P0-1;4(a) 条件成立)
- 推迟生产登录 / SSO **成立**,足以让 b 在 **dev/test** 获得真实密码学校验门;但 **"b 起写保护即为真" 限定为 "非生产密码学 scope 门为真"**(R1)。
- **dev issuer / revoker 必须是受控控制面,不能匿名签发**:① 独立开关、默认关闭、仅 development/test 注册(复用 `api/main.py` 现有"bridge 仅 dev/test"门,Codex 确认);② production 配到 dev issuer → **启动失败**;③ 入口须 bootstrap 凭据 / 受控 CLI / 可信通道,**不接受任意本机调用者匿名签发**;④ 调用者**不得任意要求 capability**,固定或 allowlist 为 `run_state:write`;⑤ **签名密钥永不进 MATLAB 客户端**。

### 密码学 profile(R1 P0-2;Codex P1-1。锁性质不锁算法名)
- 用成熟 JOSE / JWT 库,**禁自拼 base64 / HMAC**;verifier 固定算法 allowlist,**拒 `none` / 算法混淆 / 未知 key / header 自选算法**。
- **fail-fast**:`MATLAB_BRIDGE_ENABLED=true` 时 signing key 缺失 / 过短 / 默认值 → **启动失败**,不临时回退(Codex P1-1)。
- `.env.example` / 测试 / 日志 / `.mltbx` **不得出现真实密钥**。
- claims 严格类型;**capability 精确元素匹配**(禁 substring / 通配 / 隐式层级);每 token **不可反推唯一撤销 id(`jti`)+ `iat`**(Codex P1-2:撤销靠 `jti`,不存整 token / 指纹,守"不记录 token / 指纹")。

### 撤销契约(R1 P0-3;Codex P1-2/P1-3。**撤销状态属本卡控制面,非 run-state 持久化排除项**)
- 每次验证查权威撤销状态,**不用可能过期的正向缓存**;store 不可用 / 不确定 → **503 fail-closed**,不放行。
- **本卡 dev/test 范围**:接受**进程内即时撤销 + 短 TTL**;跨重启持久撤销 **推迟**(若日后要跨重启撤销,文件清单补 SQLite / file store + 生命周期测试,Codex P1-3)。
- **单 worker 硬锁**(GPT P0-1):本卡 dev/test auth 模式**锁单 worker / 单实例**;检测到多 worker / 多实例配置 → **启动失败**——保证撤销真值唯一(避免 worker A 撤销后 worker B 仍接受)。多 worker 撤销一致性随生产 / 共享 store 另议。
- **进程代次绑定**(Codex P1-1):token 带 startup epoch / issuer instance claim(或运行期 key 派生),verifier **只接受当前进程实例签出的 token**;**重启 → 旧代次 token 一律拒**(不靠"撤销 dict 被清空"来失效,否则稳定 signing key 下重启后未过期 token 会复活)。单 worker 锁使此机制自洽(一进程一代次一撤销真值)。
- 撤销记录至少留到 `exp + clock skew`;**"即时" = 撤销提交后开始的验证全部失败**,已判定的在途请求不承诺追溯取消。

### 刷新(R1 P0-4)
- **刷新 = 重新向受保护 dev/test issuer 取新短期 access token**;**本卡不引入长效 refresh token**。

### enforcement 形态 + 守序(R1 P0-5/P0-6;Codex P1-4)
- **route-wrapper 级**(不只 `Depends`):在 `MatlabBridgeRoute`(已持 limited body + replay)处验 `Authorization`、解析 **handler 最终使用的同一个** `BridgeRunStateRequest` 的 `session_id`、构造 `request.state.bridge_auth_context`,再进原 handler。仅 `Depends` 会让顺序贴近 Pydantic、削弱 A-6/B-2 守序证明(Codex P1-4)。
- **唯一可测守序**(R1 P0-5):`loopback(403/loopback码) → application/json(415) → 32KB body limit(413) → replay(受限 body 请求重放,非 token 防重放,P2-2) → JSON/Pydantic(malformed=422) → bearer 密码学/撤销(401) → capability/session-scope(403/auth码) → auth context → service`。
- **状态码**:`401` = 缺失 / 格式错 / 签名错 / 过期 / `nbf` 未到 / 撤销 / iss-aud 错(带 `WWW-Authenticate: Bearer` + 统一外部文案);`403` = token 有效但 capability 不足 **或** body/session scope 不符;`503` = 撤销 / verifier 基础设施不可用;**既有 loopback `403` 保持原 machine code,与 auth `403` 区分**(Codex P1-6)。
- **无双重解析 + 强制 verified context**(R1 P0-6):一致性检查消费 handler 同一 `BridgeRunStateRequest`;service 公开入口**强制收 verified context**,不提供可选 / 默认 context、不另收普通 `user_id/project_id/session_id` 当可信范围;body mismatch 路径**不解析后再查 session/repository**。

### a 不是最终写授权 + 能力≠同意(R1 P0-3前/P0-4/P1-1)
- `token.session_id == body.session_id` 只是第一道门;权威 session 校验(归属 / active / 未过期 / 幂等 / 冲突 / 顺序 / current)在 **b 同一原子写事务内**完成。**a 只交付 auth context,不查 session 内容、不判 active、不写库、不建 session。**
- `run_state:write` **精确集**,**≠ 持久化同意 / read / explain / LLM 同意**;b/c 须**显式重新声明能力,不得"沿用 a 授权"**;docs/06 写明 **authorization ≠ consent**。

### auth context 表述(R1 P1-5)+ 实现形态(Codex)
- 不号称"绝对不可构造";锁:外部字段不能直接成可信 context;production wiring 仅 verifier factory 产 context;context 为 frozen / 类型化 / capability 不可变集;测试 override 不进 production 装配。
- **形态**(Codex + R1 P1-5,core 只放纯 domain/interface):`core/domain/bridge_auth.py`(frozen `BridgeAuthClaims/BridgeAuthContext` 公开 contract,**不塞 JOSE / 配置 / HTTP / store**);`features/matlab_bridge/bridge_auth_service.py`(签发 / 校验 / 撤销 store 接口+内存实现);`api/routes/matlab_bridge.py`(route 级 enforcement);`api/dependencies.py`(只给 verifier/signer factory)。b 消费 core contract,**不 import route 私货**。

---

## 实测地基(`origin/main df383c8`,Codex R6 实测一致,无 decision 15;R1 无 repo,自包含)
- bridge route 仅 `loopback → content-type → body limit`,无 Authorization / bearer / issuer / audience / expiry / revocation(`api/routes/matlab_bridge.py`)。
- 仅限 `matlab_bridge_enabled` 须 development/test,flag 关不注册 route(`api/main.py`)——dev issuance 入口须同挂此门。
- 配置仅 `matlab_bridge_enabled` / `matlab_engine_enabled`,无 signing key / issuer / audience / token TTL / revocation store(`app/config.py`)。
- MATLAB `postRunState` 仅 `baseUrl/frozenJson/timeout`,无 header;`MatlabBridgeApp.submitRunState` 仅 `sessionId`,无 user/project(`clients/matlab_bridge/...`)——需新增 token / user / project seam。
- 既有 `BridgeErrorCode` 仅 transport 三类(`features/matlab_bridge/bridge_diagnostic_schemas.py`)——auth 错误**另立**,不污染 `/diagnostic`·`/explanation` 的 OpenAPI。
- `/run-state` 现为校验 + `durable=false` ephemeral receipt(`features/matlab_bridge/bridge_run_state_service.py`)——加门后合法 token 仍返回既有临时回执,不碰持久化。
- (**供 b**)`chat_session` 仅 `session_id/project_id/created_at/updated_at/title`,无 active / expires / generation / owner / capability;b 不得直接当权威 session。

---

## Stage 0(强制,decision 15)
```bash
git fetch origin && git rev-parse origin/main      # df383c8 或后裔;不符停手报 PM
grep -n "TASK-517" docs/03_TASK_INDEX.md; ls docs/tasks/ | grep -i 517   # 确认空号
git switch -c task/TASK-517A-auth-substrate origin/main                  # 517-A 分支(517-B 另切)
```
**§实测地基不符 → 停手报 PM。**

---

## 安全契约要点(行为锁;字段名 / 算法常量随实现)
*(整合 §架构站位,供实现与审查对表)*
- **token**:JOSE/JWT;算法 allowlist 拒 none / 混淆 / 未知 key;claims 严格类型 = user/project/session(非空、有界)+ `capability`(精确集含 `run_state:write`)+ `jti` + `iat` + `exp` + `nbf`;verifier 限**最大 token lifetime**(不只信任意远期 `exp`);可注入时钟 + 固定小 clock skew 上限(R1 P1-2)。
- **标识规范化(行为契约,GPT P1-1)**:user/project/session 经**同一领域标识解析器**产出 canonical value 后**精确比较**;鉴权层**不得自行 `trim` / 大小写折叠 / 其它宽松等价**(否则 token claim 与 body 一致性会因实现漂移)。具体 parser / 字段名后定。
- **Authorization 解析**(R1 P1-3):仅一个 `Authorization` header;仅 Bearer;拒空 / 重复 / 逗号拼接 / 多凭据 / 非法结构;**bearer 字节单独上限**(32KB body limit 不覆盖 header);库异常统一翻译,外部不见异常文本。
- **一致性 + 端点形态**(R1 P0-6;Codex P1-2):`body.session_id == token.session_id`,且消费 **handler 最终使用的同一个** `BridgeRunStateRequest`;**517-B 必须改 `/run-state` 端点形态**——handler / service 从 `request.state` 取 route-wrapper 校验过的 request + verified context,**不再以 `request_body: BridgeRunStateRequest` 让 FastAPI 二次造对象**;OpenAPI 用显式 schema + freeze 补齐。不符 → `403`,无写入、不查 session。
- **撤销**:每验证查权威态;503 fail-closed;dev/test 进程内即时 + 短 TTL;靠 `jti`。
- **失败 fail-closed + 不泄漏**:见 §架构站位 + §验收门 A-6 / B-8。
- **不动** `/diagnostic`、`/explanation` 与既有守序、32KB。

---

## MATLAB 客户端(R1 P1-4;Codex P1-5)
- access token 仅 app 私有内存(**不入** base workspace / preferences / 命令历史 / 日志);bootstrap 凭据**不编进 `.mltbx`**;token **不进**已确认 run-state JSON(`Authorization` 与冻结 payload 分离)。
- `401` → **最多重取一次** token + 重发**同一冻结 payload**;**禁无限刷新循环**;网络结果不明**不擅自生成新 `run_id`**(交 b 幂等)。
- 新增 seam:`TokenProviderFunction` 或 `UserId/ProjectId/AuthToken/RefreshFunction`;`submitRunState` 加 user/project 输入。

---

## decision 13 同步面(本卡触发;实现期逐项贴 diff,缺一项=未完工)
- **OpenAPI**:security scheme **snapshot/freeze**;**security 只挂 `/run-state`**,不误挂 `/diagnostic`·`/explanation`;`401/403/503` response body + header;feature 开 / 关时 path 与 security scheme 行为;**dev issuer/revoker 若 HTTP 接口 → 同步请求 / 响应 / error 契约或 `include_in_schema=false`**(不留"如有 schema");若仓库存生成的 OpenAPI → 纳 drift 门。
- auth 错误契约(`BridgeRunStateAuthErrorResponse` 或 run-state-only mapping)+ `docs/06_OUTPUT_CONTRACTS.md`(新增鉴权门 + 错误语义 + 守序插入点 + **authorization ≠ consent**)。
- 若新增 token / issuer schema → 导出脚本 + `Makefile verify-schema` + freeze/drift + round-trip。
- `core/domain` 不 import Pydantic;core 不含 JOSE / HTTP / store。
- 跨语言:MATLAB 携带 token 的 e2e 与 Python 校验一致。

---

## 验收门(按两 PR 分段;机制 + 确定性安全护栏,质量留 b3-3 seam)

### 517-A(substrate;**不开放 run-state 写路径**)
- [ ] **A-1 token profile**:JOSE/JWT 签发 / 校验;算法 allowlist;拒 none / 混淆 / 未知 key / 篡改签名 / 改 iss / 改 aud / 过期 / nbf 未到;claims 严格类型 + capability 精确集 + `jti`/`iat` + 最大 lifetime;可注入时钟 + skew 上限。[单测]
- [ ] **A-2 key fail-fast**:`MATLAB_BRIDGE_ENABLED=true` + key 缺失 / 过短 / 默认 → 启动失败;`.env.example` / 测试 / 日志 / `.mltbx` 无真实密钥。[单测]
- [ ] **A-3 dev issuer/revoker 控制面**:默认关、仅 dev/test 注册、production 配 dev issuer → 启动失败、非匿名(bootstrap/CLI)、capability allowlist=`run_state:write`、签名密钥不进客户端。[单测]
- [ ] **A-4 撤销 + 一致性边界**:`jti` 撤销;每验证查权威态;store 不可用 → 503;**多 worker / 多实例配置 → 启动失败(单 worker 锁)**;**撤销后无其它运行实例继续接受该 token**;**重启后旧代次 token 一律拒**(进程代次 / epoch 绑定,非仅清 dict);记录留到 `exp+skew`。[单测]
- [ ] **A-5 auth context 类型**:`core/domain` frozen `BridgeAuthClaims/BridgeAuthContext`,capability 不可变集;core 不 import Pydantic / JOSE / HTTP / store;仅 verifier factory 产 context。[单测]
- [ ] **A-6 日志不泄漏(substrate 侧)**:签发 / 校验 / 撤销路径日志不含 token / 完整 claim / `jti` / 原值 user·project·session / 异常文本 / traceback;仅事件码+状态。[单测]
- [ ] **A-7 decision 13(substrate 侧)**:若 dev issuer/revoker schema → 同步 / freeze / 导出 / verify-schema;CI(ruff/format/mypy/pytest)绿。[CI]

### 517-B(enforcement;两段合并后 b 方可派)
- [ ] **B-1 route-wrapper enforcement 在副作用前**:在 `MatlabBridgeRoute` 处验 token + 构 context,**非法 token 在任何持久化预备 / 任何 session 触碰前失败**;合法 token 走通 `/run-state` 仍返回 `durable=false` 既有回执。[单测+e2e]
- [ ] **B-2 唯一守序**:`loopback→content-type→32KB→replay→JSON/Pydantic→bearer→capability/session→context→service`;malformed JSON=422 在矩阵内;32768/32769 边界对。[单测+e2e]
- [ ] **B-3 状态码 + header**:401(+`WWW-Authenticate: Bearer`,统一文案)/ 403(capability 或 scope 不符)/ 503(基础设施不可用);loopback 403 原码与 auth 403 区分。[单测]
- [ ] **B-4 Authorization 解析**:单 header、仅 Bearer、拒空 / 重复 / 逗号 / 多凭据 / 非法;bearer 字节上限;异常统一翻译不外泄。[单测]
- [ ] **B-5 一致性 + 无双重解析 + verified context 强制**:`body.session_id≠token.session_id`→403、无写入、不查 session;**改端点形态:handler/service 从 `request.state` 取已校验 request + context,无 `request_body` 二次解析**;service 入口强制 verified context,无可选 / 默认 / 普通范围旁路。[单测]
- [ ] **B-6 auth 错误模型隔离**:auth 错误不污染 `/diagnostic`·`/explanation` 的 OpenAPI / response。[单测]
- [ ] **B-7 客户端携带 / 刷新 / 秘密**:token 仅私有内存、不入 .mltbx / workspace / 历史 / 日志 / run-state JSON;401 重取一次+重发同一 payload、无限循环禁;不擅生成新 `run_id`。[本机+单测]
- [ ] **B-8 fail-closed + 不回显(新增鉴权路径)**:**本卡新增鉴权失败路径** handler 无副作用、不回显 payload、不泄漏(R1 P1-8 限定,**不改既有 413/415/422**);auth 失败日志范围含 access/error log / stdout-stderr / MATLAB 异常展示。[单测]
- [ ] **B-9 OpenAPI 守门**:security 只挂 `/run-state`;401/403/503 body+header;feature 开 / 关 path 与 security 行为;OpenAPI snapshot/freeze;现有 schema 零漂移;`/diagnostic`·`/explanation` 完全不变;`/run-state` 合法 token 下 receipt 字节/语义兼容,无 token 的新 401 是有意变更(R1 P1-8 拆分)。[CI]
- [ ] **B-10 CI 卫生 + 不上 production**:全管道绿;feature 关 path 不存在;b1/b2/b3-1 无回归;不变量 14。[CI+本机]

---

## 不做(明确排除)
- ❌ **持久化 / 跨轮状态机 / TTL / 删除(b)**——**但鉴权撤销状态属本卡控制面,非持久化排除项**(R1 P0-3/P2-3);dev/test 进程内即时撤销 + 短 TTL,跨重启持久撤销推迟。
- ❌ run-state 的 LLM 解释 / 读历史 / 建议 / read·explain 能力(c)。
- ❌ 生产身份提供方 / 登录 / SSO;**长效 refresh token**(刷新=重取短 token);**token 单次使用 / 请求 nonce**(短 bearer 有效期内可重用,业务幂等归 b,R1 P2-2)。
- ❌ 改 `/diagnostic`、`/explanation` 语义;动守序与 `MAX_BRIDGE_BODY_BYTES`(32KB)。
- ❌ 拓宽 `MatlabEngineProvider` / 服务端跑或采集用户模型。
- ❌ 在 b 写事务里该做的权威 session 校验——a 只交付 context。
- ❌ 跨 MATLAB 版本;seam 前上 production / 作能力宣传(不变量 14)。

---

## 实施约束(全程)
- **两 PR 分段**:517-A(substrate,不开写路径)→ 517-B(enforcement);**b(TASK-518)须两段均合并后派**(R1 P0-7)。517-A 让 `MATLAB_BRIDGE_ENABLED=true` 必须配 signing key → 现有 bridge 测试 + 本地 dev env 同步补(test)key(预期摩擦,非阻塞,Codex);**单 worker 锁** = dev/test auth 模式只在单 worker 运行,多 worker / 多实例配置启动失败。
- **decision 11**:一处 `to_thread`;禁 `logger.exception`;日志 / 异常 / 对外不含 token / claim / `jti` / header / 指纹 / 异常文本 / traceback / 原始序列 / 路径 / 源码。
- **decision 12 v0.4**:本轮过后用**定向复审**(贴 §一审变更对照,各核自己 P0/P1)。
- **decision 13 / 15 / 21**:见各段;decision 21 = a 在 `features/matlab_bridge/`,共享走 `core/` 公开 contract,不 import explanation 私有。
- **不变量 14**:seam 前不上 production;确定性护栏只降低已枚举危险概率。
- **不重开已锁**:v0.3-a freeze / b1 / b2-0 / b2-1 块 A+B / b3-1 / TASK-515 v0.4 的 run/session 8 规则 + 总门 + 独立通道≠原始上传 + 两拍决策。
- **行尾**:`20260602-08`(非 decision 18)。
- **git/索引**:两 PR 各从最新 `origin/main` 切;`git diff --stat origin/main` 与 §文件清单段一致;完工 Codex 推 TASK-517 行 🔍,PM merge 后翻 ✅(decision 07 / 现行做法:Codex 改 + 开 PR、PM merge)。

---

## 文件清单(草案,Codex Stage-0 复核;按段)
**517-A**:`app/config.py`(signing key / issuer / audience / token TTL / revocation,dev/test + fail-fast);`core/domain/bridge_auth.py`(新,frozen claims/context 纯 contract);`features/matlab_bridge/bridge_auth_service.py`(新,签发 / 校验 / 撤销 store 接口+内存实现);dev issuer/revoker 入口(受控,挂 dev/test 门);测试 = token profile / key fail-fast / 控制面 / 撤销 / context 类型 / 日志。
**517-B**:`api/routes/matlab_bridge.py`(`/run-state` route 级 enforcement,**不动守序 / 32KB / 现有两端点**);`api/dependencies.py`(verifier/signer factory);auth 错误模型(`BridgeRunStateAuthErrorResponse` 等,隔离);`clients/matlab_bridge/app/+mxa/+bridge/`(`postRunState` 加 `Authorization`、`MatlabBridgeApp.submitRunState` 加 user/project + token seam、`validateBaseUrl` 视情况);OpenAPI security scheme + freeze 测试;`docs/06_OUTPUT_CONTRACTS.md`;e2e + 跨语言 golden。
**任务卡 / 索引**:本卡;完工 `docs/03_TASK_INDEX.md` 新增 TASK-517 行(🔲→🔍)。

---

## 一审变更对照(给定向复审:逐条对应,各核自己项)
| 一审项 | 源 | v0.2 处理 |
|---|---|---|
| dev 签发 / 撤销缺可信控制面 | R1 P0-1 | §控制面:默认关 / 仅 dev-test / production 配 dev issuer 启动失败 / 非匿名 bootstrap·CLI / capability allowlist / 密钥不进客户端;"写保护为真"限定"非生产 scope 门为真" |
| 密码学 profile 留实现自由 | R1 P0-2 / Codex P1-1 | §密码学:JOSE/JWT + 算法 allowlist 拒 none·混淆·未知 key;key 缺失·过短·默认启动失败;无真实密钥入样本 / 日志 / .mltbx;capability 精确匹配;`jti`+`iat` |
| 撤销契约未闭合 + 与"不持久化"冲突 | R1 P0-3 / Codex P1-2,3 | §撤销:每验证查权威态 / 503 fail-closed / dev-test 进程内即时+短 TTL+重启失效 / 留到 exp+skew / 靠 jti;§不做 注明"撤销状态属控制面,非持久化排除项" |
| refresh 无安全契约 | R1 P0-4 | 刷新=重取短 access token;不引入长效 refresh token |
| 守序 / 解析 / 错误语义未唯一化 | R1 P0-5 | §enforcement:唯一守序串 + 401/403/503 + loopback 403 区分 + malformed=422 入矩阵 + WWW-Authenticate |
| 双重解析 / 内部旁路 | R1 P0-6 | §enforcement:消费 handler 同一 `BridgeRunStateRequest`;service 强制 verified context、无旁路;mismatch 不解析后查 session |
| 单大 PR 不站得住 | R1 P0-7 | 父卡留 TASK-517;**分 517-A substrate + 517-B enforcement 两 PR 两审,b 待两段合并**(不增卡) |
| capability 机器级锁 | R1 P1-1 | 精确集、不蕴含其它能力;b/c 须重声明;docs/06 写 authorization≠consent |
| 时间 / claim 边界 | R1 P1-2 | 非空 / 有界 / 类型化 / 规范化比较 / iss·aud 唯一规则 / 可注入时钟 / skew 上限 / 最大 lifetime |
| Authorization 解析失败面 | R1 P1-3 | §安全契约:单 header / 仅 Bearer / 拒空·重复·逗号·多凭据·非法 / bearer 字节上限 / 异常翻译 |
| MATLAB 秘密 + 重试 | R1 P1-4 / Codex P1-5 | §MATLAB 客户端:私有内存 / 不入 .mltbx·workspace·历史·日志·payload / 401 重取一次+同 payload / 禁循环 / 不擅生成 run_id / 加 token·user·project seam |
| auth context 表述过强 | R1 P1-5 | §auth context:不号称绝对不可造;外部字段不直接成 context / 仅 factory 产 / frozen 类型化 / 测试 override 不进 production;core 只纯 domain |
| 日志范围扩大 | R1 P1-6 | 失败日志另禁 jti / 原值 / header / 库异常 / traceback;测 access·error·stdout-stderr·MATLAB 展示(A-6/B-8) |
| OpenAPI 专项守门 | R1 P1-7 | §decision 13 + B-9:security 只挂 /run-state / 401·403·503 body+header / feature 开关 / snapshot freeze / dev issuer schema 必同步或 include_in_schema=false |
| A-5/A-6 措辞消歧 | R1 P1-8 | B-8 限"本卡新增鉴权失败路径"不改 413/415/422;B-9 拆 /diagnostic·/explanation 不变 vs /run-state 合法兼容 vs 无 token 401 有意变更 |
| "真安全门"口径 | R1 P2-1 | 全卡改 "development/test 密码学 scope 门";生产认证归 seam |
| replay 语义 | R1 P2-2 | 守序注明 replay=受限 body 请求重放,非 token 防重放;不做 token 单次 / nonce |
| 不持久化 vs 撤销态 | R1 P2-3 | §不做 补"鉴权撤销状态属控制面",消内存 / 持久 store 反指令 |
| enforcement 须 route-wrapper 级 | Codex P1-4 | §enforcement:route-wrapper 验 token + 解析同一对象 + `request.state.bridge_auth_context`,不只 Depends(B-1/B-2) |
| auth 错误与 loopback 403 分开 | Codex P1-6 | `BridgeRunStateAuthErrorResponse` / run-state-only mapping(B-6 + §decision 13) |
| 实现形态 | Codex 倾向 | `core/domain/bridge_auth.py` + `features/.../bridge_auth_service.py` + route enforcement + dependencies factory |

---

## 二审变更对照(一轮定向复审 → v0.3;给二轮各核自己项)
| 二审项 | 源 | v0.3 处理 |
|---|---|---|
| 进程内撤销缺多 worker 边界 | R1 P0-1(旧 P0-3) | §撤销:**单 worker 硬锁**,多 worker / 多实例配置 → **启动失败**(撤销真值唯一);多 worker 一致性随生产 / 共享 store 另议;A-4 加"撤销后无其它实例继续接受 token" |
| 进程内撤销 + 重启失效机制未钉死 | Codex P1-1 | §撤销:**进程代次 / epoch / issuer instance claim 绑定**,verifier 只认当前进程签出 token,重启 → 旧代次一律拒(非仅清 dict);A-4 加"重启后旧代次一律拒" |
| 标识规范化写松 | R1 P1-1(旧 P1-2) | §安全契约:user/project/session 经**同一领域解析器**产 canonical value 后**精确比较**,鉴权层**不得 trim / 大小写折叠 / 宽松等价**(行为契约) |
| 端点签名误导双重解析 | Codex P1-2 | §一致性+端点形态 / B-5:**517-B 改 `/run-state` 端点形态**,handler/service 从 `request.state` 取已校验 request+context,不以 `request_body` 二次造对象;OpenAPI 显式 schema+freeze |
| 517-A 签名 key 摩擦 | Codex(note) | §实施约束:517-A 同步补现有 bridge 测试 + dev env 的 test signing key(预期摩擦,非阻塞) |

**R1 三定向表态(本轮)**:P0-7(两 PR review gate)认可、P0-1(非生产 scope 门控制面)认可、P0-3(撤销范围切法)有条件认可——条件 = 上述多 worker 边界,已在 v0.3 闭。

---

## 关联决策
decision 07 / 11 / **12 v0.4(双审 + 定向复审)** / **13(本卡触发,鉴权契约)** / 15 / **21**(feature boundary)/ **不变量 14** / TASK-515 v0.4 / **TASK-516 §硬前置 R1 P1-4** / GPT R1 一审 / Codex R6 一审(实测 df383c8)。

---

## 审查与派发
- 当前 = **v0.3,待二轮定向复审**(decision 12 v0.4):**R1(GPT)** 核 P0-1(多 worker 边界)+ P1-1(标识规范化)是否闭;**R6(Codex)** 核 P1-1(进程代次失效)+ P1-2(端点形态)是否闭。各只核自己剩项 + §二审变更对照,不全文重审。其余上轮项已闭 / 已 ACK 形态。
- **实现门**:R1 ACK + R6 ACK + decision 13 同步面(实现期)。过审后派 **517-A** 建;517-A 合并后派 **517-B**;**两段合并后方派 b(TASK-518)**。
- **高风险(鉴权 + 隐私)**:每段完工 PM 看 diff + 验收勾选;**架构师每次合并前亲自取证复核真 diff + 安全门**(密钥不泄漏、副作用前 fail-closed、守序未动、32KB 未动、`/diagnostic`·`/explanation` 无回归),不只看绿勾。
- **brief**:§实测地基自包含(实测 `origin/main df383c8`,Codex R6);R1 无 repo,以本卡为准。
