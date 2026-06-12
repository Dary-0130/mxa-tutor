# TASK-403 · 问答对话页(展示 citations)v0.3 完工版

> **范围**:前端单页面 — `/view/:projectId/chat`(聊天气泡 + citations 展示 + 历史会话切换 + 追问)
> **状态**:✅ **完工**(2026-06-12)。PR squash merged commit `daa67f8` + 索引收尾 chore commit `4b3d1db`;Week 4 进度 3/6;总计 29/33
> **依赖**:TASK-401 ✅ / TASK-402 ✅ / TASK-205 / TASK-206 / TASK-304 / TASK-307
> **工艺总历程**:R0 → R1 → R2 → R3 → R4 → R6(Codex Stage 0)→ R7(Claude 终审)→ 完工,共 **7 轮 R 审 + Codex 实施**,产出 21 条 P / 反例 / 守门救场

---

## v0.2.2.1 → v0.3 完工版修订摘要(★ R6 / R7 / 索引收尾沉淀)

完工版仅做账目校准 + 工艺反思沉淀,**任务卡主体所有决策不动**(D1-D20 / 接口契约 / 验收清单 / 不做清单),代码已入仓不再变更。

| # | R6 / R7 / 索引阶段事件 | 沉淀位置 |
|:-:|---|---|
| **R6-1** | Codex Stage 0 #5 守门救场:errorMessages.ts 用 TS identifier key 写法,任务卡命令字面带引号检查 13 项全 FAIL,语义检查全 PASS;Codex 严格停手报 PM | § 14 反例账目 K_28a 自抓 +1 / 守门救场 +1 |
| **R7-1** | 架构师 R7 #2 DTO 命名凭印象:任务卡写 `ChatSessionDTO` / `ChatMessageDTO`,后端实际是 `SessionDTO` / `MessageDTO`,字段契约匹配但命名差异 | § 14 反例账目 K_28a 自抓 +1 |
| **R7-2** | 架构师 R7 索引收尾 sed 命令凭印象:首次给 PM 的 sed 命令没匹配实际行格式;Codex 派单时改"贴 grep 实测再写 new"模式 | § 14 反例账目 K_28a 自抓 +1 + § 15 工艺反思 |
| **索引清账揭露 KPI 操作清单同源漏** | TASK-402 完工时 Week 4 进度条 + 总计漏刷(`1/6` 与表面 `✅` 不一致)→ 本任 R7 索引收尾时顺手清账 27 → 29 / 1/6 → 3/6 | § 14 反例账目 K_30 +1(历史欠债揭露) |
| **PR 描述 P0-2 降级处理** | Codex `gh` 未登录,PR 描述由 Codex 生成 `task403-pr-description.md`,PM 接力粘贴到 GitHub Web UI | 不入卡;留 § 15 给下任作 Codex 工具链建议 |

---

## v0.2.2 → v0.2.2.1 修订摘要(★ Claude R4 反审 GPT v0.2.2 / 2 条全采纳 / 双向反审 ROI 直接证据)

GPT R3 起草 v0.2.2 修了 v0.2.1 的 P0(canSubmit + reducer 副作用边界),做得很扎实。但 Claude R4 极窄反审 GPT 改写过程中**踩了反例 30 同源漏 × 2**:

| # | Claude R4 反审 | v0.2.2.1 修订位置 |
|:-:|---|---|
| **R4-1(P1)** | **§ 8.3 SEND_START 伪代码漏 `inputDraft: ""` 清空字段**(v0.2.1 § 8.2 表格 SEND_START 行有 `inputDraft = ""`,GPT v0.2.2 改写 reducer 时漏列;后果:正常路径 SEND_START 后 textarea 不清空) | § 8.3 SEND_START reducer 伪代码加 `inputDraft: "",`;§ 8.2 SEND_START 行加"清空 inputDraft" 描述;**注意**:D18f 验收"草稿保留"是 canSubmit=false → return state 时自然保留(无 inputDraft 改动),不矛盾 |
| **R4-2(P2)** | **§ 8.4 effect 层 `dispatch INIT_ACTIVE_SESSION` 与 § 8.2 表格 `INIT` action 名不一致**(跨段同步漏) | § 8.2 / § 8.4 统一为 `INIT_ACTIVE_SESSION`;Codex 实施依据 § 8.4 描述精准 |

**主体不变**:GPT v0.2.2 的 R3 修订全部保留(D18 + canSubmit + reducer 纯函数边界 + D20 + § 8.4 effect 层 + D18f/g 验收 + R18 风险)。Claude R4 仅做精确字段补漏 + 命名同步,不动主体方案。

---

## v0.2.1 → v0.2.2 修订摘要(★ GPT R3 职责边界审 / 2 条全采纳)

GPT R3 conditional fail · D1-D20 主体不翻 · **新增 1 P0 + 1 P1 = 2 条全采纳** · 修后 Claude R4 只需极窄复核 D18 + reducer/effect 边界。

| # | R3 反馈 | v0.2.2 修订位置 |
|:-:|---|---|
| **P0-1** | D18 只锁 `MESSAGE_RETRY`,没锁普通 `SEND_START`;首轮新会话失败后 `resolving` 期间,用户重新输入并点发送仍会无 `session_id` POST,可能创建第二个 session | § 3 新增 **D20** 职责边界 + D18 修订;§ 8.1 增 `isNewSessionUnconfirmed` / `canSubmit` selector;§ 8.2 `SEND_START` 加 reducer guard;`resolving / needs_refresh + activeSessionId=null` 时普通发送被拒绝;§ 10.3 增 **D18f / D18g** |
| **P1-1** | reducer 里写 localStorage / 触发异步 `SESSIONS_LOAD` 越界;状态机与副作用边界混合 | § 5 组件职责补充;§ 8.2/8.3 明确 `useChatReducer.ts` 是纯函数,不读写 localStorage,不发 fetch,不 dispatch 异步 action;localStorage 写/清 + `GET /sessions` 触发统一放 `ChatPage.tsx / useChatSession.ts` effect 层;§ 10.1 增 reducer 副作用 grep 守门 |

**本轮关键不变量**:

```text
未确认新会话(newSessionAttempt.status = resolving / needs_refresh)且 activeSessionId=null 时:
  - MESSAGE_RETRY 不得发 POST
  - 普通 SEND_START 不得发 POST
  - SESSION_NEW / SESSION_SWITCH 不得清掉恢复流程
  - textarea 可保留草稿,但发送按钮 disabled
  - 只有恢复出 exactly one session_id 后,后续 POST body 才允许带该 session_id 继续
```

**职责边界新增硬约束**:

```text
useChatReducer.ts:
  只做纯状态转换 + selector(canSubmit / canRetry),不得 localStorage / fetch / async dispatch。

ChatPage.tsx / useChatSession.ts:
  承担 apiGet / apiPost / localStorage write/clear / SESSIONS_LOAD 触发。

UI 组件:
  只消费 selector 结果渲染 disabled / banner / tooltip,不得自行拼状态机条件。
```

---

## v0.2 → v0.2.1 修订摘要(★ GPT R2 conditional fail / D18 三态收口)

R2 主体不翻,唯一 P0 是 D18 恢复中 retry 竞态。v0.2.1 已把 `newSessionAttempt = { failed, needsRefresh }` boolean pair 改为三状态枚举:

```typescript
type NewSessionAttempt =
  | null
  | { status: "resolving"; failedUserTempId: string }
  | { status: "resolved"; sessionId: string; failedUserTempId: string }
  | { status: "needs_refresh"; failedUserTempId: string };
```

恢复规则:
- `SEND_FAILED` 且 `pendingSessionId === null` → `resolving`,retry disabled,由 effect 层自动 `GET /sessions`。
- `SESSIONS_LOADED` 后仅当 `newSessions.length === 1` → `resolved` + `activeSessionId=sid`。
- `newSessions.length === 0` 或 `> 1` → `needs_refresh`,不自动选 session,retry disabled。
- `SESSIONS_LOAD_FAILED` → `needs_refresh`。
- `MESSAGE_RETRY` 只有 `activeSessionId !== null` 且不处于 `resolving / needs_refresh` 才允许。

---

## v0.1 → v0.2 修订摘要(★ GPT R1 全采纳 + Claude 抓 GPT 反例 28)

R1 3 P0 + 6 P1 + 6 P2 全采纳。核心已并入正文:
- 首轮新会话失败后 session 恢复 / retry 语义(D18)。
- pending request `requestId / sessionId / tempId` stale guard(D19)。
- Stage 0 空 grep / 不存在路径命令全部报告式。
- `evidence_missing` 进入错误矩阵,文案对齐 GLOBAL 第 22 条:"出了点问题,我们已经记录,稍后再试"。
- citation 卡 keyboard / focus / touch accessible。
- localStorage stale session 三触发点清理(D13)。
- E 类 history 推断标 `fallbackInferredFromHistory` heuristic。

---

## 0. § 0.5 架构师 Stage 0 自查(决策 09 v2 雏形,task-402 § 17 升级版执行)

> task-402 § 17 给下任的话明示:架构师起草接口契约 / 字段表前必须 grep 输出粘贴。本任架构师**无 repo 访问**,以 task-205-v0.2 / task-307-v0.3 / task-401-v0.3 / task-402-v0.2.2 文档为间接源,**Codex Stage 0 必须复核**。

