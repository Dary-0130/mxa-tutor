import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const adHoc = path.join(root, "eval", "ad_hoc");
const recordsPath = path.join(adHoc, "answer_records.jsonl");
const metadataPath = path.join(adHoc, "run_metadata.json");
const xlsxPath = path.join(adHoc, "results_scoring.xlsx");
const csvPath = path.join(adHoc, "results_scoring.csv");
const mdPath = path.join(adHoc, "results_compact.md");
const previewDir = path.join(adHoc, "table_previews");

const aliases = ["01_ee_a", "02_ee_b", "03_ee_c", "04_ee_d"];
const scoreHeaders = [
  "Project",
  "Case ID",
  "Type",
  "Confidence",
  "Citation Count",
  "Status",
  "Question",
  "Answer",
  "Evidence Summary",
  "PM Fact /30",
  "PM Citation /20",
  "PM Teaching /20",
  "PM Actionable /20",
  "PM No Fabrication /10",
  "PM Total",
  "PM Notes",
  "Student Fact /30",
  "Student Citation /20",
  "Student Teaching /20",
  "Student Actionable /20",
  "Student No Fabrication /10",
  "Student Total",
  "Student Notes",
  "Average Total",
  "Review Flag",
];

const detailHeaders = [
  "Case ID",
  "Type",
  "Confidence",
  "Citation Count",
  "Status",
  "Question",
  "Answer",
  "Evidence Summary",
  "PM Total",
  "Student Total",
  "Average Total",
];

function readJsonl(text) {
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function oneLine(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim();
}

function truncate(text, maxChars) {
  const clean = oneLine(text);
  return clean.length > maxChars ? `${clean.slice(0, maxChars - 1)}…` : clean;
}

function statusOf(record) {
  if (record.error_type) return `ERROR: ${record.error_type}`;
  if (record.is_fallback) return `FALLBACK: ${record.fallback_reason || "unknown"}`;
  return "OK";
}

function evidenceSummary(record, maxChars = 900) {
  const parts = (record.citations || []).map((citation, index) => {
    const ref = citation.source_ref || {};
    const symbol = ref.block_name || ref.parameter_name || "__project_overview__";
    const snippet = truncate(citation.snippet || "", 120);
    return `[${index + 1}] ${citation.source_type || "unknown"} | ${ref.file_path || ""} | ${symbol} | ${snippet}`;
  });
  return truncate(parts.join("\n"), maxChars);
}

function scoringRow(record, rowNumber) {
  const pmTotal = `=IF(COUNT(J${rowNumber}:N${rowNumber})=0,"",SUM(J${rowNumber}:N${rowNumber}))`;
  const studentTotal = `=IF(COUNT(Q${rowNumber}:U${rowNumber})=0,"",SUM(Q${rowNumber}:U${rowNumber}))`;
  const averageTotal = `=IF(OR(O${rowNumber}="",V${rowNumber}=""),"",AVERAGE(O${rowNumber},V${rowNumber}))`;
  const reviewFlag = `=IF(OR(O${rowNumber}="",V${rowNumber}=""),"",IF(ABS(O${rowNumber}-V${rowNumber})>=20,"协调",""))`;
  return [
    record.project_alias,
    record.case_id,
    record.question_type,
    record.confidence || "error",
    (record.citations || []).length,
    statusOf(record),
    record.question,
    record.answer,
    evidenceSummary(record),
    "",
    "",
    "",
    "",
    "",
    pmTotal,
    "",
    "",
    "",
    "",
    "",
    "",
    studentTotal,
    "",
    averageTotal,
    reviewFlag,
  ];
}

function detailRow(record) {
  return [
    record.case_id,
    record.question_type,
    record.confidence || "error",
    (record.citations || []).length,
    statusOf(record),
    record.question,
    record.answer,
    evidenceSummary(record),
    "",
    "",
    "",
  ];
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function columnLetter(index) {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    out = String.fromCharCode(65 + rem) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

function writeTable(sheet, startCell, headers, rows, tableName) {
  const matrix = [headers, ...rows];
  const range = sheet.getRangeByIndexes(0, 0, matrix.length, headers.length);
  range.values = matrix;
  const lastCol = columnLetter(headers.length - 1);
  const table = sheet.tables.add(`${startCell}:${lastCol}${matrix.length}`, true, tableName);
  table.showFilterButton = true;
  table.showBandedColumns = false;
  return { range, table };
}

function styleHeader(sheet, colCount) {
  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
}

function styleSheetBasics(sheet, rowCount, colCount) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getRangeByIndexes(0, 0, rowCount, colCount);
  used.format = {
    font: { name: "Arial", size: 10 },
    wrapText: true,
    verticalAlignment: "top",
  };
  used.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  styleHeader(sheet, colCount);
}

function setScoringWidths(sheet) {
  const widths = [
    88, 118, 64, 86, 92, 128, 360, 520, 430, 84, 96, 96, 108, 126, 84, 180, 104, 118, 118, 130, 154, 104, 190, 108, 90,
  ];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 61, 1).format.columnWidthPx = width;
  });
  sheet.getRange("A1:Y61").format.rowHeightPx = 72;
  sheet.getRange("A1:Y1").format.rowHeightPx = 36;
}

