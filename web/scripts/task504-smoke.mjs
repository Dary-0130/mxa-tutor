import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  sourceBadge: "src/routes/paper/SourceBadge.tsx",
  parameterTable: "src/routes/paper/ParameterTable.tsx",
  tuningPanel: "src/routes/paper/TuningPanel.tsx",
  useUserSupply: "src/routes/paper/useUserSupply.ts",
  paperCss: "src/styles/paper.css",
};

for (const file of Object.values(files)) {
  if (!existsSync(join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const sourceBadge = readFileSync(join(root, files.sourceBadge), "utf8");
for (const label of ["论文提取", "用户补充", "待补充"]) {
  if (!sourceBadge.includes(label)) {
    throw new Error(`Missing source badge label: ${label}`);
  }
}
const parameterTable = readFileSync(join(root, files.parameterTable), "utf8");
if (!parameterTable.includes('row.kind === "missing" && !row.user_supplied_value')) {
  throw new Error("Missing unresolved prompt three-state guard");
}
for (const text of ["可填入数值,亦可留空", "各参数已标注来源。缺失参数可选填,留空不影响其余建模步骤。"]) {
  if (!parameterTable.includes(text)) {
    throw new Error(`Missing parameter table text: ${text}`);
  }
}
if (parameterTable.includes("mapping.paper_reference") || parameterTable.includes("mapping?.paper_reference")) {
  throw new Error("Parameter mapping rows must not render per-parameter evidence");
}
if (!parameterTable.includes("prompt.paper_reference")) {
  throw new Error("Missing prompt evidence rendering");
}

const tuningPanel = readFileSync(join(root, files.tuningPanel), "utf8");
for (const label of ["增大", "减小", "区间内调整"]) {
  if (!tuningPanel.includes(label)) {
    throw new Error(`Missing tuning direction label: ${label}`);
  }
}
const directionBlock = tuningPanel.slice(
  tuningPanel.indexOf("const DIRECTION_LABELS"),
  tuningPanel.indexOf("const CONFIDENCE_LABELS"),
);
if (/[0-9]+|%|倍|±|~|～/.test(directionBlock)) {
  throw new Error("Tuning direction labels must not add numeric guidance");
}
const mockRenderedTuningText = [
  "仅给出调整方向,不提供具体数值。",
  "增大",
  "减小",
  "区间内调整",
  "磁链响应更平稳",
  "预期影响",
  "置信度:",
  "高",
  "需在 MATLAB 中验证",
].join("");
if (/[0-9]+|%|倍|±|~|～/.test(mockRenderedTuningText)) {
  throw new Error("Mock numeric-free tuning render unexpectedly contains numeric guidance");
}

const useUserSupply = readFileSync(join(root, files.useUserSupply), "utf8");
const postIndex = useUserSupply.indexOf("postUserSupply");
const getIndex = useUserSupply.indexOf("getPaperPlan", postIndex);
if (postIndex === -1 || getIndex === -1 || getIndex < postIndex) {
  throw new Error("User supply flow must POST before refreshing GET /plan");
}

const paperCss = readFileSync(join(root, files.paperCss), "utf8");
if (!/\.paper-copy\{[^}]*color:\s*var\(--color-ite\)/.test(paperCss)) {
  throw new Error("Missing readable paper copy style");
}

console.log("TASK-504 smoke passed");
