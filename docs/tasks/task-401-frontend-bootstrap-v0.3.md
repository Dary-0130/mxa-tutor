# TASK-401: 前端框架选型 + 项目搭建

## 状态
🔲 未开始

## 审批级别

**GPT R1 → v0.2 → R2 → v0.3 → R3 通过。可交 Codex。**

R1(6 P0 + 5 P1):前端工具链凭印象写 + D6 口径冲突。v0.2 全部采纳。
R2(1 P0 + 3 P1):`/projects` proxy 与 BrowserRouter 页面路由冲突(D6 更隐蔽的同源路径问题)+ Tailwind v3 fallback 逃逸 + D1 版本措辞。v0.3 全部采纳。

D1(React + Vite)、D4(按页面分组)、D11(砼核)不翻。

**R3 极窄审范围**(v0.3 修完后 GPT 只看):
1. D6 页面路由是否改为 `/view/:projectId`,不再与 `/projects` API proxy 冲突
2. 风险表是否删除 Tailwind v3 降级自由裁量
3. D1 是否改为 React >=18

### 反例累积(R1 + R2)

| 类型 | 抓方 | 条数 | 明细 |
|---|---|---|---|
| 反例 28 | GPT → Claude | 6 | R1: P0-2 Node / P0-4 Tailwind / P0-5 ESLint / P0-6 types.ts / P1-1 RR v7; R2: P0-1 proxy vs 页面路由未验证 Vite 行为 |
| 反例 30 | GPT → Claude | 1 | R1: P0-1 D6 `/api/*` 口径 |
| 反例 28 | Claude → GPT | 0 | — |

---

## 上下文

Week 4 第一个 Task。后端 3 周已交付完整 API:上传解析(202)、工程导览(203/207)、向量 RAG 问答(205/304/307)、SQLite 存储(204)、错误中文化(206)。本 Task 建前端骨架,让 TASK-402(上传页+导览页)和 TASK-403(问答页)有地方写代码。

02 架构总览 § 3 目录结构预留了 `web/` 目录,标注"Next.js / Vue 3, Task 401 时定型"。本 Task 落锤。

### 产品形态约束(01 宪法 § 3)

- 用户:中国工科本科生,中文母语,手机/电脑都用
- 核心流程:上传 zip → 等解析 → 看导览 → 提问 → 看带 citations 的回答
- 付费模式:激活码(MCS 阶段手动发码)
- 部署:前端 Nginx 静态托管 / Vercel,后端阿里云/腾讯云轻量(02 § 10)

### 后端 API 端点清单(TASK-402/403/404 需对接)

| 端点 | 方法 | 用途 | 来源 Task |
|---|---|---|---|
| `/health` | GET | 健康检查 | 201 |
| `/upload` | POST | 上传 zip(202 Accepted) | 202 |
| `/projects/{pid}/status` | GET | 轮询解析状态 | 202 |
| `/projects/{pid}/overview` | GET | 获取导览 JSON | 203 |
| `/projects/{pid}/chat` | POST | 发送问题(首次,自动建 session) | 205 |
| `/projects/{pid}/sessions` | GET | 列出历史会话 | 205 |
| `/projects/{pid}/sessions/{sid}/messages` | POST | 追问(已有 session) | 205 |
| `/projects/{pid}/sessions/{sid}/messages` | GET | 获取会话历史消息 | 205 |

**MCS 阶段 API 路径不加 `/api` 前缀。** 若未来要统一加前缀,另起后端 API prefix migration Task,不在 TASK-401 改。

**⚠ 反例 28 兜底**:以上端点清单基于 task-202/203/205 文档核实。Codex Stage 0 仍须 `grep -rn '@router' api/routes/` 确认实际端点签名,若与本表不符停手报 PM。

---

## 输入(前置依赖)

- 必须已完成:Week 3 全部(TASK-301~305, 307, 308)
- 必须已读:01 宪法、02 架构总览、04 工程规范
- 必须存在:`api/` 目录含完整后端路由;`web/README.md` 占位文件(Stage 0 后删除,脚手架覆盖)

