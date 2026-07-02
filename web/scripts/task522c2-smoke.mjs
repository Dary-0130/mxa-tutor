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

const table = read("src/routes/paper/ParameterTable.tsx");
const header = read("src/routes/paper/PaperHeader.tsx");
const errors = read("src/lib/errorMessages.ts");

assert(table.includes("你改的"), "corrected rows must use the approved label");
assert(table.includes("AI 原本抽:"), "corrected rows must show the AI original value");
assert(
  table.includes('row.mapping?.source === "document_extracted" || Boolean(activeCorrection)'),
  "only document-extracted or active correction rows may show correction entry",
);
assert(!table.includes("用户权威值"), "frontend copy must not use the forbidden authority wording");
assert(
  header.includes("已纠错的参数值"),
  "reparse confirmation must mention corrected parameter values",
);
assert(
  errors.includes("correction_lock_conflict"),
  "correction lock errors must have visible copy",
);
assert(
  !/console\.(log|error|warn|info)/.test(table),
  "ParameterTable must not log correction values",
);

console.log("task522c2 smoke passed");
