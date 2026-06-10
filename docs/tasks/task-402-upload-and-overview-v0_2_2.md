# TASK-402 · 上传页 + 工程导览页 v0.2.2

> **范围**:前端两个页面 — `/`(上传页)+ `/view/:projectId`(工程导览页)
> **状态**:🟡 Stage 0 抓 3 处接受后端契约修文档(2026-06-10);可重派 Codex Stage 0
> **依赖**:TASK-401 ✅ / TASK-202 / TASK-203 / TASK-205 / TASK-206 / TASK-207 / TASK-301
> **架构师无 repo**(决策 09 / 反例 28):v0.2.2 已吸收 R2 5 项 + R3 P2 + Stage 0 3 处修订;**反例 28 元层级第四次触发**(K_28 = 19);**Stage 0 工艺严格执行成功抓出问题,本任不需修代码**

---

## v0.2.1 → v0.2.2 修订摘要(★ R2)

GPT R2 conditional fail · 2 P0 + 1 P1 · 修后极窄 R3 通过即进 Codex。

| # | 段 | 修订 | 来源 |
|:-:|---|---|---|
| 1 | § 7.1 主表 | 增 `parse_error`(后端 `ProjectStatusErrorCode` 专用,被我误归虚拟 code) | R2 P0-1 |
| 2 | § 7.1 主表 | 增 `method_not_allowed` + `http_error`(task-206 R1 兜底,v0.2.1 漏) | R2 P0-2 |
| 3 | § 7 段落 + § 7.1 描述 | "23 条" → "后端全部 machine code + 前端虚拟(26 backend + 2 virtual);最终以 Codex Stage 0 grep 输出为准" | R2 P0-1 + P0-2 |
| 4 | § 10 Stage 0 #3 | 拆 #3a(HTTP machine_code)+ #3b(ProjectStatusErrorCode)双来源核查 | R2 P0-1 |
| 5 | § 9 api.ts + § 3.4 UploadPage | apiUploadTask.abort() promise reject `DOMException("AbortError")`,UploadPage catch 后保持 IDLE 不进 FAILED | R2 P1-1 |

附带:§ 11.2 验收 +2 条 / § 12 +D20 / § 13 +R13 / § 15 K_28 累积 +2 / § 17 决策 09 v2 雏形强化。

**主体不变**:6 Panel 横向滚动、panorama 视差、组件结构、localStorage、轮询、视觉风格、Stage 0 #1/#2/#4/#5/#6/#7/#8 全部保留。

---

## 0. 决策上下文(沿用)

| # | 决策 | 出处 |
|:-:|---|---|
| 1 | 横屏方案 B = 横向滚动 6 Panel | PM 拍 |
| 2 | 不做手机端,desktop-first ≥ 1200px | PM 拍 |
| 3 | 砼核空旷 + 巨构压迫感 | PM 拍 |
| 4 | panorama 3840×1080(PM 已挑选入选版),上传页由其左端裁切 | PM 拍 |
| 5 | "开始提问" CTA 放 Panel 6 | Claude → GPT v0.2 |
| 6 | 不引入 framer-motion / zustand | 沿用 TASK-401 |
| 7 | `/view/{pid}/chat` 不做强 route guard | GPT v0.2 § 5.3 |
| 8 | 路径:页面 `/view/*`,API `/projects/*` | TASK-401 D6 |

---

## 1. 接口契约(v0.2.1 已修正,本任不动)

### 1.1 `POST /upload`

```
Content-Type: multipart/form-data
field: file (.zip, ≤ 50MB)

202 Accepted
{ "project_id": "string", "status": "parsing" }

400 / 413 / 429 / 502 / 503 / 504
{ "error": "string", "message": "string" }
```

### 1.2 `GET /projects/{project_id}/status`

```
200 OK
{
  "project_id": "string",
  "name": "string",
  "status": "parsing" | "ready" | "failed",
  "created_at": "string",
  "error_code": "string | null"     // ★ status body 历史字段名是 error_code(ProjectStatusErrorCode);外层错误响应用 error
}

404
{ "error": "project_not_found", "message": "..." }
```

### 1.3 `GET /projects/{project_id}/overview`

```
200 OK { /* ProjectOverview 12 字段,见 § 2 */ }

404 / 502 / 503 / 504 { "error": "string", "message": "..." }
```

### 1.4 前端 ApiException 字段映射

```typescript
// TASK-401 已实现(本任不改)
class ApiException extends Error {
  code: string;       // HTTP body 的 error 字段
  message: string;
  status: number;
}
```

业务用 `err.code`,HTTP body 写 `error`,api.ts 内部映射。

---

## 2. `web/src/lib/types.ts` 补全

```typescript
export type ProjectType =
  | "control_system" | "signal_processing" | "power_electronics"
  | "communication" | "motor_control" | "new_energy" | "general";

export interface EntryFileEntry { file_path: string; role: string; }
export interface SimulinkModelEntry { file_path: string; summary: string; }
export interface KeyFileEntry { file_path: string; why_key: string; }
export interface BlockEntry {
  block_name: string; block_type: string; location: string; why_key: string;
}
export interface SourceRefEntry {
  file_path: string;
  line_range?: [number, number] | null;
  block_id?: string | null;
}

export interface ProjectOverview {
  project_title: string;                       // ≤ 30 字
  project_type: ProjectType;
  one_sentence_summary: string;                // ≤ 80 字
  main_entry_files: EntryFileEntry[];          // 1-3
  main_simulink_models: SimulinkModelEntry[];  // 0-5(允许空)
  main_execution_flow: string[];               // 3-10(★ Stage 0 修正:原写 3-7,后端实际 3-10)
  key_files: KeyFileEntry[];                   // 1-8(★ Stage 0 修正:原写 3-8,后端实际 1-8)
  key_blocks: BlockEntry[];                    // 0-10(允许空)
  knowledge_points: string[];                  // 3-6(后端硬约束,前端 defensive fallback)
  beginner_reading_order: string[];            // 3-6
  likely_confusing_points: string[];           // 2-5(后端硬约束,defensive fallback)
  evidence: SourceRefEntry[];                  // ≥ 1(★ Stage 0 修正:原写 ≥3,后端实际 min_length=1;UI 仍按 ≥1 渲染 + defensive empty fallback)
}
```