---

## 决策表

| # | 决策 | 选定 | 理由 | 备选(被否) |
|:-:|---|---|---|---|
| D1 | 框架 | **React >=18 + Vite** | 本产品是纯 SPA(上传→轮询→导览→问答),无 SEO 需求,无 SSR 需求。React 生态最大,Codex 生成质量高。Vite 构建快,HMR 快。**React 主版本以 create-vite@latest 产出为准;若产出 React 19 不得降回 18;若与 react-router-dom v7 最低要求冲突,停手报 PM。** | A. Next.js — SSR 无价值,部署多 Node server / B. Vue 3 — 可行但 React 生态更大 |
| D2 | CSS | **Tailwind CSS v4**(Vite plugin 模式) | 快速出原型,utility-first。**v4 使用 `@tailwindcss/vite` plugin + `@import "tailwindcss"`,不生成 `tailwind.config.ts` / `postcss.config.js`。** 如需主题扩展再按需添加 CSS 文件内 `@theme` 块。 | A. CSS Modules — 开发速度慢 |
| D3 | 状态管理 | **React 内置(useState + useContext)** | MCS 阶段 3 个页面,全局状态只有 project_id。不需要 Redux / Zustand。 | — |
| D4 | 目录结构 | **按页面分组** | 页面少(3-4 个),`routes/` + `components/` + `lib/` 最直观。 | — |
| D5 | 路由 | **react-router-dom v7** | SPA 标准选择。v7 官方描述为 v6 非破坏升级,BrowserRouter API 正常可用。**固定 v7,不给 Codex 降 v6 自由裁量;若安装出实际 API 不兼容,停手报 PM。** | — |
| D6 | 跨域 + 路径分离 | **页面 `/view/*`,API `/projects/*` `/upload` `/health`;开发 Vite proxy,生产 Nginx 同源** | 后端 API 用 `/projects/{pid}/...` 前缀。**前端页面路由不得使用 `/projects` 前缀**,否则 Vite proxy 和 Nginx 反代会劫持页面刷新(Vite `server.proxy` key 按前缀匹配,命中后不再走 SPA)。前端页面统一用 `/view/:projectId`,与 API 路径无交集。生产 Nginx:API 路径 proxy_pass 后端,其余 `try_files $uri $uri/ /index.html;` 走 SPA fallback。 | A. 页面也用 `/projects` — proxy 劫持页面刷新 / B. `/app/projects/...` — 多一层嵌套,URL 过长 |
| D7 | TypeScript | **严格模式**(`"strict": true`) | 后端 Pydantic strict typing,前端对齐。 | — |
| D8 | HTTP 客户端 | **原生 fetch + 薄封装(`web/src/lib/api.ts`)** | 无额外依赖。上传进度用 XMLHttpRequest。 | A. axios — 多依赖 |
| D9 | 包管理器 | **pnpm** | 快、省磁盘、lockfile 严格。 | — |
| D10 | 代码质量 | **ESLint 9(flat config `eslint.config.js`)+ Prettier** | ESLint 9 默认 flat config,不用 `.eslintrc.cjs`。以 Vite React TS 模板产出为准,最小修补。 | — |
| D11 | 视觉方向 | **砼核(Brutalism)** | PM 明确偏好。冷灰水泥色系 + 锐利直角 + 粗体工业字体 + 混凝土纹理 + 极简几何。与工科仿真产品气质契合。详见 § 视觉规范。 | — |
| D12 | 版本策略 | **跟随 create-vite@latest** | Codex 用 `pnpm create vite@latest`。Stage 0 Node 要求 `>= 20.19` 或 `>= 22.12`(Vite 当前最低要求)。package.json 版本以脚手架产出为准,必须提交 `pnpm-lock.yaml`。 | B. pin Vite 6 — 限制脚手架版本没必要,前端从零起步 |

