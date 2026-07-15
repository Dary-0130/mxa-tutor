# Task 538 v0.2 Stage-0 Disposition As Built

Base: `origin/main@05e23f8ed406d9f2713fe5d876e1f91424eef8e7` (`05e23f8 Implement task 537A mscript fate decoupling (#209)`)

Scope: backend five-stage release only. Frontend block 3, eval raw completion recorder block 4, mscript wrapper outcome logic, mscript wrapper wrapper behavior, parameter concatenation bug, and prompt changes are out of scope.

Contract resolutions applied in this PR:

- Mscript wrapper zero change: Task 538 propagation rules apply to content paths only. The mscript trinary outcome axis, leaf degradation set, primary failure-code precedence, and `CancelledError` / `KeyboardInterrupt` / `SystemExit` propagation remain as in 537-A. Protected baseline ranges: `features/paper/paper_plan_service.py:117-133`, `:202-221`, `:352-385`.
- Content-path propagation carve-out: `LLMAuthError`, provider configuration failures, and cancellation/base-exit errors propagate. Transient provider errors (`LLMTimeoutError`, `LLMRateLimitError`, `LLMServerError`) stay on retry/fallback paths. No new broad `except Exception` / `BaseException` branch is used for the carve-out.
- Guidance-only recovery seam remains block 3: this PR does not repair the current frontend/backend hole where `build_steps` exists but guidance generation failed. It only avoids creating new false-empty guidance in backend release gates.

Old-cache strategy: historical ready bundles with `build_steps=null` are not auto-migrated. They remain bounded as old records and require existing rerun/manual regeneration paths. SQLite DDL and public schema stay byte-stable.

## 47-Row Disposition Table

