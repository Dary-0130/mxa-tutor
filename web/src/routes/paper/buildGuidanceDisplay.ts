import type {
  GuidanceBasis,
  GuidanceObligationKind,
  GuidanceStatus,
  ModelBuildStep,
  ModelGenerationPlan,
  PaperEvidenceEntry,
} from "../../lib/paperTypes";

const EMPTY_DETAIL_TEXT = "此条建议内容未完整生成";
const DATA_FORMAT_NOTICE = "部分指导数据格式不完整";

const CONFIRMATION_REASON_CODE_VALUES = [
  "missing_parameter_value",
  "library_variant_unresolved",
  "toolbox_unverified",
  "solver_unverified",
  "sample_time_unverified",
  "connection_detail_missing",
  "initial_condition_unverified",
  "switching_frequency_unverified",
  "simulation_time_unverified",
  "configuration_unverified",
  "document_evidence_unverified",
  "engineering_decision_unverified",
] as const;

export type ConfirmationReasonCode = (typeof CONFIRMATION_REASON_CODE_VALUES)[number];

export const CONFIRMATION_REASON_CODES: readonly ConfirmationReasonCode[] = Object.freeze([
  ...CONFIRMATION_REASON_CODE_VALUES,
]);

export const CONFIRMATION_REASON_TEXT: Readonly<Record<ConfirmationReasonCode, string>> =
  Object.freeze({
    missing_parameter_value:
      "需要确认 {target} 的参数值；请查看可复现实验材料或本地模型设置。",
    library_variant_unresolved:
      "需要确认 {target} 的 Simulink 模块变体；请查看本地库版本。",
    toolbox_unverified: "需要确认 {target} 的工具箱可用性；请查看已安装 MATLAB 产品。",
    solver_unverified: "需要确认 {target} 的 solver 选择；请查看复现环境。",
    sample_time_unverified: "需要确认 {target} 的采样时间处理；请查看本地模型设置。",
    connection_detail_missing: "需要确认 {target} 的连接细节；请查看源模型图。",
    initial_condition_unverified: "需要确认 {target} 的初始条件处理；请查看本地模型设置。",
    switching_frequency_unverified:
      "需要确认 {target} 的开关频率处理；请查看本地模型设置。",
    simulation_time_unverified: "需要确认 {target} 的仿真时长处理；请查看本地模型设置。",
    configuration_unverified: "需要确认 {target} 的配置细节；请查看本地模型设置。",
    document_evidence_unverified: "需要确认 {target}；该条声称的论文依据未能核实。",
    engineering_decision_unverified:
      "需要确认 {target} 的工程选择；请查看本地模型设置。",
  });

const PUNT_REASON_CODES = [
  "source_does_not_specify",
  "upstream_step_underspecified",
  "requires_user_context",
  "outside_guidance_contract",
] as const;

const TRAILING_PUNT_REASON_RE = new RegExp(
  `[；;]\\s*原因[：:]\\s*(?:${PUNT_REASON_CODES.join("|")})\\s*[。．.]?\\s*$`,
  "u",
);

const DISPLAY_PREFIXES: ReadonlyArray<{ prefix: string; basis: GuidanceBasis }> = [
  { prefix: "论文明确给出：", basis: "document_extracted" },
  { prefix: "由论文信息推导：", basis: "document_derived" },
  { prefix: "领域默认（非论文）：", basis: "domain_default" },
  { prefix: "本方案选择（可改）：", basis: "engineering_choice" },
  { prefix: "需确认你的环境：", basis: "user_environment" },
  { prefix: "需你决定：", basis: "user_decision" },
  { prefix: "暂无法确定：", basis: "user_confirmation_required" },
  { prefix: "论文依据未核实（未采用）：", basis: "document_claim_unverified" },
];

const BASIS_VALUES = new Set<string>([
  "document_extracted",
  "document_derived",
  "domain_default",
  "engineering_choice",
  "user_environment",
  "user_decision",
  "user_confirmation_required",
  "document_claim_unverified",
]);