---

## 视觉规范(D11 砼核 / Brutalism)

### 设计语言

产品面向工科学生,视觉应传达:**精确、结构化、冷峻但可靠**。不追求"友好可爱",追求"这工具看起来就很专业"。

### 色板(CSS custom properties,定义在 `index.css` 的 `@theme` 块或 `:root`)

```
--color-concrete:     #2C2C2C;    /* 主背景,深灰近黑 */
--color-ite:       #E8E4DE;    /* 文字/前景,暖白水泥色 */
--color-rebar:        #8B8680;    /* 次要文字,钢筋灰 */
--color-formwork:     #3A3A3A;    /* 卡片/面板背景,模板灰 */
--color-signal:       #E85D3A;    /* 强调色,信号橙(工程警示色) */
--color-signal-dim:   #C44D2E;    /* 强调色 hover 态 */
```

### 字体

```
--font-display: "IBM Plex Sans", "Noto Sans SC", system-ui, sans-serif;
--font-mono:    "IBM Plex Mono", "Noto Sans Mono", monospace;
```

IBM Plex Sans:工业感强、几何清晰、免费开源。中文 fallback 到 Noto Sans SC。通过 Google Fonts CDN 在 `index.html` `<link>` 引入(不安装 npm 包)。

### 纹理

本 Task 在 `index.css` 中定义一个 CSS 噪点纹理 utility class `.texture-concrete`,用 SVG inline data URI 实现细微噪点叠加,模拟水泥表面质感。**不引入图片文件**,纯 CSS 实现:

```css
.texture-concrete {
  background-image: url("data:image/svg+xml,..."); /* SVG feTurbulence 噪点 */
  background-repeat: repeat;
}
```

Codex 实现时参考 SVG `<feTurbulence>` + `<feColorMatrix>` 生成灰色噪点纹理 pattern。效果:半透明噪点叠在背景色上,模拟混凝土表面。

### 布局原则

- `border-radius: 0` 全局(锐利直角)
- 粗分割线(`border: 2px solid var(--color-rebar)`)代替阴影
- 大字号标题(`text-4xl` / `text-5xl`)+ 极细正文(`text-sm`)形成反差
- 留白大方,不挤
- 按钮:实色块 + 大写字母 + 无圆角

### 本 Task 落地范围(骨架级)

Layout.tsx 和 4 个占位页面使用上述色板和字体。不做复杂动画/粒子(Phase 2)。具体落地:
- `index.html`:引入 Google Fonts(IBM Plex Sans / IBM Plex Sans SC)
- `index.css`:定义 CSS custom properties + `.texture-concrete` class + 全局 `border-radius: 0` + body 背景色
- `Layout.tsx`:顶部导航栏用 `--color-formwork` 背景 + `--color-signal` 品牌色 + 粗体产品名
- 占位页面:大字标题 + 简短中文说明,砼核风格

**TASK-402/403 进一步细化**:卡片组件、citation 高亮、聊天气泡等具体 UI 元素。**粒子效果 / WebGL 背景留 Phase 2**。

---

## 输出(交付物)

### 新增文件清单

```
web/
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json                       # strict: true
├── tsconfig.node.json
├── vite.config.ts                      # 含 proxy + tailwindcss plugin
├── eslint.config.js                    # ESLint 9 flat config
├── .prettierrc
├── .env.example                        # VITE_API_BASE=
├── index.html                          # 含 Google Fonts <link>
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx
│   ├── App.tsx                         # 路由定义
│   ├── routes/
│   │   ├── UploadPage.tsx
│   │   ├── OverviewPage.tsx
│   │   ├── ChatPage.tsx
│   │   └── NotFoundPage.tsx
│   ├── components/
│   │   └── Layout.tsx                  # 砼核风格导航 shell
│   ├── lib/
│   │   ├── api.ts                      # fetch 封装
│   │   └── types.ts                    # 后端响应类型
│   ├── styles/
│   │   └── index.css                   # @import "tailwindcss" + 砼核 CSS vars + 噪点纹理
│   └── vite-env.d.ts
└── README.md
```