**Stage 0 #2**:`sed -n '1,200p' features/overview/overview_schemas.py` 比对 12 字段 + 5 子 schema + 字数边界,以**后端代码为权威**;`06_OUTPUT_CONTRACTS.md` 已与后端一致,前端跟随该文件。

---

## 3. 上传页(`/`)

### 3.1 状态机

```
IDLE → DRAGGING → UPLOADING → PARSING → READY (navigate) | FAILED
                       ↓ (用户点击"取消上传")
                       IDLE  ★ R2 P1-1:abort 后回 IDLE,不进 FAILED
```

### 3.2 背景叙事推进

| state | 背景 | CSS |
|---|---|---|
| IDLE | 远景静止 | `--scene-progress: 0` |
| DRAGGING | 远处结构边缘略增强 | `--scene-progress: 0.05` |
| UPLOADING | 缓慢 scale 1.00 → 1.06 | `--scene-progress: var(upload-pct)` |
| PARSING | scale 1.08,雾尘加重 | `--scene-progress: 1` |
| FAILED | 背景压暗 | `--scene-progress: 0` + `data-scene-failed` |

### 3.3 投放区交互

- 420×260,细线框,半透明深底 + backdrop-filter(@supports 退化见 § 6.4)
- 点击或拖拽同一区域触发
- 前端预检:非 .zip → `file_type_not_allowed`;> 50MB → `project_too_large`,不发请求

### 3.4 上传中 / 解析中面板(★ R2 P1-1 修订:取消语义)

宽度 420-480px:

```text
┌──────────────────────────────┐
│  power_sim_project.zip       │
│  23.6 MB                     │
│                              │
│  上传中            42%       │
│  ━━━━━━━━━━━━━━━━──────────  │
│                              │
│  取消上传                    │
└──────────────────────────────┘
```

**取消上传语义**(★ R2 P1-1):

```typescript
// UploadPage.tsx
async function handleUpload(file: File) {
  const task = apiUploadTask("/upload", file, setProgress);
  abortRef.current = task.abort;
  try {
    const res = await task.promise;
    dispatch({ type: "UPLOAD_DONE", projectId: res.project_id });
  } catch (err) {
    // ★ R2 P1-1:识别主动取消,不进 FAILED
    if (err instanceof DOMException && err.name === "AbortError") {
      dispatch({ type: "RESET_TO_IDLE" });
      return;
    }
    dispatch({ type: "FAIL", error: err });
  }
}

function onCancelClick() {
  abortRef.current?.();
}
```

### 3.5 解析轮询

```typescript
const POLL_INTERVAL_MS = 2000;   // 固定 2s × 60 = 120s
const POLL_MAX_ATTEMPTS = 60;
```

逻辑:`setTimeout` 链(非 setInterval),`ready` → navigate,`failed` → FAILED + 显示 `error_code` 对应文案(其中 `parse_error` 是 ProjectStatusErrorCode 真实 code,见 § 7),60 次仍 parsing → 虚拟 `parse_timeout`。组件卸载严格 clear timeout。

---

## 4. 工程导览页(`/view/:projectId`)

### 4.1 6 Panel 信息架构

| Panel | 字段 | 布局 | 空状态 / 边界 |
|:-:|---|---|---|
| 1 · 工程入口 | `project_type` / `project_title` / `one_sentence_summary` | 居中 + 左对齐 | 不可空 |
| 2 · 入口与模型 | `main_entry_files` / `main_simulink_models` | 双列 | `main_simulink_models=[]` 合法 → 右列"本工程无 Simulink 模型",左列扩宽 |
| 3 · 执行流程 | `main_execution_flow` | 横向时间线 | 不可空(min=3,max=10) |
| 4 · 关键文件与模块 | `key_files` / `key_blocks` | 双列 | `key_files` 后端 min=1(★ Stage 0 修正,原写 min=3):仅 1 条时仍渲染,卡片自然成单条不空洞;`key_blocks=[]` 合法 → 右列中性文案,左列扩宽 |
| 5 · 学习路径 | `knowledge_points` / `beginner_reading_order` / `likely_confusing_points` | 三段叠放 | 三字段后端均有 min_length,**正常不应空**;运行时若空 → defensive fallback 隐藏 section + `console.warn` |
| 6 · 证据与出口 | `evidence` + "开始提问" CTA | 折叠 evidence + 底部 CTA | `evidence` 后端 min=1(★ Stage 0 修正,原写 min=3):仅 1 条时正常渲染,无需折叠;若运行时为 `[]` → defensive fallback 显"暂无证据引用"但保留 CTA |

每个 Panel 右下角浮"01 / 06"。

### 4.2 长文本边界

| 字段 | CSS |
|---|---|
| `one_sentence_summary` | `max-width: 680px; line-height: 1.8` |
| `main_execution_flow` 单条 | `max-width: 280px; overflow-wrap: anywhere` |
| `evidence` 列表 | `max-height: 42vh; overflow-y: auto; data-native-scroll` |
| `key_files` / `key_blocks` 列 | `max-height: calc(100vh - 340px); overflow-y: auto; data-native-scroll` |
| Panel 3 内容卡 | `max-height: calc(100vh - 260px); overflow-y: auto; data-native-scroll` |

### 4.3 Panel 6 CTA 锁定

```css
.panel-evidence-cta {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: 100vh;
}
```

### 4.4 Overview 数据获取

新增 `web/src/routes/overview/useProjectOverview.ts`:

```typescript
export function useProjectOverview(projectId: string) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const fetch = useCallback(async () => { /* apiGet + setState */ }, [projectId]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiGet<ProjectOverview>(`/projects/${projectId}/overview`);
        if (!cancelled) setState({ data, loading: false, error: null });
      } catch (e) {
        if (!cancelled) setState({ data: null, loading: false, error: e as ApiException });
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);
  return { ...state, retry: fetch };
}
```

`OverviewPage.tsx`:

```tsx
const { data, loading, error, retry } = useProjectOverview(projectId);
```

### 4.5 错误状态与加载态

| 场景 | 显示 |
|---|---|
| Loading | 居中文字"正在生成工程导览 · 请稍候",**不显示 skeleton** |
| 404 `project_not_found` | "工程不存在 / 可能已过期或被删除" + "返回上传页" |
| 502 `overview_generation` | "导览生成失败" + "重试"(retry) + "重新上传" |
| 503 / 504 | "服务暂时不可用" + "重试" + "返回上传页" |

