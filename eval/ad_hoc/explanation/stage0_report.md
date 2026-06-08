# TASK-308 Stage 0 Report (PR #60 first baton)

- task_version: v0.2.3
- run_id: ad_hoc_20260608_024454
- evidence_pack_paths:
  - 01_ee_a: eval/ad_hoc/explanation/01_ee_a/evidence_pack.json
  - 02_ee_b: eval/ad_hoc/explanation/02_ee_b/evidence_pack.json
  - 03_ee_c: eval/ad_hoc/explanation/03_ee_c/evidence_pack.json
  - 04_ee_d: eval/ad_hoc/explanation/04_ee_d/evidence_pack.json

## Checkpoints

| checkpoint | status | note |
|---|---|---|
| #1 | PASS | features/explanation/ created; no pre-existing conflict. |
| #2 | PASS | file_path,line_range,block_id,block_name,parent_subsystem,parameter_name |
| #3 | PASS | 01_ee_a:blocks=461,chunks=491; 02_ee_b:blocks=391,chunks=399; 03_ee_c:blocks=789,chunks=816; 04_ee_d:blocks=126,chunks=134 |
| #4 | PASS | E1 category distribution + high-frequency unclassified types recorded; not a boolean gate in v0.2.3. |
| #5 | PASS | Ambiguous naming report-only; all projects nonzero, no PM stop. |
| #6 | PASS | D3 selected_count=40 for all projects; L1 raw ratios below 95%; each top layer has 5+ candidates. |
| #OV | PASS | Average overview score is >=1.0 for all projects; recommendation: weak_hint_only. |
| #LLM_EST | PASS | token_est_total=316515; per_project=[80020, 80655, 80360, 75480] |
| #ATTR | PASS | 9 failed/fallback records attributed; distribution={'prompt_failure': 1, 'parameter_context_missing': 3, 'topology_missing': 5} |
| #11 | PASS | eval/ad_hoc/explanation/ created as untracked local artifact directory. |
| #12 | PASS | 01_ee_a, 02_ee_b, 03_ee_c, 04_ee_d |
| #13 | PASS | Stop after PR #60 ready for PM overview/EvidenceBuilder coverage review; no second baton work started. |
| #14 | PASS | no absolute paths or standalone 10+ digit id patterns in evidence packs |

## #4 / #5 / #6 Metrics

### 01_ee_a
- blocks: 461; chunks: 491
- E1 categories: {"power": 8, "unclassified": 78, "measurement": 13, "routing": 186, "input_source": 68, "math_control": 108}
- high-frequency unclassified: [["SubSystem", 34], ["Discrete 2nd-Order Filter", 14], ["abc to dq0 Transformation", 4], ["RelationalOperator", 4], ["Trigonometry", 3], ["Discrete Variable-Frequency Mean Value", 2], ["Discrete SV PWM Generator", 2], ["Cart2Polar", 2], ["Polar2Cart", 2], ["Logic", 2], ["Three-Phase Programmable Voltage Source", 1], ["Three-Phase Series RLC Load", 1]]
- ambiguous: {"count": 294, "ratio": 0.6377, "ambiguous_high_value_count": 292, "ambiguous_high_value_ratio": 0.6334}
- D3 raw layers: {"L1": 59, "L2": 379, "L3": 104, "L4": 48, "L5": 292, "L6": 135, "total_blocks": 461}
- D3 top layers: {"L1": 10, "L2": 10, "L3": 5, "L4": 8, "L5": 5, "L6": 5}; selected=40; L1 raw ratio=0.128
- score distribution: {"topology": {"min": 0.143, "median": 0.429, "max": 1.0}, "rarity": {"min": 0.844, "median": 0.965, "max": 0.998}, "clarity": {"min": 0.0, "median": 1.0, "max": 1.0}, "parameter": {"min": 0.0, "median": 0.6, "max": 1.0}, "keyword": {"min": 0.0, "median": 1.0, "max": 1.0}, "total": {"min": 2.781, "median": 3.534, "max": 4.569}}