const BASIS_RETIRED_ALIASES: Readonly<Record<string, GuidanceBasis>> = Object.freeze({
  engineering_convention: "engineering_choice",
});

export type GuidanceSourceRank =
  | "paper-original"
  | "paper-derived"
  | "standard"
  | "user-action"
  | "needs-check"
  | "source-incomplete";

export type GuidanceSourceTone = "original" | "derived" | "standard" | "user" | "check" | "plain";

export interface GuidanceSourceDisplay {
  rank: GuidanceSourceRank;
  tone: GuidanceSourceTone;
  label: string;
  description: string;
  evidenceTitle: "论文摘录" | "推导依据" | null;
}

export interface CleanGuidanceText {
  text: string;
  prefixMismatch: boolean;
  matchedPrefixBasis: GuidanceBasis | null;
}

export interface GuidanceKindDisplay {
  category: GuidanceGroupCategory;
  label: string;
  mark: string;
}

export type GuidanceGroupCategory = "parameter" | "connection" | "configuration" | "block" | "other";

export interface GuidanceEvidenceChip {
  key: string;
  title: string;
  excerpt: string | null;
  locatorText: string;
}

export interface GuidanceEvidenceDisplay {
  title: "论文摘录" | "推导依据";
  summary: string;
  chips: GuidanceEvidenceChip[];
}

export interface DisplayGuidanceItem {
  itemType: "detail" | "gap";
  key: string;
  id: string;
  stepId: string | null;
  category: GuidanceGroupCategory;
  groupKey: string;
  groupLabel: string;
  kind: GuidanceKindDisplay;
  text: string;
  source: GuidanceSourceDisplay | null;
  reasonText: string | null;
  evidence: GuidanceEvidenceDisplay | null;
  severityLabel: string | null;
  severityHint: string | null;
  targetLine: string | null;
}

export interface DisplayGuidanceGroup {
  key: string;
  label: string;
  category: GuidanceGroupCategory;
  items: DisplayGuidanceItem[];
  detailCount: number;
  gapCount: number;
}

export interface DisplayGuidanceBucket {
  key: string;
  title: string;
  anchorId: string;
  detailCount: number;
  gapCount: number;
  totalCount: number;
  groups: DisplayGuidanceGroup[];
}

export interface DisplayGuidanceModel {
  stepBuckets: Map<string, DisplayGuidanceBucket>;
  looseBucket: DisplayGuidanceBucket;
  counts: {
    details: number;
    gaps: number;
    inputTotal: number;
    visibleTotal: number;
  };
  dataNotice: string | null;
  statusText: string | null;
}

interface BucketDraft {
  key: string;
  title: string;
  anchorId: string;
  items: DisplayGuidanceItem[];
}

interface DetailSourceInput {
  basis: unknown;
  hasEvidence: boolean;
  confirmationReasonCode: string | null;
  prefixMismatch: boolean;
}