---

## 5. 横向滚动技术方案

### 5.1 主结构

```tsx
<section className="overview-scroll" ref={scrollRef}>
  <PanelIntro index={0} /> ... <PanelEvidenceCta index={5} />
</section>
```

```css
.overview-scroll {
  display: flex;
  width: 100vw; height: 100vh;
  overflow-x: auto; overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  overscroll-behavior: contain;
}
.overview-panel { flex: 0 0 100vw; height: 100vh; scroll-snap-align: start; }
```

### 5.2 鼠标滚轮转横向

```typescript
function onWheel(e: WheelEvent) {
  if (!(e.target instanceof Element)) return;
  if (Math.abs(e.deltaX) >= Math.abs(e.deltaY)) return;   // 触摸板横滑放行

  const nativeScroll = e.target.closest("[data-native-scroll]");
  if (nativeScroll) {
    const el = nativeScroll as HTMLElement;
    const atTop = el.scrollTop === 0;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
    if (e.deltaY < 0 && !atTop) return;
    if (e.deltaY > 0 && !atBottom) return;
  }

  e.preventDefault();
  scrollRef.current!.scrollLeft += e.deltaY;
}
// addEventListener('wheel', onWheel, { passive: false })
```

### 5.3 键盘无障碍

```typescript
function onKeyDown(e: KeyboardEvent) {
  const W = window.innerWidth;
  const cur = Math.round(scrollRef.current!.scrollLeft / W);
  switch (e.key) {
    case "ArrowRight": case "PageDown": e.preventDefault(); scrollToPanel(cur + 1); break;
    case "ArrowLeft": case "PageUp": e.preventDefault(); scrollToPanel(cur - 1); break;
    case "Home": e.preventDefault(); scrollToPanel(0); break;
    case "End": e.preventDefault(); scrollToPanel(5); break;
    case "ArrowDown": case "ArrowUp":
      if (!isFocusInScrollable(e.target)) {
        e.preventDefault();
        scrollToPanel(cur + (e.key === "ArrowDown" ? 1 : -1));
      }
      break;
  }
}
```

**Panel 焦点**:每个 Panel `tabIndex={0}` + `aria-label="导览第 X 屏 / 共 6 屏"` + `onFocus → scrollToPanel(index)`;PanelIndicator 按钮放 DOM 尾部。

**ARIA**:`.overview-scroll` 加 `role="region" aria-label="工程导览"`,指示器 `role="navigation"`。

### 5.4 `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
  .overview-scroll { scroll-behavior: auto; }
  .dust-canvas { display: none; }
  .panel-content { transition: none !important; }
  /* 不禁用 .scene-panorama transform — 保留 instant parallax */
}
```

**DustCanvas 行为**(★ R3 P2 措辞统一):reduced-motion 时 **DustCanvas 不渲染**(可选实现:CSS `display: none` 或 React 条件不挂载),**不得执行粒子动画**。视差仍跟随 `scrollLeft` 即时更新(不做 rAF 平滑)。

### 5.5 panel 进度指示器

固定右下角"01 02 03 [04] 05 06",由 IntersectionObserver(threshold 0.6)驱动当前 Panel,点击 → `scrollToPanel(n)`(`scrollTo({ behavior: "smooth" })`)。

### 5.6 首次访问引导

`localStorage` 存 `mxa:scroll-hint-shown`,未存则显示 2.5s toast:"用 ← → 方向键或滚轮浏览",显示后立即 setItem(无 TTL)。

---

## 6. 背景场景层

### 6.1 上传页

```tsx
<div className="upload-scene" data-scene={state} style={{ '--scene-progress': progress }}>
  <img className="scene-far-bg" src="/assets/upload-bg.webp" alt="" />
  <div className="scene-fog" />
  <DustCanvas opacity={fogOpacity(state)} />
  <div className="scene-vignette" />
</div>
```

`upload-bg.webp`:由 PM 入选的导览页 panorama 左端 1920×1080 裁切。

### 6.2 导览页

```tsx
<div className="panorama-scene">
  <img className="scene-panorama" src="/assets/panorama.webp" alt=""
       style={{ transform: `translate3d(${panoramaX}px, 0, 0)` }} />
  <div className="scene-fog" />
  <DustCanvas />
  <div className="scene-vignette" />
</div>
```

**视差**:

```typescript
const W = window.innerWidth;
const totalScrollable = 5 * W;        // 6 Panel 间 5 间隔
const panoramaWidth = 3840;
const maxBgOffset = panoramaWidth - W;