| 校验项 | 源 / 状态 | 备注 |
|---|---|---|
| TASK-403 索引行存在性 | 03 索引 Week 4 段 `TASK-403` 行 `🔲` | grep 已确认 |
| 上游 TASK-401 完工 | 03 索引 Week 4 段 `TASK-401` 行 `✅` | grep 已确认 |
| 上游 TASK-402 完工状态 | 03 索引 Week 4 段 `TASK-402` 行 `✅`(假设) | **Codex Stage 0 #1 必须 grep 确认** |
| 上游 TASK-205 ChatResponse 8 字段 | task-205-v0.2 § 5.1 + § 8.3 | **Codex Stage 0 #2 必须 grep `class ChatResponse` 确认实际 schema** |
| 上游 TASK-205 endpoint 路径 | task-205-v0.2 § 5.1-5.3 | **Codex Stage 0 #2 必须 grep `@router` api/routes/chat.py 确认**(★ 反例 28 候选 — TASK-401 端点表错) |
| 上游 TASK-307 R12 sentinel 消解 | task-307-v0.3 § 接口契约 | backend 已替换 `__project_overview__` → "项目总览" 用户可见短标签;前端仍 defensive |
| 前端共享 lib 现状 | task-402 § 9 组件结构 + § 7.1 GLOBAL_ERROR_MESSAGES (27 backend + 2 virtual) | **Codex Stage 0 #3 必须 cat `web/src/lib/{api,types,errorMessages,localStore}.ts` 确认实际产物** |
| 路由 `/view/:projectId/chat` 占位 | task-401-v0.3 App.tsx + ChatPage.tsx 占位 | TASK-401 ✅ 完工时已落 |

**架构师无 repo 自承认**:本 v0.1 接口契约 / 字段表 / endpoint 路径**部分**基于上游任务卡推断。任一与 Codex Stage 0 实测不符,Codex 停手报 PM(决策 09 纪律 1),修文档不修代码。

---

## 1. 上下文

### 在项目中的位置

Week 4 第 3 个前端任务(401 ✅ → 402 ✅ → **403** → 404 / 405 / 406)。

后端三周已交付:
- TASK-202 上传(202 Accepted)
- TASK-203 / 207 工程导览
- **TASK-205 粗 RAG 问答 API**(POST /chat / GET /sessions / GET /messages)
- TASK-304 向量 RAG 整合(替换 KeywordRetriever → VectorRetriever)
- TASK-307 Evidence Citation Enforcer(`__project_overview__` sentinel backend 消解)

前端 401 + 402 已交付:
- 框架:React + Vite + TypeScript strict + Tailwind v4 + react-router-dom v7
- 路径:页面 `/view/:projectId/chat`,API `/projects/*` `/upload` `/health`
- 共享 lib:`api.ts`(apiGet / apiPost / apiUpload / apiUploadTask)/ `types.ts`(ProjectOverview)/ `errorMessages.ts`(GLOBAL_ERROR_MESSAGES 27 backend + 2 virtual)/ `localStore.ts`(24h TTL)
- 砼核视觉(冷灰水泥 + 信号橙 + IBM Plex + 锐利直角 + 噪点纹理)

本任落地"用户与 mxa 交互的核心界面":学生上传工程 → 看导览 → 在导览页 Panel 6 CTA 点击"开始提问" → 进入本页 → 提问 → 看带 citations 的回答 → 追问 → 切换历史会话 → 关闭。

### 产品定位约束(01 宪法)

- 01 § 11 line 364:**单次问答响应 < 8 秒**(HTTP 同步等待,MCS 不做 streaming)
- 01 § 9 line 339:数据库不存工程原始内容
- 01 § 9 line 340:日志不记录原文(前端 console.error 同理:不打印 question / answer 原文,只 metadata)
- 01 壁垒 3:**强制证据引用**,citation 区块在每条 assistant 消息下必显示
- 05 § 7.4 前端展示:"依据" 区块可点击(MCS 阶段先**不**真实跳转,只渲染 + tooltip)+ E 类回答标注"证据不足"
- 05 § 8.4 禁止 emoji(05 § 7.4 自身的 ⚠️ 字符示例**违反** § 8.4,本任以 § 8.4 为准 — 用文字 "证据不足" 替代图形)

### 后端 API(以 TASK-205 § 5 为准,Codex Stage 0 #2 复核)

| 端点 | 方法 | body / params | 响应 |
|---|---|---|---|
| `/projects/{pid}/chat` | POST | `{ question: str(1-1000), session_id?: str }` | `ChatResponse`(8 字段)|
| `/projects/{pid}/sessions` | GET | — | `{ project_id, sessions: ChatSessionDTO[] }` |
| `/projects/{pid}/sessions/{sid}/messages` | GET | `?limit=50&offset=0`(FastAPI Query 约束)| `{ session_id, messages: ChatMessageDTO[] }` |

**★ 反例 28 兜底**:TASK-401 端点表(task-401-v0.3 § 上下文)写了 **POST** `/projects/{pid}/sessions/{sid}/messages`(追问),实际 TASK-205 § 5.1 是**首次 / 追问统一 POST `/chat` + body 带 session_id**。Codex Stage 0 #2 必须 grep 实际路径,以 TASK-205 为准。

---

## 2. 输入(前置依赖)

- **必须已完成**:TASK-401 ✅ / TASK-402 ✅(GLOBAL_ERROR_MESSAGES + localStore + api.ts + Layout 已落)/ TASK-205 / TASK-206 / TASK-304 / TASK-307
- **必须已读**:01 宪法、02 架构总览(§ 3 目录 + § 10 部署)、04 工程规范、05 风格指南 § 5 D 类 / § 6 E 类 / § 7.4 前端展示
- **必须存在**:`web/src/routes/ChatPage.tsx` 占位(TASK-401 落)+ `web/src/lib/{api,types,errorMessages,localStore}.ts`(TASK-402 落)+ `web/src/components/Layout.tsx`(TASK-401 落)

---

## 3. 决策表

> D1-D17 沿用 v0.1 主体;D5 / D7 / D13 / D16 按 R1 修订;D18 / D19 / D20 为 R1-R3 新增硬约束。

| # | 决策 | 选定 | 理由 / 边界 |
|:-:|---|---|---|
| **D1** | 布局 | 单列主区 + 顶部"会话切换"下拉 | MCS 阶段单工程会话量低,不做固定侧边栏 |
| **D2** | 状态管理 | `useReducer` + ChatPage 局部状态机 | 不引 Zustand/Jotai/Redux;状态集中但不全局化 |
| **D3** | 消息渲染 | 纯文本 `white-space: pre-wrap`,不解析 Markdown | 0 新依赖,降低 XSS 面 |
| **D4** | citation 展示 | 每条 assistant 消息下内联"依据"区块 | 对齐 05 D 类输出,不做右侧 panel |
| **D5** | citation 交互 | 不真实跳转;citation card 可 Tab focus;Enter/Space 展开/收起;hover/focus 展示完整字段;触屏点击展开 | MCS 无文件查看器;"不跳转"不等于 hover-only |
| **D6** | `__project_overview__` sentinel UI defensive | `citation.file_path === "__project_overview__"` 时显示"项目总览" | TASK-307 已后端消解,前端仍 defensive |
| **D7** | E 类降级展示 | 当轮 POST 用 `is_fallback`;history replay 用 `role=assistant && citations=[]` heuristic,并标 `fallbackInferredFromHistory=true` | GET messages 不返回 `is_fallback / fallback_reason / confidence`;代码层必须区分真值与推断 |
| **D8** | 错误处理 | 单条消息失败,不整页崩;retry = 新一轮 POST `/chat` | 对齐 TASK-205 失败持久化:user 已入库,assistant 不入库 |
| **D9** | orphan user message | history replay 中 user 后无 assistant → 显示"上次回答未生成,点击重试" | 承接 TASK-205 orphan user message 风险 |
| **D10** | 发送状态 | 乐观渲染 user + pending assistant;响应后替换 | <8s 同步 HTTP 下避免空白等待 |
| **D11** | 输入框 | 多行 textarea;Enter 发送 / Shift+Enter 换行;1000 字前端硬限 | 避免 422 体验差 |
| **D12** | 自动滚动 | 新消息自动到底;用户回看历史时不强制滚 | 避免抢视线 |
| **D13** | localStorage active session | key `mxa:chat-active-session:{pid}`;三清理触发点:(a) `project_not_found` 清 key;(b) `chat_session_not_found` 且 key 匹配 sid 清 key;(c) "新会话"按钮保留旧 key,直到新 session_id 返回后覆盖 | 不能笼统写"project 删除时一并清";必须有可执行触发点 |
| **D14** | 新会话创建时机 | POST `/chat` 不带 `session_id` → 后端建 session + 返回 `session_id`;前端收到后写 localStorage + 刷新 sessions | 不预创建空 session |
| **D15** | 列表性能 | 不引入虚拟列表 | MCS 单会话消息量低 |
| **D16** | 视觉风格 | 砼核延续;E 类 banner 固定纯文本 `[证据不足] 以下回答仅供参考` | 不使用 `⚐` / `⚠️` / emoji |
| **D17** | 依赖边界 | 0 新增 prod 依赖 | 复用 TASK-401 / 402 白名单 |
| **D18** | 新会话首轮失败 session 恢复 | 首轮 POST 失败且 `activeSessionId === null` → `newSessionAttempt.status="resolving"`;effect 层 `GET /sessions`;exactly one 新 sid 才恢复;0 或 >1 新 sid / load 失败 → `needs_refresh`;未确认期间 retry 和普通发送均禁止 | 闭合 R1/R2/R3 同一 P0:不得因错误响应不带 session_id 而创建第二个 session |
| **D19** | pending request stale guard | `pendingRequestId / pendingSessionId / pendingAssistantTempId`;`SEND_SUCCESS / SEND_FAILED` 必须带 requestId,不匹配 ignore;`RESET` 后旧响应不得写入 | reducer 层 guard,不只靠按钮 disabled |
| **D20** | 状态机职责边界 | reducer 纯函数;effect 层负责 API / localStorage / SESSIONS_LOAD;UI 只消费 selector | 防副作用混入 reducer,也防 UI 自行组合 flag 绕过状态机 |