export function buildGuidanceDisplayModel(
  plan: Pick<ModelGenerationPlan, "build_guidance" | "guidance_status">,
  steps: readonly Pick<ModelBuildStep, "step_id">[],
): DisplayGuidanceModel {
  const stepIds = steps.map((step) => step.step_id).filter((stepId) => stepId.trim() !== "");
  const stepSet = new Set(stepIds);
  const stepBuckets = new Map<string, BucketDraft>();
  stepIds.forEach((stepId, index) => {
    stepBuckets.set(stepId, {
      key: stepId,
      title: `步骤 ${index + 1}`,
      anchorId: `paper-guidance-step-${index + 1}`,
      items: [],
    });
  });

  const looseBucket: BucketDraft = {
    key: "loose",
    title: "未能归入具体步骤的建议 · 全局待确认",
    anchorId: "paper-guidance-loose",
    items: [],
  };

  const guidance = asRecord(plan.build_guidance);
  const rawDetails = guidance?.details;
  const rawGaps = guidance?.gaps;
  const detailsOk = rawDetails === undefined && !guidance ? true : Array.isArray(rawDetails);
  const gapsOk = rawGaps === undefined && !guidance ? true : Array.isArray(rawGaps);
  const detailValues = Array.isArray(rawDetails) ? rawDetails : [];
  const gapValues = Array.isArray(rawGaps) ? rawGaps : [];

  detailValues.forEach((detail, index) => {
    addItemToBucket(analyzeDetail(detail, index), stepSet, stepBuckets, looseBucket);
  });
  gapValues.forEach((gap, index) => {
    addItemToBucket(analyzeGap(gap, index), stepSet, stepBuckets, looseBucket);
  });

  const finalizedStepBuckets = new Map<string, DisplayGuidanceBucket>();
  stepBuckets.forEach((bucket, stepId) => {
    finalizedStepBuckets.set(stepId, finalizeBucket(bucket));
  });
  const finalizedLooseBucket = finalizeBucket(looseBucket);
  const detailCount = detailValues.length;
  const gapCount = gapValues.length;
  const visibleTotal = detailCount + gapCount;
  const dataNotice = detailsOk && gapsOk ? null : DATA_FORMAT_NOTICE;
  const statusText = getStatusText(plan.guidance_status, visibleTotal, dataNotice);

  return {
    stepBuckets: finalizedStepBuckets,
    looseBucket: finalizedLooseBucket,
    counts: {
      details: detailCount,
      gaps: gapCount,
      inputTotal: visibleTotal,
      visibleTotal,
    },
    dataNotice,
    statusText,
  };
}

export function cleanGuidanceDisplayText(value: unknown, basis: unknown): CleanGuidanceText {
  const normalizedBasis = normalizeBasis(basis);
  let text = stringValue(value).replace(TRAILING_PUNT_REASON_RE, "").trim();
  let prefixMismatch = false;
  let matchedPrefixBasis: GuidanceBasis | null = null;

  for (const entry of DISPLAY_PREFIXES) {
    if (!text.startsWith(entry.prefix)) {
      continue;
    }
    matchedPrefixBasis = entry.basis;
    if (normalizedBasis === entry.basis) {
      text = text.slice(entry.prefix.length).trim();
    } else {
      prefixMismatch = true;
    }
    break;
  }

  return {
    text: text || EMPTY_DETAIL_TEXT,
    prefixMismatch,
    matchedPrefixBasis,
  };
}

export function sourceDisplayForDetail(input: DetailSourceInput): GuidanceSourceDisplay {
  const basis = normalizeBasis(input.basis);
  if (input.confirmationReasonCode === "document_evidence_unverified") {
    return sourceDisplays.documentEvidenceUnverified;
  }
  if (basis === "document_claim_unverified") {
    return sourceDisplays.documentEvidenceUnverified;
  }
  if (input.prefixMismatch) {
    return sourceDisplays.sourceMismatch;
  }
  if (basis === "document_extracted") {
    return input.hasEvidence ? sourceDisplays.documentOriginal : sourceDisplays.sourceIncomplete;
  }
  if (basis === "document_derived") {
    return input.hasEvidence ? sourceDisplays.documentDerived : sourceDisplays.sourceIncomplete;
  }
  if (basis === "domain_default") {
    return sourceDisplays.domainDefault;
  }
  if (basis === "engineering_choice") {
    return sourceDisplays.engineeringChoice;
  }
  if (basis === "user_confirmation_required") {
    return sourceDisplays.userConfirmation;
  }
  if (basis === "user_environment") {
    return sourceDisplays.userEnvironment;
  }
  if (basis === "user_decision") {
    return sourceDisplays.userDecision;
  }
  return sourceDisplays.unknown;
}

export function confirmationReasonText(code: unknown, target: unknown): string | null {
  const cleanedCode = stringOrNull(code);
  if (!cleanedCode) {
    return null;
  }
  if (!isConfirmationReasonCode(cleanedCode)) {
    return "系统未能识别具体确认原因,请按上文内容核对";
  }
  return CONFIRMATION_REASON_TEXT[cleanedCode].replace(
    "{target}",
    describeGuidanceTarget(target) || "该项",
  );
}