function onScroll() {
  const cur = scrollRef.current!.scrollLeft;
  const progress = Math.min(1, cur / totalScrollable);
  setPanoramaX(-maxBgOffset * progress);
}
// rAF 节流,见 § 6.2 完整代码(v0.2.1 不变)
```

视差以 panel center 映射为标准:Panel 1 中心 → panorama x=960,Panel 6 中心 → x=2880。

### 6.3 DustCanvas

50-80 灰色粒子,缓慢漂浮,不发光、不彩色;**`prefers-reduced-motion` 时不渲染**(实现可选:CSS `display: none` 或 React 条件不挂载),**不得执行粒子动画**(★ R3 P2 措辞统一,详 § 5.4)。

### 6.4 backdrop-filter 退化(沿用 v0.2.1)

```css
.info-card {
  background: rgba(8, 13, 13, 0.34);
  border: 1px solid rgba(220, 230, 220, 0.14);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-radius: 2px;
}
@supports not ((backdrop-filter: blur(10px)) or (-webkit-backdrop-filter: blur(10px))) {
  .info-card {
    background:
      linear-gradient(180deg, rgba(18, 24, 23, 0.78), rgba(8, 13, 13, 0.72)),
      var(--noise-texture);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.06),
      0 24px 80px rgba(0, 0, 0, 0.22);
  }
}
```

### 6.5 资产加载

React-level preload(`OverviewPage` 内 useEffect 创建 `<link rel="preload">`),`img` 设 `onerror` 隐藏,CSS 兜底背景色 `--color-concrete`。

---

## 7. 错误处理 · GLOBAL_ERROR_MESSAGES(★ R1 P1-1 + R2 P0-1 / P0-2 + Stage 0 修订)

> v0.1 自称"23 条完整"漏 8 条;v0.2.1 自称"23 条完整"又漏 3 条;v0.2.2 自称"26 backend"又被 Stage 0 抓出漏 `embedding_model_load`;**反例 28 元层级第四次触发**(详 § 15)。
> v0.2.2 改为覆盖**后端全部 machine code + 前端虚拟 code**(当前已知 27 backend + 2 virtual);**最终条数以 Codex Stage 0 § 10 #3a + #3b 输出去重为准**,任何后端有本表未列的 code,Codex 停手报 PM。

### 7.1 GLOBAL_ERROR_MESSAGES(`web/src/lib/errorMessages.ts`)

| # | error code | 中文 UI 文案 | 来源 |
|:-:|---|---|---|
| 1 | `zip_bomb` | 压缩文件异常,请检查后重新上传 | task-206 |
| 2 | `zip_slip` | 压缩包内含非法路径,请重新打包后上传 | task-206 |
| 3 | `file_type_not_allowed` | 工程包内包含暂不支持的文件类型 | task-206 |
| 4 | `project_not_found` | 找不到该工程,可能已过期或已被删除,请重新上传 | task-206 |
| 5 | `project_too_large` | 工程过大,请确认压缩包不超过 50MB,并减少无关文件后重试 | task-206 |
| 6 | `upload_error` | 上传文件有问题,请检查压缩包后重新上传 | task-206 |
| 7 | `project_error` | 工程处理失败,请重新上传后再试 | task-206 |
| 8 | `internal_error` | 出了点问题,我们已经记录,稍后再试 | task-206 |
| 9 | `llm_auth` | 服务暂时不可用,请稍后重试 | task-206 |
| 10 | `llm_quota` | 服务繁忙,请稍后 | task-206 |
| 11 | `llm_rate_limit` | 请求太频繁,稍等一下 | task-206 |
| 12 | `llm_timeout` | 网络较慢,正在重试... | task-206 |
| 13 | `llm_server` | AI 服务暂不稳定,请刷新重试 | task-206 |
| 14 | `slx_parse` | Simulink 模型解析失败,可能版本过老或损坏 | task-206 |
| 15 | `m_parse` | .m 文件解析失败,请检查文件编码 | task-206 |
| 16 | `parse_error` | 工程解析失败,请检查 Simulink 或 .m 文件是否完整后重试 ★ R2 P0-1 补 | **task-202 ProjectStatusErrorCode**(status polling 专用) |
| 17 | `overview_generation` | 导览生成失败,请刷新重试 | task-206 |
| 18 | `chat_session_not_found` | 对话不存在 | task-206 |
| 19 | `store_error` | 系统暂时不可用,请稍后重试 | task-206 |
| 20 | `chat_generation` | 回答生成失败,请刷新重试 | task-206 |
| 21 | `quota_exhausted` | 已达到合理使用上限,可联系加量 | task-206 |
| 22 | `evidence_missing` | 出了点问题,我们已经记录,稍后再试 | task-206 |
| 23 | `not_found` | 请求的资源不存在 | task-206 R1 兜底 |
| 24 | `validation_error` | 请求参数有问题,请检查后重试 | task-206 R1 兜底 |
| 25 | `method_not_allowed` | 请求方式不支持 ★ R2 P0-2 补 | task-206 R1 兜底 |
| 26 | `http_error` | 请求失败,请稍后重试 ★ R2 P0-2 补 | task-206 R1 兜底 |
| 27 | `embedding_model_load` | AI 智能解析服务暂时不可用,请稍后重试 ★ Stage 0 补 | **task-301 EmbeddingProvider**(向量服务启动 / OOM 失败) |

**前端虚拟 code**(不来自后端):

| code | 触发 | 文案 |
|---|---|---|
| `parse_timeout` | 轮询 60 次仍 parsing | 解析时间超过 2 分钟,工程可能过大或服务繁忙,请稍后重试 |
| `network_error` | fetch 抛 TypeError | 网络连接失败,请检查网络后重试 |

> **注**:`parse_error` ≠ `parse_timeout`。前者是后端 status polling 真实 code(后台解析过程中失败),后者是前端等待超时虚拟 code。两者文案 / 触发条件均不同。

### 7.2 通用 resolver

```typescript
export const GLOBAL_ERROR_MESSAGES: Record<string, string> = { /* 27 backend + 2 virtual */ };

export function resolveErrorMessage(code: string | undefined): string {
  if (!code) return "出了点问题,请稍后再试";
  return GLOBAL_ERROR_MESSAGES[code] ?? `出了点问题(${code}),请稍后再试`;
}
```

### 7.3 TASK-402 实际使用子集

- **上传页**:1-15(直接错误)+ **16 `parse_error`**(status polling failed)+ 23-26(HTTP 兜底)+ 前端虚拟 2 条
- **导览页**:4 / 8 / 17 / 19 / 23-26 / LLM 类 9-13
- **chat 相关**:18 / 20 / 21 / 27 `embedding_model_load`(TASK-403 用,本任仍写入 GLOBAL 表统一管理)

---

## 8. localStorage 方案

### 8.1 keys

| key | value | TTL | 用途 |
|---|---|---|---|
| `mxa:overview-seen:{projectId}` | timestamp ms | 24h | 区分首访 / 回访 |
| `mxa:scroll-hint-shown` | "1" | 永久 | 滚动引导仅一次 |

### 8.2 实现

(沿用 v0.2.1 § 8.2 完整代码 — `markOverviewSeen` / `hasSeenOverview` / `cleanupExpiredOverviewSeen` 三函数。`main.tsx` 启动调一次清理。)

### 8.3 OverviewTopAction(不耦合 Layout)

```tsx
// web/src/routes/overview/OverviewTopAction.tsx
export function OverviewTopAction({ projectId, onJumpToEnd }: {...}) {
  const seen = hasSeenOverview(projectId);
  return seen
    ? <Link to={`/view/${projectId}/chat`}>继续提问 ↗</Link>
    : <button onClick={onJumpToEnd}>跳到末屏</button>;
}
```

`OverviewPage` 装配,Layout 不变。

### 8.4 标记 seen 时机

`usePanelObserver` 检测到 Panel 6 `intersectionRatio > 0.6` 调 `markOverviewSeen(pid)`,或点 Panel 6 CTA。

---

## 9. 组件结构

```text
web/src/
  routes/
    UploadPage.tsx / OverviewPage.tsx / ChatPage.tsx / NotFoundPage.tsx
    upload/
      UploadDropzone.tsx
      UploadStatusCard.tsx
      uploadErrorMessages.ts
      useParseStatusPolling.ts
    overview/
      panels/  PanelIntro / PanelEntries / PanelFlow / PanelKeyItems / PanelLearning / PanelEvidenceCta
      OverviewTopAction.tsx
      useProjectOverview.ts
      useHorizontalScroll.ts
      usePanelObserver.ts
      useParallaxBg.ts
  components/
    scene/  UploadScene / PanoramaScene / DustCanvas
    ui/  GlassCard / PanelIndicator / FileRow / EmptyStateText
  lib/
    api.ts            ← 追加 apiUploadTask
    types.ts          ← 扩 § 2
    errorMessages.ts  ← GLOBAL 26+2
    localStore.ts
  main.tsx            ← 启动调 cleanupExpiredOverviewSeen()