---

## 4. 接口契约

### 4.1 `web/src/lib/types.ts` 补全(本任新增)

```typescript
/** TASK-205 ChatResponse(8 字段,首次 / 追问统一)
 *  ★ Codex Stage 0 #2 必须 grep `class ChatResponse` 确认实际字段 */
export interface ChatResponse {
  session_id: string;
  message_id: string;
  answer: string;
  confidence: "high" | "medium" | "low";
  citations: SourceRef[];
  follow_up_suggestions: string[];
  is_fallback: boolean;
  fallback_reason:
    | "no_retrieval_hits"
    | "invalid_or_missing_citations"
    | "low_relevance"
    | "out_of_scope"
    | null;
}

/** TASK-205 § 5.1 ChatRequest body */
export interface ChatRequest {
  question: string;             // 1-1000 字
  session_id?: string;          // 缺省则后端建新 session
}

/** core/domain/source_ref.py 6 字段(★ Codex Stage 0 #2 grep `class SourceRef` 确认)*/
export interface SourceRef {
  file_path: string;
  line_range?: [number, number] | null;
  block_id?: string | null;
  block_name?: string | null;
  parent_subsystem?: string | null;
  parameter_name?: string | null;
}

/** TASK-205 § 5.2 GET /sessions */
export interface ChatSessionListResponse {
  project_id: string;
  sessions: ChatSessionDTO[];
}

export interface ChatSessionDTO {
  session_id: string;
  title: string;
  created_at: string;          // ISO
  updated_at: string;          // ISO
}

/** TASK-205 § 5.3 GET /messages
 *  ★ R2 P1-7:不含 is_fallback / fallback_reason / confidence;UI 用 role+citations=[] 推断 E 类 */
export interface ChatMessageListResponse {
  session_id: string;
  messages: ChatMessageDTO[];
}

export interface ChatMessageDTO {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;          // ISO
  citations: SourceRef[];      // user 消息为 []
}

/** 前端内部消息表示(client-temp-id + pending 状态)*/
export interface UIMessage {
  message_id: string;          // server message_id 或 client-temp-id "temp-{n}"
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations: SourceRef[];
  // UI-only 字段(server 不返回):
  status: "sent" | "pending" | "failed" | "orphan";   // pending: 正在等响应;failed: 当轮失败;orphan: 历史 user 无后续 assistant
  is_fallback?: boolean;       // 仅当轮 POST /chat 响应有值;历史回放为 undefined
  fallbackInferredFromHistory?: boolean; // ★ D7:history replay heuristic,与当轮 is_fallback 真值区分
  fallback_reason?: ChatResponse["fallback_reason"];
  error_code?: string;         // 当轮失败时存 backend error code
  confidence?: "high" | "medium" | "low";
  follow_up_suggestions?: string[];
}
```

### 4.2 `web/src/lib/api.ts` 不动(本任零新增)

TASK-401 `apiGet<T>` / `apiPost<T>` 已实现,本任直接 import 调用。**不**新增 helper(如 `apiChat` 包装),保持 lib 层薄。

---

## 5. 组件结构

```text
web/src/
  routes/
    ChatPage.tsx                     # 主页面,顶层路由,200-280 行
    chat/
      ChatHeader.tsx                 # 顶部:工程名 + 会话切换下拉 + "返回导览"链接,80-120 行
      MessageList.tsx                # 消息列表 + 自动滚动逻辑,100-150 行
      MessageBubble.tsx              # 单条消息气泡(user / assistant 两种)+ orphan 重试,120-180 行
      CitationCard.tsx               # 单条 citation 展示卡(file_path / block_name / line_range / parent_subsystem),60-100 行
      FallbackBanner.tsx             # E 类降级标记 + "证据不足"文案,40-60 行
      ChatInputBar.tsx               # 底部输入框 + 发送按钮 + 字数提示,80-120 行
      FollowUpChips.tsx              # 追问建议小卡片(follow_up_suggestions),40-60 行
      useChatSession.ts              # session 切换 + GET /messages hook,80-120 行
      useChatReducer.ts              # ChatPage reducer + Action type,120-180 行
      useAutoScroll.ts               # 自动滚动逻辑 hook(D12),40-60 行
      chatHelpers.ts                 # orphan 识别(D9)+ sentinel 替换(D6)+ formatTimestamp,80-100 行
      chatErrorMessages.ts           # chat 相关 4 错误 code 子集(可空,直接复用 GLOBAL)
  lib/
    types.ts                         # ← 追加 § 4.1 chat 类型(不动现有)
    localStore.ts                    # ← 追加 mxa:chat-active-session:{pid} 读写函数(不动现有 24h TTL 函数)
```

预估总新增:**约 11 文件,1200-1500 行 TS + 100-150 行 CSS**;每文件 ≤ 300 行(04 § 4 line 180)。

---

## 6. UI 设计规范(砼核延续)

### 6.1 整页布局(单列,D1)

```
┌──────────────────────────────────────────────┐  ← Layout(TASK-401)
│  mxa-tutor                            🔘     │
├──────────────────────────────────────────────┤
│  ← 返回导览  |  PMSM 矢量控制  |  会话:▼     │  ← ChatHeader
├──────────────────────────────────────────────┤
│   [user]                  右对齐橙色边框气泡  │
│   速度环 Kp 设这么大是为什么?                  │
│                                              │
│   [assistant]  左对齐灰色边框气泡             │
│   从 init_params.m 的参数定义看,Kp=5.0...    │
│   ─────                                       │
│   依据                                        │
│   • init_params.m  L15-18                    │
│   • pmsm_foc.slx / SpeedLoop / PID Controller│
│                                              │
│  ──────────────────────────────────────────  │
│  [继续追问...]                        [发送] │
└──────────────────────────────────────────────┘
```

### 6.2 色板复用

- 背景:`--color-concrete`
- 主文字:`--color-chalk`
- 次文字:`--color-rebar`
- user 边框:`--color-signal`
- assistant 边框:`--color-formwork`
- 路径 / 行号:`--font-mono`

### 6.3 气泡形态

- user:右对齐,max-width 72%,1px signal border,深灰背景
- assistant:左对齐,max-width 78%,1px formwork border,暖白正文
- pending assistant:"正在思考..."骨架,不得用 spinner 过度动画
- failed / orphan:user 气泡下方显示小型文字按钮"重试"

### 6.4 "依据" 区块 + citation a11y(D5)

- assistant `citations.length > 0` 时显示"依据"区块。
- citation card 是可聚焦元素:`tabIndex=0` 或 `<button type="button">` 语义,但**不跳转**。
- hover / focus 展示完整字段;Enter / Space 展开或收起详情;触屏点击展开或收起。
- 展开内容包含:file_path / line_range / block_name / parent_subsystem / parameter_name;缺失字段显示 `—`。
- `file_path === "__project_overview__"` 时显示"项目总览",不暴露 sentinel 字面。

### 6.5 E 类降级 banner(D7 / D16)

固定纯文本:

```text
[证据不足] 以下回答仅供参考
```

不得使用 `⚐` / `⚠️` / emoji。HTTP 5xx `evidence_missing` 不是 E 类正常回答,按单条 failed 处理;只有 200 + `is_fallback=true` 或 history heuristic 才显示本 banner。

### 6.6 输入框 + 发送按钮(D11 / D18 / D20)

- `textarea` min 1 行 / max 6 行 / auto-grow。
- Enter 发送;Shift+Enter 换行。
- 1000 字硬限;1001 字时前端拦截。
- 发送按钮 disabled 条件统一来自 `canSubmit(state)` selector,UI 不自行拼 `sending / newSessionAttempt / activeSessionId`。
- `newSessionAttempt.status="resolving" | "needs_refresh"` 且 `activeSessionId=null` 时,textarea 可保留草稿,发送按钮 disabled,不发 POST。

---

## 7. 错误处理(复用 TASK-402 § 7.1 GLOBAL_ERROR_MESSAGES)

### 7.1 本任使用的 error code 子集