export function describeGuidanceTarget(target: unknown): string | null {
  const record = asRecord(target);
  if (!record) {
    return null;
  }
  const targetKind = stringOrNull(record.target_kind);
  if (targetKind === "parameter") {
    const paper = stringOrNull(record.paper_param);
    const model = stringOrNull(record.model_param);
    if (paper && model) {
      return `参数 ${paper} -> ${model}`;
    }
    if (paper || model) {
      return `参数 ${paper ?? model}`;
    }
    return "参数";
  }
  if (targetKind === "block_choice") {
    return `模块角色 ${stringOrNull(record.block_role_ref) ?? "未标注"}`;
  }
  if (targetKind === "connection") {
    const from = portLabel(record.from_block, record.from_port);
    const to = portLabel(record.to_block, record.to_port);
    const signal = stringOrNull(record.signal_role);
    return `连接 ${from} -> ${to}${signal ? ` (${signal})` : ""}`;
  }
  if (targetKind === "configuration") {
    const owner = stringOrNull(record.owner_ref) ?? "模型";
    const setting = stringOrNull(record.setting_name) ?? "设置";
    return `配置 ${owner}.${setting}`;
  }
  return null;
}

export function detailKindDisplay(kind: unknown, target: unknown = null): GuidanceKindDisplay {
  const targetKind = stringOrNull(asRecord(target)?.target_kind);
  const normalizedKind = stringOrNull(kind);
  if (normalizedKind === "parameter_value" || targetKind === "parameter") {
    return { category: "parameter", label: "参数", mark: "PAR" };
  }
  if (normalizedKind === "connection" || targetKind === "connection") {
    return { category: "connection", label: "连线", mark: "LIN" };
  }
  if (normalizedKind === "configuration" || targetKind === "configuration") {
    return { category: "configuration", label: "配置", mark: "CFG" };
  }
  if (normalizedKind === "block_selection" || targetKind === "block_choice") {
    return { category: "block", label: "选块", mark: "BLK" };
  }
  return { category: "other", label: "其他", mark: "GEN" };
}

export function gapKindDisplay(kind: unknown, target: unknown = null): GuidanceKindDisplay {
  const targetKind = stringOrNull(asRecord(target)?.target_kind);
  const normalizedKind = stringOrNull(kind);
  if (normalizedKind === "missing_parameter_value" || targetKind === "parameter") {
    return { category: "parameter", label: "参数缺口", mark: "PAR" };
  }
  if (normalizedKind === "missing_connection_detail" || targetKind === "connection") {
    return { category: "connection", label: "连线缺口", mark: "LIN" };
  }
  if (normalizedKind === "missing_configuration_detail" || targetKind === "configuration") {
    return { category: "configuration", label: "配置缺口", mark: "CFG" };
  }
  if (normalizedKind === "missing_support_component" || targetKind === "block_choice") {
    return { category: "block", label: "选块缺口", mark: "BLK" };
  }
  return { category: "other", label: "待核对缺口", mark: "GEN" };
}

export function evidenceDisplayForDetail(
  source: GuidanceSourceDisplay,
  evidence: unknown,
): GuidanceEvidenceDisplay | null {
  if (!source.evidenceTitle) {
    return null;
  }
  const chips = evidenceEntries(evidence).filter(evidenceCanDisplay).map(evidenceChip);
  if (chips.length === 0) {
    return null;
  }
  return {
    title: source.evidenceTitle,
    summary: `${chips.length} 条依据`,
    chips,
  };
}

export function severityDisplay(severity: unknown): { label: string; hint: string } {
  if (severity === "blocking") {
    return {
      label: "关键待确认",
      hint: "系统当前将其标记为关键,可能影响搭建。",
    };
  }
  return {
    label: "建议核对",
    hint: "建议对照论文或本地环境核对。",
  };
}