### 02_ee_b
- blocks: 391; chunks: 399
- E1 categories: {"math_control": 62, "measurement": 24, "input_source": 59, "unclassified": 89, "routing": 144, "power": 13}
- high-frequency unclassified: [["SubSystem", 22], ["MultimeterPSB", 19], ["DataTypeConversion", 18], ["S-Function", 12], ["Half-Bridge MMC", 6], ["PWM Generator (Multilevel)", 6], ["Rounding", 3], ["Ground", 2], ["PSB option menu block", 1]]
- ambiguous: {"count": 297, "ratio": 0.7596, "ambiguous_high_value_count": 296, "ambiguous_high_value_ratio": 0.757}
- D3 raw layers: {"L1": 87, "L2": 318, "L3": 100, "L4": 55, "L5": 296, "L6": 6, "total_blocks": 391}
- D3 top layers: {"L1": 10, "L2": 10, "L3": 5, "L4": 8, "L5": 5, "L6": 5}; selected=40; L1 raw ratio=0.2225
- score distribution: {"topology": {"min": 0.024, "median": 0.071, "max": 1.0}, "rarity": {"min": 0.944, "median": 0.985, "max": 0.985}, "clarity": {"min": 0.0, "median": 0.5, "max": 1.0}, "parameter": {"min": 0.6, "median": 1.0, "max": 1.0}, "keyword": {"min": 0.0, "median": 0.0, "max": 0.5}, "total": {"min": 2.156, "median": 2.568, "max": 3.556}}

### 03_ee_c
- blocks: 789; chunks: 816
- E1 categories: {"unclassified": 147, "power": 7, "measurement": 8, "routing": 272, "input_source": 127, "math_control": 228}
- high-frequency unclassified: [["SubSystem", 46], ["Trigonometry", 16], ["RelationalOperator", 14], ["Logic", 7], ["DataTypeConversion", 5], ["Cart2Polar", 5], ["Discrete PI Controller", 5], ["Math", 5], ["Discrete 1st-Order Filter", 5], ["abc to dq0 Transformation", 5], ["EnablePort", 4], ["MinMax", 4]]
- ambiguous: {"count": 564, "ratio": 0.7148, "ambiguous_high_value_count": 556, "ambiguous_high_value_ratio": 0.7047}
- D3 raw layers: {"L1": 29, "L2": 653, "L3": 146, "L4": 128, "L5": 556, "L6": 264, "total_blocks": 789}
- D3 top layers: {"L1": 10, "L2": 10, "L3": 5, "L4": 8, "L5": 5, "L6": 5}; selected=40; L1 raw ratio=0.0368
- score distribution: {"topology": {"min": 0.062, "median": 0.188, "max": 0.625}, "rarity": {"min": 0.867, "median": 0.98, "max": 0.999}, "clarity": {"min": 0.0, "median": 1.0, "max": 1.0}, "parameter": {"min": 0.0, "median": 0.8, "max": 1.0}, "keyword": {"min": 0.5, "median": 1.0, "max": 1.0}, "total": {"min": 2.599, "median": 3.524, "max": 4.179}}

### 04_ee_d
- blocks: 126; chunks: 134
- E1 categories: {"unclassified": 25, "measurement": 6, "power": 6, "routing": 58, "input_source": 13, "math_control": 18}
- high-frequency unclassified: [["SubSystem", 8], ["abc to dq0 Transformation", 2], ["Second-Order Filter", 2], ["Three-Phase Mutual Inductance Z1-Z0", 1], ["Three-Phase Programmable Voltage Source", 1], ["Three-Phase Series RLC Load", 1], ["Ground", 1], ["Multimeter", 1], ["PSB option menu block", 1], ["PLL (3ph)", 1], ["Power (dq0, Instantaneous)", 1], ["PWM Generator (2-Level)", 1]]
- ambiguous: {"count": 83, "ratio": 0.6587, "ambiguous_high_value_count": 79, "ambiguous_high_value_ratio": 0.627}
- D3 raw layers: {"L1": 18, "L2": 101, "L3": 33, "L4": 14, "L5": 79, "L6": 58, "total_blocks": 126}
- D3 top layers: {"L1": 10, "L2": 10, "L3": 5, "L4": 8, "L5": 5, "L6": 5}; selected=40; L1 raw ratio=0.1429
- score distribution: {"topology": {"min": 0.167, "median": 0.417, "max": 1.0}, "rarity": {"min": 0.849, "median": 0.968, "max": 0.992}, "clarity": {"min": 0.0, "median": 0.25, "max": 1.0}, "parameter": {"min": 0.0, "median": 0.6, "max": 1.0}, "keyword": {"min": 0.0, "median": 0.5, "max": 1.0}, "total": {"min": 2.543, "median": 3.181, "max": 4.159}}