| code | 来源 | UI 文案 / 行为 |
|---|---|---|
| `chat_session_not_found` | TASK-205 / 206 | GET messages:整页/局部会话加载错误;POST chat:单条 failed + 清 active session key |
| `chat_generation` | TASK-205 | 单条消息 failed,文案用 GLOBAL:"回答生成失败,请刷新重试" |
| `llm_auth` | TASK-206 | 单条 failed |
| `llm_quota` | TASK-206 | 单条 failed |
| `llm_rate_limit` | TASK-206 | 单条 failed |
| `llm_timeout` | TASK-206 | 单条 failed,可 retry |
| `llm_server` | TASK-206 | 单条 failed |
| `store_error` | TASK-205 / 206 | 整页或单条,视触发点 |
| `evidence_missing` | TASK-206 GLOBAL 第 22 条 | **HTTP 5xx 单条 failed**,文案必须是"出了点问题,我们已经记录,稍后再试";不显示 E 类 banner |
| `project_not_found` | TASK-201 / 206 | 整页 banner + 清 active session key + 返回上传 |
| `quota_exhausted` | TASK-206 / 404 | 单条 failed 或整页 quota 提示 |
| `embedding_model_load` | TASK-301 / 402 GLOBAL | 单条 failed |
| `network_error` | 前端虚拟 | 单条 failed |

### 7.2 UI 决策矩阵

| 层级 | 触发 | UI |
|---|---|---|
| 整页错误 | GET `/projects/{pid}/sessions` 失败且无法继续 | 顶部错误区 + 返回导览 |
| 整页错误 | GET `/sessions/{sid}/messages` 返回 `chat_session_not_found` | 清 `mxa:chat-active-session:{pid}`(若 key 匹配 sid),回到新会话态或显示"返回导览 / 新建会话" |
| 整页错误 | 任一路径返回 `project_not_found` | 清 `mxa:chat-active-session:{pid}`,返回上传 |
| 单条消息错误 | POST `/chat` 返回 `chat_session_not_found` | 单条 failed;清 active session key;提示"当前会话已失效,请新建会话重试" |
| 单条消息错误 | POST `/chat` 返回 `chat_generation` / LLM 类 / `evidence_missing` / `embedding_model_load` / `network_error` | user 消息保留;pending assistant 移除;失败区展示 GLOBAL 文案 + retry 条件按钮 |
| E 类正常回答 | 200 + `is_fallback=true` | assistant 正常展示 + `[证据不足] 以下回答仅供参考` banner |
| E 类 history heuristic | GET messages 中 assistant `citations=[]` | `fallbackInferredFromHistory=true`;显示同 banner,但代码层标 heuristic |
| 新会话首轮失败 | POST `/chat` 且 `pendingSessionId === null` 返回任一错误 | 进入 D18 recovery;`resolving` 期间 retry / 普通发送均禁;恢复 exactly one sid 后才允许继续 |

### 7.3 422 防御

- 前端提交前 trim;空字符串不发送。
- `question.length > 1000` 时前端拦截,不等后端 422。
- 若仍收到 422,显示 GLOBAL 兜底文案;不展示 FastAPI `detail` 原文。

---

## 8. 状态机(ChatPage reducer)

### 8.1 State shape(★ D18 / D19 / D20)

```typescript
type NewSessionAttempt =
  | null
  | { status: "resolving"; failedUserTempId: string }
  | { status: "resolved"; sessionId: string; failedUserTempId: string }
  | { status: "needs_refresh"; failedUserTempId: string };

interface ChatState {
  projectId: string;
  activeSessionId: string | null;
  sessions: ChatSessionDTO[];
  messages: UIMessage[];
  inputDraft: string;

  sessionsLoading: boolean;
  messagesLoading: boolean;
  sending: boolean;
  pageError: string | null;

  // D19 stale guard
  pendingRequestId: string | null;
  pendingSessionId: string | null;
  pendingAssistantTempId: string | null;

  // D18 first-send failure recovery
  preSendSessionsSnapshot: ChatSessionDTO[] | null;
  newSessionAttempt: NewSessionAttempt;

  tempIdCounter: number;
}
```

### 8.1.1 Selectors(★ D18 / D20)

```typescript
export function isNewSessionUnconfirmed(state: ChatState): boolean {
  return state.newSessionAttempt?.status === "resolving" ||
         state.newSessionAttempt?.status === "needs_refresh";
}

export function canSubmit(state: ChatState): boolean {
  if (state.sending) return false;
  if (state.activeSessionId === null && isNewSessionUnconfirmed(state)) return false;
  return true;
}

export function canRetry(state: ChatState): boolean {
  if (state.sending) return false;
  if (state.activeSessionId === null) return false;
  if (state.newSessionAttempt?.status === "resolving") return false;
  if (state.newSessionAttempt?.status === "needs_refresh") return false;
  return true;
}
```

UI 只能消费 `canSubmit / canRetry`,不得自行组合 flag。reducer 也必须调用同一 selector,形成 UI + reducer 双防线。

### 8.2 Action 列表

| Action | 触发 | reducer 语义 |
|---|---|---|
| `INIT_ACTIVE_SESSION` | 页面加载 | 从 localStorage 读 active sid 的动作在 effect 层;reducer 只接收结果(★ v0.2.2.1 R4-2 命名同步,与 § 8.4 一致) |
| `SESSIONS_LOAD_START` | effect 层 GET `/sessions` 前 | `sessionsLoading=true` |
| `SESSIONS_LOADED` | GET `/sessions` 成功 | 更新 sessions;若 `newSessionAttempt.status="resolving"`,比对 `preSendSessionsSnapshot`;仅 `newSessions.length === 1` → `activeSessionId=sid`, `newSessionAttempt={status:"resolved",sessionId:sid,...}`;0 或 >1 → `needs_refresh`,不自动选 sid |
| `SESSIONS_LOAD_FAILED` | GET `/sessions` 失败 | 若 resolving → `needs_refresh`;retry/send disabled |
| `SESSION_SWITCH` | 用户切会话 | 若 `sending=true` 或 `newSessionAttempt.status="resolving"` → ignore;否则切换 sid + 清 messages + messagesLoading |
| `SESSION_NEW` | 用户点普通"新会话" | 若 `sending=true` 或 `newSessionAttempt.status="resolving"` 或 (`activeSessionId=null && status="needs_refresh"`) → ignore;否则 activeSessionId=null/messages=[];localStorage key 保留到新 sid 返回后覆盖 |
| `SEND_START` | 用户普通发送 | **先跑 `canSubmit(state)`;false → ignore,不发 POST**。true → 生成 requestId;`pendingSessionId=activeSessionId`;若 active null 则快照 sessions;追加 user temp + assistant pending;**清空 inputDraft = ""**(★ v0.2.2.1 R4-1 补);清旧 resolved attempt(newSessionAttempt status==="resolved" → null) |
| `SEND_SUCCESS` | POST `/chat` 200 | 校验 requestId 匹配;不匹配 ignore;替换 pending assistant;若 pendingSessionId 为 null,用 response.session_id 设 activeSessionId;effect 层持久化 localStorage + 刷 sessions |
| `SEND_FAILED` | POST `/chat` 失败 | 校验 requestId;不匹配 ignore;user temp 标 failed;移除 pending assistant;sending=false;若 pendingSessionId 为 null → `newSessionAttempt={status:"resolving",failedUserTempId}`;effect 层触发 `GET /sessions` |
| `MESSAGE_RETRY` | 用户点失败消息 retry | **先跑 `canRetry(state)`;false → ignore**。true → 删除 failed user + 重新走 SEND_START;POST body 必带 activeSessionId |
| `RESET` | projectId 变化 / unmount | 清 pending 三件套;旧响应返回因 requestId 不匹配被 ignore |

### 8.3 reducer 伪代码边界(D20)

```typescript
function chatReducer(state: ChatState, action: Action): ChatState {
  switch (action.type) {
    case "SEND_START": {
      if (!canSubmit(state)) return state;
      const requestId = action.requestId;
      const pendingAssistantTempId = action.pendingAssistantTempId;
      return {
        ...state,
        sending: true,
        pendingRequestId: requestId,
        pendingSessionId: state.activeSessionId,
        pendingAssistantTempId,
        preSendSessionsSnapshot: state.activeSessionId === null ? state.sessions : null,
        newSessionAttempt: state.newSessionAttempt?.status === "resolved" ? null : state.newSessionAttempt,
        messages: appendOptimisticMessages(state.messages, action.userTempMessage, pendingAssistantTempId),
        inputDraft: "",   // ★ v0.2.2.1 R4-1 补:正常路径清空草稿;canSubmit=false 时已 return state 自然保留(D18f 验收"草稿保留"语义)
      };
    }

    case "SEND_SUCCESS": {
      if (action.requestId !== state.pendingRequestId) return state;
      return applySuccessfulAssistantResponse(state, action.response);
      // 不在 reducer 里写 localStorage;effect 层观察 activeSessionId 变化后写。
    }

    case "SEND_FAILED": {
      if (action.requestId !== state.pendingRequestId) return state;
      const next = markUserFailedAndRemovePendingAssistant(state, action.errorCode);
      if (state.pendingSessionId === null) {
        return {
          ...next,
          sending: false,
          pendingRequestId: null,
          pendingSessionId: null,
          pendingAssistantTempId: null,
          newSessionAttempt: { status: "resolving", failedUserTempId: action.failedUserTempId },
        };
      }
      return clearPending(next);
    }

    case "SESSIONS_LOADED": {
      const base = { ...state, sessions: action.sessions, sessionsLoading: false };
      if (state.newSessionAttempt?.status !== "resolving") return base;

      const oldIds = new Set((state.preSendSessionsSnapshot ?? []).map((s) => s.session_id));
      const newSessions = action.sessions.filter((s) => !oldIds.has(s.session_id));

      if (newSessions.length === 1) {
        const sid = newSessions[0].session_id;
        return {
          ...base,
          activeSessionId: sid,
          newSessionAttempt: {
            status: "resolved",
            sessionId: sid,
            failedUserTempId: state.newSessionAttempt.failedUserTempId,
          },
        };
      }

      return {
        ...base,
        newSessionAttempt: {
          status: "needs_refresh",
          failedUserTempId: state.newSessionAttempt.failedUserTempId,
        },
      };
    }

    case "MESSAGE_RETRY": {
      if (!canRetry(state)) return state;
      return prepareRetry(state, action.failedUserTempId);
    }
  }
}
```