function analyzeDetail(value: unknown, index: number): DisplayGuidanceItem {
  const record = asRecord(value);
  if (!record) {
    return malformedItem("detail", index);
  }
  const target = record.target ?? null;
  const clean = cleanGuidanceDisplayText(record.display_text, record.basis);
  const evidence = evidenceEntries(record.evidence);
  const reasonCode = stringOrNull(record.confirmation_reason_code);
  const source = sourceDisplayForDetail({
    basis: record.basis,
    hasEvidence: evidence.some(evidenceCanDisplay),
    confirmationReasonCode: reasonCode,
    prefixMismatch: clean.prefixMismatch,
  });
  const kind = detailKindDisplay(record.detail_kind, target);
  const targetLabel = describeGuidanceTarget(target);
  return {
    itemType: "detail",
    key: `detail-${stringOrNull(record.detail_id) ?? index + 1}-${index}`,
    id: stringOrNull(record.detail_id) ?? `detail-${index + 1}`,
    stepId: stringOrNull(record.step_id),
    category: kind.category,
    groupKey: groupKey(kind.category, target, record.obligation_kind),
    groupLabel: groupLabel(kind.label, targetLabel),
    kind,
    text: clean.text,
    source,
    reasonText: confirmationReasonText(reasonCode, target),
    evidence: evidenceDisplayForDetail(source, evidence),
    severityLabel: null,
    severityHint: null,
    targetLine: targetLine(targetLabel, record.obligation_kind),
  };
}

function analyzeGap(value: unknown, index: number): DisplayGuidanceItem {
  const record = asRecord(value);
  if (!record) {
    return malformedItem("gap", index);
  }
  const target = record.target ?? null;
  const targetLabel = describeGuidanceTarget(target);
  const kind = gapKindDisplay(record.gap_kind, target);
  const severity = severityDisplay(record.severity);
  const clean = cleanGuidanceDisplayText(record.display_text, "user_confirmation_required");
  return {
    itemType: "gap",
    key: `gap-${stringOrNull(record.gap_id) ?? index + 1}-${index}`,
    id: stringOrNull(record.gap_id) ?? `gap-${index + 1}`,
    stepId: stringOrNull(record.step_id),
    category: kind.category,
    groupKey: groupKey(kind.category, target, record.obligation_kind),
    groupLabel: groupLabel(kind.label, targetLabel),
    kind,
    text: clean.text,
    source: null,
    reasonText: null,
    evidence: null,
    severityLabel: severity.label,
    severityHint: severity.hint,
    targetLine: targetLine(targetLabel, record.obligation_kind),
  };
}

function malformedItem(itemType: "detail" | "gap", index: number): DisplayGuidanceItem {
  const kind =
    itemType === "detail" ? detailKindDisplay(null) : gapKindDisplay(null);
  return {
    itemType,
    key: `${itemType}-malformed-${index}`,
    id: `${itemType}-${index + 1}`,
    stepId: null,
    category: kind.category,
    groupKey: `${kind.category}:malformed`,
    groupLabel: DATA_FORMAT_NOTICE,
    kind,
    text: DATA_FORMAT_NOTICE,
    source: itemType === "detail" ? sourceDisplays.unknown : null,
    reasonText: null,
    evidence: null,
    severityLabel: itemType === "gap" ? "建议核对" : null,
    severityHint: itemType === "gap" ? "建议对照论文或本地环境核对。" : null,
    targetLine: null,
  };
}

function addItemToBucket(
  item: DisplayGuidanceItem,
  stepSet: ReadonlySet<string>,
  stepBuckets: Map<string, BucketDraft>,
  looseBucket: BucketDraft,
): void {
  if (item.stepId && stepSet.has(item.stepId)) {
    stepBuckets.get(item.stepId)?.items.push(item);
    return;
  }
  looseBucket.items.push(item);
}

function finalizeBucket(bucket: BucketDraft): DisplayGuidanceBucket {
  const groupDrafts = new Map<string, DisplayGuidanceGroup>();
  for (const item of bucket.items) {
    if (!groupDrafts.has(item.groupKey)) {
      groupDrafts.set(item.groupKey, {
        key: item.groupKey,
        label: item.groupLabel,
        category: item.category,
        items: [],
        detailCount: 0,
        gapCount: 0,
      });
    }
    const group = groupDrafts.get(item.groupKey);
    if (!group) {
      continue;
    }
    group.items.push(item);
    if (item.itemType === "detail") {
      group.detailCount += 1;
    } else {
      group.gapCount += 1;
    }
  }

  const groups = [...groupDrafts.values()].sort((left, right) => {
    const categoryDiff = categoryOrder(left.category) - categoryOrder(right.category);
    return categoryDiff || left.label.localeCompare(right.label, "zh-Hans-CN");
  });
  const detailCount = bucket.items.filter((item) => item.itemType === "detail").length;
  const gapCount = bucket.items.length - detailCount;

  return {
    key: bucket.key,
    title: bucket.title,
    anchorId: bucket.anchorId,
    detailCount,
    gapCount,
    totalCount: bucket.items.length,
    groups,
  };
}