function setDetailWidths(sheet, rowCount) {
  const widths = [118, 64, 86, 92, 128, 390, 540, 430, 90, 110, 110];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, rowCount, 1).format.columnWidthPx = width;
  });
  sheet.getRangeByIndexes(0, 0, rowCount, 11).format.rowHeightPx = 78;
  sheet.getRange("A1:K1").format.rowHeightPx = 36;
}

function safeSheetName(alias) {
  return alias.replaceAll("_", "-");
}

function makeMarkdown(records, metadata) {
  const lines = [
    `# mxa 评测结果紧凑版(${metadata.run_id})`,
    "",
    `- 模型:${metadata.model_name}`,
    `- 成功:${metadata.success_count}/${metadata.question_count}`,
    `- 失败:${metadata.failure_count}`,
    `- fallback:${metadata.fallback_count}`,
    "",
    "## 总览",
    "",
    "| 工程 | 题数 | high | medium | low | error | fallback | 失败题 |",
    "|---|---:|---:|---:|---:|---:|---:|---|",
  ];
  for (const alias of aliases) {
    const subset = records.filter((record) => record.project_alias === alias);
    const conf = countBy(subset, (record) => record.confidence || "error");
    const failures = subset.filter((record) => record.error_type).map((record) => record.case_id);
    lines.push(
      `| ${alias} | ${subset.length} | ${conf.high || 0} | ${conf.medium || 0} | ${conf.low || 0} | ${conf.error || 0} | ${subset.filter((record) => record.is_fallback).length} | ${failures.join(", ") || "-"} |`,
    );
  }
  lines.push("");

  for (const alias of aliases) {
    lines.push(`## ${alias}`, "");
    lines.push("| Case | 类型 | Conf | 引用 | 状态 | 题目 | 答案预览 |");
    lines.push("|---|---|---|---:|---|---|---|");
    for (const record of records.filter((item) => item.project_alias === alias)) {
      lines.push(
        `| ${record.case_id} | ${record.question_type} | ${record.confidence || "error"} | ${(record.citations || []).length} | ${statusOf(record)} | ${escapeMd(record.question)} | ${escapeMd(truncate(record.answer, 180))} |`,
      );
    }
    lines.push("");
    for (const record of records.filter((item) => item.project_alias === alias)) {
      lines.push(`<details><summary>${record.case_id} — ${record.question_type} — ${record.confidence || "error"}</summary>`);
      lines.push("");
      lines.push(`**题目**: ${record.question}`);
      lines.push("");
      lines.push("**答案**:");
      lines.push("");
      lines.push(record.answer);
      lines.push("");
      lines.push("**证据摘要**:");
      lines.push("");
      lines.push(evidenceSummary(record, 1400) || "无");
      lines.push("");
      lines.push("| 评分人 | 事实/30 | 引用/20 | 教学/20 | 可操作/20 | 不编造/10 | 总分 | 备注 |");
      lines.push("|---|---:|---:|---:|---:|---:|---:|---|");
      lines.push("| PM |  |  |  |  |  |  |  |");
      lines.push("| 研究生 |  |  |  |  |  |  |  |");
      lines.push("");
      lines.push("</details>");
      lines.push("");
    }
  }
  return `${lines.join("\n").trim()}\n`;
}

function escapeMd(text) {
  return oneLine(text).replaceAll("|", "\\|");
}