硬边界:
- reducer 不调用 `apiGet / apiPost`。
- reducer 不读写 `localStorage`。
- reducer 不 `dispatch(SESSIONS_LOAD)`。
- reducer 不打印 console。

### 8.4 effect / handler 层职责(D20)

`ChatPage.tsx / useChatSession.ts` 负责:

```text
- 页面 mount:读 localStorage active sid → dispatch INIT_ACTIVE_SESSION
- activeSessionId 变化:按 D13 写 active session key;若为 null 不立即清 key
- project_not_found / chat_session_not_found:按 D13 清 key
- SEND_SUCCESS 后:若 response.session_id 是新 sid → 写 localStorage + 触发 GET /sessions
- SEND_FAILED 后:若 state.newSessionAttempt.status 从 null 变 resolving → 触发 GET /sessions
- SESSIONS_LOADED resolved 后:写恢复出的 session_id 到 localStorage
- 所有 API catch:只把 machine code 传 action,不传 question / answer / citations 原文到 console
```

### 8.5 orphan 识别算法(D9)

```typescript
export function markOrphanUsers(messages: ChatMessageDTO[]): UIMessage[] {
  return messages.map((m, idx) => {
    if (m.role !== "user") return toUIMessage(m);
    const next = messages[idx + 1];
    if (!next || next.role !== "assistant") return { ...toUIMessage(m), status: "orphan" };
    return toUIMessage(m);
  });
}
```

### 8.6 sentinel defensive(D6)

```typescript
export function displayFilePath(ref: SourceRef): string {
  if (ref.file_path === "__project_overview__") return "项目总览";
  return ref.file_path;
}
```

---

## 9. Stage 0 实地核查清单(Codex 第一步)

> 决策 09 / 反例 28 兜底:以下命令任一 FAIL 停手报 PM。预期无输出 / 不存在路径的检查必须写成报告式,不得因 grep exit 1 误停手。

### 9.1 后端契约

```bash
# #1 ChatService endpoint 实际路径
if grep -rnE "@router\.(get|post)" api/routes/chat.py; then
  echo "PASS: chat routes found"
else
  echo "FAIL: api/routes/chat.py routes not found"
  exit 1
fi
# 期望:
#   POST /projects/{project_id}/chat
#   GET  /projects/{project_id}/sessions
#   GET  /projects/{project_id}/sessions/{session_id}/messages

# #2 ChatResponse / ChatRequest / DTO schema
if grep -rnE "class (ChatResponse|ChatRequest|ChatMessageDTO|ChatSessionDTO|SourceRefDTO)" api/ features/chat/ 2>/dev/null; then
  echo "PASS: chat schemas found"
else
  echo "FAIL: chat schemas not found"
  exit 1
fi

# #3 SourceRef domain 实际字段
if grep -rn "class SourceRef" core/domain/ 2>/dev/null; then
  echo "PASS: SourceRef found"
else
  echo "FAIL: SourceRef not found"
  exit 1
fi

# #4 GET /messages 响应字段
if grep -rnE "class ChatMessageDTO|class ChatMessage" api/ features/chat/ core/domain/ 2>/dev/null; then
  echo "PASS: chat message schema found"
else
  echo "FAIL: chat message schema not found"
  exit 1
fi

# #5 GLOBAL_ERROR_MESSAGES chat/error 子集
if cat web/src/lib/errorMessages.ts | grep -E "(chat_session_not_found|chat_generation|store_error|quota_exhausted|embedding_model_load|evidence_missing)"; then
  echo "PASS: chat/global error messages found"
else
  echo "FAIL: required chat/global error messages missing"
  exit 1
fi

# #6 GLOBAL_ERROR_MESSAGES LLM 5 code
if cat web/src/lib/errorMessages.ts | grep -E "(llm_auth|llm_quota|llm_rate_limit|llm_timeout|llm_server)"; then
  echo "PASS: llm error messages found"
else
  echo "FAIL: llm error messages missing"
  exit 1
fi
```

### 9.2 前端骨架

```bash
# #7 TASK-401 / 402 已落 lib 文件
cat web/src/lib/api.ts
cat web/src/lib/types.ts
cat web/src/lib/errorMessages.ts
cat web/src/lib/localStore.ts
cat web/src/components/Layout.tsx
cat web/src/routes/ChatPage.tsx
cat web/src/App.tsx

# #8 forbidden prod dependencies:预期无命中,报告式
if grep -E "react-markdown|markdown-it|remark|zustand|jotai|redux|axios" web/package.json; then
  echo "FAIL: forbidden dependency found"
  exit 1
else
  echo "PASS: no forbidden dependency"
fi
```

### 9.3 资产 / 现状

```bash
# #9 routes/chat 目录实施前应不存在;本任完工后应存在
if [ -d web/src/routes/chat ]; then
  echo "FAIL: web/src/routes/chat already exists before TASK-403 implementation"
  exit 1
else
  echo "PASS: web/src/routes/chat does not exist before TASK-403"
fi

# #10 TODO/FIXME 扫描需排除 .venv/.git/node_modules
if grep -rnE "TODO|FIXME|XXX" web/src --exclude-dir="node_modules" --exclude-dir=".git" --exclude-dir=".venv"; then
  echo "FAIL: TODO/FIXME/XXX found in web/src"
  exit 1
else
  echo "PASS: no TODO/FIXME/XXX in web/src"
fi
```

---

## 10. 验收标准

### 10.1 静态

- [ ] `pnpm lint` + `pnpm typecheck` 全绿。
- [ ] `pnpm build` 成功;`dist/` 总大小 ≤ 1.5MB;主 chunk gzip 后 ≤ 400KB(PR 描述贴 `du -sh dist/` 与 Vite 摘要)。
- [ ] `web/src/routes/ChatPage.tsx` + `web/src/routes/chat/*.{ts,tsx}` 全部 ≤ 300 行,逐文件 `wc -l` 入 PR 描述。
- [ ] 无新增 npm prod 依赖;`git diff web/package.json` 不含新增 dependencies。
- [ ] forbidden deps 0 命中:`grep -rnE "react-markdown|markdown-it|remark|zustand|jotai|redux|axios" web/src/ || true`。
- [ ] console 隐私守门 0 命中:`grep -rnE "console\.(log|warn|error|debug).*(question|answer|content|citations|source_text)" web/src/routes/chat/ web/src/routes/ChatPage.tsx || true`。
- [ ] reducer 副作用守门 0 命中:`grep -rnE "localStorage|apiGet|apiPost|fetch\(|dispatch\(" web/src/routes/chat/useChatReducer.ts || true`。
- [ ] `useChatReducer.ts` 导出 `canSubmit / canRetry` selector;UI 组件不自行拼 `newSessionAttempt` 条件。

### 10.2 功能(对照决策表逐项)

- [ ] **D1** 单列布局 + 顶部 ChatHeader 含会话切换下拉,无侧边栏。
- [ ] **D3** assistant 消息 `white-space: pre-wrap`,Markdown 原样不解析。
- [ ] **D4** 每条 assistant 消息含"依据"区块(若 `citations.length > 0`)。
- [ ] **D5 a11y**:Tab 能聚焦 citation card;Enter / Space 展开详情;鼠标 hover / focus 展示完整字段;触屏点击展开;点击不跳转。
- [ ] **D6 sentinel defensive**:mock citation `file_path="__project_overview__"` → UI 显示"项目总览"。
- [ ] **D7 当轮 fallback**:mock POST 200 `is_fallback=true` → banner;`fallbackInferredFromHistory` false/undefined。
- [ ] **D7 history heuristic**:mock GET messages assistant `citations=[]` → `fallbackInferredFromHistory=true` + banner。
- [ ] **D8** mock LLM timeout → user message 保留 + assistant failed + retry 条件符合 `canRetry`。
- [ ] **D9 orphan**:GET `/messages` 返回 `[user, user, assistant]` → 第 1 条 user 标 orphan + retry。
- [ ] **D10** 点发送立即追加 user + assistant pending;500ms mock 后替换 pending。
- [ ] **D11** Enter 发送 / Shift+Enter 换行;1001 字硬拦截。
- [ ] **D12** 自动滚动逻辑符合用户回看不抢视线。
- [ ] **D13a** mock `project_not_found` → 清 active session key + 返回上传。
- [ ] **D13b** localStorage 存不存在 sid + GET messages `chat_session_not_found` → key 被清,刷新不重复进坏 session。
- [ ] **D13c** 点击"新会话" → key 保留;首次发送收到 session_id 后覆盖。
- [ ] **D14** 新会话首次发送无 session_id → 后端建 session + UI 写 localStorage + sessions 列表刷新。
- [ ] **D16** E 类 banner 固定纯文本 `[证据不足] 以下回答仅供参考`,无 emoji / 图形符号。
- [ ] **FollowUpChips** 点击只填充 inputDraft,不触发 POST。