**v0.2 修订**(R1 P0-3/P0-4/P0-5/P1-5):
- 删除 `tailwind.config.ts`、`postcss.config.js`(Tailwind v4 Vite plugin 不需要)
- `.eslintrc.cjs` → `eslint.config.js`(ESLint 9 flat config)
- 新增 `.env.example`
- `hooks/` 空目录不列入交付(git 不跟踪空目录;TASK-402 按需建)

### 修改文件清单

| 路径 | 修改 |
|---|---|
| `web/README.md` | 覆盖写(原占位 → 完整开发指南,含 SPA fallback 提醒) |
| `.gitignore` | 追加 `web/node_modules/` 和 `web/dist/` |
| `docs/03_TASK_INDEX.md` | TASK-401 行 🔲 → 🔍 |

### 新增依赖

以 `pnpm create vite@latest` 脚手架产出为准。预期核心依赖:

```
dependencies:
  react, react-dom, react-router-dom

devDependencies:
  @vitejs/plugin-react, typescript, vite,
  tailwindcss, @tailwindcss/vite,
  eslint, prettier
  (具体版本以脚手架产出 + pnpm add 实际安装为准)
```

**v0.2 修订**(R1 P0-2/P0-4):不写死版本号,不列 `autoprefixer` / `postcss`(Tailwind v4 Vite plugin 模式不需要)。

### 新增配置项

前端 `.env.example`:

```
# 默认空 = 同源(走 Vite proxy / Nginx 反代)
# 若前端单独部署到不同域名,设完整后端 base URL
VITE_API_BASE=
```

---

## 接口契约

### `web/src/lib/api.ts`

```typescript
/** 后端标准错误响应体(对齐 TASK-201 锁定的 shape) */
export interface ApiError {
  error: string;
  message: string;
}

export class ApiException extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly userMessage: string,
  ) {
    super(userMessage);
  }
}

/**
 * 统一 GET 请求。
 * path 必须以单个 `/` 开头,禁止 `//` 开头(防 scheme-relative 外部请求)。
 */
export async function apiGet<T>(path: string): Promise<T>;

/** 统一 POST 请求(JSON body) */
export async function apiPost<T>(path: string, body?: unknown): Promise<T>;

/**
 * 上传文件(multipart/form-data,支持 onProgress)。
 * 内部用 XMLHttpRequest 以支持 progress 事件。
 */
export async function apiUpload(
  path: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse>;
```

实现要点:
- base URL 从 `import.meta.env.VITE_API_BASE` 读取,默认 `""`
- `path` 必须以单个 `/` 开头;`//` 开头也拒绝(防 scheme-relative 外部请求)。实现:`if (!path.startsWith("/") || path.startsWith("//")) throw new Error(...)`
- 响应 `!ok` 时解析 `{"error", "message"}` 抛 `ApiException`;解析失败抛通用网络错误
- **不**在此层做重试/缓存

### `web/src/lib/types.ts`(v0.2 对齐 TASK-202 / TASK-205 实际 schema)

```typescript
/** 对齐 api/schemas/upload.py::UploadResponse */
export interface UploadResponse {
  project_id: string;
  status: "parsing";
}

/** 对齐 api/schemas/upload.py::ProjectStatusResponse (5 字段) */
export interface ProjectStatus {
  project_id: string;
  name: string;
  status: "parsing" | "ready" | "failed";
  created_at: string;                    // ISO datetime
  error_code: string | null;             // ProjectStatusErrorCode 或 null
}

/** 对齐 TASK-207 ProjectOverview schema(骨架,TASK-402 补全完整字段) */
export interface ProjectOverview {
  project_title: string;
  project_type: string;
  one_sentence_summary: string;
  // TODO: TASK-402 补全剩余 9 字段(对齐 06_OUTPUT_CONTRACTS.md)
}

/** 对齐 TASK-205 ChatResponse */
export interface ChatResponse {
  answer: string;
  citations: SourceRef[];
  is_fallback: boolean;
  fallback_reason?: string;
  session_id: string;
}

/** 对齐 core/domain/source_ref.py */
export interface SourceRef {
  file_path: string;
  block_name?: string;
  line_range?: [number, number];
  description?: string;
}
```

**⚠ 反例 28 兜底**:以上 TypeScript 类型已对齐 task-202 文档核实的实际字段。ChatResponse / SourceRef 仍基于 task-205 文档推断,Codex Stage 0 须 `grep` 确认。TASK-402/403 实施时进一步补全。

### `web/vite.config.ts`(v0.2 修正代理路径 + Tailwind v4 plugin)

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/upload": "http://localhost:8000",
      "/projects": "http://localhost:8000",
    },
  },
});
```

**v0.2 修订**(R1 P0-1):三个精确前缀,不写 `/api`。后续 TASK-404 若新增路径前缀需补 proxy。

### `web/src/styles/index.css`(Tailwind v4 + 砼核 CSS vars + 噪点纹理)

```css
@import "tailwindcss";