function countBy(rows, fn) {
  const counts = {};
  for (const row of rows) {
    const key = fn(row);
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

async function main() {
  const records = readJsonl(await fs.readFile(recordsPath, "utf8"));
  const metadata = JSON.parse(await fs.readFile(metadataPath, "utf8"));
  await fs.mkdir(previewDir, { recursive: true });

  const scoringRows = records.map((record, index) => scoringRow(record, index + 2));
  const csvRows = [scoreHeaders, ...scoringRows.map((row) => row.map((value) => String(value).startsWith("=") ? "" : value))];
  await fs.writeFile(csvPath, csvRows.map((row) => row.map(csvEscape).join(",")).join("\n") + "\n", "utf8");
  await fs.writeFile(mdPath, makeMarkdown(records, metadata), "utf8");

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  const scoring = workbook.worksheets.add("Scoring");

  const confidenceCounts = countBy(records, (record) => record.confidence || "error");
  const typeCounts = countBy(records, (record) => record.question_type);
  const summaryRows = [
    ["Metric", "Value"],
    ["Run ID", metadata.run_id],
    ["Model", metadata.model_name],
    ["Prompt Version", metadata.prompt_version],
    ["Questions", metadata.question_count],
    ["Success", metadata.success_count],
    ["Failures", metadata.failure_count],
    ["Fallback", metadata.fallback_count],
    ["High Confidence", confidenceCounts.high || 0],
    ["Medium Confidence", confidenceCounts.medium || 0],
    ["Low Confidence", confidenceCounts.low || 0],
    ["Error", confidenceCounts.error || 0],
    ["Started", metadata.started_at],
    ["Ended", metadata.ended_at],
  ];
  summary.getRangeByIndexes(0, 0, summaryRows.length, 2).values = summaryRows;
  summary.getRange("A1:B1").format = { fill: "#1F4E79", font: { bold: true, color: "#FFFFFF" } };
  summary.getRange("A1:B14").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  summary.getRange("A:A").format.columnWidthPx = 160;
  summary.getRange("B:B").format.columnWidthPx = 260;
  summary.showGridLines = false;

  const distributionStart = 17;
  const distribution = [["Project", "Total", "总体", "模块", "参数", "修改", "High", "Medium", "Low", "Error", "Fallback"]];
  for (const alias of aliases) {
    const subset = records.filter((record) => record.project_alias === alias);
    const byType = countBy(subset, (record) => record.question_type);
    const byConf = countBy(subset, (record) => record.confidence || "error");
    distribution.push([
      alias,
      subset.length,
      byType["总体"] || 0,
      byType["模块"] || 0,
      byType["参数"] || 0,
      byType["修改"] || 0,
      byConf.high || 0,
      byConf.medium || 0,
      byConf.low || 0,
      byConf.error || 0,
      subset.filter((record) => record.is_fallback).length,
    ]);
  }
  summary.getRangeByIndexes(distributionStart - 1, 0, distribution.length, distribution[0].length).values = distribution;
  summary.getRangeByIndexes(distributionStart - 1, 0, 1, distribution[0].length).format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
  };
  summary.getRangeByIndexes(distributionStart - 1, 0, distribution.length, distribution[0].length).format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9E2F3",
  };
  for (let col = 0; col < distribution[0].length; col += 1) {
    summary.getRangeByIndexes(distributionStart - 1, col, distribution.length, 1).format.columnWidthPx = col === 0 ? 110 : 78;
  }

  const failureRows = [["Case ID", "Error Type"], ...records.filter((record) => record.error_type).map((record) => [record.case_id, record.error_type])];
  summary.getRangeByIndexes(24, 0, failureRows.length, failureRows[0].length).values = failureRows;
  summary.getRange("A25:B25").format = { fill: "#7F1D1D", font: { bold: true, color: "#FFFFFF" } };
  summary.getRangeByIndexes(24, 0, failureRows.length, 2).format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };

  writeTable(scoring, "A1", scoreHeaders, scoringRows, "ScoringTable");
  styleSheetBasics(scoring, scoringRows.length + 1, scoreHeaders.length);
  setScoringWidths(scoring);
  scoring.getRange("D2:D61").conditionalFormats.add("containsText", { text: "low", format: { fill: "#FEF3C7" } });
  scoring.getRange("D2:D61").conditionalFormats.add("containsText", { text: "error", format: { fill: "#FCA5A5" } });
  scoring.getRange("F2:F61").conditionalFormats.add("containsText", { text: "ERROR", format: { fill: "#FCA5A5", font: { bold: true } } });
  scoring.getRange("F2:F61").conditionalFormats.add("containsText", { text: "FALLBACK", format: { fill: "#DBEAFE" } });

  const validations = [
    ["J2:J61", 0, 30],
    ["K2:N61", 0, 20],
    ["Q2:Q61", 0, 30],
    ["R2:U61", 0, 20],
  ];
  for (const [range, min, max] of validations) {
    scoring.getRange(range).dataValidation = {
      rule: { type: "whole", operator: "between", formula1: min, formula2: max },
    };
  }

  for (const alias of aliases) {
    const sheet = workbook.worksheets.add(safeSheetName(alias));
    const subset = records.filter((record) => record.project_alias === alias);
    writeTable(sheet, "A1", detailHeaders, subset.map(detailRow), `${alias.replaceAll("_", "")}Table`);
    styleSheetBasics(sheet, subset.length + 1, detailHeaders.length);
    setDetailWidths(sheet, subset.length + 1);
    sheet.getRange("C2:C16").conditionalFormats.add("containsText", { text: "low", format: { fill: "#FEF3C7" } });
    sheet.getRange("C2:C16").conditionalFormats.add("containsText", { text: "error", format: { fill: "#FCA5A5" } });
    sheet.getRange("E2:E16").conditionalFormats.add("containsText", { text: "ERROR", format: { fill: "#FCA5A5", font: { bold: true } } });
    sheet.getRange("E2:E16").conditionalFormats.add("containsText", { text: "FALLBACK", format: { fill: "#DBEAFE" } });
  }

  const inspection = await workbook.inspect({
    kind: "table",
    range: "Summary!A1:K29",
    tableMaxRows: 30,
    tableMaxCols: 12,
    tableMaxCellChars: 100,
    maxChars: 4000,
  });
  console.log(inspection.ndjson);
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 200 },
    summary: "formula error scan",
    maxChars: 2000,
  });
  console.log(errors.ndjson);

  for (const sheetName of ["Summary", "Scoring", ...aliases.map(safeSheetName)]) {
    const preview = await workbook.render({
      sheetName,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(previewDir, `${sheetName}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(xlsxPath);
  console.log(JSON.stringify({ xlsxPath, csvPath, mdPath, records: records.length }, null, 2));
}

await main();