| # | Baseline file:line | Branch / risk | As-built disposition |
|---:|---|---|---|
| 1 | `features/paper/paper_plan_service.py:678` | build_steps top-level JSON not object/list | Bad JSON and top-level shape still fail into existing fallback, not 500. |
| 2 | `features/paper/paper_plan_service.py:678` | `build_steps=[]` | Still terminal `empty_steps`; no fabricated artifact. |
| 3 | `features/paper/paper_plan_service.py:678` | per-step DTO bad item | Bad item is degraded/dropped; remaining valid steps continue. |
| 4 | `features/paper/paper_plan_service.py:678` | nested block/parameter/connection/config DTO bad item | Bad nested item is dropped locally; parent step remains. |
| 5 | `features/paper/paper_plan_service.py:678` | model-owned extra fields | Unknown model fields are stripped and logged as metadata only. |
| 6 | `features/paper/paper_plan_service.py:678` | source_ref omitted/null/blank | Step/detail body remains; evidence entry or paper_reference is emptied. |
| 7 | `features/paper/paper_plan_service.py:678` | source_ref non-string | Same local evidence degradation; no whole-plan reject. |
| 8 | `features/paper/paper_plan_service.py:678` | source_ref no match | Same local evidence degradation; no fake verified-paper badge. |
| 9 | `features/paper/paper_plan_service.py:678` | source_ref ambiguous | Evidence is dropped locally; no copied ownership fields. |
| 10 | `features/paper/paper_plan_service.py:678` | source_ref valid but model also sends ownership fields | Backend rebuilds ownership from private reference; model-supplied ownership is ignored. |
| 11 | `features/paper/paper_plan_service.py:1004` | final evidence invalid | Invalid final evidence is dropped locally; remaining build_steps continue. |
| 12 | `features/paper/paper_plan_service.py:1004` | user_supplied evidence in initial content path | Evidence is stripped; step remains. |
| 13 | `features/paper/paper_plan_helpers.py:511` | step id invalid | Invalid steps are dropped; all-invalid still terminal `empty_steps`. |
| 14 | `features/paper/paper_plan_helpers.py:511` | duplicate step id | Duplicate item is dropped; first valid step remains. |
| 15 | `features/paper/paper_plan_helpers.py:511` | unknown dependency | Unknown dependency edge is removed; step remains. |
| 16 | `features/paper/paper_plan_helpers.py:511` | self dependency | Self edge is removed; step remains. |
| 17 | `features/paper/paper_plan_helpers.py:511` | dependency cycle | Dependencies are locally cleared; steps remain. |
| 18 | `features/paper/paper_plan_helpers.py:632` | parameter_ref no match | Bad parameter_ref is dropped; step remains. |
| 19 | `features/paper/paper_plan_helpers.py:632` | parameter mapping duplicate | Still terminal because downstream identity is ambiguous. |
| 20 | `features/paper/paper_plan_helpers.py:643` | block_ref no match | Bad block_ref is dropped; step remains. |
| 21 | `features/paper/paper_plan_helpers.py:643` | duplicate block recommendation pair | First deterministic recommendation is used; ambiguity logged. |
| 22 | `features/paper/paper_plan_helpers.py:643` | duplicate block_ref_id | Duplicate block_ref is dropped; no bad relation inserted. |
| 23 | `features/paper/paper_plan_helpers.py:659` | invisible connection refs | Bad connection hint is dropped; step remains. |
| 24 | `features/paper/paper_plan_helpers.py:511` | step lacks operable refs/hints | Textual step remains; no forced legacy fallback. |
| 25 | `features/paper/paper_plan_helpers.py:511` | recommendation coverage missing | Artifact remains and metadata subcode records coverage gap. |
| 26 | `features/paper/paper_plan_helpers.py:709` | redline parameter value in content text | Content remains, subcode logged; no raw value in gate log. |
| 27 | `features/paper/paper_plan_helpers.py:709` | redline parameter value in config identifiers | Content remains, subcode logged; config allowlist behavior preserved. |
| 28 | `features/paper/paper_plan_service.py:610` | build_steps provider timeout/rate/server | Converted through precise transient branches to existing fallback. |
| 29 | `features/paper/paper_plan_service.py:610` | build_steps provider auth/config/cancel | Propagates out; no legacy fallback. |
| 30 | `features/paper/paper_plan_service.py:639` | build_steps regeneration transient provider error | Same precise transient fallback. |
| 31 | `features/paper/paper_plan_service.py:325` | guidance generator broad failure | Fail-closed only for content/guidance exceptions; auth/config propagate. |
| 32 | `features/paper/build_guidance_generator.py:446` | guidance no document basis terminal | New generation returns `generation_failed`, not new `no_document_basis`; old status remains readable. |
| 33 | `features/paper/build_guidance_generator.py:446` | guidance unresolved evidence handle | Generated guidance can survive as unverified detail plus gaps. |
| 34 | `features/paper/build_guidance_generator.py:446` | guidance grounding mismatch | Detail is downgraded to unverified; no fake evidence badge. |
| 35 | `features/paper/build_guidance_generator.py:446` | guidance provider auth/config | Auth and configuration failures propagate; transient provider errors still use retry/failure. |
| 36 | `features/paper/build_guidance_semantic_validator.py:269` | validator rewrites returns | Changed return rewriting so non-empty downgraded details are kept. |
| 37 | `features/paper/build_guidance_semantic_validator.py:390` | all document details lost | No longer clears if renderable downgraded details remain; clears only when details are empty. |
| 38 | `features/paper/build_guidance_lifecycle.py:52` | generated lifecycle floor | Requires v2 and non-empty details; no hard document-evidence detail requirement. |
| 39 | `features/paper/paper_schemas.py:675` | API schema model validator | Mirrors lifecycle floor; public JSON schema remains unchanged. |
| 40 | `adapters/storage/sqlite_paper_cache.py:737` | SQLite semantic readback | Readback keeps generated unverified guidance when details remain. |
| 41 | `api/routes/paper_query.py:63` | GET plan record integrity | Uses returned degraded record, so API mirrors backend degradation. |
| 42 | `api/routes/paper_tuning.py:57` | tuning record integrity | Uses returned degraded record before tuning. |
| 43 | `features/paper/paper_plan_integrity.py:17` | record conflict stale, build_step text | Structure-class readback/API degradation: clears stale build_steps and step-bound guidance, marks `stale_pending_regeneration`. |
| 44 | `features/paper/paper_plan_integrity.py:63` | composer conflict stale | Composer-facing `validate_plan_does_not_resolve_conflicts` still hard-fails; no partial composer salvage. |
| 45 | `docs/06_OUTPUT_CONTRACTS.md:519` | behavior contract | Documents generated guidance with unverified renderable details; schema is explicitly byte-stable. |
| 46 | `features/paper/paper_plan_service.py:117-133/:202-221/:352-385` | mscript wrapper outcome logic | No outcome-logic edit in this PR; 537-A behavior retained. |
| 47 | `docs/06_OUTPUT_CONTRACTS.md:567-571` | historical `build_steps=null` | No automatic migration; old null remains bounded and rerun/manual regeneration handles refresh. |

## Verification Hooks Added

- Deterministic content/structure/security split: `tests/features/paper/test_paper_plan_helpers.py`, `tests/features/paper/test_paper_plan_service.py`.
- Provider carve-out regression tests: build_steps auth/config/cancel propagation and transient fallback; guidance auth/config propagation.
- Full backend loop: `tests/api/test_paper_query.py::test_get_paper_plan_preserves_unverified_guidance_after_sqlite_readback` covers write, SQLite readback, API serialization, and non-empty build_steps/guidance.
- Conflict stale carve-out: `tests/features/paper/test_paper_plan_integrity.py` and `tests/api/test_paper_query.py` cover composer hard fail vs API/readback local degradation.

