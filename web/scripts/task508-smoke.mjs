import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  buildSteps: "src/routes/paper/BuildSteps.tsx",
  paperCss: "src/styles/paper.css",
};

for (const file of Object.values(files)) {
  if (!existsSync(join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const buildSteps = readFileSync(join(root, files.buildSteps), "utf8");
const paperCss = readFileSync(join(root, files.paperCss), "utf8");

const structuredGate =
  "const structuredSteps = Array.isArray(plan.build_steps) && plan.build_steps.length > 0 ? plan.build_steps : null;";
if (!buildSteps.includes(structuredGate)) {
  throw new Error("Structured build_steps gate must stay exact");
}

for (const signal of ["fallback", "legacy", "degraded", "overview"]) {
  if (new RegExp(signal, "i").test(buildSteps)) {
    throw new Error(`BuildSteps must not render or label silent return path with: ${signal}`);
  }
}

const returnPathStart = buildSteps.indexOf('<p className="paper-library-choice">');
if (returnPathStart === -1) {
  throw new Error("Missing library choice return path");
}
const returnPath = buildSteps.slice(returnPathStart);
for (const token of ["SourceBadge", "paper-build-step-list", "paper-build-step-card", "paper-build-step-meta"]) {
  if (returnPath.includes(token)) {
    throw new Error(`Silent return path must not include structured-only marker: ${token}`);
  }
}

for (const forbiddenRead of ["parameter_mapping", ".value", ".unit"]) {
  if (buildSteps.includes(forbiddenRead)) {
    throw new Error(`BuildSteps must not read parameter mapping values or units: ${forbiddenRead}`);
  }
}
for (const forbiddenText of [/推荐设为\s*\d/, /增大\s*\d/, /\d+\s*%/, /\d+\s*倍/, /最优/]) {
  if (forbiddenText.test(buildSteps)) {
    throw new Error(`BuildSteps must not hard-code numeric tuning guidance: ${forbiddenText}`);
  }
}

if (!buildSteps.includes("function sourceToBadgeKind")) {
  throw new Error("Missing explicit evidence source to badge helper");
}
if (!buildSteps.includes('if (source === "document_extracted") return "document_extracted";')) {
  throw new Error("Missing document_extracted badge mapping");
}
if (!buildSteps.includes('if (source === "user_supplied") return "user_supplied_resolved";')) {
  throw new Error("Missing user_supplied badge mapping");
}
if (buildSteps.includes("missing_unresolved")) {
  throw new Error("BuildSteps must not use missing_unresolved");
}
if (/SourceBadge\s+kind=\{[^}]*\.source/.test(buildSteps)) {
  throw new Error("BuildSteps must not pass raw evidence.source to SourceBadge");
}

const libraryLineStart = buildSteps.indexOf('<p className="paper-secondary paper-build-step-library">');
const libraryLineEnd = buildSteps.indexOf("</p>", libraryLineStart);
if (libraryLineStart === -1 || libraryLineEnd === -1) {
  throw new Error("Missing structured library path line");
}
const libraryLine = buildSteps.slice(libraryLineStart, libraryLineEnd);
if (!libraryLine.includes('block.library_path ?? "库路径待确认"')) {
  throw new Error("Empty library_path must render 库路径待确认");
}
if (libraryLine.includes("SourceBadge") || libraryLine.includes("renderEvidenceMeta")) {
  throw new Error("Library path pending text must not carry a badge");
}

for (const cssClass of [
  ".paper-build-step-list",
  ".paper-build-step-block",
  ".paper-build-step-param-list",
  ".paper-build-step-meta",
]) {
  if (!paperCss.includes(cssClass)) {
    throw new Error(`Missing build step CSS class: ${cssClass}`);
  }
}
if (!/\.paper-build-step-card \.paper-token\s*\{[^}]*overflow-wrap\s*:\s*anywhere/.test(paperCss)) {
  throw new Error("Build step tokens must wrap long content");
}

console.log("TASK-508 smoke passed");