## #OV ProjectOverview Quality

| alias | average | tier | scores |
|---|---:|---|---|
| 01_ee_a | 1.2 | weak_hint_only | {"one_sentence_summary": 1, "main_execution_flow": 1, "key_blocks.why_key": 1, "beginner_reading_order": 2, "likely_confusing_points": 1} |
| 02_ee_b | 1.2 | weak_hint_only | {"one_sentence_summary": 1, "main_execution_flow": 1, "key_blocks.why_key": 1, "beginner_reading_order": 2, "likely_confusing_points": 1} |
| 03_ee_c | 1.2 | weak_hint_only | {"one_sentence_summary": 1, "main_execution_flow": 1, "key_blocks.why_key": 1, "beginner_reading_order": 2, "likely_confusing_points": 1} |
| 04_ee_d | 1.2 | weak_hint_only | {"one_sentence_summary": 1, "main_execution_flow": 1, "key_blocks.why_key": 1, "beginner_reading_order": 2, "likely_confusing_points": 1} |

Recommendation: use ProjectOverview only as weak overview_hint in PR #61; do not rely on a single project_overview_field evidence item for parameter_reason / connection_logic / modification_advice claims.

## #LLM_EST EvidencePack Budget

| alias | evidence_count | chars | token_estimate | kind_counts |
|---|---:|---:|---:|---|
| 01_ee_a | 209 | 235943 | 80020 | {"project_overview_field": 5, "slx_block": 40, "parameter": 73, "measurement": 3, "bus_signal": 7, "subsystem": 12, "slx_line": 60, "simulink_caveat": 9} |
| 02_ee_b | 213 | 237849 | 80655 | {"project_overview_field": 5, "slx_block": 40, "parameter": 80, "measurement": 6, "goto_from_tag": 5, "subsystem": 8, "slx_line": 60, "simulink_caveat": 9} |
| 03_ee_c | 204 | 236962 | 80360 | {"project_overview_field": 5, "slx_block": 40, "parameter": 70, "measurement": 2, "bus_signal": 3, "goto_from_tag": 2, "scope": 1, "subsystem": 12, "slx_line": 60, "simulink_caveat": 9} |
| 04_ee_d | 203 | 222323 | 75480 | {"project_overview_field": 5, "slx_block": 40, "parameter": 72, "bus_signal": 4, "goto_from_tag": 2, "measurement": 2, "scope": 1, "subsystem": 8, "slx_line": 60, "simulink_caveat": 9} |

Total estimated tokens: 316515 / 400000. Heuristic: ceil((EvidencePack JSON chars + prompt chars + 2000 overhead) / 3).

## #ATTR Failure Attribution

- run_metadata: success=59, failures=1, fallback=8, answer_rows=60
- attribution_distribution: {"prompt_failure": 1, "parameter_context_missing": 3, "topology_missing": 5}

| case_id | project | question_type | primary_attribution | runtime_reason |
|---|---|---|---|---|
| 01_ee_a_005 | 01_ee_a | 总体 | prompt_failure | parse_validation_error |
| 01_ee_a_015 | 01_ee_a | 修改 | parameter_context_missing | invalid_or_missing_citations |
| 02_ee_b_002 | 02_ee_b | 总体 | topology_missing | invalid_or_missing_citations |
| 02_ee_b_004 | 02_ee_b | 总体 | topology_missing | invalid_or_missing_citations |
| 02_ee_b_007 | 02_ee_b | 模块 | topology_missing | invalid_or_missing_citations |
| 02_ee_b_010 | 02_ee_b | 模块 | topology_missing | invalid_or_missing_citations |
| 02_ee_b_012 | 02_ee_b | 参数 | parameter_context_missing | invalid_or_missing_citations |
| 03_ee_c_002 | 03_ee_c | 总体 | topology_missing | invalid_or_missing_citations |
| 04_ee_d_013 | 04_ee_d | 参数 | parameter_context_missing | invalid_or_missing_citations |

## Privacy Gate

- evidence_pack scan: PASS
- final grep gate: PASS(no private absolute paths or standalone 10+ digit id patterns).