### 10.3 错误处理 / 状态机(D18 / D19 / D20)

- [ ] mock `chat_generation` 502 → 单条 failed + GLOBAL 文案。
- [ ] mock `evidence_missing` 500 → 单条 failed,文案为"出了点问题,我们已经记录,稍后再试",不显示 E 类 banner。
- [ ] mock POST `chat_session_not_found` 404 → 单条 failed + 清 active key + 提示"当前会话已失效,请新建会话重试"。
- [ ] mock GET messages `chat_session_not_found` 404 → 整页/局部加载错误 + 清 active key。
- [ ] mock 网络断开 → 单条 failed + `network_error` 文案。
- [ ] **D18a**:mock 首轮 POST `llm_timeout`;GET `/sessions` 返回 exactly 1 个新增 sid → `activeSessionId=sid`,localStorage 写 sid,retry enabled;retry POST body 必带该 `session_id`。
- [ ] **D18b**:mock 首轮 POST `llm_timeout`;GET `/sessions` 失败 → `newSessionAttempt.status="needs_refresh"`;retry disabled;普通发送 disabled。
- [ ] **D18c**:mock 首轮 POST `llm_timeout`;GET `/sessions` 返回 0 个新增 sid → 不自动选 session,retry disabled,提示"会话状态未确认,请刷新会话列表后重试"。
- [ ] **D18d**:mock 首轮 POST `llm_timeout`;GET `/sessions` 延迟 500ms;在 `resolving` 期间点击 retry → 不发第二个 POST。
- [ ] **D18e**:mock 首轮 POST `llm_timeout`;GET `/sessions` 返回 2 个新增 sid → 不自动选择任一 sid,不写 active session localStorage,retry disabled。
- [ ] **D18f**:mock 首轮 POST `llm_timeout`;GET `/sessions` 延迟 500ms;在 `resolving` 期间用户输入新问题并点发送 → reducer ignore `SEND_START` 或 `canSubmit=false`;网络层不发第二个 POST;草稿保留。
- [ ] **D18g**:`newSessionAttempt.status="needs_refresh"` 且 `activeSessionId=null` 时点击发送 → 不发 POST;显示"会话状态未确认,请刷新会话列表后重试"。
- [ ] **D19a**:mock POST 延迟 500ms;期间 dispatch `RESET` / projectId 切换;旧响应 requestId 不匹配 → 不写 messages / localStorage / sessions。
- [ ] **D19b**:sending=true 时 reducer 层拒绝 `SESSION_SWITCH / SESSION_NEW`,不只按钮 disabled。
- [ ] **D20**:单测或 PR 描述证明 reducer 无 localStorage / fetch / async dispatch;effect 层负责 SESSIONS_LOAD 与 localStorage。

### 10.4 浏览器兼容

- [ ] Chrome / Edge / Safari / Firefox 最新版全功能。
- [ ] 窄屏(≥ 320px)不白屏,核心发送 / 查看答案可用;不承诺完整移动端体验。

### 10.5 真启动

- [ ] `pnpm dev` + `uvicorn` + 上传测试工程 → 导览页 Panel 6 CTA → `/view/:projectId/chat` → 发问"这工程在做什么?" → 得到带 citations 答案。
- [ ] 追问"速度环 Kp 设多少?" → POST body 带同一 session_id。
- [ ] 切换历史会话 → 加载历史消息 + orphan / fallback heuristic 识别。
- [ ] 临时 mock backend 502 → 单条 retry 可用且符合 D18/D19 guard。

### 10.6 单元测试(可选,Vitest 引入边界)

> TASK-401 / 402 未引入 Vitest;本任原则上不引入。纯函数 helper / reducer 若不引测试框架,PR 描述必须给出 manual test steps + 截图或浏览器 mock 录屏。D18 / D19 / D20 是强验收,不能只口头说明。

---

## 11. 不做(明确排除)

- ❌ 不做 streaming(MCS 同步 < 8s,TASK-205 D 类)。
- ❌ 不做 Markdown 渲染(D3)。
- ❌ 不做后端改动(`git diff origin/main..HEAD --stat -- api/ core/ adapters/ features/ app/` 应空)。
- ❌ 不实现 citation 真实跳转到文件 / block(D5 Phase 2)。
- ❌ 不实现激活码 UI(TASK-404)。
- ❌ 不实现导出对话 / 复制 markdown(Phase 2)。
- ❌ 不实现 retry 后端覆盖语义;retry = 新一轮 POST `/chat`。
- ❌ 不实现语音输入 / 图片输入(Phase 2)。
- ❌ 不实现 follow_up_suggestions 自动发送;chip 只填 inputDraft。
- ❌ 不引入 Vitest / react-window / markdown-it / remark / react-markdown / Zustand / Jotai / Redux。
- ❌ 不修改 GLOBAL_ERROR_MESSAGES 文案;本任只消费,`evidence_missing` 文案以 GLOBAL 第 22 条为准。
- ❌ 不修改 Layout.tsx;ChatPage 内部自起 ChatHeader。
- ❌ 不修改 api.ts;直接使用 `apiGet<T>` / `apiPost<T>`。
- ❌ 不修改 localStore 既有 overview TTL 函数;只允许追加 chat active session helper。
- ❌ 不在 reducer 内做 localStorage / fetch / async dispatch。
- ❌ 不提供"放弃未确认会话并新建"普通入口;若产品要加,必须显式按钮 + 文案,不能复用普通"新会话"。

---

## 12. 风险与对冲

| R | 风险 | 对冲 |
|:-:|---|---|
| R1 | 后端 endpoint 路径与 TASK-401 表不一致 | Stage 0 #1 强制 grep;以 TASK-205 § 5 为准 |
| R2 | ChatResponse 实际字段与 4.1 不符 | Stage 0 #2 grep;不符停手报 PM |
| R3 | LLM 偶发输出 `__project_overview__` 字面到 answer 文本 | UI 只替换 citation 字段显示名,不替换 answer 正文 |
| R4 | 当轮 fallback_reason 4 枚举 backend 仅产前 2 个 | D7 文案合一,forward compatible |
| R5 | history replay 不返回 is_fallback / confidence | `fallbackInferredFromHistory` 标 heuristic,避免误当真值 |
| R6 | 长 answer + 多 citation 气泡过高 | max-height + native scroll |
| R7 | textarea auto-grow 浏览器差异 | 四浏览器验收;Phase 2 再引 autosize 依赖 |
| R8 | 新会话首次发送状态抖动 | D14 乐观渲染 + SEND_SUCCESS 后刷新 sessions |
| R9 | 切换会话 messages 闪烁 | messagesLoading 骨架 |
| R10 | localStorage 写入失败 | try/catch + metadata-only warn;本会话内存态继续工作 |
| R11 | pending 时切换 / 新建 | D19 reducer guard + UI disabled 双防线 |
| R12 | citation 字段缺失 | CitationCard fallback `—`,不抛 UI 错误 |
| R13 | GET /sessions 大数据集分页 | MCS <20 会话;Phase 2 加分页 |
| R14 | follow_up_suggestions >3 | UI `slice(0,3)` defensive |
| **R15** | **首轮新会话失败后恢复中 retry 或普通发送创建第二 session** | D18 三态 + `canRetry / canSubmit` + D18d/f/g 验收 |
| **R16** | **多个新增 session 自动选错** | 只有 exactly one 新 sid 才 resolved;0 或 >1 一律 needs_refresh |
| **R17** | **stale response 写错会话** | D19 requestId / pendingSessionId guard |
| **R18** | **reducer 副作用导致测试/StrictMode 问题** | D20 reducer 纯函数;localStorage / API 全部在 effect 层 |
| R19 | localStorage stale session 无清理触发 | D13 三触发点 |
| R20 | Stage 0 命令预期空输出误停手 | § 9 全报告式 if/else |

---

## 13. 完工三件套

- **PR 标题**:`TASK-403: 问答对话页(展示 citations + E 类降级 + 历史会话切换)`
- **PR 描述**:
  - 对照 § 10 验收逐条勾选 + 实测命令输出。
  - Stage 0 #1-#10 报告(每条 grep / cat 实际输出)。
  - 关键截图:user/assistant 气泡 / citation a11y 展开 / E 类 banner / orphan retry / D18 recovery 提示 / 会话切换下拉。
  - D18d/e/f/g + D19a/b + D20 reducer 边界验证说明。