/* ========== 砼核色板 ========== */
:root {
  --color-concrete:     #2C2C2C;
  --color-ite:       #E8E4DE;
  --color-rebar:        #8B8680;
  --color-formwork:     #3A3A3A;
  --color-signal:       #E85D3A;
  --color-signal-dim:   #C44D2E;

  --font-display: "IBM Plex Sans", "Noto Sans SC", system-ui, sans-serif;
  --font-mono:    "IBM Plex Mono", "Noto Sans Mono", monospace;
}

/* ========== 全局重置(砼核) ========== */
*, *::before, *::after {
  border-radius: 0 !important;
}

body {
  margin: 0;
  background-color: var(--color-concrete);
  color: var(--color-ite);
  font-family: var(--font-display);
  -webkit-font-smoothing: antialiased;
}

/* ========== 混凝土噪点纹理 ========== */
.texture-concrete {
  position: relative;
}
.texture-concrete::after {
  content: "";
  position: absolute;
  inset: 0;
  opacity: 0.03;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  background-repeat: repeat;
}
```

### `web/src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { UploadPage } from "./routes/UploadPage";
import { OverviewPage } from "./routes/OverviewPage";
import { ChatPage } from "./routes/ChatPage";
import { NotFoundPage } from "./routes/NotFoundPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<UploadPage />} />
          <Route path="view/:projectId" element={<OverviewPage />} />
          <Route path="view/:projectId/chat" element={<ChatPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

**v0.3 修订**(R2 P0-1):页面路由从 `projects/:projectId` 改为 `view/:projectId`,避免与 `/projects` API proxy 前缀冲突。

### 占位页面规范

每个占位页面:
- 导出函数组件
- 大字标题(`text-4xl font-bold`)+ 一行中文功能说明 + "TASK-4XX 实现" 提示
- 使用砼核色板(深灰背景 + 暖白文字 + 信号橙点缀)
- 能被 Router 正常渲染,不白屏
- **不超过 30 行**

---

## 范围(必须做)

- [ ] **Stage 0 全部 7 项**(详见 § Stage 0)
- [ ] 删除 `web/README.md` 占位文件,执行 `pnpm create vite@latest web -- --template react-ts` 脚手架
- [ ] `cd web && pnpm add react-router-dom`
- [ ] `cd web && pnpm add -D @tailwindcss/vite tailwindcss prettier`
- [ ] 清理脚手架样板文件(`App.css` / logo / 默认内容)
- [ ] 创建 `vite.config.ts`(含 proxy + tailwindcss plugin)
- [ ] 创建 `src/styles/index.css`(`@import "tailwindcss"` + 砼核 CSS vars + 噪点纹理)
- [ ] 在 `index.html` 追加 Google Fonts `<link>`(IBM Plex Sans + Noto Sans SC)
- [ ] 创建 `src/lib/api.ts`(完整实现,非仅类型签名)
- [ ] 创建 `src/lib/types.ts`(对齐 Stage 0 核查结果)
- [ ] 创建 `src/components/Layout.tsx`(砼核风格导航 shell + `<Outlet />`)
- [ ] 创建 4 个占位页面(Upload / Overview / Chat / NotFound),砼核风格
- [ ] 创建 `src/App.tsx` 路由定义
- [ ] 创建 `web/.env.example`
- [ ] 覆盖写 `web/README.md`(启动命令 + 目录说明 + proxy 说明 + **页面路径 `/view/*` vs API 路径 `/projects/*` 分离说明** + SPA fallback 提醒 + 后续 Task 扩展点)
- [ ] `.gitignore` 追加 `web/node_modules/` 和 `web/dist/`
- [ ] ESLint 配置:以脚手架产出的 `eslint.config.js` 为准,最小修补
- [ ] Prettier:创建 `.prettierrc`
- [ ] `pnpm install` 成功 + `pnpm dev` 启动 + 4 个路由不白屏
- [ ] `pnpm build` 成功
- [ ] `pnpm lint` 无 error
- [ ] 改 `docs/03_TASK_INDEX.md`:TASK-401 行 🔲 → 🔍
- [ ] 完工三件套(决策 08)

---

## 不做(明确排除)

- ❌ 不实现上传功能(TASK-402)
- ❌ 不实现导览页渲染(TASK-402)
- ❌ 不实现问答 UI(TASK-403)
- ❌ 不实现激活码输入(TASK-404)
- ❌ 不改后端代码
- ❌ 不做 SSR / SSG
- ❌ 不做 i18n
- ❌ 不做前端单元测试框架(TASK-402 按需引入 Vitest)
- ❌ 不做 CI 集成(TASK-405)
- ❌ 不做 PWA / Service Worker
- ❌ 不做粒子效果 / WebGL 背景(Phase 2)
- ❌ 不做 `tailwind.config.ts` / `postcss.config.js`(Tailwind v4 不需要)
- ❌ 不生成 `package-lock.json` / `yarn.lock`

---

## 验收标准

### 1. 依赖安装

```bash
cd web && pnpm install
```

期望:成功,无 peer dependency 冲突。

### 2. lockfile 守门

```bash
test -f web/pnpm-lock.yaml
test ! -f web/package-lock.json
test ! -f web/yarn.lock
```

期望:3 条全过。

### 3. 开发服务器启动

```bash
cd web && pnpm dev
```

期望:Vite 启动 `http://localhost:5173`,终端无 error。

### 4. 四个路由可访问

浏览器手动验证:
- `http://localhost:5173/` → 上传页占位(砼核风格深灰背景 + 大字中文标题)
- `http://localhost:5173/view/test-123` → 导览页占位
- `http://localhost:5173/view/test-123/chat` → 问答页占位
- `http://localhost:5173/no-such-page` → 404 页

每个页面:不白屏,有中文文字,有顶部导航,砼核视觉风格可辨认。

### 5. 开发代理生效

```bash
# 先启动后端
DEEPSEEK_API_KEY=fake-for-test uvicorn api.main:app --port 8000 &
# 再启动前端
cd web && pnpm dev &
sleep 3
# 验证
curl -sS http://localhost:5173/health
```

期望:返回 `{"status":"ok", ...}`。

### 6. 生产构建

```bash
cd web && pnpm build
```

期望:`dist/` 产出,0 TypeScript error,0 build error。warning 可接受但 PR 描述须贴 warning 原文。

### 7. Lint

```bash
cd web && pnpm lint
```

期望:0 error。

### 8. TypeScript strict

```bash
grep -c '"strict": true' web/tsconfig.json
```

期望:1。

### 9. `api.ts` 实现可用

`api.ts` 内 `apiGet` / `apiPost` / `apiUpload` 已实现(非仅类型签名),TASK-402 import 后能直接调用。

### 10. `.gitignore` 已更新

```bash
grep -qx 'web/node_modules/' .gitignore && echo OK
grep -q 'web/dist' .gitignore && echo OK
```

期望:2 个 OK。

### 11. 后端不动

```bash
git diff origin/main..HEAD --stat -- api/ core/ adapters/ features/ app/
```

期望:无输出。

### 12. 文件结构

```bash
ls web/src/lib/api.ts web/src/lib/types.ts web/src/components/Layout.tsx \
   web/src/routes/UploadPage.tsx web/src/routes/OverviewPage.tsx \
   web/src/routes/ChatPage.tsx web/src/routes/NotFoundPage.tsx \
   web/.env.example
```

期望:8 个文件全部存在。

### 13. ESLint flat config

```bash
test -f web/eslint.config.js
test ! -f web/.eslintrc.cjs
test ! -f web/.eslintrc.json
```

期望:全过。

### 14. Tailwind v4 配置

```bash
# 不应存在 v3 配置文件
test ! -f web/tailwind.config.ts
test ! -f web/tailwind.config.js
test ! -f web/postcss.config.js
test ! -f web/postcss.config.ts

# CSS 入口应为 @import "tailwindcss" 而非 @tailwind directives
grep -q '@import "tailwindcss"' web/src/styles/index.css
```

期望:全过。

### 15. README 内容

```bash
grep -q 'pnpm dev' web/README.md
grep -q 'pnpm build' web/README.md
grep -q 'VITE_API_BASE' web/README.md
grep -q 'proxy' web/README.md
grep -q 'try_files' web/README.md
grep -q 'TASK-402' web/README.md
grep -q '/view/' web/README.md
```

期望:7 个 grep 全命中。

### 16. 砼核视觉

```bash
grep -q 'color-concrete' web/src/styles/index.css
grep -q 'IBM Plex' web/index.html
grep -q 'texture-concrete' web/src/styles/index.css
grep -q 'border-radius: 0' web/src/styles/index.css
```

期望:4 个 grep 全命中。

### 17. 页面路由与 API 路径分离(R2 P0-1 守门)

```bash
# 页面路由用 /view,不用 /projects
grep -q 'view/:projectId' web/src/App.tsx
# App.tsx 不应包含 path="projects/ 页面路由
! grep -q 'path="projects/' web/src/App.tsx
```

期望:两条全过。

---

## Stage 0 实地核查(Codex 第一步)

```bash
# 1. 后端路由端点实际清单
grep -rn '@router\.\(get\|post\|put\|delete\)' api/routes/ --include='*.py'
# 对照 § 上下文端点表

# 2. 后端响应 schema 实际字段
grep -rn 'class.*Response' api/schemas/ --include='*.py'
grep -rn 'class SourceRef' core/domain/ --include='*.py'
# 对照 types.ts

# 3. web/ 目录当前状态
ls -la web/
# 期望:只有 README.md

# 4. .gitignore 当前内容
grep 'node_modules\|web/dist' .gitignore
# 避免重复追加

# 5. Node.js 版本(可执行检查,不靠人眼比较)
node -e '
const v = process.versions.node.split(".").map(Number);
const ok = (v[0]===20 && v[1]>=19) || (v[0]===22 && v[1]>=12) || v[0]>22;
if (!ok) throw new Error("Node " + process.versions.node + " does not satisfy Vite requirement (>=20.19 or >=22.12)");
console.log("Node " + process.versions.node + " OK");
'

# 6. pnpm 可用
pnpm --version
# 若不存在:npm install -g pnpm

# 7. 确认脚手架非交互流程
rm web/README.md
pnpm create vite@latest web -- --template react-ts
# 期望:非交互成功;若仍提示覆盖确认,改用:
#   pnpm create vite@latest web_tmp -- --template react-ts
#   rm -rf web && mv web_tmp web
```

任一异常停手报 PM。

---

## 风险与注意点

| # | 风险 | 规避 |
|--:|---|---|
| 1 | 脚手架在非空目录卡交互 | Stage 0 #7:先删 README.md 再跑脚手架;或用临时目录 |
| 2 | Tailwind v4 与 Vite 最新版兼容问题 | 若 `@tailwindcss/vite` 安装失败,**停手报 PM**。不得自行降到 Tailwind v3 + PostCSS(违反 D2 + 不做清单)。 |
| 3 | Node 版本不够 | Stage 0 #5 检查;若 < 20.19 则 `nvm install 22` |
| 4 | proxy 路径遗漏 | TASK-404 若加新路径前缀需补 proxy |
| 5 | Windows 路径问题 | `web/` 不放 OneDrive 同步目录 |
| 6 | Google Fonts CDN 在国内较慢 | Phase 2 可改为本地字体文件;MCS 内测可接受 |
| 7 | `types.ts` 与后端 schema 仍有偏差 | Stage 0 核查 + TASK-402/403 补全 |

---

## 下游接力点

- **TASK-402**:在 `routes/UploadPage.tsx` 和 `routes/OverviewPage.tsx` 实现真实 UI;import `api.ts` 和 `types.ts`;上传成功后 navigate 到 `/view/:projectId`
- **TASK-403**:在 `routes/ChatPage.tsx` 实现聊天 UI + citations 展示;路径 `/view/:projectId/chat`
- **TASK-404**:激活码输入页;可能需要新增路由(不与 API 路径撞前缀)和 proxy 规则
- **TASK-405**:Nginx 配置要点:API 路径(`/health`、`/upload`、`/projects`)proxy_pass 后端;其余路径 `try_files $uri $uri/ /index.html;` 走 SPA fallback。**不得用粗粒度 `location /` 同时匹配 API 和页面**

---

## 估时

- 架构师 v0.2 + GPT R2 窄审:0.5 天
- Codex 实施:0.5-1 天
- PM 验收:0.5 天

**总计:1.5-2 天**

---

## 给 Codex 的提示

### 范围严守

本 Task 只搭骨架。占位页面不超过 30 行。看到自己想写上传逻辑或聊天 UI → 停手。

### 脚手架优先

先 `pnpm create vite@latest`,再在产出上改。脚手架自带的样板文件(App.css / logo / counter 组件)清理掉。

### 砼核风格落地

占位页面要能一眼看出砼核风格:深色背景、暖白大字、直角、粗线条。不要用 Vite 默认的白底蓝链接样板。`Layout.tsx` 导航栏用 `--color-formwork` 背景 + `--color-signal` 品牌名。

### proxy 验证

配好 proxy 后,先启动后端,再启动前端,浏览器 devtools 确认 `/health` 被代理。

### `api.ts` 写实现

`apiGet` / `apiPost` / `apiUpload` 必须是可调用的实现。TASK-402 第一行代码就会 import 并调用。path 校验写成:`if (!path.startsWith("/") || path.startsWith("//")) throw new Error("API path must start with a single '/'")`。

### `types.ts` 标注不确定性

已确认的字段(UploadResponse / ProjectStatus)直接写。不确认的(ChatResponse / SourceRef)加 `// TODO: TASK-402/403 补全` 注释,不编造。

### 不动后端

`git diff` 不应出现 `api/` / `core/` / `adapters/` / `features/` / `app/` 改动。

---

**版本**:v0.3(R3 通过,可交 Codex)
**日期**:2026-06-10
**作者**:Claude(架构师,第二十八任)
**关联宪法版本**:v2.1(冻结)
**审批历史**:R1 不通过(6 P0 + 5 P1)→ v0.2 → R2 不通过(1 P0 + 3 P1)→ v0.3 → R3 通过
**前置 commit**:main HEAD(决策 16 merge 后)
**R3 P2 采纳**:`api.ts` path 校验增加 `//` 双斜杠防御(GPT R3 建议)
