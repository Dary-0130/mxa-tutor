import assert from "node:assert/strict";

import {
  CONFIRMATION_REASON_CODES,
  CONFIRMATION_REASON_TEXT,
  buildGuidanceDisplayModel,
  cleanGuidanceDisplayText,
  confirmationReasonText,
  evidenceDisplayForDetail,
  sourceDisplayForDetail,
} from "../src/routes/paper/buildGuidanceDisplay.ts";

const targetParameter = {
  target_kind: "parameter",
  paper_param: "P_0",
  model_param: "Kp",
};

const targetConnection = {
  target_kind: "connection",
  from_block: "B1",
  from_port: "out",
  to_block: "B2",
  to_port: "in",
  signal_role: "feedback",
};

const evidence = {
  source: "document_extracted",
  document_id: "DOC-001",
  paper_section_id: "SEC-1",
  equation_id: "EQ-2",
  figure_id: null,
  excerpt: "The paper states the controller gain.",
};

type TestCase = {
  name: string;
  run: () => void;
};

const tests: TestCase[] = [];

function test(name: string, run: () => void): void {
  tests.push({ name, run });
}

function detail(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    detail_id: "GD-001",
    step_id: "STEP-1",
    detail_kind: "parameter_value",
    basis: "document_extracted",
    display_text: "论文明确给出：参数 P_0 = [1, D/(2H)]。",
    evidence: [evidence],
    confirmation_reason_code: null,
    target: targetParameter,
    obligation_kind: "determine_parameter_value",
    ...overrides,
  };
}

function gap(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    gap_id: "GAP-001",
    gap_kind: "missing_parameter_value",
    scope: "step",
    step_id: "STEP-1",
    basis: "user_confirmation_required",
    severity: "blocking",
    display_text: "需要确定参数 P_0。",
    target: targetParameter,
    obligation_kind: "determine_parameter_value",
    ...overrides,
  };
}