```

**`api.ts` 扩展契约**(★ R2 P1-1 完善 abort 语义):

```typescript
export interface UploadTask<T> {
  promise: Promise<T>;
  abort: () => void;
}

export function apiUploadTask(
  path: string,
  file: File,
  onProgress?: (percent: number) => void,
): UploadTask<UploadResponse>;

// abort 实现(★ R2 P1-1)
//   1. apiUploadTask.abort() 内部调 xhr.abort()
//   2. xhr.onabort 触发:reject(new DOMException("Upload aborted", "AbortError"))
//   3. UploadPage catch 识别 err.name === "AbortError" → 回 IDLE,不进 FAILED
//   4. UploadPage 不展示任何错误文案,等待用户重新选文件

// 保留兼容(TASK-401 已有调用):
export function apiUpload(path: string, file: File, onProgress?: (p: number) => void) {
  return apiUploadTask(path, file, onProgress).promise;
}
```

预估总新增:**约 20 文件,1700 行代码 + 300 行 CSS**,每文件 ≤ 300 行。

---

## 10. Stage 0 实地核查清单(★ R2 P0-1 拆 #3a/#3b)

### 10.1 后端契约一致性

```bash
# #1 endpoint + 状态码
grep -rnE "@router\.(post|get)|status_code=" api/routes/upload.py api/routes/overview.py
# 期望:POST /upload (202) + GET /projects/{pid}/status (200) + GET /projects/{pid}/overview (200)

# #2 Pydantic schema
sed -n '1,200p' features/overview/overview_schemas.py

# #3a 后端 HTTP machine_code(error_handler.py + 兜底)
grep -nE "machine_code\s*=" api/middleware/error_handler.py
grep -rnE "\"error\"\s*:|machine_code" api/middleware/

# #3b 后端 status polling 专用 ProjectStatusErrorCode(★ R2 P0-1)
grep -rn "ProjectStatusErrorCode" core/ features/ adapters/ api/
sed -n '/class ProjectStatusErrorCode/,/^$/p' $(grep -rl "class ProjectStatusErrorCode" core/ features/ adapters/ api/ 2>/dev/null)

# 期望:#3a 输出约 23 条 machine_code(含 not_found / method_not_allowed / http_error / validation_error 兜底)
#       #3b 输出约 8 条 ProjectStatusErrorCode(含 parse_error)
#       两者合并去重后**必须 ⊆ § 7.1 GLOBAL_ERROR_MESSAGES 26 条**
#       后端有本任表未列的 code,Codex 停手报 PM(反例 28 防护)

# #4 ProjectStatusResponse / UploadResponse 实际形态
grep -rnE "class (ProjectStatusResponse|UploadResponse)" api/ core/ features/
```

### 10.2 前端骨架核查

```bash
# #5 TASK-401 已落文件
cat web/src/lib/api.ts
cat web/src/lib/types.ts
cat web/src/routes/UploadPage.tsx
cat web/src/routes/OverviewPage.tsx
cat web/src/components/Layout.tsx
cat web/vite.config.ts

# #6 依赖白名单
cat web/package.json | grep -E "framer-motion|zustand|jotai|redux"
# 期望:无输出