- **commit 拆分**(建议 8 commits):
  1. `chore(web): expand types.ts with chat schemas and UIMessage flags`
  2. `feat(web/lib): add chat-active-session localStore helpers`
  3. `feat(web): add chat helpers and citation display helpers`
  4. `feat(web): add pure chat reducer with D18 recovery and D19 stale guards`
  5. `feat(web): add chat session effects and autos scroll hooks`
  6. `feat(web): implement MessageBubble CitationCard FallbackBanner FollowUpChips`
  7. `feat(web): wire ChatPage shell with ChatHeader ChatInputBar MessageList`
  8. `chore: update TASK_INDEX TASK-403 to reviewing`(决策 07:🔲 → 🔍,不写 ✅)

---

## 14. 关联文档 / 决策 / 反例

### 关联宪法 / Task

- 01 § 3 用户 / § 9 数据隐私 / § 11 用户体验底线。
- 02 § 1 系统分层 / § 3 web/ 目录 / § 10 部署。
- 04 § 4 文件大小 / § 6 依赖 / § 11 review checklist。
- 05 § 5 D 类 / § 6 E 类 / § 7 证据强制 / § 7.4 前端展示 / § 8.4 禁 emoji。
- **上游**:TASK-401 / 402 / 205 / 206 / 304 / 307。
- **下游**:TASK-404(激活码)/ TASK-405(部署)/ TASK-406(内测发布)。

### 关联决策

- 决策 06 / 07(03 索引推 🔍 不写 ✅)。
- 决策 08(完工三件套;改文本保留原始字节,本任务文档修订需注意 CRLF/LF)。
- 决策 09(架构师必须实地核查;Stage 0 强制)。
- 决策 11(前端不涉及 async logger,但隐私日志精神沿用:console 不打原文)。
- 决策 12 v0.3.1(双 AI 互审协议;本轮按 R3 极窄职责边界审修订)。
- 决策 16(overview_schemas 留 features/overview;本任不涉及)。

### 关联反例账目(★ v0.3 完工版最终校准 / R0 → R7 全量)

| 方向 | 类型 | 本任新增 | 明细 |
|---|---|---:|---|
| GPT → Claude | 反例 28 | R1 +3 | Stage 0 shell 退出码凭印象 / evidence_missing 漏列 / localStorage 清理触发点凭印象 |
| GPT → Claude | 反例 30 | R1 +1 | E 类 banner 符号边界跨段不一致 |
| Claude → GPT | 反例 28 | R1 +1 | GPT R1 给 `evidence_missing` 文案凭印象,与 GLOBAL 第 22 条不符 |
| GPT → Claude | 反例 30 | R2 +2 | D18 boolean pair 状态机跨段漏;顶部字段名 `lastKnownNewSessionAttempt` 残留 |
| GPT → Claude | 反例 30 | R3 +1 | D18 只锁 retry,漏普通 SEND_START 同一不变量(R2 P0-1 同源拓展) |
| GPT → Claude | 工程职责边界漏(K_36 候选)| R3 +1 | reducer 内 localStorage / async 触发越界(D20 修订;归 K_30 衍生或新立项,留下任决策 12 v0.3.2 拍板) |
| **Claude → GPT** | **反例 30** | **R4 +2(★ 项目级关键事件)** | **R4-1: GPT v0.2.2 改写 SEND_START reducer 时漏列 `inputDraft: ""` 字段** / **R4-2: GPT v0.2.2 § 8.4 effect 层 `INIT_ACTIVE_SESSION` 与 § 8.2 表格 `INIT` 命名不一致** |
| 架构师自抓 | 反例 28 | R6 +1 | **R6 Codex Stage 0 #5 命令凭印象写带引号 key 检查**,实际 TASK-402 用 TS identifier key;触发 Codex 守门救场 |
| **守门救场** | — | **R6 +1** | **Codex 严格按"任一 FAIL 停手 + 不补猜"停手报 PM,工艺正向(项目守门救场累计 4 → 5)** |
| 架构师自抓 | 反例 28 | R7 +1 | **R7 #2 DTO 命名凭印象**:任务卡 `ChatSessionDTO` / `ChatMessageDTO`,后端实际 `SessionDTO` / `MessageDTO`(字段契约匹配,命名差异不阻断) |
| 架构师自抓 | 反例 28 | R7 +1 | **R7 索引收尾 sed 命令凭印象**:首次给 PM 的 sed 没匹配实际行格式;后续修改清单又凭印象推数字(27 漏计 402)|
| 索引清账揭露 | 反例 30 | R7 +1 | **TASK-402 完工时 Week 4 进度条 + 总计漏刷历史欠债**(`1/6` 与 401 + 402 ✅ 不一致);本任 R7 索引收尾顺手清账揭露 |