function getStatusText(
  status: GuidanceStatus,
  visibleTotal: number,
  dataNotice: string | null,
): string | null {
  if (dataNotice && visibleTotal === 0) {
    return dataNotice;
  }
  if (visibleTotal > 0) {
    return null;
  }
  if (status === "no_document_basis") {
    return "未从论文中形成可定位的逐条建议;现有搭建路线仍可参考。";
  }
  if (status === "not_generated") {
    return "逐条建模建议尚未生成。";
  }
  if (status === "generation_failed") {
    return "本次逐条建议未生成成功,现有步骤已保留。";
  }
  if (status === "stale_pending_regeneration") {
    return "建议基于旧版本,等待更新。";
  }
  return "指导数据不完整。";
}

function normalizeBasis(value: unknown): GuidanceBasis | null {
  const basis = stringOrNull(value);
  if (!basis) {
    return null;
  }
  if (basis in BASIS_RETIRED_ALIASES) {
    return BASIS_RETIRED_ALIASES[basis];
  }
  return BASIS_VALUES.has(basis) ? (basis as GuidanceBasis) : null;
}

function isConfirmationReasonCode(code: string): code is ConfirmationReasonCode {
  return CONFIRMATION_REASON_CODES.includes(code as ConfirmationReasonCode);
}

function evidenceEntries(value: unknown): PaperEvidenceEntry[] {
  return Array.isArray(value) ? (value.filter(asRecord) as unknown as PaperEvidenceEntry[]) : [];
}

function evidenceCanDisplay(entry: unknown): boolean {
  const record = asRecord(entry);
  if (!record) {
    return false;
  }
  return Boolean(
    stringOrNull(record.excerpt) ||
      stringOrNull(record.paper_section_id) ||
      stringOrNull(record.equation_id) ||
      stringOrNull(record.figure_id),
  );
}

function evidenceChip(entry: PaperEvidenceEntry, index: number): GuidanceEvidenceChip {
  const locators = [
    locatorPart("文档", entry.document_id),
    locatorPart("章节", entry.paper_section_id),
    locatorPart("公式", entry.equation_id),
    locatorPart("图表", entry.figure_id),
  ].filter(Boolean);
  return {
    key: `${entry.document_id ?? "doc"}-${entry.paper_section_id ?? "section"}-${
      entry.equation_id ?? entry.figure_id ?? index
    }`,
    title: `依据 ${index + 1}`,
    excerpt: stringOrNull(entry.excerpt),
    locatorText: locators.length > 0 ? locators.join(" · ") : "已关联到论文摘录",
  };
}

function locatorPart(label: string, value: unknown): string | null {
  const text = stringOrNull(value);
  return text ? `${label} ${text}` : null;
}

function groupKey(
  category: GuidanceGroupCategory,
  target: unknown,
  obligationKind: unknown,
): string {
  const record = asRecord(target);
  const parts = [
    category,
    stringOrNull(obligationKind) ?? "no-obligation",
    stringOrNull(record?.target_kind) ?? "no-target",
    stringOrNull(record?.model_param),
    stringOrNull(record?.paper_param),
    stringOrNull(record?.owner_ref),
    stringOrNull(record?.setting_name),
    stringOrNull(record?.block_role_ref),
    stringOrNull(record?.from_block),
    stringOrNull(record?.from_port),
    stringOrNull(record?.to_block),
    stringOrNull(record?.to_port),
    stringOrNull(record?.signal_role),
  ];
  return parts.filter(Boolean).join("::");
}

