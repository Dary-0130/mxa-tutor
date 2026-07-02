import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  errorMessages: "src/lib/errorMessages.ts",
  packageJson: "package.json",
  paperApi: "src/lib/paperApi.ts",
  paperHeader: "src/routes/paper/PaperHeader.tsx",
  paperResult: "src/routes/PaperResultPage.tsx",
  paperTypes: "src/lib/paperTypes.ts",
  usePaperResult: "src/routes/paper/usePaperResult.ts",
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

function assertNotRegex(source, regex, message) {
  if (regex.test(source)) {
    throw new Error(message);
  }
}

assertIncludes(sources.paperTypes, "PaperReparseResponse", "paperTypes must define PaperReparseResponse");
assertIncludes(sources.paperApi, 'paperPath(paperId, "/reparse")', "paperApi must post to /reparse");
assertIncludes(sources.paperApi, "postPaperReparse", "paperApi must expose postPaperReparse");
assertIncludes(sources.usePaperResult, "postPaperReparse(paperId)", "hook must call reparse API");
assertIncludes(sources.usePaperResult, "state.reparsing", "hook must guard repeated reparse calls");
assertIncludes(sources.usePaperResult, "version: previousVersion + 1", "reparse success must bump result version");
assertIncludes(sources.usePaperResult, "documentStatuses: undefined", "reparse result must not resurrect upload statuses");
assertIncludes(sources.usePaperResult, 'apiError.code === "reparse_source_unavailable"', "hook must detect 410 source unavailable");

for (const text of [
  "重新解析会用同一份论文文字重新抽取并",
  "替换当前结果",
  "已补充的缺失参数、当前 plan 和调参结果会被替换",
  "它只重跑已读入的论文文字;若缺的信息在图片 / 表格里,或某篇上传时就失败,重新解析补不回,需要重新上传或等解析升级。",
]) {
  assertIncludes(sources.paperHeader, text, "confirm dialog copy must match TASK-522-B text");
}
assertIncludes(sources.paperHeader, "<strong>{REPARSE_CONFIRM_COPY.currentResult}</strong>", "current result replacement must be emphasized");
assertIncludes(sources.paperHeader, "<strong>{REPARSE_CONFIRM_COPY.resetScope}</strong>", "reset scope must be emphasized");
assertIncludes(sources.paperHeader, "重新解析", "header must expose reparse action");
assertIncludes(sources.paperHeader, "重新上传", "header must keep reupload action");
assertIncludes(sources.paperHeader, 'disabled={reparsing || sourceUnavailable}', "button must disable while reparsing or unavailable");
assertIncludes(sources.paperHeader, "这份结果没有可重跑的临时文字,请重新上传", "header must show 410 source unavailable hint");
assertIncludes(sources.paperHeader, "onDismissReparseError", "reparse failure must be dismissible");
assertIncludes(sources.paperResult, "onReparse={reparse}", "result page must wire reparse callback");
assertIncludes(sources.paperResult, 'key={`${data.paperId}-${data.version}`}', "ask/tuning temporary state must reset after success");

for (const code of [
  "reparse_source_unavailable",
  "reparse_in_progress",
  "paper_reparse_failed",
  "paper_reparse_store_failed",
]) {
  assertIncludes(sources.errorMessages, code, `Missing reparse error mapping for ${code}`);
}

for (const [name, source] of Object.entries(sources)) {
  if (name === "packageJson") {
    continue;
  }
  assertNotRegex(source, /console\.[a-z]+/i, `${name} must not add console logging`);
}

const packageJson = JSON.parse(sources.packageJson);
if (packageJson.scripts?.["smoke:task522b"] !== "node scripts/task522b-smoke.mjs") {
  throw new Error("package.json must expose smoke:task522b");
}
