# mxa-tutor web

TASK-401 前端骨架:React + Vite + TypeScript + Tailwind CSS v4。

## 命令

```bash
pnpm install
pnpm dev
pnpm build
pnpm lint
pnpm smoke:task402
```

开发服务器默认运行在 `http://localhost:5173`。

## 目录

- `src/routes/`:页面级入口。`UploadPage` / `OverviewPage` 已接入 TASK-402 交互。
- `src/routes/upload/`:上传 dropzone、状态卡、解析轮询。
- `src/routes/overview/`:工程导览 hook、横向滚动 hook、6 个 panel。
- `src/components/`:通用 UI 与 scene 层。
- `src/lib/api.ts`:原生 fetch / XMLHttpRequest 的薄封装。
- `src/lib/types.ts`:对齐后端响应的 TypeScript 类型。
- `src/lib/errorMessages.ts`:全局 machine code 中文文案表。
- `src/lib/localStore.ts`:导览首访与滚动提示 localStorage。
- `src/styles/index.css`:Tailwind v4 入口与砼核视觉变量。

## API base

`.env.example` 提供 `VITE_API_BASE`。默认留空表示同源请求:

- 开发环境走 Vite `proxy` 到 `http://localhost:8000`
- 生产环境由 Nginx 反代到后端

当前开发代理覆盖 `/health`、`/upload`、`/projects`。

## 路径分离

前端页面路径使用 `/view/:projectId` 和 `/view/:projectId/chat`。后端 API 使用
`/projects/*`、`/upload`、`/health`。不要把页面路由放到 `/projects/*`,否则 Vite
proxy 和生产 Nginx 反代会抢走页面刷新请求。

## SPA fallback

生产 Nginx 需要让 API 路径走后端,其余路径回退到 SPA:

```nginx
location /health { proxy_pass http://backend; }
location /upload { proxy_pass http://backend; }
location /projects { proxy_pass http://backend; }
location / { try_files $uri $uri/ /index.html; }
```

## TASK-402 烟测

```bash
pnpm smoke:task402
```

该脚本检查 TASK-402 关键文件、`panorama.webp` / `upload-bg.webp`、全局错误码表与禁用依赖。

## 后续 Task

TASK-403 在问答页接入会话与 citations 展示。TASK-405 可把前端 lint/build/smoke 接入 CI。