function groupLabel(kindLabel: string, targetLabel: string | null): string {
  return targetLabel ? `${kindLabel} · ${targetLabel}` : kindLabel;
}

function targetLine(targetLabel: string | null, obligationKind: unknown): string | null {
  if (!targetLabel) {
    return null;
  }
  const obligation = obligationLabel(obligationKind);
  return obligation ? `核对对象：${targetLabel} · ${obligation}` : `核对对象：${targetLabel}`;
}

function obligationLabel(obligationKind: unknown): string | null {
  const normalized = stringOrNull(obligationKind) as GuidanceObligationKind | null;
  if (normalized === "determine_parameter_value") {
    return "参数值";
  }
  if (normalized === "select_component") {
    return "模块选择";
  }
  if (normalized === "configure_setting") {
    return "配置细节";
  }
  if (normalized === "connect_signal") {
    return "连接细节";
  }
  return null;
}

function portLabel(block: unknown, port: unknown): string {
  const blockText = stringOrNull(block);
  const portText = stringOrNull(port);
  if (blockText && portText) {
    return `${blockText}.${portText}`;
  }
  return blockText ?? "未知端点";
}

function categoryOrder(category: GuidanceGroupCategory): number {
  if (category === "parameter") return 0;
  if (category === "connection") return 1;
  if (category === "configuration") return 2;
  if (category === "block") return 3;
  return 4;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value.trim() : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

const sourceDisplays: Readonly<Record<string, GuidanceSourceDisplay>> = Object.freeze({
  documentOriginal: {
    rank: "paper-original",
    tone: "original",
    label: "论文原文",
    description: "已关联到论文原文摘录;仍需结合你的模型和上下文核对。",
    evidenceTitle: "论文摘录",
  },
  documentDerived: {
    rank: "paper-derived",
    tone: "derived",
    label: "据论文推导 · 非原文结论",
    description: "基于论文内容推导,非论文原文结论;请核对推导过程和具体数值。",
    evidenceTitle: "推导依据",
  },
  domainDefault: {
    rank: "standard",
    tone: "standard",
    label: "领域默认",
    description: "论文未提供,这是该领域常见起点;不保证适合当前场景,可按需要调整。",
    evidenceTitle: null,
  },
  engineeringChoice: {
    rank: "standard",
    tone: "standard",
    label: "工程设定",
    description: "论文未规定,这是为搭建模型选的工程取值;可按需要调整。",
    evidenceTitle: null,
  },
  userConfirmation: {
    rank: "user-action",
    tone: "user",
    label: "待你确认",
    description: "这条不是已确定的事实,需要你核对或选择。",
    evidenceTitle: null,
  },
  userEnvironment: {
    rank: "user-action",
    tone: "user",
    label: "环境相关",
    description: "取值取决于你的 MATLAB 环境(版本、工具箱、硬件),请按实际情况填写。",
    evidenceTitle: null,
  },
  userDecision: {
    rank: "user-action",
    tone: "user",
    label: "你的选择",
    description: "这是需你决定的设计取舍,请结合你的目标选择。",
    evidenceTitle: null,
  },
  documentEvidenceUnverified: {
    rank: "needs-check",
    tone: "check",
    label: "出处待核",
    description: "论文中可能提及,但本次未能核到确切出处;请对照论文核实后再采用,别直接信。",
    evidenceTitle: null,
  },
  unknown: {
    rank: "needs-check",
    tone: "check",
    label: "来源待核",
    description: "系统未能识别这条的来源类别,请以论文核对为准。",
    evidenceTitle: null,
  },
  sourceMismatch: {
    rank: "needs-check",
    tone: "check",
    label: "来源标注不一致 · 待核",
    description: "这条的标注前后不一致,系统未采信;请以论文核对为准。",
    evidenceTitle: null,
  },
  sourceIncomplete: {
    rank: "source-incomplete",
    tone: "plain",
    label: "来源信息不完整",
    description: "这条标注为论文来源,但当前缺少可展示摘录或定位;请对照论文核实。",
    evidenceTitle: null,
  },
});
