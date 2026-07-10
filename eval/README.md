# eval/ - QA Prompt 评测体系(TASK-306 评测框架)

本目录是 TASK-306 建立的 QA prompt 评测基础设施。

## 当前状态

**评测框架已完工**(feat/task-306-impl PR merge);**真实评分待 306b 接力**。

当前入仓的 4 个 fixture 是 MATLAB 官方 demo,不是真专家工程。正式评测产物(raw CSV / scored / final / report)在 306b 阶段产出。

## 目录结构

- `_bootstrap.py` - eval ChatService 装配 + 4 层 wrapper(RecordingRetriever / RecordingTextProvider / RecordingPromptBuilder / PromptLoader)+ loaded-version audit + db_path override
- `run_eval.py` - 评测 CLI;baseline 与 rc 各跑一轮,产 raw CSV
- `make_scoring_queue.py` - 半盲化 CLI;raw -> scoring_queue + scoring_unblind_key + scoring_project_key
- `finalize_scores.py` - 两阶段 CLI;第一阶段产 adjudication_queue,第二阶段产 final_merged
- `scoring_guide.md` - 评分员指南(5 维度 100 分 + edge case + adjudication 流程)
- `project_map.template.json` - 4 fixture 入仓稳定信息(PM gate 拍板;runtime_project_id 不入此文件)
- `baselines/qa_v0.1.yaml` - TASK-305 修改前的 v0.1 baseline prompt(机械 git 提取)
- `cases/<alias>/` - 4 fixture(zip 形态)+ questions.jsonl(每工程 17 题:5 overall + 5 module + 3 param + 2 modify + 2 edge)
- `results/<run_id>/` - eval db + manifest + resolved + raw + scored + final 等评测产物;`.gitignore` 排除 `eval.sqlite`

## 如何使用(306b 阶段)

参考 `docs/tasks/task-306-v0_1.md` 给 Codex 的提示。

完整流程:

1. PM 替换 fixture:`tests/fixtures/slx_samples/` 入仓真实专家工程 zip -> cp 到 `eval/cases/<alias>/`
2. PM + Codex 重写 questions.jsonl(题目贴新 fixture 实际结构)
3. Codex 跑 #13c 重新灌 eval db
4. Codex 跑 `run_eval.py`(baseline + rc 各一轮)
5. Codex 跑 `make_scoring_queue.py`
6. **PM + 领域专家半盲打分**(`scoring_queue_scored_PM.csv` + `_reviewer.csv`)
7. Codex 跑 `finalize_scores.py` 第一阶段(若有 adjudication required -> 退出码 2)
8. 若需要 adjudication:adjudicator 填 `adjudication_resolved.csv` -> 跑第二阶段
9. Codex 写 `docs/eval/reports/<date>-qa-v0.2rc-eval.md`
10. PM 拍板 v0.2 final / 回滚 / v0.3

## 当前 fixture chunk_count(20260607_205221_fixture_bootstrap)

- `pmsm_foc_c2000`:1831(TI C2000 SDK 完整工程)
- `buck_voltage_control`:66
- `pid_antiwindup`:33
- `lms_noise_cancel`:61

## 关键设计参考

任务卡 `docs/tasks/task-306-v0_1.md`:

- D4 direct ChatService + `eval/_bootstrap.py`(不走 HTTP)
- D7 raw CSV 39 字段
- D8 评分 CSV 三层 + adjudication 两阶段
- D12 生产 Python 零变更(本 PR 验证 OK)
- R4-P0-1 RecordingPromptBuilder citation 评分唯一真值源
- R4-P0-2 scoring_queue 保留 `project_alias` + `scoring_project_key` 提供工程上下文
- R4-P0-3 finalize 两阶段(`unresolved_adjudication_count == 0` 才生 final)
- R4-P0-4 #13c eval db fixture bootstrap + `eval_db_build_manifest.json`
- R4b 必改:Recording wrappers 生命周期内持续存在;`source_table_capture_mode` 2 enum;`citation_type_available_rate` 守门

## paper-to-model 本地 PDF smoke lane

`run_paper_pdf_smoke.py` 是本地真机 smoke lane,与 `eval/cases/paper_to_model/`
里的 stripped-md golden 回归并存,默认不进 CI。它从本地论文目录读取 PDF,逐篇走同步
`upload-document` 主路:upload → parse → spec → plan → guidance。运行时使用
`eval/out/paper_pdf_smoke/<run_id>/_runtime/` 下的临时 SQLite DB 和临时上传目录,
不会触碰 `data/mxa.db`;actual 与 summary 也落在 `eval/out/`,该目录已被 `.gitignore`
排除。

论文目录通过 `PAPER_EVAL_DIR` 或 `--paper-dir` 配置;未配置时默认 `E:\桌面\样例`。
单篇单轮约 8-9 分钟,默认 `--rounds 1`,需要量方差时再手动调高。

示例:

```powershell
$env:PAPER_EVAL_DIR = 'E:\桌面\样例'
python eval/run_paper_pdf_smoke.py --rounds 1
```

输出:

- `paper_pdf_smoke.summary.json`
- `paper_pdf_smoke.summary.csv`
- `actual/*.actual.json`

summary 固定字段包含主路终态、build_steps 结果码、build_steps finish_reason 与 token/上限、
guidance 是否触达与结果、`dto_invalid` 的脱敏 Pydantic `(loc,type)`,以及混合型候选论文的
`no_document_basis` 护栏专项结论。CI 中默认拒绝真实运行;测试只 mock harness 管路,不跑 LLM
或真实 PDF parse。