# #7 apiUpload 当前签名
grep -nA 10 "export.*apiUpload" web/src/lib/api.ts
```

### 10.3 资产路径

```bash
# #8 panorama / upload-bg 是否到位
ls web/public/assets/ 2>/dev/null
# 期望:panorama.webp + upload-bg.webp 已到位(PM 已挑选 + 上传页裁切版)
# 若没到位,代码用相对路径引用兜底背景色,不阻塞
```

---

## 11. 验收标准

### 11.1 静态

- [ ] `pnpm lint` + `pnpm typecheck` 全绿
- [ ] `pnpm build` 成功,bundle ≤ 1MB(不含 panorama)
- [ ] 每文件 ≤ 300 行
- [ ] 无新增 npm 依赖
- [ ] `grep -rnE "framer-motion|zustand|jotai|redux" web/src/` 空

### 11.2 功能(★ R2 P0-1 / P1-1 验收补)

- [ ] 上传 .zip → 进度 → 解析中 → 自动跳导览页
- [ ] **取消上传按钮真实中断 XHR;UI 回 IDLE,不进 FAILED,不显示 network_error / upload_error**(★ R2 P1-1)
- [ ] 上传失败 15 个 ERROR_MAP code 至少手工模拟 5 个,UI 显示对应中文
- [ ] **mock `/status` 返回 failed + `parse_error`,上传页显示"工程解析失败..."中文文案**(★ R2 P0-1)
- [ ] 上传 > 50MB 文件,前端预检拦截,不发请求
- [ ] 导览页 6 Panel 滚轮 + 方向键 + Home/End 均可切换
- [ ] Tab 焦点按 Panel 1 → 6 顺序,Panel 获焦时自动 scrollToPanel
- [ ] PanelIndicator 按钮在 Tab 顺序最后
- [ ] Panel 2 / Panel 4 喂空数组 mock 数据(`main_simulink_models=[]` / `key_blocks=[]`),UI 渲染中性文案
- [ ] **Panel 4 喂 `key_files=[<1 条>]` 最小边界**(★ Stage 0 修正:后端 min=1),UI 不空洞,卡片自然单条渲染
- [ ] Panel 5 喂空数组(defensive 触发):section 隐藏 + console.warn
- [ ] **Panel 6 喂 `evidence=[<1 条>]` 最小边界**(★ Stage 0 修正:后端 min=1),UI 正常渲染单条 + CTA 可见
- [ ] Panel 6 evidence 喂 20 条,展开后内部纵向滚动,CTA 仍底部可见
- [ ] **mock `embedding_model_load` 错误**(★ Stage 0 补),resolveErrorMessage 返回 "AI 智能解析服务暂时不可用,请稍后重试"
- [ ] 首访 toast 显示一次,刷新后不显示
- [ ] `prefers-reduced-motion: reduce`:dust canvas 消失、视差仍跟随滚动即时更新
- [ ] Layout 不引用 OverviewPage 内部函数;OverviewTopAction 仅在导览页挂载

### 11.3 浏览器兼容

- [ ] Chrome / Edge / Safari / Firefox 最新版全功能
- [ ] backdrop-filter 退化 fallback 在不支持的浏览器正确显示

### 11.4 真启动

- [ ] `pnpm dev` + `uvicorn` → 浏览器上传 fixture → 跳导览页 → 6 Panel 渲染
- [ ] `pnpm build && pnpm preview` 生产构建可访问

---

## 12. 决策日志(D1-D20)

| D | 决策 | 理由 | 替代 / 为何不选 |
|:-:|---|---|---|
| D1 | useReducer + useContext 管状态 | 范围有限 | Zustand 仍是新依赖 |
| D2 | 原生 scroll-snap + wheel 转换 | 401 白名单 | framer-motion 14KB |
| D3 | panorama 一张 + 视差(实际 1:5) | 色调一致 | 6 张图风格漂移 |
| D4 | 上传页 bg 由 panorama 左端裁切 | 视觉无断裂 | 单独出图浪费 |
| D5 | error_code 完整全局表 | TASK-403 复用 | 子集会暴露 chat code |
| D6 | localStorage TTL = 24h | 与后端 24h 一致 | 永久存导致 404 |
| D7 | scroll-hint toast 永久存 | UX 引导非用户数据 | TTL 打扰回访 |
| D8 | direct `/chat` 不做 route guard | UI 不当权限层 | 强拦阻路径 |
| D9 | Panel 6 CTA 用 grid 锁底部 | evidence 展开不挤出 | sticky 不稳 |
| D10 | dust canvas 50-80 粒子 | 性能 + a11y | 多卡顿少空虚 |
| D11 | wheel `{ passive: false }` | 需 preventDefault | passive 无法转向 |
| D12 | `data-native-scroll` 边界放行 | evidence 内部滚优先 | 全劫持破坏 evidence |
| D13 | > 50MB 前端预检 | UX + 省带宽 | 全依赖后端体验差 |
| D14 | 轮询固定 2s × 60 严格 2 分钟 | 算术一致 | backoff 与目标矛盾 |
| D15 | apiUploadTask 支持 abort | 取消必须真实中断 | 降级 UI 而不中断 |
| D16 | OverviewTopAction 不进 Layout | Layout 不依赖页面内部 | 耦合传染 chat 页 |
| D17 | useProjectOverview hook | OverviewPage ≤ 300 行 | 直 fetch 文件爆 |
| D18 | 空数组只 defensive fallback | 后端 min_length 已硬约束 | 假设可空留漏洞 |
| D19 | 视差以 panel center 映射为准 | 1:5 / 1:6 措辞易误 | 口头比例 Codex 纠结 |
| D20 | **abort 后 promise reject `DOMException("AbortError")`,UploadPage 识别后保持 IDLE 不进 FAILED**(★ R2 P1-1) | 取消是主动行为非错误 | 用 Error 子类被 catch 当 FAILED;不 reject 让 promise leak |

---

## 13. 风险与对冲

| R | 风险 | 对冲 |
|:-:|---|---|
| R1 | 横向滚动劫持引反感 | toast + 指示器 + 键盘 + 横滑保留 |
| R2 | panorama 加载慢首屏白屏 | React preload + 兜底背景色 |
| R3 | backdrop-filter 套壳浏览器失效 | `@supports not` 4 层退化 |
| R4 | wheel preventDefault 警告 | 显式 `{ passive: false }` |
| R5 | 内部滚动与主滚动冲突 | `data-native-scroll` 边界检测 |
| R6 | StrictMode 双 mount polling 重复 | useEffect cleanup |
| R7 | localStorage 写入失败 | try/catch 全部调用 |
| R8 | 后端 schema 与本表不一致 | Stage 0 #1-#4 抓 |
| R9 | 上传中刷新失去 project_id | MCS 不解决 |
| R10 | Panel 6 evidence 喂 100 条 | max-height + Phase 2 虚拟列表 |
| R11 | dust canvas 低端机卡顿 | rAF + 粒子数可调 |
| R12 | `error` vs `error_code` 后端两套 | api.ts 内部映射 → ApiException.code |
| R13 | **ProjectStatusErrorCode 与 HTTP machine_code 两套来源,Codex 漏 grep 任一会致 GLOBAL_ERROR_MESSAGES 不全**(★ R2 P0-1) | Stage 0 #3a / #3b 强制双核查 + 报 PM |

---

## 14. 完工三件套

- **PR 标题**:`TASK-402: 上传页 + 工程导览页(6 Panel 横向滚动)`
- **PR 描述**:对照 § 11 验收逐条勾选 + Stage 0 #1-#8 报告 + 截图(每 Panel + 失败态 + 空状态 + 取消上传)
- **commit 拆分**(11 commits):
  1. `chore(web): expand types.ts to full ProjectOverview 12 fields + 5 sub schemas`
  2. `feat(web/lib): add GLOBAL_ERROR_MESSAGES (26 backend + 2 virtual) + resolveErrorMessage`
  3. `feat(web/lib): add localStore with 24h TTL for overview-seen`
  4. `feat(web/lib): add apiUploadTask supporting abort with AbortError semantics`
  5. `feat(web): implement UploadPage with state machine + polling + abort handling`
  6. `feat(web): add UploadScene background layer`
  7. `feat(web): implement OverviewPage 6 panels skeleton + useProjectOverview`
  8. `feat(web): add horizontal scroll + wheel + keyboard hooks`
  9. `feat(web): add PanoramaScene with parallax + DustCanvas`
  10. `feat(web): add @supports backdrop-filter fallback + GlassCard + OverviewTopAction`
  11. `chore: update TASK_INDEX TASK-402 to reviewing`

---

## 15. 关联文档 / 决策 / 反例(R2 累积更新)

### 关联宪法 / Task

- 01 § 9 数据隐私 / § 11 用户体验底线 / 02 § 1 系统分层 / 04 § 4 + § 6
- **上游**:TASK-401 / 202 / 203 / 205 / 206 / 207
- **下游**:TASK-403(共享 GLOBAL_ERROR_MESSAGES + localStore + Layout)/ TASK-405

### 关联决策

- 决策 06 / 07 / 08(沿用)
- **决策 09**(架构师必须实地核查):本任 R1 + R2 反例 28 反复触发,见反例段
- 决策 11(async + logger;前端不涉及)
- **决策 12 v0.2**(双 AI 互审):R0 → GPT v0.1 → Claude R0 → GPT v0.2 → Claude R1 抓 GPT 5 处 → GPT R1 抓 Claude 16 处 → Claude v0.2.1 → GPT R2 抓 Claude 3 处 → Claude v0.2.2 → GPT R3 PASS → **Codex Stage 0 抓 Claude 3 处**(★ 新增)→ Claude 修文档接受后端契约 → 重派 Codex
- 决策 16(overview_schemas 留 features/overview/)

### 关联反例(★ Stage 0 累积更新)

**反例 28**(架构师无 repo 凭推理):
- **TASK-308 收官 K_28 = 7**
- v0.1 时 Claude 自抓 1(error_code 列表只 7 条)→ K_28 = 8
- v0.1 → R1 GPT 抓 Claude **6 处**(状态码 / 字段名 / schema 路径 / Pydantic 约束 / apiUpload 签名 / "完整 23 条" 漏 8)→ K_28 = 14
- v0.2.1 → R2 GPT 抓 Claude **2 处**(parse_error 误归虚拟 + method_not_allowed / http_error 漏)→ K_28 = 16
- v0.2.2 → **Codex Stage 0 抓 Claude 3 处**(★ 新增):
  1. task-401 路径笔误(`v0_3.md` vs 实际 `v0.3.md`)
  2. schema 字数边界三处不符(`main_execution_flow 3-7` 实际 `3-10` / `key_files 3-8` 实际 `1-8` / `evidence >=3` 实际 `>=1`)
  3. `embedding_model_load` 漏列(task-301 EmbeddingProvider 真实 machine code)
- → **K_28 = 19,项目历史新高**
- 反例 24(数学错误)累积:R1 + 2(轮询 150s ≠ 120s / 视差 1:6 实际 1:5)

**反例 28 元层级第四次触发**(★ 新增):
- R0 自抓 → R1 仍漏 8 条 → v0.2.1 自称"完整 23 条" 又漏 3 条 → v0.2.2 自称"完整 26 条" 又漏 1 条 + schema 边界 3 处 + 路径 1 处
- **四轮反例 28,每轮都漏 code 或字段约束;每轮都"以为修完了"**
- 这次不是 GPT 抓,是 **Codex 严格 Stage 0 抓**;说明工艺级硬约束的威力(否则 Codex 凭印象自己补猜就过去了)
- **意识 ≠ 行为约束**;§ 17 决策 09 v2 雏形必须升级为强制流程

**反例 30** K_30 = 5(不变);**反例 31** K_31 = 1(不变);**K 总 = 25**(K_28 = 19 + K_30 = 5 + K_31 = 1)。

### v0.3 升仪议题(必须交下任处理)

K_28 = 19 / K_30 = 5 / K 总 = 25,**全部远超阈值**。
- 反例 28 元层级**已成项目稳定模式**,不是孤立现象。
- 本任不启动决策 09 v2 / 决策 12 v0.3 起草(收尾要紧),但 § 17 已给出**升级版**雏形,下任接手必须立即起草入仓。

---

## 16. R0 → R3 流程归档(★ R3 PASS,本档闭环)

| 阶段 | 产物 | 结论 |
|---|---|---|
| R0 | Claude 给 GPT 设计反馈 + 出图 prompt | GPT 出 v0.2 方案 |
| R1 | Claude 抓 GPT v0.2 五处 + GPT 抓 Claude v0.1 十六处 | v0.2.1 修订 16 条 |
| R2 | GPT 抓 Claude v0.2.1 三处(2 P0 + 1 P1) | v0.2.2 修订 5 条 |
| R3 | GPT 极窄验 5 项 + 1 P2 措辞非阻断 | **PASS** · P2 已就地统一 · 进 Codex |
| **Stage 0** | **Codex 严格 grep 抓 Claude 3 处**(路径 + schema 边界 + embedding_model_load 漏列) | **conditional fail · 接受后端契约 · 修文档不修代码 · 重派 Codex** |

### R3 验收清单(GPT 已核完)

- [x] § 7.1 GLOBAL_ERROR_MESSAGES 含 `parse_error`(★ R2 P0-1)
- [x] § 7.1 GLOBAL_ERROR_MESSAGES 含 `method_not_allowed` + `http_error`(★ R2 P0-2)
- [x] § 7 段落改"以 Stage 0 grep 输出为最终准"
- [x] § 10 Stage 0 #3a HTTP machine_code + #3b ProjectStatusErrorCode 双核查
- [x] § 9 + § 3.4 apiUploadTask.abort() 明确 `DOMException("AbortError")` 语义

### R3 P2 非阻断(已统一)

- [x] § 5.4 + § 6.3 prefers-reduced-motion 下 DustCanvas 行为措辞统一

### Stage 0 修订清单(★ 本轮)

- [x] § 2 types.ts:`main_execution_flow 3-10` / `key_files 1-8` / `evidence >=1`(接受后端契约)
- [x] § 4.1 Panel 4 / Panel 6 描述:适应 min=1 单条最小情况
- [x] § 7.1 增第 27 条 `embedding_model_load`
- [x] § 7 段落:"26 backend + 2 virtual" → "27 backend + 2 virtual,以 Stage 0 输出为最终准"
- [x] § 7.3 实际使用子集:embedding_model_load 列入 chat 相关(TASK-403 用)
- [x] § 7.2 resolver 注释:`/* 26 + 2 */` → `/* 27 backend + 2 virtual */`
- [x] § 11.2 验收 +3 条(key_files 单条边界 / evidence 单条边界 / embedding_model_load 文案)
- [x] § 15 反例 28 累积:K_28 = 16 → **19**(项目历史新高)
- [x] § 17 给下任的话:升级强化(本任不修代码即可重派 Codex)

---

## 17. 给下任的话(★ 工艺反思,R2 强化)

### 反例 28 元层级问题

本任 R0 / R1 / R2 / Stage 0 **四次触发反例 28**,同一文档同一类错误四次:
- R0:自抓"error_code 凭印象"
- R1:仍只列 7 条,GPT 抓出实际 23 条;Claude 接受修订
- R2:Claude 自称"修订到 23 条完整",GPT 又抓出还漏 3 条
- **Stage 0:Claude 自称"修订到 26 条完整",Codex 严格 grep 又抓出漏 1 条 + schema 边界 3 处 + 路径 1 处**

**关键观察**:Stage 0 这一次抓到的不只是"漏列",还有 schema 字数边界(完全没核查后端实际 Pydantic Field 约束)+ 路径笔误(连任务卡文件名都没 ls 确认)。这说明反例 28 的范围已经从"error_code 列表"扩散到"任何接口契约相关字段"。

**根因**:架构师无 repo,凭"印象 + 部分 grep 输出 + 部分前序文档摘抄"写所有接口契约相关内容;意识到反例 28 三次后,**仍依赖"GPT/Codex 互审兜底"而不在源头硬约束**。这次 Codex 工艺生效抓出来,如果没有 Stage 0 严格停手机制,这些错会直接进生产。

### Stage 0 工艺验证(★ 本任最大正面收获)

虽然反例 28 第四次触发是负面,但 Stage 0 这次**机制本身工作得非常好**:
- Codex 严格按硬要求 grep + 去重,**没有自己补猜**
- 报告精确(逐 code 列出 + UNKNOWN 集合)
- 立即停手报 PM,**这是工艺的核心价值**

下任接手时:**Stage 0 严格执行**应被列为决策 09 v2 的**对等机制**:架构师写错没事,Codex 严格抓即可;但 Codex 自己补猜则是更严重的反例。

### 建议写进决策 09 v2 的硬约束(本任原型 → 升级版)

```text
架构师起草任何接口契约 / 字段表 / error_code 表 / Pydantic schema 描述 / 跨文档路径引用之前,
必须先跑以下命令,并把输出关键行**逐字粘贴**到任务卡前言"§ 0.5 架构师 Stage 0 自查"段:

  # [A] 后端 HTTP error machine_code(全局 ERROR_MAP)
  sed -n '1,400p' api/middleware/error_handler.py
  grep -nE "machine_code\s*=" api/middleware/error_handler.py | sort -u

  # [B] 后端业务专用 error code(如 status polling)
  grep -rnE "class \w+ErrorCode" core/ features/ adapters/
  sed -n '/class \w+ErrorCode/,/^$/p' <匹配文件>

  # [C] 后端响应 schema 完整 Pydantic Field 定义
  sed -n '1,300p' <feature 内 *_schemas.py>
  # 重点核查每个 Field 的 min_length / max_length / ge / le / Literal 取值

  # [D] 后端 endpoint + 状态码
  grep -rnE "@router\.(post|get|put|delete)|status_code=" api/routes/<相关路由>.py

  # [E] 跨文档引用路径必须 ls 确认存在
  ls docs/tasks/<本任引用的所有任务卡文件名>
  ls docs/decisions/<本任引用的所有决策文件名>

