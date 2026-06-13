# TASK-403 v0.4:Chat 页背景复用 PanoramaScene(治标治问答页"灰色一片")

## 状态

🔍 v0.1.3 PM git mv 入仓决议补丁完成(R1 5 落地 + 2 归档;R2 5 全部落地;v0.1.3 PM 主动决策 task-403 v0.3 → v0.4 走 git mv 覆盖保留历史;**不升 R3**,可派 Codex Stage 0)— 2026-06-13,后端第三十五任,接 `c4d8346`

---

## 派单结论(v0.1.3)

**R1 + R2 双轮 conditional pass + v0.1.3 PM 入仓决议**,Codex 派单前最终修订:

- **R1(GPT R1 一审 2026-06-13)**:2 P0 + 4 P1 + 1 P2 = 7 条;**5 条直接落地本任卡** + **2 条归档为派单工艺反思**
- **R2(GPT R2 二审 2026-06-13)**:3 P0 + 1 P1 + 1 P2 = 5 条**全部直接落地**
- **v0.1.3(PM 主动决策 2026-06-13)**:**task-403 v0.3 → v0.4 走 `git mv` 覆盖**(沿用决策 12 v0.2 → v0.3 入仓 git mv 模式),让 Codex 通过 git history 能追溯 task-403 演进;v0.3 不再保留,v0.4 是 TASK-403 唯一版本;**不算反例**(PM 主动决策点,架构师 v0.1 起稿粒度漏明示入仓模式 = K_28b 微反例,沿用 § 反例账目)
- **架构师反审 R1 + R2 均无 challenge 项**

**修订不改变任务范围,不引入新代码路径,不升 R3**。修完可交 Codex Stage 0。

Codex 实施期重点守门:

