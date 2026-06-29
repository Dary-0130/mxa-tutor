import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  buildSteps: "src/routes/paper/BuildSteps.tsx",
  equationList: "src/routes/paper/EquationList.tsx",
  packageJson: "package.json",
  parameterTable: "src/routes/paper/ParameterTable.tsx",
  paperAnchors: "src/routes/paper/paperAnchors.ts",
  paperCss: "src/styles/paper.css",
  paperEvidence: "src/lib/paperEvidence.ts",
  paperResultPage: "src/routes/PaperResultPage.tsx",
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

assertIncludes(sources.paperResultPage, "paper-equations", "PaperResultPage must render paper-equations section");
assertIncludes(sources.paperResultPage, "EquationList", "PaperResultPage must use EquationList");
assertIncludes(sources.paperResultPage, "includeEquations", "SectionNav must be gated with the equation section");
assertIncludes(sources.paperResultPage, "latex_or_text.trim() !== \"\"", "Equation filtering must trim only for emptiness");

assertIncludes(sources.equationList, "paper-eq-${equation.equation_id}", "EquationList must use paper-eq-{equation_id}");
assertIncludes(sources.equationList, "equation.latex_or_text", "EquationList must render original latex_or_text");
if (/dangerouslySetInnerHTML/.test(sources.equationList)) {
  throw new Error("EquationList must not use dangerouslySetInnerHTML");
}

for (const cssClass of [
  ".paper-equation-list",
  ".paper-equation-item",
  ".paper-equation-body",
  ".paper-equation-id",
]) {
  assertIncludes(sources.paperCss, cssClass, `Missing equation CSS class: ${cssClass}`);
}
if (!/\.paper-equation-body\{[^}]*white-space:pre-wrap/.test(sources.paperCss)) {
  throw new Error("Equation body must preserve whitespace with pre-wrap");
}
if (!/\.paper-equation-body\{[^}]*font:800 \.94rem var\(--font-mono\)/.test(sources.paperCss)) {
  throw new Error("Equation body must use the mono font");
}
if (!/\.paper-equation-body\{[^}]*overflow-wrap:anywhere/.test(sources.paperCss)) {
  throw new Error("Equation body must wrap dirty or long formula text");
}

assertIncludes(sources.paperAnchors, "paper-param-map-${rowIndex}-${hash}", "Mapping anchor shape must stay public");
assertIncludes(sources.paperAnchors, "paper-param-missing-${promptId}", "Missing prompt anchor shape must stay public");
assertIncludes(sources.paperAnchors, "codePointAt(0)", "Mapping hash must iterate code points");
assertIncludes(sources.paperAnchors, "Math.imul(hash, 0x01000193)", "Mapping hash must use FNV-1a 32-bit multiplication");
assertIncludes(sources.paperAnchors, "hash.toString(36)", "Mapping hash must be base36 DOM-id-safe text");
assertIncludes(sources.paperAnchors, "`${paperParamName}|${modelParamName}`", "Mapping hash input must be paper|model");

assertIncludes(sources.parameterTable, "from \"./paperAnchors\"", "ParameterTable must import paperAnchors helpers");
assertIncludes(sources.parameterTable, "mappingIndex?: number", "ParameterRow must carry mappingIndex");
assertIncludes(sources.parameterTable, "mappingIndex: index", "mergeRows must preserve the mapping row index");
assertIncludes(sources.parameterTable, "makePlanMappingAnchorId(", "Mapping anchors must use the shared helper");
assertIncludes(sources.parameterTable, "makeMissingPromptAnchorId(", "Missing prompt anchors must use the shared helper");
assertIncludes(sources.parameterTable, "id={rowAnchorId}", "Parameter row must receive the computed anchor id");
assertIncludes(sources.parameterTable, "paper-anchor-stub", "Merged mapping+prompt rows need a zero-layout prompt anchor");
if (/paper-param-map-undefined/.test(sources.parameterTable) || /paper-param-map-undefined/.test(sources.paperAnchors)) {
  throw new Error("Mapping anchors must never bake undefined into the id");
}

for (const [label, source] of [
  ["PaperResultPage", sources.paperResultPage],
  ["EquationList", sources.equationList],
  ["ParameterTable", sources.parameterTable],
]) {
  for (const forbidden of ["scrollIntoView", "location.hash", "window.location", "AnchorRegistry"]) {
    if (source.includes(forbidden)) {
      throw new Error(`${label} must not introduce B2 navigation behavior: ${forbidden}`);
    }
  }
}

const packageJson = JSON.parse(sources.packageJson);
const allDeps = { ...(packageJson.dependencies ?? {}), ...(packageJson.devDependencies ?? {}) };
for (const dep of ["katex", "mathjax", "mathjax-full", "react-katex", "better-react-mathjax"]) {
  if (Object.hasOwn(allDeps, dep)) {
    throw new Error(`Task 520 B1 must not add a math rendering dependency: ${dep}`);
  }
}

for (const [label, source] of [
  ["BuildSteps", sources.buildSteps],
  ["ParameterTable", sources.parameterTable],
]) {
  if (/\bfunction\s+formatEvidence\b/.test(source) || /\bconst\s+formatEvidence\b/.test(source)) {
    throw new Error(`${label} must not keep a local formatEvidence copy`);
  }
  assertIncludes(source, "from \"../../lib/paperEvidence\"", `${label} must import shared paperEvidence`);
}
assertIncludes(sources.paperEvidence, "emptyText = \"\"", "paperEvidence default emptyText must stay empty");
assertIncludes(
  sources.parameterTable,
  "formatEvidence(prompt.paper_reference, { emptyText: \"依据:未标注\" })",
  "ParameterTable must preserve missing evidence text",
);
assertIncludes(
  sources.parameterTable,
  "formatEvidence(entry, { emptyText: \"依据:未标注\" })",
  "ParameterTable must preserve plan evidence empty text",
);

console.log("TASK-520-B1 smoke passed");