输出贴文档后,逐项核对自己写的字段名 / code 名 / 状态码 / 约束值 / 路径与代码 / 文件系统一致。
不一致 → 改文档,不改代码 / 不改文件名。

特别强调(Stage 0 教训):
- 不要凭"前序文档摘抄"假设字数边界(如 evidence ≥3 实际是 ≥1)
- 不要凭命名习惯写文件名(如 v0_3.md vs v0.3.md)
- 不要假设 task-206 ERROR_MAP 就是全部 error code(如 task-301 EmbeddingProvider 有自己的 code)

如此:
- 反例 28 凭印象问题在架构师阶段就被堵住
- Codex Stage 0 不再是"兜底",而是"复核"
- "反例 28 互审兜底"被工艺级硬约束替代,K_28 累积可见下降
```

### 给下任的具体动作

1. **第三十任接手时,起 docs 补丁 chore**:
   - 起决策 09 v2(本任 § 17 雏形→正式化)
   - 起决策 12 v0.3(K_28 / K_30 / K_31 全超阈值,工艺规则细化)
   - 同步 03_TASK_INDEX 反例库累积段

2. **第三十任起草任何接口/契约类任务卡前**:
   - 跑本任 § 17 给的命令清单
   - 输出粘贴到任务卡 § 0.5
   - 不跑 = R3 违反

3. **互抓反例 28 不再视作"协议正常工作",视作"工艺缺陷"**:
   - 每出现一次反例 28 互抓,任务卡末尾必须分析"为何架构师没在源头跑 § 17 命令"
   - 累积 3 次同任务内反例 28 → 强制升仪决策 09 v2

---

**版本**:v0.2.2(2026-06-10 第二十九任,吸收 R2 5 项 + R3 P2 + Stage 0 3 处修订)
**作者**:Claude(第二十九任,本项目架构师)
**状态**:🟡 接受后端契约修文档完成,可重派 Codex Stage 0
**前置**:v0.2.1 → R2 5 项 → v0.2.2 → R3 PASS → Stage 0 抓 3 处 → 修文档(本档)→ 重派 Codex
**关联**:`task-402-ui-discussion-claude-to-gpt.md`(R0) / `task-402-panorama-prompts-to-gpt.md`(出图) / `task-402-codex-handoff.md`(派活模板,需同步修路径笔误)
