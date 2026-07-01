import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import vm from "node:vm";
import ts from "typescript";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  api: "src/lib/api.ts",
  errorMessages: "src/lib/errorMessages.ts",
  logic: "src/routes/paper/paperUploadLogic.ts",
  packageJson: "package.json",
  paperApi: "src/lib/paperApi.ts",
  paperDropzone: "src/routes/paper/PaperDropzone.tsx",
  paperHeader: "src/routes/paper/PaperHeader.tsx",
  paperResult: "src/routes/PaperResultPage.tsx",
  paperUpload: "src/routes/PaperUploadPage.tsx",
  paperUploadQueue: "src/routes/paper/PaperUploadQueue.tsx",
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

assertIncludes(sources.paperDropzone, "onFiles: (files: File[]) => void", "PaperDropzone must emit File[]");
assertIncludes(sources.paperDropzone, "multiple", "PaperDropzone input must allow multiple files");
assertIncludes(sources.paperDropzone, "Array.from(files)", "PaperDropzone must convert FileList with Array.from");
assertIncludes(sources.paperDropzone, 'event.currentTarget.value = "";', "PaperDropzone must reset input value");
assertNotRegex(sources.paperDropzone, /\.item\(0\)/, "PaperDropzone must not keep the first-file-only path");

assertIncludes(sources.api, "apiUploadFormTask", "apiUploadFormTask must exist");
assertIncludes(sources.api, "xhr.send(formData)", "apiUploadFormTask must send caller-provided FormData");
assertIncludes(sources.api, 'formData.append("file", file);', "apiUploadTask must remain single-file compatible");
assertIncludes(sources.paperApi, "for (const file of files)", "paperApi.uploadDocument must append every file");
assertIncludes(sources.paperApi, 'formData.append("primary_index", String(primaryIndex));', "paperApi.uploadDocument must append primary_index only when present");
assertNotRegex(sources.paperApi, /apiUploadTask/, "paperApi.uploadDocument must use the FormData upload helper");

assertIncludes(sources.paperUpload, "primaryLocalId: string | null", "Upload reducer must store primaryLocalId");
assertIncludes(sources.paperUpload, "buildPaperUploadSubmission(state.items, state.primaryLocalId)", "Submit must derive primary_index from the selected snapshot");
assertIncludes(sources.paperUpload, "localId: createLocalId()", "Selected rows must get localId keys");
assertIncludes(sources.paperUpload, "MAX_PAPER_UPLOAD_FILES = 5", "Client upload limit must be 5");
assertIncludes(sources.paperUpload, "validation: validationCode ? \"invalid\" : \"valid\"", "Validation must be per-file");
assertIncludes(sources.paperUploadQueue, "key={item.localId}", "Queue rows must key by localId");
assertIncludes(sources.paperUploadQueue, "aria-pressed={isPrimary}", "Primary toggle must be keyboard-accessible button state");
assertNotRegex(sources.paperUpload, /primaryIndex:\s*number/, "Upload state must not store primaryIndex");

assertIncludes(sources.logic, "const validItems = items.filter", "Primary index helper must derive from valid items");
assertIncludes(sources.logic, "validItems.length <= 1", "Single-file uploads must not send primary_index");
assertIncludes(sources.logic, "validItems.findIndex", "Primary index helper must search the valid snapshot");
assertIncludes(sources.logic, "primaryIndex >= 0 ? primaryIndex : null", "Missing/invalid primary must submit as no-primary");

const transpiledLogic = ts.transpileModule(sources.logic, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const sandbox = { exports: {} };
vm.runInNewContext(transpiledLogic, sandbox);
const { buildPaperUploadSubmission } = sandbox.exports;
const mockItems = [
  { localId: "doc-2", file: "second.pdf", validation: "valid" },
  { localId: "doc-3", file: "third.pdf", validation: "valid" },
];
const submission = buildPaperUploadSubmission(mockItems, "doc-3");
if (submission.primaryIndex !== 1 || submission.files.join(",") !== "second.pdf,third.pdf") {
  throw new Error("Primary index case failed: choose 3rd, delete 1st must submit index=1");
}
const invalidSubmission = buildPaperUploadSubmission(
  [
    { localId: "doc-1", file: "bad.txt", validation: "invalid" },
    { localId: "doc-2", file: "second.pdf", validation: "valid" },
    { localId: "doc-3", file: "third.pdf", validation: "valid" },
  ],
  "doc-3",
);
if (invalidSubmission.primaryIndex !== 1 || invalidSubmission.files.join(",") !== "second.pdf,third.pdf") {
  throw new Error("Invalid files must not participate in primary_index");
}
const singleSubmission = buildPaperUploadSubmission(
  [{ localId: "doc-1", file: "single.pdf", validation: "valid" }],
  "doc-1",
);
if (singleSubmission.primaryIndex !== null) {
  throw new Error("Single-file upload must not send primary_index");
}

assertIncludes(sources.usePaperResult, "documentStatuses?: UploadDocumentStatus[]", "PaperResultData must keep route document statuses");
assertIncludes(sources.usePaperResult, "documentStatuses: location.state.document_statuses", "Route state must carry document_statuses");
assertIncludes(sources.paperResult, "documentStatuses={data.documentStatuses}", "PaperHeader must receive document statuses");
assertIncludes(sources.paperHeader, "documentStatuses?.length ?? spec.documents.length", "Source display must use original document count from statuses");
assertIncludes(sources.paperHeader, "document.document_id === spec.primary_document_id", "Primary badge must read spec.primary_document_id");
assertIncludes(sources.paperHeader, "status.status === \"failed\"", "Partial banner must use failed document statuses");

for (const code of [
  "document_parse_failed",
  "paper_spec_generation_failed",
  "document_processing_failed",
]) {
  assertIncludes(sources.errorMessages, code, `Missing document status mapping for ${code}`);
}
assertIncludes(sources.errorMessages, "DOCUMENT_STATUS_ERROR_MESSAGES[code] ??", "Unknown document status errors must use a fallback");
assertNotRegex(sources.errorMessages, /\$\{code\}/, "Error fallback must not render raw machine codes");

for (const [name, source] of Object.entries(sources)) {
  if (name === "packageJson") {
    continue;
  }
  assertNotRegex(source, /console\.[a-z]+\([^)]*file/i, `${name} must not console-log files`);
  assertNotRegex(source, /console\.[a-z]+\([^)]*error_code/i, `${name} must not console-log error_code`);
}

const packageJson = JSON.parse(sources.packageJson);
if (packageJson.scripts?.["smoke:task521d"] !== "node scripts/task521d-smoke.mjs") {
  throw new Error("package.json must expose smoke:task521d");
}

console.log("TASK-521-D smoke passed");
