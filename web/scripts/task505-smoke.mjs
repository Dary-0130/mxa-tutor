import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  uploadPage: "src/routes/UploadPage.tsx",
  uploadDropzone: "src/routes/upload/UploadDropzone.tsx",
  uploadCss: "src/styles/upload.css",
};

for (const file of Object.values(files)) {
  if (!existsSync(join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const uploadPage = readFileSync(join(root, files.uploadPage), "utf8");
for (const text of [
  'useState<EntryTabKey>("engineering")',
  'role="tablist"',
  'role="tab"',
  'role="tabpanel"',
  'aria-label="首页入口"',
  "工程导览 / 资料复现",
  "工程导览",
  "资料复现",
  "上传论文 / 报告后，系统将生成复现路线图、参数对应说明与调参方向。该入口独立于工程 .zip 解析流程。",
  "进入资料复现 →",
  'navigate("/paper")',
]) {
  if (!uploadPage.includes(text)) {
    throw new Error(`Missing upload page entry tab contract: ${text}`);
  }
}

for (const guard of [
  'const activeTab: EntryTabKey = busy ? "engineering" : selectedTab',
  'if (busy && tab === "paper")',
  'setSelectedTab("engineering")',
  'event.key === "Enter" || event.key === " "',
  'aria-disabled={busy ? "true" : undefined}',
]) {
  if (!uploadPage.includes(guard)) {
    throw new Error(`Missing busy tab guard: ${guard}`);
  }
}
for (const removedText of ["upload-hero-note", "工程导览 + 资料复现路线图"]) {
  if (uploadPage.includes(removedText)) {
    throw new Error(`Removed left-column copy is still present: ${removedText}`);
  }
}

const uploadDropzone = readFileSync(join(root, files.uploadDropzone), "utf8");
for (const text of ["拖拽工程压缩包", "或点击选择 .zip 文件"]) {
  if (!uploadDropzone.includes(text)) {
    throw new Error(`Dropzone copy changed or missing: ${text}`);
  }
}

const uploadCss = readFileSync(join(root, files.uploadCss), "utf8");
if (uploadCss.includes(".upload-hero-note")) {
  throw new Error("Removed upload hero note styles are still present");
}
for (const selector of [
  ".upload-entry-tabs",
  ".upload-entry-tab",
  ".upload-entry-tab--active",
  ".upload-entry-panel",
  ".upload-paper-entry",
  ".upload-entry-tab:focus-visible",
]) {
  if (!uploadCss.includes(selector)) {
    throw new Error(`Missing entry tab selector: ${selector}`);
  }
}

console.log("TASK-505 smoke passed");
