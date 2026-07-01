import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {
  citationChip: "src/routes/paper/CitationChip.tsx",
  packageJson: "package.json",
  paperAskPanel: "src/routes/paper/PaperAskPanel.tsx",
  paperCss: "src/styles/paper.css",
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

function assertNotRegex(source, regex, message) {
  if (regex.test(source)) {
    throw new Error(message);
  }
}

assertIncludes(
  sources.paperResultPage,
  "import { PaperAskPanel } from \"./paper/PaperAskPanel\";",
  "PaperResultPage must import PaperAskPanel",
);
assertIncludes(sources.paperResultPage, "paper-body-grid", "PaperResultPage must wrap the body in a grid");
assertIncludes(sources.paperResultPage, "paper-content-column", "PaperResultPage must keep paper sections in the content column");
assertIncludes(sources.paperResultPage, "<PaperAskPanel", "PaperAskPanel must mount after the paper body content");
assertIncludes(sources.paperResultPage, "documents={data.spec.documents}", "PaperAskPanel must receive paper documents for document labels");
assertNotRegex(sources.paperResultPage, /id=["']paper-ask/, "PaperAskPanel mount must not add a section id");

assertIncludes(sources.paperAskPanel, "postPaperAsk", "PaperAskPanel must consume postPaperAsk");
assertIncludes(sources.paperAskPanel, "MAX_QUESTION_LENGTH = 1000", "PaperAskPanel must keep the 1000-character client gate");
assertIncludes(sources.paperAskPanel, "trimmed.length === 0", "PaperAskPanel must block empty submissions");
assertIncludes(sources.paperAskPanel, "trimmed.length > MAX_QUESTION_LENGTH", "PaperAskPanel must block overlong submissions");
assertIncludes(sources.paperAskPanel, "disabled={!canSubmit}", "PaperAskPanel must disable submit while invalid or loading");
assertIncludes(sources.paperAskPanel, "requestIdRef", "PaperAskPanel must guard stale responses with a request id");
assertIncludes(sources.paperAskPanel, "lastSubmittedQuestion", "PaperAskPanel retry must use the last submitted question");
assertIncludes(sources.paperAskPanel, "session_id: sessionId", "PaperAskPanel may only pass mount-local session_id");
assertIncludes(sources.paperAskPanel, "updateQuestion(suggestion)", "Follow-up chips must fill the input");
assertNotRegex(sources.paperAskPanel, /localStorage|sessionStorage|history\.|window\.location|location\./, "PaperAskPanel must not persist or expose session state");
assertNotRegex(sources.paperAskPanel, /getElementById|scrollIntoView/, "PaperAskPanel must not implement citation DOM navigation");

for (const fallbackCopy of [
  "当前资料里没有足够可核验的依据支撑这个回答,所以没有生成带出处的结论。",
  "这次回答生成的出处没有通过校验,因此没有作为正式回答展示。",
  "这次回答引用的依据没有稳定对应到当前结果页中的公式、参数或区块,因此没有作为正式回答展示。",
  "这个问题超出了当前论文复现结果能可靠回答的范围。",
  "可以试着围绕论文的公式、参数、建模步骤或调参建议来提问。",
]) {
  assertIncludes(sources.paperAskPanel, fallbackCopy, `Missing fallback copy: ${fallbackCopy}`);
}
assertIncludes(sources.paperAskPanel, "调用层错误", "HTTP errors must be distinct from fallback answers");
assertIncludes(sources.paperAskPanel, "response.is_fallback", "Fallback UI must read is_fallback");
assertIncludes(sources.paperAskPanel, "response.fallback_reason", "Fallback UI must read fallback_reason");

assertIncludes(
  sources.citationChip,
  "resolveCitationTargetElement(citation.target)",
  "CitationChip clickable state must use resolveCitationTargetElement",
);
assertIncludes(
  sources.citationChip,
  "scrollToCitationTarget(citation.target)",
  "CitationChip click must use scrollToCitationTarget",
);
assertIncludes(sources.citationChip, "paper-source-badge paper-citation-chip", "CitationChip must reuse paper-source-badge");
assertIncludes(sources.citationChip, 'document_extracted: "document_extracted"', "CitationChip must map document citations");
assertIncludes(sources.citationChip, 'user_supplied: "user_supplied_resolved"', "CitationChip must map user-supplied citations");
assertIncludes(sources.citationChip, 'data-clickable="false"', "Unresolved citations must render as disabled chips");
assertNotRegex(sources.citationChip, /missing_unresolved|SourceBadge|getElementById|scrollIntoView|window\.location|location\./, "CitationChip must not create fallback badges or local navigation");

assertIncludes(sources.paperCss, ".paper-body-grid{display:grid", "Desktop body must reserve a right dock");
assertIncludes(sources.paperCss, ".paper-ask-panel-wrap{position:sticky", "Desktop ask panel must be sticky");
assertIncludes(sources.paperCss, ".paper-ask-panel-wrap{position:fixed", "Mobile ask panel must be fixed to the bottom");
assertIncludes(sources.paperCss, ".paper-page{padding-bottom:300px;}", "Mobile page must reserve bottom-panel space");
assertNotRegex(sources.paperCss, /top:0;[^}]*paper-ask-panel|paper-ask-panel[^}]*top:0;/, "Ask panel must not become a top fixed bar");

const packageJson = JSON.parse(sources.packageJson);
if (packageJson.scripts?.["smoke:task520d"] !== "node scripts/task520d-smoke.mjs") {
  throw new Error("package.json must expose smoke:task520d");
}

console.log("TASK-520-D smoke passed");