test("effective source display keeps only original document evidence green", () => {
  assert.equal(
    sourceDisplayForDetail({
      basis: "document_extracted",
      hasEvidence: true,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).rank,
    "paper-original",
  );
  assert.equal(
    sourceDisplayForDetail({
      basis: "document_derived",
      hasEvidence: true,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).rank,
    "paper-derived",
  );
  assert.notEqual(
    sourceDisplayForDetail({
      basis: "document_derived",
      hasEvidence: true,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).tone,
    "original",
  );
  assert.equal(
    sourceDisplayForDetail({
      basis: "document_extracted",
      hasEvidence: false,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).label,
    "来源信息不完整",
  );
});

test("unverified, unknown, and retired basis values resolve honestly", () => {
  assert.equal(
    sourceDisplayForDetail({
      basis: "document_claim_unverified",
      hasEvidence: true,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).label,
    "出处待核",
  );
  assert.equal(
    sourceDisplayForDetail({
      basis: "document_extracted",
      hasEvidence: true,
      confirmationReasonCode: "document_evidence_unverified",
      prefixMismatch: false,
    }).label,
    "出处待核",
  );
  assert.equal(
    sourceDisplayForDetail({
      basis: "unknown_basis",
      hasEvidence: false,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).label,
    "来源待核",
  );
  assert.equal(
    sourceDisplayForDetail({
      basis: "engineering_convention",
      hasEvidence: false,
      confirmationReasonCode: null,
      prefixMismatch: false,
    }).label,
    "工程设定",
  );
});

test("display text strips only matching full-width prefixes and known punt tails", () => {
  const cleaned = cleanGuidanceDisplayText(
    "论文明确给出：参数 P_0 = [1, D/(2H)]；原因：source_does_not_specify。",
    "document_extracted",
  );
  assert.equal(cleaned.text, "参数 P_0 = [1, D/(2H)]");
  assert.equal(cleaned.prefixMismatch, false);

  const mismatch = cleanGuidanceDisplayText("论文明确给出：Kp 取值。", "engineering_choice");
  assert.equal(mismatch.prefixMismatch, true);
  assert.equal(mismatch.text, "论文明确给出：Kp 取值。");

  const untouched = cleanGuidanceDisplayText(
    "参数 P_0 和数组 [0,1,2,10,20] 保持原样。",
    "document_extracted",
  );
  assert.equal(untouched.text, "参数 P_0 和数组 [0,1,2,10,20] 保持原样。");

  const normalReason = cleanGuidanceDisplayText(
    "正文说明原因：source_does_not_specify 只是样例,不是尾部机器码。",
    "document_extracted",
  );
  assert.equal(
    normalReason.text,
    "正文说明原因：source_does_not_specify 只是样例,不是尾部机器码。",
  );

  assert.equal(cleanGuidanceDisplayText("论文明确给出：", "document_extracted").text, "此条建议内容未完整生成");
});

test("confirmation reasons cover the 12-value table and hide raw unknown codes", () => {
  assert.equal(CONFIRMATION_REASON_CODES.length, 12);
  assert.deepEqual(
    Object.keys(CONFIRMATION_REASON_TEXT).sort(),
    [...CONFIRMATION_REASON_CODES].sort(),
  );
  assert.equal(
    confirmationReasonText("missing_parameter_value", targetParameter),
    "需要确认 参数 P_0 -> Kp 的参数值；请查看可复现实验材料或本地模型设置。",
  );
  assert.equal(
    confirmationReasonText("document_evidence_unverified", null),
    "需要确认 该项；该条声称的论文依据未能核实。",
  );
  const unknown = confirmationReasonText("mystery_code", targetParameter);
  assert.equal(unknown, "系统未能识别具体确认原因,请按上文内容核对");
  assert(!unknown?.includes("mystery_code"));
});

test("grouping preserves detail and gap counts including unmatched step ids", () => {
  const plan = {
    guidance_status: "generated",
    build_guidance: {
      details: [
        detail(),
        detail({
          detail_id: "GD-002",
          step_id: "STEP-MISSING",
          target: targetConnection,
          obligation_kind: "connect_signal",
          detail_kind: "connection",
        }),
      ],
      gaps: [
        gap(),
        gap({
          gap_id: "GAP-002",
          step_id: "STEP-MISSING",
          target: targetConnection,
          obligation_kind: "connect_signal",
          gap_kind: "missing_connection_detail",
        }),
      ],
    },
  };

  const model = buildGuidanceDisplayModel(plan as never, [{ step_id: "STEP-1" }]);
  assert.equal(model.counts.details, 2);
  assert.equal(model.counts.gaps, 2);
  assert.equal(model.counts.inputTotal, 4);
  assert.equal(model.counts.visibleTotal, 4);
  assert.equal(model.stepBuckets.get("STEP-1")?.totalCount, 2);
  assert.equal(model.looseBucket.totalCount, 2);

  const firstGroup = model.stepBuckets.get("STEP-1")?.groups[0];
  assert.equal(firstGroup?.detailCount, 1);
  assert.equal(firstGroup?.gapCount, 1);
});

test("all guidance moves to the global bucket when no structured steps are available", () => {
  const model = buildGuidanceDisplayModel(
    {
      guidance_status: "generated",
      build_guidance: {
        details: [detail()],
        gaps: [gap()],
      },
    } as never,
    [],
  );
  assert.equal(model.looseBucket.totalCount, 2);
  assert.equal(model.counts.inputTotal, model.counts.visibleTotal);
});

test("stale snapshot gaps with missing step references stay visible globally", () => {
  const model = buildGuidanceDisplayModel(
    {
      guidance_status: "stale_pending_regeneration",
      build_guidance: {
        details: [detail()],
        gaps: [
          gap({ gap_id: "GAP-STALE", step_id: "STEP-STALE" }),
          gap({ gap_id: "GAP-GLOBAL", step_id: null }),
        ],
      },
    } as never,
    [{ step_id: "STEP-1" }],
  );
  const looseItems = model.looseBucket.groups.flatMap((group) => group.items);

  assert.equal(model.counts.details, 1);
  assert.equal(model.counts.gaps, 2);
  assert.equal(model.counts.inputTotal, 3);
  assert.equal(model.counts.visibleTotal, 3);
  assert.equal(model.stepBuckets.get("STEP-1")?.totalCount, 1);
  assert.equal(model.looseBucket.totalCount, 2);
  assert.deepEqual(
    looseItems.map((item) => item.id).sort(),
    ["GAP-GLOBAL", "GAP-STALE"],
  );
});

test("malformed arrays remain visible and non-array collections show a format notice", () => {
  const model = buildGuidanceDisplayModel(
    {
      guidance_status: "generated",
      build_guidance: {
        details: [null],
        gaps: "not-an-array",
      },
    } as never,
    [{ step_id: "STEP-1" }],
  );
  assert.equal(model.dataNotice, "部分指导数据格式不完整");
  assert.equal(model.looseBucket.totalCount, 1);
  assert.equal(model.looseBucket.groups[0]?.items[0]?.text, "部分指导数据格式不完整");
});

test("empty states are status-specific", () => {
  const statuses = new Map([
    ["no_document_basis", "未从论文中形成可定位的逐条建议;现有搭建路线仍可参考。"],
    ["not_generated", "逐条建模建议尚未生成。"],
    ["generation_failed", "本次逐条建议未生成成功,现有步骤已保留。"],
    ["stale_pending_regeneration", "建议基于旧版本,等待更新。"],
    ["generated", "指导数据不完整。"],
  ]);
  for (const [status, text] of statuses) {
    const model = buildGuidanceDisplayModel(
      { guidance_status: status, build_guidance: { details: [], gaps: [] } } as never,
      [{ step_id: "STEP-1" }],
    );
    assert.equal(model.statusText, text);
  }
});

test("evidence chips keep excerpts primary and expose every entry", () => {
  const source = sourceDisplayForDetail({
    basis: "document_extracted",
    hasEvidence: true,
    confirmationReasonCode: null,
    prefixMismatch: false,
  });
  const display = evidenceDisplayForDetail(source, [
    evidence,
    {
      ...evidence,
      document_id: "DOC-002",
      paper_section_id: null,
      equation_id: null,
      excerpt: "A second excerpt.",
    },
  ]);
  assert.equal(display?.title, "论文摘录");
  assert.equal(display?.summary, "2 条依据");
  assert.equal(display?.chips.length, 2);
  assert.equal(display?.chips[0]?.excerpt, "The paper states the controller gain.");
  assert.equal(display?.chips[1]?.locatorText, "文档 DOC-002");
  assert(!display?.chips.some((chip) => chip.locatorText.includes("已定位到具体出处")));
});

for (const item of tests) {
  item.run();
}

console.log(`task538b substrate tests passed (${tests.length} tests)`);
