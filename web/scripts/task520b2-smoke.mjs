import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  anchorRegistry: "src/routes/paper/anchorRegistry.ts",
  equationList: "src/routes/paper/EquationList.tsx",
  packageJson: "package.json",
  paperAnchors: "src/routes/paper/paperAnchors.ts",
  paperCss: "src/styles/paper.css",
  paperTypes: "src/lib/paperTypes.ts",
};

for (const file of Object.values(files)) {
  if (!existsSync(join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const sources = Object.fromEntries(
  Object.entries(files).map(([key, file]) => [key, readFileSync(join(root, file), "utf8")]),
);

function assertIncludes(source, text, message) {
  if (!source.includes(text)) {
    throw new Error(message);
  }
}

function assertRegex(source, regex, message) {
  if (!regex.test(source)) {
    throw new Error(message);
  }
}

function assertNotRegex(source, regex, message) {
  if (regex.test(source)) {
    throw new Error(message);
  }
}

function countMatches(source, regex) {
  return source.match(regex)?.length ?? 0;
}

function exportedFunctionBlock(source, name) {
  const match = source.match(new RegExp(`export function\\s+${name}\\b[\\s\\S]*?^}`, "m"));
  if (!match) {
    throw new Error(`Missing exported function block: ${name}`);
  }
  return match[0];
}

const anchorRegistry = sources.anchorRegistry;
const anchorIdBlock = exportedFunctionBlock(anchorRegistry, "resolveCitationTargetAnchorId");
const elementBlock = exportedFunctionBlock(anchorRegistry, "resolveCitationTargetElement");
const scrollBlock = exportedFunctionBlock(anchorRegistry, "scrollToCitationTarget");

for (const exportedName of [
  "resolveCitationTargetAnchorId",
  "resolveCitationTargetElement",
  "scrollToCitationTarget",
]) {
  assertIncludes(anchorRegistry, `export function ${exportedName}`, `AnchorRegistry must export ${exportedName}`);
}

assertIncludes(sources.paperTypes, "export type PaperCitationTarget", "paperTypes must export PaperCitationTarget");
for (const typeName of [
  "SectionTarget",
  "EquationTarget",
  "PlanMappingParameterTarget",
  "MissingPromptParameterTarget",
]) {
  assertIncludes(sources.paperTypes, `export interface ${typeName}`, `Missing target type: ${typeName}`);
}
for (const literal of [
  'kind: "section"',
  'result_section:',
  '"paper-summary"',
  '"paper-subsystems"',
  '"paper-build-steps"',
  '"paper-parameters"',
  '"paper-tuning"',
  'kind: "equation"',
  "equation_id: string",
  'origin: "plan_mapping"',
  "row_index: number",
  "paper_param_name: string",
  "model_param_name: string",
  'origin: "missing_prompt"',
  "prompt_id: string",
  "parameter_name: string",
]) {
  assertIncludes(sources.paperTypes, literal, `PaperCitationTarget must mirror 520-A §3 literal: ${literal}`);
}
assertNotRegex(sources.paperTypes, /paper-equations/, "paper-equations must not be a SectionTarget result_section");

assertIncludes(
  elementBlock,
  "document.getElementById(resolveCitationTargetAnchorId(target))",
  "DOM resolution must go through getElementById(resolveCitationTargetAnchorId(target))",
);
if (countMatches(anchorRegistry, /document\.getElementById/g) !== 1) {
  throw new Error("AnchorRegistry must have exactly one DOM id lookup");
}
assertNotRegex(anchorRegistry, /querySelector(All)?\s*\(/, "AnchorRegistry must not use querySelector");
assertNotRegex(anchorRegistry, /location\.hash|window\.location/, "AnchorRegistry must not mutate or inspect location");
assertNotRegex(anchorRegistry, /\bfuzzy\b/i, "AnchorRegistry must not add fuzzy matching");
assertNotRegex(
  anchorRegistry,
  /(resolveCitationTargetElement\s*\([^)]*\)|getElementById\s*\([^)]*\))\s*!/,
  "AnchorRegistry must not non-null assert resolver or getElementById results",
);
assertNotRegex(anchorRegistry, /console\./, "AnchorRegistry must not add runtime console output");

assertIncludes(anchorIdBlock, "return target.result_section;", "Section target must resolve to result_section");
assertIncludes(anchorIdBlock, "`paper-eq-${target.equation_id}`", "Equation target must resolve to paper-eq-{equation_id}");
assertIncludes(sources.equationList, "paper-eq-${equation.equation_id}", "EquationList must still use paper-eq-{equation_id}");
assertIncludes(anchorRegistry, 'from "./paperAnchors"', "AnchorRegistry must import paperAnchors helpers");
assertIncludes(anchorIdBlock, "makePlanMappingAnchorId(", "Plan mapping target must use makePlanMappingAnchorId");
assertIncludes(anchorIdBlock, "target.row_index", "Plan mapping target must pass row_index");
assertIncludes(anchorIdBlock, "target.paper_param_name", "Plan mapping target must pass paper_param_name to the helper");
assertIncludes(anchorIdBlock, "target.model_param_name", "Plan mapping target must pass model_param_name to the helper");
assertIncludes(anchorIdBlock, "makeMissingPromptAnchorId(target.prompt_id)", "Missing prompt target must use makeMissingPromptAnchorId");
assertNotRegex(anchorRegistry, /hashCodePoints|Math\.imul|toString\(36\)/, "AnchorRegistry must not reimplement paperAnchors hashing");

const allowedParameterHelperCall =
  /makePlanMappingAnchorId\(\s*target\.row_index,\s*target\.paper_param_name,\s*target\.model_param_name,\s*\)/;
if (!allowedParameterHelperCall.test(anchorIdBlock)) {
  throw new Error("paper_param_name/model_param_name must appear only as makePlanMappingAnchorId arguments");
}
const anchorIdWithoutAllowedHelper = anchorIdBlock.replace(allowedParameterHelperCall, "");
assertNotRegex(
  anchorIdWithoutAllowedHelper,
  /paper_param_name|model_param_name/,
  "Parameter names must not be used for selector or fuzzy lookup",
);

const nullReturnIndex = scrollBlock.indexOf("if (el === null)");
const scrollIntoViewIndex = scrollBlock.indexOf("scrollIntoView");
if (nullReturnIndex === -1 || scrollIntoViewIndex === -1 || nullReturnIndex > scrollIntoViewIndex) {
  throw new Error("scrollToCitationTarget must return null before scrollIntoView when the element is unresolved");
}
assertIncludes(scrollBlock, "return null;", "scrollToCitationTarget must return null for unresolved targets");
assertIncludes(
  scrollBlock,
  'closest<HTMLElement>(".paper-equation-item, .paper-param-row, .paper-section")',
  "scrollToCitationTarget must closest<HTMLElement> to the visible row/section",
);
const clearIndex = scrollBlock.indexOf("clearCurrentHighlight();");
const highlightIndex = scrollBlock.indexOf("applyAnchorHighlight(visibleTarget)");
if (clearIndex === -1 || clearIndex > scrollIntoViewIndex) {
  throw new Error("scrollToCitationTarget must clear the previous highlight before scrolling");
}
if (highlightIndex === -1 || highlightIndex < scrollIntoViewIndex) {
  throw new Error("scrollToCitationTarget must apply the transient highlight after scrolling");
}
assertIncludes(anchorRegistry, "clearCurrentHighlight();", "AnchorRegistry must clear the previous highlight");
assertIncludes(anchorRegistry, "void target.offsetWidth;", "AnchorRegistry must retrigger highlight on repeated clicks");
assertIncludes(anchorRegistry, "paper-anchor-highlight", "AnchorRegistry must use the transient highlight class");

assertRegex(
  sources.paperCss,
  /\.paper-equation-item,\.paper-param-row\{scroll-margin-top:36px;\}/,
  "Equation and parameter targets need desktop scroll-margin-top:36px",
);
const mobileMarginMatch = sources.paperCss.match(
  /@media \(max-width:980px\)\{[\s\S]*?\.paper-equation-item,\.paper-param-row\{scroll-margin-top:(\d+)px;\}/,
);
if (!mobileMarginMatch) {
  throw new Error("Equation and parameter targets need mobile scroll-margin-top inside max-width:980px media");
}
if (Number(mobileMarginMatch[1]) <= 36) {
  throw new Error("Mobile scroll-margin-top must be larger than the desktop 36px baseline");
}
assertRegex(
  sources.paperCss,
  /\.paper-anchor-highlight\{[^}]*border-radius:0;[^}]*animation:paper-anchor-highlight-pulse/,
  "Highlight class must use border-radius:0 and the transient pulse animation",
);
assertIncludes(sources.paperCss, "var(--color-signal)", "Highlight CSS must use --color-signal");
assertIncludes(sources.paperCss, "@media (prefers-reduced-motion:reduce)", "Highlight CSS needs reduced-motion handling");

const packageJson = JSON.parse(sources.packageJson);
if (packageJson.scripts?.["smoke:task520b2"] !== "node scripts/task520b2-smoke.mjs") {
  throw new Error("package.json must expose smoke:task520b2");
}

assertIncludes(sources.paperAnchors, "paper-param-map-${rowIndex}-${hash}", "Mapping helper shape must remain public");
assertIncludes(sources.paperAnchors, "paper-param-missing-${promptId}", "Missing prompt helper shape must remain public");

console.log("TASK-520-B2 smoke passed");
