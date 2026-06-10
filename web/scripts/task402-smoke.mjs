import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const requiredFiles = [
  "src/routes/UploadPage.tsx",
  "src/routes/OverviewPage.tsx",
  "src/lib/errorMessages.ts",
  "src/lib/localStore.ts",
  "src/components/scene/PanoramaScene.tsx",
  "src/components/scene/UploadScene.tsx",
  "public/assets/panorama.webp",
  "public/assets/upload-bg.webp",
];

const requiredCodes = [
  "zip_bomb",
  "zip_slip",
  "file_type_not_allowed",
  "project_not_found",
  "project_too_large",
  "upload_error",
  "project_error",
  "internal_error",
  "llm_auth",
  "llm_quota",
  "llm_rate_limit",
  "llm_timeout",
  "llm_server",
  "slx_parse",
  "m_parse",
  "parse_error",
  "overview_generation",
  "chat_session_not_found",
  "store_error",
  "chat_generation",
  "quota_exhausted",
  "evidence_missing",
  "not_found",
  "validation_error",
  "method_not_allowed",
  "http_error",
  "embedding_model_load",
  "parse_timeout",
  "network_error",
];

const bannedDeps = ["framer-motion", "zustand", "jotai", "redux"];

for (const file of requiredFiles) {
  if (!existsSync(join(root, file))) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const packageJson = readFileSync(join(root, "package.json"), "utf8");
for (const dep of bannedDeps) {
  if (packageJson.includes(dep)) {
    throw new Error(`Banned dependency present: ${dep}`);
  }
}

const messages = readFileSync(join(root, "src/lib/errorMessages.ts"), "utf8");
for (const code of requiredCodes) {
  if (!messages.includes(code)) {
    throw new Error(`Missing error code: ${code}`);
  }
}

console.log("TASK-402 smoke passed");
