import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(path) {
  return readFileSync(join(root, path), "utf8");
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const paperApi = read("src/lib/paperApi.ts");
const buildSteps = read("src/routes/paper/BuildSteps.tsx");
const resultPage = read("src/routes/PaperResultPage.tsx");
const usePaperResult = read("src/routes/paper/usePaperResult.ts");
const errors = read("src/lib/errorMessages.ts");
const css = read("src/styles/paper.css");

assert(
  paperApi.includes('paperPath(paperId, "/regenerate-steps")'),
  "paper API must expose regenerate-steps endpoint",
);
assert(
  paperApi.includes("apiPost<UpdatedPlanResponse>") && paperApi.includes(", {})"),
  "regenerate-steps request body must be empty",
);
assert(buildSteps.includes("重新生成步骤"), "fallback view must show approved button copy");
assert(buildSteps.includes("生成中…"), "fallback view must show neutral loading copy");
assert(
  usePaperResult.includes("暂未生成完整步骤,可稍后重试"),
  "fail-closed neutral notice must be present",
);
assert(
  resultPage.includes("paper-interaction-lock"),
  "result page must lock interaction while regenerating",
);
assert(
  resultPage.includes("hasRegenerationWork") &&
    resultPage.includes("structuredSteps == null") &&
    resultPage.includes("guidanceStatusRequiresRegeneration(data.plan.guidance_status)") &&
    resultPage.includes('"generation_failed"') &&
    resultPage.includes('"not_generated"') &&
    resultPage.includes('"stale_pending_regeneration"') &&
    !resultPage.includes("data.plan.m_script_skeleton === null") &&
    !resultPage.includes("data.parameterCorrections.length > 0"),
  "regenerate button predicate must use structured build steps and recoverable guidance statuses",
);
assert(
  resultPage.includes("这是 AI 生成的搭建建议,仅供参考"),
  "build steps section must show the fixed AI guidance banner",
);
assert(
  errors.includes("regenerate_lock_conflict") && errors.includes("regenerate_store_failed"),
  "regenerate error messages must have visible copy",
);

for (const source of [buildSteps, resultPage, usePaperResult]) {
  assert(!/console\.(log|error|warn|info)/.test(source), "regeneration UI must not log details");
}

for (const forbidden of ["AI 重新生成", "基于当前参数重新推导", "可能与之前不同"]) {
  assert(!buildSteps.includes(forbidden), `forbidden regeneration wording: ${forbidden}`);
}

function shouldShowRegenerateButton(plan) {
  const structuredSteps =
    Array.isArray(plan.build_steps) && plan.build_steps.length > 0 ? plan.build_steps : null;
  const guidanceStatusRequiresRegeneration =
    plan.guidance_status === "not_generated" ||
    plan.guidance_status === "stale_pending_regeneration" ||
    plan.guidance_status === "generation_failed";
  return structuredSteps == null || guidanceStatusRequiresRegeneration;
}

assert(
  shouldShowRegenerateButton({
    build_steps: null,
    m_script_skeleton: "clear; clc;",
    guidance_status: "generated",
    parameterCorrections: [{ correction_id: "CORR-1" }],
  }),
  "corrected plan with suppressed build_steps must show regenerate button",
);
assert(
  shouldShowRegenerateButton({
    build_steps: null,
    m_script_skeleton: null,
    guidance_status: "generated",
  }),
  "suppressed build_steps must show regenerate button even when m_script is null",
);
assert(
  !shouldShowRegenerateButton({
    build_steps: [{ step_id: "STEP-001" }],
    m_script_skeleton: "clear; clc;",
    guidance_status: "generated",
    parameterCorrections: [{ correction_id: "CORR-1" }],
  }),
  "complete regenerated plan must hide button even when an active correction remains",
);
assert(
  !shouldShowRegenerateButton({
    build_steps: [{ step_id: "STEP-001" }],
    m_script_skeleton: null,
    guidance_status: "generated",
  }),
  "complete build steps must hide regenerate button even when m_script is null",
);
assert(
  shouldShowRegenerateButton({
    build_steps: [{ step_id: "STEP-001" }],
    m_script_skeleton: "clear; clc;",
    guidance_status: "generation_failed",
  }),
  "complete build steps with failed guidance must show regenerate button",
);
assert(
  !shouldShowRegenerateButton({
    build_steps: [{ step_id: "STEP-001" }],
    m_script_skeleton: "clear; clc;",
    guidance_status: "generated",
    guidance_basis: "document_claim_unverified",
  }),
  "generated unverified guidance must not show regenerate button",
);

for (const cssClass of [
  ".paper-regenerate-steps-button",
  ".paper-regenerate-steps-notice",
  ".paper-interaction-lock",
  ".paper-button-spinner",
  ".paper-guidance-honesty-banner",
]) {
  assert(css.includes(cssClass), `missing CSS class: ${cssClass}`);
}

console.log("task522d1 smoke passed");