**累积更新**(以前任交接 § 3 末态为基):
- K_28a(GPT → Claude):22(R1)
- K_28a(Claude → GPT):**1**(R1 项目首次)
- K_28a 架构师自抓:**4**(R6 #5 命令 + R7 #2 DTO 命名 + R7 sed 命令 + R7 索引数字凭印象)
- K_30(GPT → Claude):**9**(R1+R2+R3)
- **K_30(Claude → GPT):2**(★ R4 项目级双向反审 ROI 实证)
- K_30(自抓):**2**(R1 自抓 + R7 索引清账揭露 TASK-402 漏刷)
- 工程职责边界漏(K_36 候选):**1**(R3)
- 守门救场:4 → **5**(R6,Codex 工艺正向,**不计 K 总**)
- **K 总(剔除救场)**:34 → **47**

不新增反例 31:本任 R0-R7 无决策回避,修法明确。
不新增反例 34:本任不是语义记忆错位是 GPT 改写 / 架构师凭印象的字段同步漏。

### ★ 项目级关键事件汇总

**反例 30 在 D18 状态机系列反复触发 8 次**(本任最高频反例),覆盖 R 轮全程:R1 自抓 1 / R2 GPT 抓 Claude 2 / R3 GPT 抓 Claude 1 / R3 工程职责边界 1 / **R4 Claude 抓 GPT 2** / R7 索引清账揭露 1。**核心观察**:状态机设计 + reducer 重构 + 多 dispatch 路径 + 同源字段操作,**在 7 轮 R 审中需要反复验证**;每一轮都贴近 P0-1 同一不变量(首轮新会话失败不能创建第二 session)。

**双向反审 ROI 项目级实证**:Claude 抓 GPT 共 3 次(R1 evidence_missing 文案 / R4 inputDraft / R4 INIT 命名)。**若仅 GPT 单向审 Claude,这 3 处会直接进 Codex,造成 runtime bug + 字段不清空 + action 名不存在的真实事故**。**这是决策 12 v0.3.1 R 轮工艺设计的最强 ROI 兑现**。

**守门救场 R6 / Codex 工艺正向**:Stage 0 #5 守门救场是本任第 5 次项目守门救场,**也是 Codex 第一次主动救场架构师**(前 4 次都是 Codex 救前任 PM)。**Codex 严格按"任一 FAIL 停手 + 不补猜"工艺,价值由本任直接证明**。

### 数字校准与入仓状态

- **决策 12 v0.3.2 微补丁议题**(留下任拍板):
  - K_36 新立项("工程职责边界漏" / R3 反例)或归 K_30 衍生子分类
  - K_30 当前累积 14(含本任 9 + 2 + 2 + 1)调入分类
  - 决策 09 v2(架构师 § 0.5 自查)新增"Stage 0 命令字面 vs 上游产物语法兼容性"项
  - 决策 12 v0.3 § 4.1 升仪触发条件 #2 沿用本任执行(已沉淀)
- **03 索引反例库累积段同步**(留下任):前任交接 § 11.4 提示位置 ~351-353 行;本任完工后实际累积值已在本任卡 § 14 锁定,下任在 03 索引同步时一并入仓

---

---

## 15. 给下任的话(★ 完工版 / R0 → R7 工艺反思总结)

### 本任完工状态(2026-06-12)

- PR squash merged commit:`daa67f8`(实施 8 commits + 任务卡入仓 1 commit = 9 commits squashed)
- 索引收尾 chore commit:`4b3d1db`(Week 4 1/6 → 3/6 / 总计 27/33 → 29/33 / 最后更新 06-12 / 顺手清 TASK-402 漏刷的历史欠债)
- main HEAD 当前:`<合并 chore PR 后的 commit>`(下次起任务时校验)
- D18 / D19 / D20 三大不变量经 5 轮 R 审反复打磨,**Codex 实施浏览器 mock 全 PASS**(D18d/e/f/g + D19a + D20 grep 空)
- E2E 真启动验证由 PM 自测完成

### R 轮工艺收益(本任产出的核心资产)

本任 v0.1 → v0.3 完工版走完 **7 轮 R 审 + Codex 实施 + 索引收尾**,**这是项目首次完成决策 12 v0.3.1 全套主线 task 工艺**:

| 阶段 | 产出 | 关键收益 |
|---|---|---|
| R0 v0.1 | 架构师起稿(699 行) | 范围控制 + D1-D17 主体方案 |
| R1 GPT 审 | 3 P0 + 6 P1 + 6 P2 全采纳 | evidence_missing 错误码 / a11y / banner 文案 / fallback heuristic |
| R2 GPT 审 | D18 boolean pair 跨段同步漏(R1 P0-1 复活) | 用 NewSessionAttempt 三状态枚举锁恢复窗口 |
| R3 GPT 改写 v0.2.2 | canSubmit 漏 SEND_START + reducer 副作用 | canSubmit 锁普通发送 + D20 reducer 纯函数边界 |
| **R4 Claude 反审 GPT** | inputDraft 漏 + INIT 命名(★ 双向反审 ROI)| **Claude 抓 GPT 反例 30 × 2**(项目级首次双向反审实战) |
| R6 Codex Stage 0 | #5 errorMessages.ts key 守门救场 | Codex 工艺正向停手报 PM 不补猜 |
| R7 Claude 终审 | 任务卡入仓 + D18/19/20 mock 验收 + 索引收尾 | 三大不变量真实浏览器 mock 全 PASS |

**双向反审 ROI 项目级实证**:Claude 抓 GPT 共 3 次(R1 evidence_missing 文案 + R4 inputDraft + R4 INIT 命名)。**若仅 GPT 单向审 Claude,这 3 处会直接进 Codex,造成 runtime bug + 字段不清空 + action 名不存在的真实事故**。**这是决策 12 v0.3.1 R 轮工艺设计的最强 ROI 兑现**。

### 给下一任的 5 条工艺改进建议(决策 12 v0.3.2 候选议题)

#### 1. 架构师起 Stage 0 命令时必须 grep 上游产物语法

R6-1 教训:架构师起任务卡 § 9 Stage 0 命令时,凭印象写 `grep -q "\"$code\""` 假设 errorMessages.ts 用带引号 key,实际 TS identifier key 不带引号 → Codex 实施期间触发守门救场。

**建议**:决策 09 v2 / R7 强制清单加入 **"Stage 0 命令字面 vs 上游产物语法兼容性"** 项;特别是 TS / Python object key、引号 / 不引号、单 / 双引号、字面 / 模式等。

#### 2. 任务卡 DTO 命名 vs 后端实际产物命名

R7-1 教训:任务卡 § 9.1 / § 4.1 命名 `ChatSessionDTO` / `ChatMessageDTO`,后端实际 `SessionDTO` / `MessageDTO`。字段契约匹配,但命名差异让 Codex Stage 0 grep 时需额外搜索;若你写后续 task,Stage 0 grep 命令的"期望类名"必须 grep 后端实际产物先确认。

#### 3. 架构师远程接力命令必须基于 PM 实测

R7-2 教训:架构师给 PM 接力命令时,首次给的 sed 不工作(没匹配实际行格式),后续给的修改清单又凭印象推数字(27 漏计 402)。**第二次比第一次更糟,反例 28 自抓累计 +5**。

**建议**:决策 12 v0.3.2 加入硬约束:**架构师给 PM 的接力命令链,只能给"先 grep 哪几个文件"+"贴输出我再给改法"两步**;**不许直接给 sed -i / 直接给完整 commit 命令**。Codex 派单同理。

#### 4. KPI 操作清单同源漏的项目级证据

索引清账揭露 TASK-402 完工时漏刷 Week 4 进度条 + 总计(`1/6` 与表面 `✅` 不一致 = 历史欠债)→ R7 索引收尾顺手清账揭露。**反例 30 在 task 完工 index 刷新这一同源点反复触发**。

**建议**:**04 工程标准 § 11 review checklist 加项**:每个 task 完工 PR squash merge 前,PM 必须核对:
- 03 索引 task 行 🔍 → ✅
- 对应 Week 段进度条 + 计数
- 总计计数
- "下一步" 段
- "最后更新"日期

(参考前任交接 § 2 TASK-209 收口 6 处修改模式)

#### 5. Codex `gh` 未授权时的 PR 描述接力模式

R7 实战:Codex 本机 `gh` 未登录 + Anthropic 会话内无 GitHub MCP connector → Codex 把 PR 描述生成本地文件 `task403-pr-description.md`,PM 接力粘贴到 GitHub Web UI。这是可接受的降级方案。

**建议**:若你能给 Codex / Claude 配 GitHub MCP connector,可省 PM 一步;否则沿用本任降级模式即可,不阻断主线。

### TASK-404 接力关键点

TASK-404(激活码系统)是 Week 4 主线下一个任务,**这是产品收钱的最近一步**(用户:上传 → 用完免费额度 → 付费激活码 → 继续问答)。

**前置约束**:
- 依赖 TASK-204(SQLite 存储)— 已 ✅
- 后端 + 前端联动,需新建数据库表(用户 / 激活码)+ 后端 endpoint + 前端激活页
- 工作量约 1-2 天
- 业务模式:手动发码(PM 自己生成激活码 + 邮件发给付费用户)→ TASK-406 内测发布前不引第三方支付

**关键决策点(留下任架构师起 v0.1 时拍板)**:
- 激活码格式(UUID v4 / 自定义 mxa-2026-XXXX 之类 / 长度边界)
- 单激活码 1 次使用 vs 多次 / 时效 / 与单工程 / 与单用户绑定
- quota 字段在 chat_message 表 vs 独立 quota_usage 表
- 前端激活页路径(`/activate/:code` 或 `/account` 内 input)
- TASK-403 chat 页 "quota_exhausted" banner 已预留(GLOBAL 第 21 条),TASK-404 只需触发该 code 即可联动
- 接 TASK-405 部署:激活码邮件由 PM 手动发,不引第三方邮件服务

### 升仪议题

K 总 47,持续超阈值 ≥ 15。决策 12 v0.3 / v0.3.1 已完成本任不再单独升仪。下任在 03 索引反例库累积同步 + 决策 12 v0.3.2 微补丁时,**建议立项 K_36(工程职责边界漏)分类**(本任 R3 反例),或确认归 K_30 衍生子分类。

---

## 16. R 轮流程归档(完工版)

| 阶段 | 产物 | 结论 |
|---|---|---|
| R0 | v0.1 起稿(699 行)| Claude 自承认架构师无 repo + 反例 28 候选明示 |
| R1 | GPT R1 | conditional fail;3 P0 + 6 P1 + 6 P2 全采纳;Claude 抓 GPT 反例 28 × 1 |
| R1 修订 | v0.2(879 行) | 进入 R2 |
| R2 | GPT R2 | conditional fail;D18 retry 竞态(R1 P0-1 复活)|
| R2 修订 | v0.2.1(1055 行) | D18 三态枚举收口 |
| R3 | GPT R3 起草 v0.2.2 | canSubmit 漏 SEND_START + reducer 副作用越界 |
| R4 | Claude R4 反审 v0.2.2 | conditional PASS;**Claude 抓 GPT 反例 30 × 2(★ 项目级双向反审 ROI 实证)** |
| R4 修订 | v0.2.2.1(991 行) | 进入 Codex Stage 0 |
| **R6 Codex Stage 0** | **#1-#11 全 PASS / #5 守门救场** | **守门救场 +1 / Codex 工艺正向** |
| R6 实施 | 8 commits 推 | 三大不变量浏览器 mock 全 PASS |
| **R7 Claude 终审** | 任务卡入仓 + PR 描述 + E2E + 索引收尾 | conditional PASS / 主体 PASS / 任务卡入仓 |
| 完工 PR squash merge | commit `daa67f8` | TASK-403 ✅ |
| 索引收尾 chore PR squash merge | commit `4b3d1db` | Week 4 3/6 / 总计 29/33 |
| **v0.3 完工版任务卡入仓** | **本档** | **留 PM 下次空窗顺手 git add** |

---

**版本**:v0.3 完工版(2026-06-12;R0 → R7 + Codex 实施 + 索引收尾全套完成)
**日期**:2026-06-12
**作者**:Claude(架构师,后端第三十二任;v0.2.2 GPT R3 代起草;v0.2.2.1 Claude R4 反审;v0.3 完工版反例账目最终校准 + 工艺反思沉淀)
**关联宪法版本**:v2.1(冻结)
**前置 commit**:main HEAD `aad6bc3`(决策 12 v0.3.1 merge 后)
**完工 commit**:PR squash merged `daa67f8` + 索引收尾 chore `4b3d1db`
**审批历史**:R0 v0.1 → GPT R1 → v0.2 → GPT R2 → v0.2.1 → GPT R3 起草 v0.2.2 → Claude R4 反审 v0.2.2.1 → **Codex R6 Stage 0(守门救场)+ 实施 8 commits + 浏览器 mock 全 PASS → Claude R7 终审 + 任务卡入仓 + 索引收尾** → ✅ 完工
**关联反例最终值**:K_28a 22(R1 GPT 抓)/ K_28a Claude→GPT 1(R1 项目首次)/ K_28a 自抓 4(R6+R7)/ K_30 9(R1+R2+R3)/ **K_30 Claude→GPT 2(★ R4 项目级双向反审 ROI)** / K_30 自抓 2(R1+R7 索引清账揭露)/ 工程职责边界漏 1(R3,K_36 候选)/ 守门救场 5(R6 Codex 工艺正向 / 不计 K 总)/ **K 总 47**

---

## 🎉 完工

TASK-403 ✅ 已收口。Week 4 进度 3/6,主线下一步:**TASK-404 激活码系统**(用户付费收钱路径,Week 4 业务价值最高一环)。