1. **任务卡入仓走 `git mv`**(v0.1.3 PM 决议):`git mv docs/tasks/task-403-chat-page-v0_3.md docs/tasks/task-403-chat-page-v0_4.md` + 字节级全替换为 v0.4 内容;**v0.3 不再保留**,v0.4 是 TASK-403 唯一版本
2. **30 行阈值仅限 4 TSX 源码文件**(任务卡 rename 不计入;验收 #5 / 自动升 R2 #5 / Checklist 三处已同步)
3. **Stage 0 命令必须可复制即运行**(全 fenced code block + PowerShell 5.1 兼容,不用 `&&` / `\|` 转义)
4. **验收 #3 grep 限定 3 个源码文件**(避免任务卡内描述性引用误判)
5. **验收 #2 加 StatusStrip 状态触发观察**(若不可读不在本任修,留 Task C2,K_36 范围严守)
6. Codex 实施期任一 8 条触发自动升 R2(详 § 自动升 R2 条件)

---

## 上下文(本任为什么做)

### 产品体验数据驱动(PM 实测 2026-06-13 20:41)

PM 在 TASK-203 v0.4 完工后实测整链路,**到了 chat 页(问答对话页)直接卡住**:

- 顶部一片实色暗灰 `#2c2c2c`
- 中间一个 `READY / 从工程本身开始问 / 可以问入口文件、Simulink 模块、参数含义,回答会尽量带上依据` 的卡片孤零零在屏幕中央
- 卡片上下大量空灰背景
- 视觉饱满度极低,与同款应用(ChatGPT / Claude)对比明显贫瘠

PM 原话:**"是问答部分的,没有背景,只有灰色的部分"**;后追加 **"有视觉背景(壁纸/工程相关图/几何纹理),就和之前的解析页的背景一样吧"**。

### 根因(已 view 确认)

`web/src/routes/ChatPage.tsx` line 41 顶层 `<section>` 套了 `bg-[var(--color-concrete)]` 实色背景,**把 scene 层全遮死**(scene.css `.panorama-scene` 是 `position: fixed; inset: 0; z-index: 0`,本应在底层显示但被前景实色 cover);ChatPage.tsx **从未引入任何 scene 组件**(无 `PanoramaScene` / `UploadScene` / `DustCanvas` import)。

**对比 OverviewPage.tsx**(line 33 / 56 / 124):3 处分别用 `<PanoramaScene panoramaX={0} />`(loading / error)和 `<PanoramaScene panoramaX={panoramaX} />`(主体含视差)。

**MessageBubble.tsx**(line 27 / 30)已是半透明设计:`bg-black/10`(user)/ `bg-[var(--color-formwork)]/70`(assistant)。**前任做 chat 页时显然预想了有背景**,只是漏了一个 scene 引用 + 顶层背景没改透明。

### TASK-403 v0.3 体系归属

本任修 TASK-403 v0.3 实施缺陷,**挂 TASK-403 v0.4 微补丁**(类比决策 12 v0.3 → v0.3.1 / TASK-203 v0.3 → v0.4 / TASK-305 v0.1 → v0.2 模式)。

**反审完成**:TASK-403 v0.3 line 1-100 摘要 + Week 4 索引 line 245 状态 ✅ 一致;TASK-404 / 405 / 406 / 后端任何 task 无依赖 chat 页背景的契约;本任挂 TASK-403 v0.4 无 K_28a 反例 28a 风险。

---

## 审批级别(反例 18 5 维评估)

| 维度 | 评分 |
|---|---|
| 决策密度 | **低-中**(主要决策:Header/Footer 半透方式 / 空态卡片 backdrop-blur / scene 引用方式 — 3-4 个 D 已识别推荐路径)|
| 下游扩散面 | **小**(只动 chat 页 4 个 .tsx 文件;不动 PanoramaScene / scene.css / chat 业务逻辑 / 后端任何契约 / 任何 schema)|
| 用户可见性 | **高**(直接影响 chat 页视觉体验 — PM 实测反馈"没有背景")|
| 异步 / LLM 首次定型 | **无**(纯前端样式补丁,不动 async / 不动 LLM 调用 / 不动 state 机)|
| 隐私 / 安全 | **无变**(不动日志 / 不动 API)|

**结论**:**走 GPT R1 一审起步**(类比 TASK-305 v0.2 / TASK-203 v0.4 R1 起步先例);R1 任一 P0 复杂度高升 R2;Codex Stage 0 + 实施 + Claude R7 终审。Task 范围窄(初估 ~10-30 行改动),R1 大概率 conditional pass。

---

## 上游契约(stand-alone 给 GPT R1)

### 现状文件清单(架构师已 view 确认,Stage 0 兜底)

| 文件 | 角色 | 本任改动 |
|---|---|---|
| `web/src/routes/ChatPage.tsx` | chat 页顶层组件 + StatusStrip 内嵌 | **改**:加 PanoramaScene 引用 + 顶层 section 去 bg-concrete + 加 relative z-10 |
| `web/src/routes/chat/ChatHeader.tsx` | 顶部 toolbar(返回导览 / 新会话下拉 / 新会话按钮)| **改**:bg-concrete → 半透 + backdrop-blur(D1)|
| `web/src/routes/chat/ChatInputBar.tsx` | 底部输入框 + 字数 + SEND | **改**:bg-concrete → 半透 + backdrop-blur(D1)|
| `web/src/routes/chat/MessageList.tsx` | 消息列表 + 空态 READY 卡片 | **改**:空态卡片加 bg + backdrop-blur(D2)|
| `web/src/components/scene/PanoramaScene.tsx` | scene 组件(已存在,接 panoramaX) | **不动**(消费即可)|
| `web/src/styles/scene.css` | scene 样式(.panorama-scene fixed z-0 / .scene-fog / .scene-vignette)| **不动** |
| `web/src/components/scene/DustCanvas.tsx` | 粒子动效(prefers-reduced-motion 自动关闭)| **不动** |
| `web/src/routes/chat/MessageBubble.tsx` | 消息气泡(已半透 user `/10` / assistant `/70`)| **不动**(前任设计意图)|
| `web/src/routes/chat/CitationCard.tsx` / `FallbackBanner.tsx` / `FollowUpChips.tsx` | 子组件 | **不动** |
| `web/src/routes/chat/useChatSession.ts` / `useChatReducer.ts` / `chatHelpers.ts` / `useAutoScroll.ts` | 状态机 / 副作用 | **不动**(本任纯样式)|

### PanoramaScene 组件契约(已 view `PanoramaScene.tsx`)

```tsx
interface PanoramaSceneProps {
  panoramaX: number;
}

export function PanoramaScene({ panoramaX }: PanoramaSceneProps) {
  return (
    <div className="panorama-scene" aria-hidden="true">
      <img className="scene-panorama" src="/assets/panorama.webp" alt=""
        style={{ transform: `translate3d(${panoramaX}px, 0, 0)` }}
        onError={(event) => { event.currentTarget.hidden = true; }} />
      <div className="scene-fog" />
      <DustCanvas opacity={0.38} />
      <div className="scene-vignette" />
    </div>
  );
}
```

- 接受 `panoramaX: number` 一个 prop
- `panoramaX={0}` 是 OverviewLoading / OverviewError 已用模式(无视差,纯背景),沿用即可
- panorama.webp 加载失败 → onError 自动 hidden,显示底层黑色,**chat 内容仍可读**(不会脏掉布局)
- DustCanvas 已 prefers-reduced-motion check,无障碍合规

### scene.css 层叠契约(已 view `scene.css`)

```css
.panorama-scene {
  position: fixed;
  inset: 0;
  z-index: 0;          /* 底层 */
  overflow: hidden;
  background: #1b1d1b;
}
```

- scene 是 `fixed` 全屏 z-0 → chat 内容只需 `relative z-10` 即可压在上层
- scene.css 已含 `.scene-fog` / `.scene-vignette` 渐变层 → 边缘暗化,chat 顶部 / 底部 toolbar 视觉锚点会自然增强

### Tailwind 4 类名兼容性(架构师已确认)

- `bg-[var(--color-concrete)]/70` = 任意值 + 透明度,Tailwind 4 支持(已在 `web/src/styles/index.css` `@import "tailwindcss";` 全局启用)
- `backdrop-blur-md` = Tailwind 内置(`backdrop-filter: blur(12px)`),所有现代浏览器支持(Chrome 76+ / Firefox 103+ / Safari 9+)
- `relative` / `z-10` = 内置,无兼容性问题

### 已完工产物(本任不动)

- `web/src/routes/UploadPage.tsx`(已用 UploadScene)
- `web/src/routes/OverviewPage.tsx`(已用 PanoramaScene + useParallaxBg)
- `web/src/components/scene/*`(本任只消费)
- 所有后端 Python 代码(本任纯前端)

---

## 范围(必须做)

1. 改 `web/src/routes/ChatPage.tsx`:
   - 加 `import { PanoramaScene } from "../components/scene/PanoramaScene";`
   - `ChatPageContent` return JSX 顶层加 `<PanoramaScene panoramaX={0} />`(用 Fragment 或外层 wrapper)
   - `<section>` 去 `bg-[var(--color-concrete)]`,加 `relative z-10`,保留 `flex h-[calc(100vh-72px)] min-h-[620px] flex-col` 高度类
2. 改 `web/src/routes/chat/ChatHeader.tsx`:
   - `<header>` className `bg-[var(--color-concrete)]` → `bg-[var(--color-concrete)]/70 backdrop-blur-md`(D1 决议)
3. 改 `web/src/routes/chat/ChatInputBar.tsx`:
   - `<footer>` className `bg-[var(--color-concrete)]` → `bg-[var(--color-concrete)]/70 backdrop-blur-md`(D1 决议)
4. 改 `web/src/routes/chat/MessageList.tsx`:
   - 空态卡片 `<div className="border border-[var(--color-rebar)] p-6">` → 加 `bg-[var(--color-formwork)]/40 backdrop-blur-md`(D2 决议)
5. **任务卡入仓**(v0.1.3 PM 决议:走 `git mv` 覆盖保留历史,沿用决策 12 v0.2 → v0.3 入仓模式):
   - 命令:`git mv docs/tasks/task-403-chat-page-v0_3.md docs/tasks/task-403-chat-page-v0_4.md`
   - 字节级全替换为 v0.4 内容(决策 08 第 2 条:`read_bytes` + `write_bytes`,不用 `read_text` / `write_text` 避免 LF/CRLF 行尾被规范化)
   - **v0.3 不再保留**,v0.4 是 TASK-403 唯一版本
   - `git diff --stat origin/main` 可能显示为 rename(若 git 识别 ≥ 30% 相似度)或 delete + create 两个 entries(若识别为完全不同 — 本任内容差异大,大概率后者)— **任一形态均算正常**,只要文件名匹配 v0.3 → v0.4 即可
   - **task 卡入仓行数(~870 行)不计入 30 行阈值** — 详 § 验收 #5 / § 自动升 R2 #5

## 不做(明确排除)

- ❌ 改 `PanoramaScene.tsx` / `UploadScene.tsx` / `DustCanvas.tsx`(本任只消费,不改 scene 组件本身)
- ❌ 改 `web/src/styles/scene.css`(scene 样式现成 / 全屏 fixed z-0 即可)
- ❌ 改 `MessageBubble.tsx` / `CitationCard.tsx` / `FollowUpChips.tsx` / `FallbackBanner.tsx`(前任已是半透明设计 — `bg-black/10` / `bg-[var(--color-formwork)]/70`,本任尊重设计意图,不动)
- ❌ 改 `useChatSession.ts` / `useChatReducer.ts` / `useAutoScroll.ts` / `chatHelpers.ts`(纯样式补丁,不动状态机 / 副作用 / 路由)
- ❌ 改 `StatusStrip` 错误条样式(C2 范围,本任只动顶层 scene 引用 + 顶底 toolbar + 空态卡片背景)
- ❌ 改 ChatHeader "新会话下拉 + 新会话按钮"功能重复(C2 范围,本任不动)
- ❌ 引入 `useParallaxBg` / 视差(chat 页是纵向 messageList 滚动,无横滚 → 视差无意义,`panoramaX={0}` 固定即可)
- ❌ 改后端 Python 代码 / API contract / overview retry 用尽问题(retry 用尽是 PM 偶发实测信号,留 TASK-306 评测解锁后看真实失败率;本任纯前端样式补丁不混)
- ❌ 引入新前端依赖 / 新 hook / 新 scene 组件(`<ChatScene>` 单独包?— 触发 § 自动升 R2 #2)
- ❌ 改 `OverviewPage.tsx` 或 chat 页之外的 routes(本任只 chat 页)
- ❌ 改 `tailwind.config.*` / `vite.config.*` / `package.json`(本任仅消费现有类名)
- ❌ 加视觉资源文件(本任复用 `/assets/panorama.webp`,不新增图片 / svg / 字体)

---

## R1 拍板结论(GPT R1 一审 2026-06-13)

GPT R1 conditional pass + **2 P0 + 4 P1 + 1 P2 = 7 条;5 条直接落地本任卡 + 2 条归档为派单工艺反思**(P0-1 / P1-2 r1-prompt 文件本身不返工,作为下任决策 12 v0.4 候选纪律);Claude 反审 GPT R1 **无 challenge 项**(grep 核查:GPT 引用的反例分类 K_28a / K_30 / K_36 全部对位准确;GPT 修法 PowerShell 语法实测无误;GPT 未用"很到位 / 抓得对"等隐式认账措辞);**架构师 K_28a 自抓 +2 / K_30 自抓 +3 / K_36 自抓 +1**(详 § 反例账目)。

### D1-D6 R1 全通过(无方向性分歧)

D1 / D2 / D3 / D4 / D5 / D6 推荐路径全部 R1 通过,不动方向(详 § D 决策段)。

### P0-1:派单 prompt 占位符内嵌矛盾(K_30 跨段同步漏)

- **架构师原稿问题**:r1-prompt 顶部"派单上下文"段写"任务卡 v0.1 内容已内嵌,不需另外附件",但 `§ 任务卡 v0.1 全文(GPT review 对象)` 仍是 `[在这里完整粘贴 ...]` 占位符;末尾 PM 实操步骤又要求"替换占位符" — 同一份文档 3 处描述自相矛盾。
- **修法**:本次 R1 实际由 PM 替换占位符后 GPT 看到 v0.1 全文做出反馈(R1 已完成不必返工 prompt 文件)。**作为下任工艺纪律**记入决策 12 v0.4 候选 — "派单 prompt 起稿完成 → 必 grep `\[在这里` 命中 = 0 + grep 顶部表述与 § 全文段一致"(沿用 R7.1 grep 兜底模式)。
- **影响**:r1-prompt 文件本身不修(R1 已完成);本任卡 § R1 拍板结论记录工艺反思。

### P0-2:Stage 0 命令 PowerShell 5.1 兼容性(K_28a / 工具默认行为凭印象)

- **架构师原稿问题**:Stage 0 #1 用 `cd F:\mxa-tutor && git log -1 --oneline`,PowerShell 5.1 不支持 `&&`(7+ 才支持);多处管道命令在 markdown 表格中写 `\| Select-String` 转义,Codex 复制反斜杠会失败。
- **修法**:Stage 0 全部命令改 fenced code block + PowerShell 5.1 兼容(单独行 + 真实 `|`)。
- **影响**:§ Stage 0 派单 整段重写(下文)。

### P1-1:`Get-Content -Raw` 与"全文行号"矛盾(K_28a)

- **架构师原稿问题**:Stage 0 #3 写 `Get-Content ... -Raw`(返回单字符串无行号)+ "报告全文行号 + 内容"(需要行号)— 命令与期望输出矛盾。
- **修法**:删 `-Raw`,改 `Select-String` 模式 / 限定 line 范围;不要求"全文行号",只要求"关键段 line 号 anchor"。
- **影响**:Stage 0 #3-#7 命令重写(下文)。

### P1-2:派单 prompt "必含 7 个段" vs 输出 6 段(K_30)

- **架构师原稿问题**:r1-prompt R1 任务描述"产出 sibling challenge 清单 ... **必含 7 个段**",但反馈输出格式只有 § 1-§ 6 六段(混了"R1 任务 7 项"和"输出 6 段")。
- **修法**:r1-prompt 文件本身不修(R1 已完成);**作为下任工艺纪律**记入决策 12 v0.4 候选 — "派单 prompt 起稿完成 → 必 grep 段数自描述与实际段数一致"。
- **影响**:本任卡 § R1 拍板结论记录工艺反思。

### P1-3:验收 grep `\b` 不稳 + 未限定文件(K_30 / K_28a 反例 25 同源)

- **架构师原稿问题**:验收 #3 写 `grep -rn "bg-\[var(--color-concrete)\]\b" ...`,`\b` 在 GNU grep / PowerShell Select-String 行为不一致;且未限定目标文件 → 任务卡内大量描述性引用 / 反例账目段 K_30 instance 描述会误判。
- **修法**:验收 #3 grep 限定 3 个源码文件(ChatPage.tsx / ChatHeader.tsx / ChatInputBar.tsx)+ 匹配旧类后边界(空格 / 引号),不依赖 `\b`。
- **影响**:§ 验收 #3 整段重写(下文)。

### P1-4:StatusStrip 视觉验收边界(K_36 工程职责边界漏)

- **架构师原稿问题**:验收 #2 要求"PM 视觉确认 StatusStrip 视觉无回归",但**未强制触发** StatusStrip 状态(resolving / needs_refresh / error);正常空态 / 成功问答看不到 StatusStrip,可能漏"红字叠在 panorama 上可读性"风险。
- **修法**:验收 #2 加一条"PM 触发或观察 StatusStrip 至少一种状态,视觉确认文字 + 操作可点击 + 在 scene 背景上清晰可读";若不可读 → **不在本任修**(尊重不做清单 #5)+ 记录在 PR 备注里**留 Task C2**(K_36 范围严守,避免 Codex 实施期当场扩范围)。
- **影响**:§ 验收 #2 加条;**架构师明确不采纳 GPT 提的"PM 当场授权在 wrapper 加半透背景"模式**(违反 § 7.1.1 紧迫感预防 — 架构师 / Codex 不能在实施期单方面扩范围)。

### P2-1:Tailwind 任意值透明度 DevTools 兜底(K_28a 兜底建议)

- **架构师原稿问题**:任务卡断言 Tailwind 4 支持 `bg-[var(--color-concrete)]/70`(架构师"已确认"未实测 build 跑通)。
- **修法**:验收 #2 加一条"PM 真启动验收时打开 DevTools Elements / Computed,看 Header / Footer / 空态卡片 computed `background-color` 是否带 alpha(`rgba` 或 `color-mix` 形式)";若不带 alpha(实际是实色)→ 提示 Tailwind 4 任意值透明度兼容性问题,留 Task C2 评估。
- **影响**:§ 验收 #2 加条。

---

## R2 拍板结论(GPT R2 二审 2026-06-13)

GPT R2 conditional fail + **3 P0 + 1 P1 + 1 P2 = 5 条全部直接落地本任卡**;Claude 反审 GPT R2 **无 challenge 项**(grep 核查:R2 引用的 line 号 / 字面 / 反例分类全部对位准确;R2 修法 PowerShell `-SimpleMatch` 文档实证 PASS / `$LASTEXITCODE` chain 语法实测 PASS;R2 未用隐式认账措辞);**架构师 K_28a 自抓 +1 / K_30 自抓 +3 / R7.1 工艺纪律深化教训**(详 § 反例账目)。

### P0-1:"30 行阈值"与"任务卡入仓"自相矛盾,会自触发自动升 R2 #5 硬阻断(K_30 + K_36 范围阈值边界)

- **架构师原稿问题**:验收 #5 / 自动升 R2 #5 / Checklist 三处写"总改动行数 ≤ 30",但范围 #5 + 验收 #4 又要求 `git diff --stat origin/main` 含 5 个文件含**任务卡入仓(~786 lines create mode)**;Codex 完工跑 `git diff --stat` 必看到总改 ~800 行 > 30 → 自动升 R2 #5 硬阻断
- **修法**:三处明示"**4 个 TSX 源码文件净改动 ≤ 30 行;`docs/tasks/task-403-chat-page-v0_4.md` 任务卡入仓不计入该阈值**";自动升 R2 #5 同步改"4 TSX 源码文件净改 > 30"
- **影响**:范围 #5 / 验收 #5 / 自动升 R2 #5 / Checklist 四处同步修订(下文)
- **架构师 K_30 + K_36 边界口径自抓**:阈值口径模糊("总改动行数"可解释为 diff 总数 / 单文件 / 4 TSX 净改),起稿时未沿用 task-203 v0.4 模式(`overview_service.py` 总行数 ≤ 300 = 单文件)或明示阈值口径

### P0-2:Stage 0 #3b `Select-String -SimpleMatch` 配反斜杠转义字面 = 0 命中误升 R2(K_28a / 反例 27 工具行为)

- **架构师原稿问题**:Stage 0 #3b 命令是 `Select-String -Path web\src\routes\ChatPage.tsx -Pattern 'bg-\[var\(--color-concrete\)\]' -SimpleMatch`;`-SimpleMatch` 把 pattern 当字面字符串 → 实际查找包含真实反斜杠的字符串 `bg-\[var\(--color-concrete\)\]`,源码无反斜杠 → **0 命中** → Codex 自判"ChatPage 已无 bg-concrete → 升 R2 #1"硬阻断
- **修法**:改为 `Select-String -Path web\src\routes\ChatPage.tsx -Pattern 'bg-[var(--color-concrete)]' -SimpleMatch`(字面无反斜杠 + SimpleMatch 把 `[` / `(` / `)` 当字面字符)
- **影响**:Stage 0 #3b 命令重写
- **架构师 K_28a 自抓**:凭"`-SimpleMatch` = 字面匹配应该接受 regex 转义"印象,**未实测 PowerShell `-SimpleMatch` 行为**(实测应 `Get-Help Select-String -Examples`)— 反例 27 同源(工具默认行为凭印象)

### P0-3:验收 #1 残留 `&&`(K_30 + K_28a / R1 P0-2 同源未修复)

- **架构师原稿问题**:v0.1.1 修订时 R1 P0-2 改了 Stage 0 命令的 `&&`,但**漏改验收 #1**:`cd F:\mxa-tutor\web && npm run <typecheck> && npm run <lint> && npm run <build>` 仍用 `&&` 不兼容 PowerShell 5.1
- **修法**:验收 #1 改 PowerShell 5.1 兼容 fenced code block + `$LASTEXITCODE` chain:
  ```powershell
  Set-Location F:\mxa-tutor\web
  npm run <typecheck>
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  npm run <lint>
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  npm run <build>
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  ```
- **影响**:§ 验收 #1 整段重写
- **架构师 K_30 + R7.1 工艺纪律失效深化教训**:v0.1.1 R7.1 grep 字面只查 "`cd F:\mxa-tutor &&`"(直接接 `&&`),漏抓 line 527 "`cd F:\mxa-tutor\web &&`"(中间 `\web`)同源残留 — **R7.1 grep 字面必须先用宽字面(如 `&&`)grep 整篇文档找所有同根因模式,再去逐项判断指令性 vs 描述性**(反例 25 / 30 同源延伸)

### P1-1:R7.1 grep 兜底未覆盖 `&&` 全部残留(K_30)

- **架构师原稿问题**:R7.1 grep 兜底表只查窄字面 "`cd F:\mxa-tutor &&`",P0-3 的 line 527 "`cd F:\mxa-tutor\web &&`" 漏抓 = **R7.1 自验失败**
- **修法**:扩 R7.1 grep 字面 — 改为 `&& npm` / `&& git` / `&& [a-z]+` 等 shell chain 形式(描述性引用如反例账目 / R1 R2 拍板结论描述 `&&` 命中允许保留)
- **影响**:R7.1 grep 兜底表扩列(下文)
- **架构师工艺纪律深化**:R7.1 grep 字面起稿前必须先以**宽字面**(如根字符 `&&` / `Get-Content` / `Raw`)grep 整篇文档,看命中分布,再拟定指令性残留判定字面 — 不要从已知狭窄字面起稿(经典 grep 字面太严漏抓教训)

### P2-1:"7 条全采纳"措辞略过度(K_30)

- **架构师原稿问题**:v0.1.1 顶部 + 派单结论 + R1 拍板结论 + 末尾审批历史多处写"7 条全采纳",但 R1 P0-1 / P1-2 实际修法是"r1-prompt 文件本身不修,作为下任工艺反思" — "全采纳"措辞容易被理解为所有源文件均已实际修复
- **修法**:多处措辞改"**5 条直接落地本任卡 + 2 条归档为派单工艺反思**"
- **影响**:状态行 / 派单结论 / R1 拍板结论 顶部 / 末尾审批历史 同步修订(已完成,见上下文)

---

## D 决策(R1 已拍板)

架构师推荐路径,GPT R1 全通过,无方向性分歧。

### D1 — Header / Footer 半透方式

| 选项 | 描述 | 推荐? |
|---|---|---|
| D1.A | 保持实色 `bg-[var(--color-concrete)]`(顶底锚点强,但与 MessageBubble `/70` 半透中段视觉断层)| ❌ |
| **D1.B** | **改 `bg-[var(--color-concrete)]/70 backdrop-blur-md`**(scene 微透 + 顶底锚点 + 与中段半透一致)| ✅ **推荐** |
| D1.C | 改 `bg-[var(--color-concrete)]/50 backdrop-blur-md`(scene 较透,但顶底锚点弱化,可能误以为非交互层)| ❌ |

**推荐 D1.B**:与 OverviewPage 的 PanelFrame / OverviewTopAction 风格大致一致(半透 + blur 让 scene 微透出层次感)。

### D2 — 空态卡片(READY / 从工程本身开始问)backdrop-blur

| 选项 | 描述 | 推荐? |
|---|---|---|
| D2.A | 不动(只 border,scene 直接透 → 文字可读性受影响)| ❌ |
| **D2.B** | **加 `bg-[var(--color-formwork)]/40 backdrop-blur-md`**(类比 assistant bubble 半透 + blur,文字清晰 scene 仍透)| ✅ **推荐** |
| D2.C | 加 `bg-[var(--color-formwork)]` 实色(可读最强,但视觉与 scene 切断)| ❌ |

**推荐 D2.B**:scene 仍能透,文字可读性 OK,与 MessageBubble assistant 风格(`/70`)同源 lineage(同 formwork token)。

### D3 — MessageBubble 透明度调整

| 选项 | 描述 | 推荐? |
|---|---|---|
| **D3.A** | **不动**(前任 `bg-black/10` user / `bg-[var(--color-formwork)]/70` assistant 设计意图明显;本任尊重)| ✅ **推荐** |
| D3.B | 微调(user → `/20` 强化 / assistant → `/60` 降低)| ❌(超范围,可能破坏前任 contrast 决策)|

**推荐 D3.A**:本任治标治"灰色一片",**不动**前任已半透的子组件。若 R1 / PM 实测发现 scene 加上后某些气泡可读性下降 → 留 Task C2(C2/C3 拆分计划)。

### D4 — Scene 引用方式

| 选项 | 描述 | 推荐? |
|---|---|---|
| **D4.A** | **直接 `<PanoramaScene panoramaX={0} />`**(沿用 OverviewLoading / OverviewError line 33 / 56 模式,一致性最强)| ✅ **推荐** |
| D4.B | 新建独立 `<ChatScene>` 组件(语义清晰,但增范围 + 触发 § 自动升 R2 #2)| ❌ |
| D4.C | 引入 useParallaxBg(chat 页纵向滚 → 横滚 panoramaX 无意义)| ❌ |

**推荐 D4.A**:最小侵入,最高一致性。

### D5 — Scene 引用位置(JSX 结构)

| 选项 | 描述 | 推荐? |
|---|---|---|
| **D5.A** | **Fragment + 同级**:`<><PanoramaScene panoramaX={0} /><section className="relative z-10 ...">...</section></>`(scene 作为 fixed 全屏不需要被 section 包裹)| ✅ **推荐** |
| D5.B | 外层 wrapper div:`<div className="relative"><PanoramaScene .../><section ...>...</section></div>`(无必要的额外 DOM)| ❌ |

**推荐 D5.A**:scene 本身已 `position: fixed`,不需要相对父容器;Fragment 不引入额外 DOM 节点。OverviewPage line 124-141 用的就是 Fragment 同级模式(`<main>` 内 `<PanoramaScene/>` + `<OverviewTopAction/>` + `<section>` 同级 sibling)。

### D6 — 顶层 `<section>` 高度类 `h-[calc(100vh-72px)] min-h-[620px]` 处理

| 选项 | 描述 | 推荐? |
|---|---|---|
| **D6.A** | **保留**(chat 页全屏布局依赖,本任不动)| ✅ **推荐**(必留)|
| D6.B | 改 `h-screen`(简化,但与现有 72px header offset 计算冲突 — 不知 72px 何处定义,**未实地查 → 凭印象动 = K_28a 候选**)| ❌ |

**推荐 D6.A**:不动布局尺寸,本任纯样式补丁。

---

## 接口契约 / 实施设计稿(D1-D6 推荐路径)

### 7.1 `web/src/routes/ChatPage.tsx` 修订设计稿

```tsx
// === BEFORE (line 1-15) ===
import { useReducer } from "react";
import { useParams } from "react-router-dom";
import { resolveErrorMessage } from "../lib/errorMessages";
import { ChatHeader } from "./chat/ChatHeader";
// ... (无 PanoramaScene import)

// === AFTER ===
import { useReducer } from "react";
import { useParams } from "react-router-dom";
import { PanoramaScene } from "../components/scene/PanoramaScene";  // NEW
import { resolveErrorMessage } from "../lib/errorMessages";
import { ChatHeader } from "./chat/ChatHeader";
// ... (其他 import 不变)


// === BEFORE (ChatPageContent return,line 39-67) ===
return (
  <section className="flex h-[calc(100vh-72px)] min-h-[620px] flex-col bg-[var(--color-concrete)]">
    <ChatHeader ... />
    <StatusStrip ... />
    <MessageList ... />
    <ChatInputBar ... />
  </section>
);

// === AFTER ===
return (
  <>
    <PanoramaScene panoramaX={0} />
    <section className="relative z-10 flex h-[calc(100vh-72px)] min-h-[620px] flex-col">
      <ChatHeader ... />
      <StatusStrip ... />
      <MessageList ... />
      <ChatInputBar ... />
    </section>
  </>
);
```

**关键改动**(2 处):
- Line 3 附近:加 `import { PanoramaScene } from "../components/scene/PanoramaScene";`(D4)
- ChatPageContent return JSX:Fragment 包裹 + scene 同级 sibling(D5)+ section 去 `bg-[var(--color-concrete)]` + 加 `relative z-10`(D6)

**ChatPage 早 return**(line 21-27,无 projectId 时):**不动**。

### 7.2 `web/src/routes/chat/ChatHeader.tsx` 修订设计稿

```tsx
// === BEFORE (line 22) ===
<header className="border-b-2 border-[var(--color-rebar)] bg-[var(--color-concrete)] px-4 py-3">

// === AFTER ===
<header className="border-b-2 border-[var(--color-rebar)] bg-[var(--color-concrete)]/70 backdrop-blur-md px-4 py-3">
```

**关键改动**(1 处):D1 决议,bg-concrete → bg-concrete/70 + backdrop-blur-md。

### 7.3 `web/src/routes/chat/ChatInputBar.tsx` 修订设计稿

```tsx
// === BEFORE (line 28) ===
<footer className="border-t-2 border-[var(--color-rebar)] bg-[var(--color-concrete)] px-4 py-4">

// === AFTER ===
<footer className="border-t-2 border-[var(--color-rebar)] bg-[var(--color-concrete)]/70 backdrop-blur-md px-4 py-4">
```

**关键改动**(1 处):D1 决议,同 ChatHeader 模式。

### 7.4 `web/src/routes/chat/MessageList.tsx` 修订设计稿

```tsx
// === BEFORE (line 26-32) ===
{!messagesLoading && messages.length === 0 ? (
  <div className="border border-[var(--color-rebar)] p-6">
    <p className="section-kicker">READY</p>
    <h2 className="mt-3 text-2xl font-black">从工程本身开始问</h2>
    <p className="mt-3 text-sm leading-7 text-[var(--color-rebar)]">
      可以问入口文件、Simulink 模块、参数含义,回答会尽量带上依据。
    </p>
  </div>
) : null}

// === AFTER ===
{!messagesLoading && messages.length === 0 ? (
  <div className="border border-[var(--color-rebar)] bg-[var(--color-formwork)]/40 backdrop-blur-md p-6">
    <p className="section-kicker">READY</p>
    <h2 className="mt-3 text-2xl font-black">从工程本身开始问</h2>
    <p className="mt-3 text-sm leading-7 text-[var(--color-rebar)]">
      可以问入口文件、Simulink 模块、参数含义,回答会尽量带上依据。
    </p>
  </div>
) : null}
```

**关键改动**(1 处):D2 决议,空态卡片加 `bg-[var(--color-formwork)]/40 backdrop-blur-md`。

### 7.5 总改动行数(架构师初估)

| 文件 | 改动行数 |
|---|---|
| `ChatPage.tsx` | +1 import / 1 行 JSX 结构改 / +1 PanoramaScene 引用 = **~3 行净增**(去掉 bg-concrete,加 relative z-10 是同行修改)|
| `ChatHeader.tsx` | className 1 处改 = **~1 行净改** |
| `ChatInputBar.tsx` | className 1 处改 = **~1 行净改** |
| `MessageList.tsx` | className 1 处加 = **~1 行净改** |
| **总计** | **~6-10 行净改 / 4 文件**(若 ChatPage Fragment 包裹算多行,可能 ~15 行)|

---

## Stage 0 派单(精确事实校验,决策 12 § R7 / § R7.1 / § R6.1)

Codex 实施前必跑(任一 FAIL 停手报 PM,**禁止凭文档伪代码补猜真实代码 — 决策 09 纪律 1**)。

**命令规范**(v0.1.1 P0-2 + P1-1 修订):
- 全部 fenced code block(可复制即运行)
- PowerShell 5.1 兼容(不用 `&&` / `||`,改 `;` 分隔或独立行;管道用真实 `|`)
- 不用 `Get-Content -Raw`(返回单字符串无行号),改 `Select-String -Path` 或 `Get-Content` 不带 `-Raw`(自动按行返回 + Select-String 模式)
- 工作目录:**Codex 实施前先 `Set-Location F:\mxa-tutor`**(本任工作根)

### #1 — main HEAD(本任基线 = `c4d8346`)

```powershell
Set-Location F:\mxa-tutor
git log -1 --oneline
```

**期望** HEAD = `c4d8346 chore: decision-12 v0.3.2 + 03 索引同步 + 清理 task-403 遗留 (#84)`
**若 HEAD ≠ `c4d8346`**:报告当前 HEAD,跑 `git log --oneline -5` 列最近 commit,等 PM 确认是否为授权的新 main(类比 TASK-203 v0.4 灵活 HEAD 模式)。

### #2 — Working tree clean

```powershell
git status
```

**期望**:`nothing to commit, working tree clean`

### #3 — `ChatPage.tsx` import 段 + 顶层 section className(P1-1 修订:去 -Raw,改用 Select-String 行号模式)

```powershell
# 3a: imports (line 1-15)
Get-Content web\src\routes\ChatPage.tsx | Select-Object -First 15
```

**期望**:line 1-15 中**无任何 scene 组件 import**(无 `PanoramaScene` / `UploadScene` / `DustCanvas`)
**若已存在 scene import** → 升 R2 #1(已是某种 scene 集成,设计变更)

```powershell
# 3b: 顶层 <section> className anchor (SimpleMatch 字面查找,不需 regex 转义)
Select-String -Path web\src\routes\ChatPage.tsx -Pattern 'bg-[var(--color-concrete)]' -SimpleMatch
```

**期望**:命中 1 处,在 line ~41 附近,字面为 `<section className="flex h-[calc(100vh-72px)] min-h-[620px] flex-col bg-[var(--color-concrete)]">`
**若 0 命中**:`<section>` 已无 `bg-[var(--color-concrete)]` → 升 R2 #1(已修改)
**若 ≥ 2 命中** → 报告所有命中位置,等 PM 确认
**注意**(v0.1.2 R2 P0-2 修订):`-SimpleMatch` 把 pattern 当字面字符串(`[` / `(` / `)` 都是字面字符),**不可用反斜杠转义**;若误写 `'bg-\[var\(--color-concrete\)\]' -SimpleMatch` 会查找带真实反斜杠的字符串,源码无反斜杠 → 0 命中误判

```powershell
# 3c: 报告 ChatPageContent 函数体 return JSX 结构 (line ~40-67)
Get-Content web\src\routes\ChatPage.tsx | Select-Object -Skip 30 -First 40
```

**期望**:Codex 在 PR 中粘贴该段(为 Fragment 包裹改动对位)

### #4 — `ChatHeader.tsx` 当前 `<header>` className

```powershell
Select-String -Path web\src\routes\chat\ChatHeader.tsx -Pattern '<header' -Context 0,2
```

**期望**:命中 1 处,`<header>` className 含 `bg-[var(--color-concrete)]`,**不含** `backdrop-blur` / `/70` 等透明度修饰
**若已含 backdrop-blur 或透明度修饰** → 升 R2 #1

### #5 — `ChatInputBar.tsx` 当前 `<footer>` className

```powershell
Select-String -Path web\src\routes\chat\ChatInputBar.tsx -Pattern '<footer' -Context 0,2
```

**期望**:命中 1 处,`<footer>` className 含 `bg-[var(--color-concrete)]`,**不含** `backdrop-blur` / `/70` 等透明度修饰
**若已含 backdrop-blur 或透明度修饰** → 升 R2 #1

### #6 — `MessageList.tsx` 空态卡片当前 className

```powershell
Select-String -Path web\src\routes\chat\MessageList.tsx -Pattern 'border border-\[var\(--color-rebar\)\] p-6' -Context 0,1
```

**期望**:命中 1 处,字面只有 `border border-[var(--color-rebar)] p-6`,**不含** `bg-` / `backdrop-blur`
**若已含 bg / backdrop-blur** → 升 R2 #1

### #7 — `PanoramaScene.tsx` 当前签名(确认未被改 — 升 R2 守门)

```powershell
Get-Content web\src\components\scene\PanoramaScene.tsx
```

**期望**:`PanoramaSceneProps` interface 仍只接 `panoramaX: number` 一个 prop
**若已加新 prop / 改签名** → 升 R2 #1

### #8 — `scene.css` `.panorama-scene` z-index 实测

```powershell
Select-String -Path web\src\styles\scene.css -Pattern '\.panorama-scene' -Context 0,8
```

**期望**:命中段含 `position: fixed; inset: 0; z-index: 0;`
**若 z-index ≠ 0** → 调整本任 chat `<section>` 的 `relative z-10` 应改为相应高于 scene 的 z 值(报告等 PM 确认)

### #9 — web 目录 npm scripts 真实命令(反例 27 同源,凭印象会写错命令名)

```powershell
Get-Content web\package.json | Select-String '"scripts"' -Context 0,15
```

**期望报告**:`scripts` 字段全部命令(常见 `dev` / `build` / `lint` / `typecheck` / `format` / `test`,真实命令名以本命令输出为准)
**作用**:为验收 1 提供精确命令字符串(避免凭印象写 `npm run typecheck` 而实际是 `tsc --noEmit` / `npm run lint` 实际是 `eslint . --max-warnings 0` 等)

### #10 — 前端测试套件存在性(无强制加测试要求,但需报告)

```powershell
Get-ChildItem -Recurse -Path web\src -File -Include *.test.ts,*.test.tsx,*.spec.ts,*.spec.tsx -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
```

**期望**:可能无任何前端测试文件(本任纯样式补丁,无业务逻辑变更,**不强制加测试** — 验收靠真启动 #2 PM 实测视觉)
**若已有 chat 相关测试** → 报告路径,Codex 实施期评估是否需要补 className 断言(不必须;PM 决定)

---

报告格式:**每项独立粘贴命令 + 实测输出片段 + PASS / FAIL**;任一 FAIL 停手报 PM,**禁止补猜**(决策 09 纪律 1)。

---

## 验收

1. **`web/` 目录 typecheck / lint / build 全 PASS**(Stage 0 #9 报告的精确命令;**v0.1.2 R2 P0-3 修订:改 PowerShell 5.1 兼容,不用 `&&`**):
   - **首选完整管道**(PowerShell 5.1 兼容,沿用 R1 P0-2 fenced code block 模式):
     ```powershell
     Set-Location F:\mxa-tutor\web
     npm run <typecheck>
     if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
     npm run <lint>
     if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
     npm run <build>
     if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
     ```
   - 具体命令名 `<typecheck>` / `<lint>` / `<build>` 以 Stage 0 #9 报告为准,**禁止凭印象**
   - 若 main 既有 hygiene 问题 → 贴**完整失败输出**(不截断)+ **PM 明确授权** 后拆条跑本任相关 gate;**未授权不得自判 PASS**(沿用 TASK-203 v0.4 验收 1 模式)
   - 未经 PM 授权,管道任一步 `$LASTEXITCODE ≠ 0` = FAIL,停手报 PM

2. **真启动验收(关键 — PM 实测视觉,v0.1.1 P1-4 + P2-1 修订)**:
   - PM 启动 mxa-tutor(前端 + 后端)
   - 浏览器进 chat 页(任意已 ingested 工程 → 进 chat 子页)
   - PM 视觉确认 **4 件事全部 PASS**:
     - ✅ chat 页背景出现 panorama scene(类比解析页),不再是纯灰
     - ✅ ChatHeader / ChatInputBar 半透 + scene 微透出
     - ✅ 空态 `READY / 从工程本身开始问` 卡片文字清晰可读(blur 让背景可见但不干扰文字)
     - ✅ MessageBubble / Citations 视觉无回归(可读 / 可点击 / 颜色对比足够)
   - **强制触发 StatusStrip 至少一种状态(v0.1.1 P1-4 新增)**:
     - PM 或 Codex 通过下列任一手段触发 StatusStrip:
       - (a) mock `sessionsErrorCode` / `messagesErrorCode`(在浏览器 React DevTools 修改 state)
       - (b) 后端临时挂掉 `/sessions` 接口(触发 vite proxy ECONNREFUSED → request_failed,沿用 PM 此前实测场景)
       - (c) 任意已知 error code 触发(如 LLM rate limit 模拟)
     - 视觉确认 StatusStrip 红字 / 文本叠在 panorama 上**清晰可读**(对比度足够)
     - **若 StatusStrip 不可读** → **不在本任修**(K_36 范围严守,尊重不做清单 #5)+ PR 备注里写"留 Task C2:StatusStrip wrapper 加半透背景"
   - **DevTools computed style 兜底(v0.1.1 P2-1 新增)**:
     - PM 真启动时打开浏览器 DevTools → Elements → Computed
     - 检查 `<header>` / `<footer>` / 空态卡片 `<div>` 计算后的 `background-color` 字段
     - **期望**:rgba / color-mix 形式带 alpha(如 `rgba(44, 44, 44, 0.7)` 或 `color-mix(in srgb, var(--color-concrete) 70%, transparent)`)
     - **若实色无 alpha**(Tailwind 4 任意值透明度兼容性问题)→ 报 PM 评估,留 Task C2 / 改 CSS class fallback
   - PM 视觉 + 功能确认 **业务无回归**:
     - ✅ 输入问题 → 发送 → 回答正常(包含 citations 展示)
     - ✅ 切换 session 正常(若 PM 已有多 session)
     - ✅ 新会话按钮正常
     - ✅ 错误状态显示正常(由强制触发 StatusStrip 已覆盖)
   - **未能视觉确认任一项 = FAIL**,Codex 停手报 PM 分析

3. **既有 chat 业务功能无回归 + grep 兜底(v0.1.1 P1-3 修订:限定 3 源码文件)**:
   - 本任纯样式,不动 `useChatSession.ts` / `useChatReducer.ts` / `chatHelpers.ts` / 任何 state 机
   - **PowerShell 兜底**(本任主要环境):
     ```powershell
     Select-String -Path web\src\routes\ChatPage.tsx, web\src\routes\chat\ChatHeader.tsx, web\src\routes\chat\ChatInputBar.tsx -Pattern 'bg-\[var\(--color-concrete\)\][\s"]'
     ```
     **期望**:**0 命中**(原实色 className 已全部清除,新类 `bg-[var(--color-concrete)]/70` 因后接 `/` 不会匹配 `[\s"]`)
   - **bash / GNU grep 兜底**(Codex 若 Linux 环境):
     ```bash
     grep -rnE 'bg-\[var\(--color-concrete\)\]([[:space:]]|")' \
       web/src/routes/ChatPage.tsx \
       web/src/routes/chat/ChatHeader.tsx \
       web/src/routes/chat/ChatInputBar.tsx
     ```
     **期望**:**0 命中**
   - 若任一命令命中 ≥ 1 = K_30 跨段同步漏 → 应进入 R7.1 grep 兜底闭环,Codex 修补漏改

4. **改动文件范围严守(K_36 防范,R6.1 完工 report 实证)**:
   - `git diff --stat origin/main` 实证**只有 5 处改动**(v0.1.3 PM 决议 git mv 模式):
     - 4 TSX 改动:`web/src/routes/ChatPage.tsx` / `web/src/routes/chat/ChatHeader.tsx` / `web/src/routes/chat/ChatInputBar.tsx` / `web/src/routes/chat/MessageList.tsx`
     - 1 处任务卡 rename + 替换:`docs/tasks/task-403-chat-page-v0_3.md` → `docs/tasks/task-403-chat-page-v0_4.md`(git mv 保留意图;若 git 因相似度 < 30% 显示为 `delete` + `create` 两个 entries 也算正常,**只要文件命名匹配 v0.3 → v0.4 即可**)
   - 若 `git diff --stat` 列出**任何**范围外文件改动 → **停手报 PM,不许在 PR body / 完工 report 中省略**(决策 12 § R6.1)

5. **总改动行数阈值**(v0.1.2 R2 P0-1 修订 + v0.1.3 PM git mv 决议):**4 个 TSX 源码文件净改动 ≤ 30 行**(`ChatPage.tsx` / `ChatHeader.tsx` / `ChatInputBar.tsx` / `MessageList.tsx`,预估 6-15 行)。**任务卡 git mv 入仓**(`task-403-chat-page-v0_3.md` → `task-403-chat-page-v0_4.md`,**rename + 全替换 ~870 行**)**不计入该阈值**。若 4 TSX 文件净改 > 30 → 触发 § 自动升 R2 #5。Codex 验证命令:
   ```powershell
   git diff --stat origin/main -- web/src/routes/ChatPage.tsx web/src/routes/chat/ChatHeader.tsx web/src/routes/chat/ChatInputBar.tsx web/src/routes/chat/MessageList.tsx
   ```
   报告 4 个 TSX 文件的 `insertions + deletions` 总和

6. **完工三件套(决策 08)+ PR**(沿用 TASK-203 v0.4 PR 模式)

---

## 风险与注意点

### R1:scene z-index 与 chat 子组件 z-index 冲突
scene.css `.panorama-scene` 是 z-index: 0。本任 chat `<section>` 加 `relative z-10` 应足以覆盖。但子组件 ChatHeader / ChatInputBar / MessageList / MessageBubble 都没有显式 z-index,**全部 inherit 父级 z-context**。若 Stage 0 #8 实测 scene z-index ≠ 0(如 z-index: -1 之类)→ 本任设计需调整。

### R2:backdrop-blur 浏览器兼容性
Tailwind `backdrop-blur-md` 实现 `backdrop-filter: blur(12px)`。Safari 9+ / Chrome 76+ / Firefox 103+ 均支持;但 Firefox 103 之前需 `-webkit-` 前缀 — Tailwind 4 应自动加。若 PM 实测时浏览器(Edge / Chrome 现代版本)无问题 → 验收 PASS;若发现某用户浏览器看不到 blur → 退化到 `bg-concrete/85`(无 blur 不透明度)留 Task C2。

### R3:panorama.webp 加载失败时回退
PanoramaScene 已有 `onError → hidden`,失败时显示底层黑色(scene.css `background: #1b1d1b`)。**chat 内容仍可读**(黑底 + 半透 toolbar)。但若 webp 资源缺失,chat 页视觉劣化为"近似纯黑+toolbar"而非 PM 期望的"和解析页一样"。Stage 0 / PM 实测时若浏览器 Network 看到 `/assets/panorama.webp` 404 → 报 PM(资源问题,本任不修)。

### R4:dust canvas 性能开销
DustCanvas 已 prefers-reduced-motion 自动关闭。但若 PM 实测 chat 页 LLM 调用期间 / 长会话时感受卡顿 → 考虑 Task C2 调 DustCanvas opacity 或对 chat 页降低粒子数(本任不动,留 C2)。

### R5:与 OverviewPage 视差体验不一致
OverviewPage 有横向视差(`panoramaX` 跟随滚动),chat 页本任固定 `panoramaX={0}`(纵向滚 → 视差无意义)。**这是设计决策(D4),不是 bug**。若 R1 / PM 拍板"chat 页要视差" → 触发 § 自动升 R2 #3。

### R6:Header / Footer 半透 + backdrop-blur 与 MessageBubble 视觉冲突
ChatHeader / ChatInputBar 加 backdrop-blur 后,顶底 toolbar 类玻璃质感;MessageBubble user `/10` 几乎全透 / assistant `/70` 半透。若 PM 实测发现视觉风格断层(如顶底玻璃感 vs 中段实色卡片对比突兀)→ 留 Task C2 调和。

### R7:空态卡片 backdrop-blur 与 message bubble 风格一致性
空态卡片本任加 `bg-formwork/40 backdrop-blur-md`;MessageBubble assistant 是 `bg-formwork/70`(不带 blur)。**视觉差异:空态更透 + 模糊;assistant 实在**。这是有意设计差异(空态本身是"占位",不是实际内容,可以更虚化)。若 R1 / PM 要求一致 → D2.B 改 `/70`(无 blur 或加 blur)。

### R8:不动 MessageBubble 的隐含风险
前任 MessageBubble user `bg-black/10` 在原灰底上视觉为"深一点的黑灰";加 scene 后底色变 panorama → user bubble 在不同 scene 位置可能对比度变化(scene 暗处文字反白 vs scene 亮处文字深字)。**本任不动 MessageBubble** 是范围控制决策;若 PM 实测发现 user 气泡可读性下降 → 留 Task C2(可能要 `/40` + dark text 或调亮)。

### R9:H/F 顶层不动会议题
顶层 `<section>` 去掉 `bg-[var(--color-concrete)]` 后,如果 ChatHeader / ChatInputBar 加 backdrop-blur 但其间 StatusStrip / MessageList 是透明 → scene 在中段直接透出,文字与 scene 直接叠。这正是 D2 空态卡 backdrop-blur 的理由;MessageBubble 半透 + 高透明度本任不动 = 前任已 OK。

---

## Codex 提示

### 范围严守(K_36 强化 + R6.1 兑现)

- 只动 5 个文件:
  - `web/src/routes/ChatPage.tsx`
  - `web/src/routes/chat/ChatHeader.tsx`
  - `web/src/routes/chat/ChatInputBar.tsx`
  - `web/src/routes/chat/MessageList.tsx`
  - `docs/tasks/task-403-chat-page-v0_4.md`(本任卡入仓)
- **不动其他前端 .tsx / .ts / .css**(`MessageBubble.tsx` / `CitationCard.tsx` / `FollowUpChips.tsx` / `FallbackBanner.tsx` / `useChatSession.ts` / `useChatReducer.ts` / `useAutoScroll.ts` / `chatHelpers.ts` / `OverviewPage.tsx` / `UploadPage.tsx` / `PanoramaScene.tsx` / `UploadScene.tsx` / `DustCanvas.tsx` / `Layout.tsx` / `App.tsx` / `main.tsx` / `lib/*.ts` / `styles/*.css`)
- **不动后端 Python**(`features/` / `api/` / `core/` / `adapters/` / `app/`)
- **不动任何 docs**(除本任卡 docs/tasks/task-403-chat-page-v0_4.md;**默认不改** `docs/03_TASK_INDEX.md`,沿用 TASK-203 v0.4 / TASK-305 v0.2 模式 — PM 明确授权才改 TASK-403 行备注)
- **本任明确 git mv 覆盖 `task-403-chat-page-v0_3.md` → `task-403-chat-page-v0_4.md`**(v0.1.3 PM 决议,沿用决策 12 v0.2 → v0.3 入仓 git mv 模式;v0.3 不再保留,v0.4 是 TASK-403 唯一版本);**不动其他历史 task 卡**(task-401 / task-402 / task-201 / task-203 / task-305 等任一 → 停手报 PM)
- 任一额外文件改动 → **停手报 PM,不许半步对齐**(决策 12 § R6.1)

### 完工 report 工艺严守(决策 12 § R6.1)

- **完工 report 必须按 `git diff --stat origin/main` 实证列出全部改动文件**,不许凭记忆 / 凭 commit 列表 / 凭范围声明
- 若实际改动文件 ≠ 派单范围列出的 5 个 → **停手报 PM 解释为什么有范围外文件**;不许在 PR body / 完工 report 中省略
- commit 拆分要与文件作用域 1:1 对应

### Stage 0 必跑

- 10 项 Stage 0 全跑(详 § Stage 0 派单);任一 FAIL 停手报 PM
- 重点:#3-#6(确认 4 个改动文件当前 className 与本任伪代码 BEFORE 一致 — K_28a 防范)/ #7(确认 PanoramaScene 签名不变 — 升 R2 守门)/ #9(实测 npm scripts 真实命令名 — 反例 27 同源教训)

### 实施模式(沿用 TASK-403 v0.3 / TASK-203 v0.4)

- React + Tailwind 4,**不引入新依赖**
- Fragment 包裹模式(D5)沿用 OverviewPage 同款
- className 修改用编辑器或 Python 字节级(决策 08 第 2 条;**禁止** `sed -i` / `path.write_text`,沿用 TASK-101 教训)
- 单文件总行数 ≤ 300(04 § 4),所有 4 个改动文件本身就 ≤ 100 行,无超 300 风险

### 入仓操作(v0.1.3 PM git mv 决议,沿用决策 12 v0.2 → v0.3 入仓模式)

任务卡入仓走 `git mv` + 字节级全替换,保留 git log --follow 历史可追:

```powershell
Set-Location F:\mxa-tutor

# 1. git mv 重命名声明(让 git 记录 rename 意图)
git mv docs/tasks/task-403-chat-page-v0_3.md docs/tasks/task-403-chat-page-v0_4.md

# 2. 字节级写入 v0.4 内容(决策 08 第 2 条:read_bytes + write_bytes,不用 read_text / write_text)
# Codex 用编辑器或 Python 字节级写入,确保 LF/CRLF 行尾与项目仓库一致

# 3. 验证 git status 显示 renamed 或 deleted+new
git status
# 期望(任一形态正常):
#   - "renamed: docs/tasks/task-403-chat-page-v0_3.md -> docs/tasks/task-403-chat-page-v0_4.md"(git 识别 ≥ 30% 相似度)
#   - 或 "deleted: docs/tasks/task-403-chat-page-v0_3.md" + "new file: docs/tasks/task-403-chat-page-v0_4.md"(本任内容差异大,大概率此形态)
```

**关键**:无论 git status 显示哪种形态,Codex 完工 report 必须明示 "task-403 v0.3 → v0.4 入仓"(让 PM 知道 v0.3 已被覆盖,不再保留)。

### 完工三件套(决策 08)

- PR 标题:`TASK-403 v0.4: chat 页背景复用 PanoramaScene`
- PR 正文:对照 § 验收 1-6 逐条勾选;说明每条做了什么 + 真启动验收 #2 PM 实测数据 + **明示 task-403 v0.3 → v0.4 入仓覆盖**(v0.1.3 PM 决议)
- commit 拆 2-3:
  1. `feat(chat): reuse PanoramaScene as chat page background`(主交付:ChatPage.tsx 改动)
  2. `style(chat): make header / input bar / empty card translucent`(次:ChatHeader / ChatInputBar / MessageList className 改)
  3. `docs(tasks): rename task-403 v0.3 → v0.4 and replace content`(任务卡 git mv 覆盖,v0.1.3 PM 决议,沿用决策 12 v0.2 → v0.3 入仓模式)

---

## 关联文档 / 决策 / 反例

### 关联宪法
- 01 § 2 真实痛点(产品定位:中文教学产品 → UI 体验同样关键)
- 04 § 4(单文件 ≤ 300 行)
- 04 § 11 review 检查清单 § 教学输出(本任纯 UI 不涉及 LLM 输出,但视觉体验关联)

### 关联 Task
- **上游**:TASK-401 ✅(前端框架)/ TASK-402 ✅(UploadPage + OverviewPage 已用 scene)/ TASK-403 v0.3 ✅(chat 页主功能)
- **平行**:TASK-203 v0.4 ✅(本任前导,无关 chat 页)/ TASK-305 v0.2 ✅(yaml 中文化,无关)
- **下游**:Task C2 / C3 UI 后续整改(本任拆出留待)/ TASK-404 激活码 / TASK-405 部署 / TASK-406 内测

### 关联决策
- 决策 06(Codex 可读仓库文件)— Stage 0 实地核查
- 决策 07(03 索引更新边界)— 默认不改 03 索引
- 决策 08(完工三件套 + 字节级文件操作)
- 决策 09(架构师必须实地核查)— Stage 0 #3-#7 兑现
- 决策 12 v0.3.2 § 7.1(R 轮范围)— 本任主线 task 含 UI 用户可见性高,走完整 R 轮(GPT R1 起步)
- 决策 12 v0.3.2 § R7(精确事实校验)— Stage 0 10 项兑现
- 决策 12 v0.3.2 § R6.1(Codex 完工 report 实证)— § Codex 提示 + 验收 4 兑现
- 决策 12 v0.3.2 § R7.1(修订时 grep 全文兜底)— 架构师本任 v0.1 末尾 grep 验证(详 v0.1 末尾)
- 决策 12 v0.3.2 § 7.1.1(紧迫感预防)— 本任接手时 PM 实测发现 UI 问题,**未豁免 R 轮**,走正规 R1 工艺

### 关联反例
- 反例 18(审批级别 5 维评估)— § 审批级别兑现
- 反例 27 / 反例 28a(架构师无 repo 凭印象)— Stage 0 #9 npm scripts 实测兜底(避免凭印象写 `npm run typecheck`)
- 反例 30(跨段同步漏)— 本任 v0.1.x 修订须做全文跨段一致性扫描(本任接手时 K_30 累积 14)
- 反例 31(决策回避 / 软妥协)— D3 不动 MessageBubble 是有理由的明确决策,不是软妥协(尊重前任设计意图 + 范围控制)
- 反例 36(工程职责边界漏)— 本任接手时 K_36 = 2 触发独立阈值;Codex 完工时 R6.1 强制 `git diff --stat` 实证防漂移

---

## 自动升 R2 条件

若 Codex 实施期出现任一情况,**自动升 R2 — 停手报 PM,Claude 重起 GPT R2 一审**:

1. Stage 0 #3-#7 实测 main 真实代码与本任 BEFORE 伪代码不一致(已有 scene 引用 / 已 backdrop-blur / 已加透明度 / PanoramaScene 签名变 / scene.css z-index ≠ 0)— 设计变更
2. 需要新建 ChatScene 组件 / 修改 PanoramaScene 签名(D4 触发)
3. 需要引入 useParallaxBg(D4 / D6 触发)
4. 需要改 MessageBubble / CitationCard / FollowUpChips / FallbackBanner(D3 触发)
5. **4 个 TSX 源码文件净改 > 30 行**(`ChatPage.tsx` / `ChatHeader.tsx` / `ChatInputBar.tsx` / `MessageList.tsx`;`docs/tasks/task-403-chat-page-v0_4.md` 任务卡入仓**不计入**;范围红线,v0.1.2 R2 P0-1 修订)
6. 子组件 z-index 重设(scene z-context 冲突)
7. 需要改 scene.css 或新增 chat.css(本任明示不动)
8. 需要改后端 Python / API contract(本任纯前端)

---

## Checklist(精简)

**实施前**(Codex 第一棒):
- [ ] 读 5 核心文档(01 / 02 / 03 / 04 / 05)
- [ ] 读决策 06 / 07 / 08 / 09 / 11 / 12 v0.3.2
- [ ] 读 task-403-chat-page-v0_3.md(尤其 § 5 组件职责 / § 10 验收)
- [ ] 读 task-203-v0_4.md / task-305-v0_2.md(沿用 Stage 0 / Codex 提示模式)
- [ ] 跑 Stage 0 10 项,报告 PASS / FAIL + 异常细节

**实施中**:
- [ ] 只动 5 个文件(4 个 .tsx + 1 个 docs)
- [ ] ChatPage.tsx Fragment 包裹 + PanoramaScene 引用(D4 + D5)
- [ ] ChatHeader.tsx / ChatInputBar.tsx 半透 + backdrop-blur(D1)
- [ ] MessageList.tsx 空态卡片 backdrop-blur(D2)
- [ ] 字节级 / 编辑器改 className(决策 08 第 2 条)
- [ ] 4 个 .tsx 文件每个单文件 ≤ 300 行(全部 ≤ 100,无风险)
- [ ] 4 TSX 源码文件净改动 ≤ 30 行(任务卡入仓不计入;若超触发 § 自动升 R2 #5,v0.1.2 R2 P0-1 修订)

**完工前**:
- [ ] 验收 1-6 全过
- [ ] **真启动验收 #2 关键**:PM 实测视觉 + 业务无回归
- [ ] `git diff --stat origin/main` 实证 5 处改动严格匹配(4 TSX + 1 任务卡 rename,v0.1.3 PM git mv 决议)
- [ ] commit 拆 2-3
- [ ] commit subject 单行无 body(反例 17)
- [ ] PR 标题 + 正文按 § Codex 提示模板
- [ ] 完工三件套(决策 08)

---

## 本任接手时的反例账目(待 docs 补丁 chore 累积同步)

| 反例 | 前任末态(c4d8346) | v0.1 起稿末 | v0.1.1 R1 后 | v0.1.2 R2 后 | v0.1.3 PM 决议后 | 备注 |
|---|---|---|---|---|---|---|
| K_28a 经典(架构师无 repo 凭印象) | 27 | 28 | 31 | 32 | 32(沿用)| (a) **接手编号自抓 +1**:看到"Task C UI 整改"代号 + 前任交接 § 5.1 文字描述,**凭印象当作新功能,直接编号 TASK-407**,未 view 03 索引 line 245 把"问答页"映射回 TASK-403 编号体系;PM 一句话守门救场<br>(b) **v0.1.1 GPT R1 抓 P0-2 +1**:Stage 0 #1 用 `cd F:\mxa-tutor && git log -1 --oneline`,凭印象用 `&&` — 实际 PowerShell 5.1 不支持<br>(c) **v0.1.1 GPT R1 抓 P1-1 +1**:Stage 0 #3 用 `Get-Content ... -Raw` + "报告全文行号" — 凭"标准 PowerShell 用法"印象<br>(d) **v0.1.2 GPT R2 抓 P0-2 +1**:Stage 0 #3b `Select-String -SimpleMatch` 配反斜杠转义字面 = 0 命中误升 R2;凭"`-SimpleMatch` = 字面匹配应接 regex 转义"印象 |
| K_28b(架构师起稿粒度问题)| 3 | 3 | 3 | 3 | **4** | **v0.1.3 PM 决议自抓 +1**:v0.1 起稿 § 范围 #5 写"任务卡入仓:docs/tasks/task-403-chat-page-v0_4.md"粒度过粗,**未主动提议入仓模式决策点供 PM 拍板**(git mv 覆盖 v0.3 保留历史 vs create_file 并存);PM 主动救场点出"让 codex 覆盖吧,它也好知道 task403 发生了什么变化" → 升 v0.1.3 PM 决议补丁;**根因**:架构师沿用 task-203 v0.4 / task-305 v0.2 入仓默认 create 模式(那两份没有同名旧任务卡 v0.x 需要覆盖),**未识别 TASK-403 已有 v0.3 实体卡的特殊情况**(交接 § 1 line 35 明示"task-403 实体卡只剩 task-403-chat-page-v0_3.md" — 架构师 v0.1 起稿时未连接此前置约束 = 跨段同步漏微反例,沿用 K_28a 同源 — 也可记 K_30,但主类 K_28b 更精确:**架构师起稿粒度未明示入仓模式决策点**);沿用决策 12 v0.2 → v0.3 入仓 git mv 模式范本(架构师起稿时未参考此先例) |
| K_30(跨段同步漏) | 14 | 14 | 17 | 20 | 20(沿用)| (a-g) 详 v0.1.2 R2 后累积条目 |
| K_31(协议自反 / 决策回避) | 2 | 2 | 2 | 2 | 2(沿用)| 前任记 |
| K_34(语义记忆错位)| 6 | 6 | 6 | 6 | 6(沿用)| 前任记 |
| K_36(工程职责边界漏)| 2 | 2 | 3 | 4 | 4(沿用)| (a) **v0.1.1 GPT R1 抓 P1-4 +1**:验收 #2 未强制触发 StatusStrip 状态<br>(b) **v0.1.2 GPT R2 抓 P0-1 边界口径自抓 +1**:"30 行阈值"语义模糊 + 任务卡入仓边界 |
| **PM 救场架构师** | 1 | 2 | 2 | 2 | **3** | **v0.1.3 PM 主动救场 +1,本任接手第三次,项目第三次** — PM 一句话"让 codex 覆盖吧,它也好知道 task403 发生了什么变化" 主动救场架构师 v0.1 起稿粒度漏明示入仓模式(K_28b 同源);前任阶段 1 + 本任 2 = 3 次,**继续触发独立阈值 ≥ 2**(决策 12 v0.4 升仪时累积)|
| Codex 守门救场 | 8 | 8 | 8 | 8 | 8(沿用)| 待本任 Codex 实施触发 |

**v0.1.1 R1 后累积**:K_28a 28 → **31**(+3)/ K_30 14 → **17**(+3)/ K_36 2 → **3**(+1)/ K 总 53 → **57**(+4)
**v0.1.2 R2 后累积**:K_28a 31 → **32**(+1)/ K_30 17 → **20**(+3)/ K_36 3 → **4**(+1)/ K 总 57 → **62**(+5)

**v0.1.2 R7.1 工艺纪律深化教训**(可纳入决策 12 v0.4 候选):
- **R7.1 grep 字面**起稿前必须先用**宽字面**(如根字符)grep 整篇文档看命中分布,再去拟定指令性残留判定字面(反例 5/25/30 同源延伸)
- 字面**太精确**(如 `cd F:\mxa-tutor &&` 直接接)= 漏抓同源变体(如 `cd F:\mxa-tutor\web &&` 中间多 `\web`)
- 沿用"K_30 KPI"+ "反例 25 KPI" 双重叠加:任何 grep 字面必须先在 outputs 本地实测过命中分布,再下笔写"应空 vs 应保留"判定

---

## R7.1 grep 兜底(架构师 v0.1.2 末尾自验,决策 12 v0.3.2 § R7.1 + v0.1.2 工艺纪律深化)

v0.1.2 修订完成后,架构师跑 grep 扫旧字面 / 命名残留 / 跨段一致性(v0.1.2 R2 P1-1 修订后**扩字面**,沿用"先宽字面后窄判定"工艺):

| Grep 字面 | 期望 | 备注 |
|---|---|---|
| `TASK-407` | **空**(指令性);仅反例账目段 / R7.1 grep 表 / R1/R2 拍板结论描述性引用允许保留 | 若指令性命中 = K_30 跨段同步漏 |
| `Task C1` / `C1` | 仅描述性引用允许保留(反例账目段 + R7.1 grep 表)| 同上 |
| **`&&` 宽字面**(v0.1.2 R2 P1-1 扩) | **任何 shell command chain 形式应空**(如 `&& npm` / `&& git` / `cd \|...\| && ...`);仅描述性引用允许保留(反例账目 / R1 R2 拍板结论描述 GPT 抓的问题 / Codex 提示"不用 `&&`"明示)| 字面太精确漏抓同源教训(P0-3 / P1-1 根因)|
| `cd F:\mxa-tutor` + `&&` 任意接续(扩 P1-1)| **指令性段应空**;若任一可执行命令段含此组合 = K_30 漏改 | 工艺纪律深化:不只查 `cd F:\mxa-tutor &&` 窄字面 |
| `Get-Content .* -Raw` | **指令性段应空**(P1-1 修订已删 -Raw);仅描述性引用允许保留 | 命中 ≥ 1 指令性 = K_30 漏改 |
| `\\\|` (markdown 表格转义管道)| **指令性段应空**(Stage 0 / 验收命令应在 fenced code block 用真实 `\|`);仅描述性引用允许保留 | 命中 ≥ 1 指令性 = 残留漏改 |
| `必含 7 个段` | **空**(本任卡内不应出现;r1-prompt 文件 R1 已完成不返工) | 命中 ≥ 1 = K_30 漏清 |
| `bg-\[var\(--color-concrete\)\]\b` 旧字面 | **已废除**(P1-3 修订);若仍命中 = R7.1 残留 | 验收 #3 已改新字面 |
| `7 条全采纳` | **空**(v0.1.2 P2-1 已改"5 落地 + 2 归档")| 命中 ≥ 1 = K_30 漏改 |
| `Pattern.*-SimpleMatch` 配反斜杠转义 | **指令性段应空**(P0-2 修订:`-SimpleMatch` 配字面无反斜杠);仅描述性引用允许保留 | 命中 ≥ 1 指令性 = K_30 漏改 |
| `create mode` (v0.1.3 PM git mv 决议后应清除)| **指令性段应空**(v0.1.3 PM 决议入仓用 `git mv` rename + 替换,**非 create**);仅描述性引用 / git status 输出描述允许保留 | 命中 ≥ 1 指令性 = v0.1.2 → v0.1.3 跨段同步漏 |
| `不动 task-403 v0.2.2.1 / v0.3 旧卡` | **空**(v0.1.3 PM 决议改 git mv 覆盖,旧 § Codex 提示语已删)| 命中 ≥ 1 = K_30 v0.1.2 → v0.1.3 漏改 |
| `git mv` (v0.1.3 PM 决议新增指令)| 应在 § 范围 #5 / § Codex 提示入仓操作 / § 验收 #4 / commit 拆 #3 / 派单结论 / 末尾审批历史 等多处贯穿 | v0.1.3 PM 决议正确落地标志 |
| `TASK-403 v0.4` | 应**贯穿全文**(标题 / commit 拆 / PR title / 验收 / 关联 Task 等) | 命名一致性 |

架构师执行 grep 结果(待 PM 在仓库内 / 工作区跑):本任卡内部一致性 PM 可视觉扫(本任卡篇幅 ~ 905 行)。

---

**版本**:v0.1.3(2026-06-13 PM git mv 入仓决议补丁)
**作者**:Claude(架构师,后端第三十五任)
**关联宪法版本**:v2.1(冻结,不修改)
**前置 commit**:`c4d8346`(TASK-203 v0.4 + chore #84 squash merge,2026-06-13)— Stage 0 #1 兜底实测期望 HEAD = `c4d8346`;若漂移停手报 PM
**审批历史**:
- v0.1 起稿(2026-06-13 后端第三十五任)— 待 GPT R1 一审
- v0.1.1(2026-06-13)— GPT R1 conditional pass(2 P0 + 4 P1 + 1 P2 = 7 条;**5 条直接落地本任卡 + 2 条归档为派单工艺反思**;不升 R2);Claude 反审 GPT R1 **无 challenge 项**;**K_28a +3 / K_30 +3 / K_36 +1 自抓**;**v0.1.1 强制工艺改进**:Stage 0 命令 fenced code block + PowerShell 5.1 兼容 + 验收 grep 限定 3 源码文件 + 验收 #2 加 StatusStrip 强制触发 + DevTools computed style 兜底
- v0.1.2(2026-06-13)— GPT R2 conditional fail(3 P0 + 1 P1 + 1 P2 = 5 条**全部直接落地**;**不升 R3**);Claude 反审 GPT R2 **无 challenge 项**;**K_28a +1 / K_30 +3 / K_36 +1 自抓**;**v0.1.2 强制工艺改进**:(a) "30 行阈值"明示限定 4 TSX 源码文件(任务卡入仓不计入)(b) Stage 0 #3b `-SimpleMatch` 改字面无反斜杠 (c) 验收 #1 改 `$LASTEXITCODE` chain PowerShell 5.1 兼容 (d) R7.1 grep 兜底扩字面 + 沉淀"先宽字面后窄判定"工艺纪律(决策 12 v0.4 候选)(e) "7 条全采纳" → "5 落地 + 2 归档"措辞精修
- v0.1.3(2026-06-13)— PM 主动决策:**task-403 v0.3 → v0.4 走 `git mv` 覆盖**(沿用决策 12 v0.2 → v0.3 入仓 git mv 模式),保留 git history 让 Codex 能追溯 task-403 演进;v0.3 不再保留,v0.4 是 TASK-403 唯一版本;**架构师 K_28b 微反例自抓 +1**(v0.1 起稿粒度漏明示入仓模式 — 应在 v0.1 § 范围 #5 起稿时主动提议 git mv vs create_file 决策点供 PM 拍板,而不是凭印象写"任务卡入仓"模糊措辞);**v0.1.3 强制工艺改进**:(a) 范围 #5 / Codex 提示 / 验收 #4 / 验收 #5 / commit 拆 #3 五处明示 git mv 模式 (b) R7.1 grep 兜底加 `create mode` / `不动 task-403 旧卡` / `git mv` 三项验证字面 (c) "不动 task-403 v0.2.2.1 / v0.3 旧卡" 旧 Codex 提示语删除(本任明确动 v0.3)
**审批级别**:**GPT R1 + R2 双轮已通过 + v0.1.3 PM 决议补丁;不升 R3**;Codex 实施期任一 8 条触发自动升 R2(详 § 自动升 R2 条件)