# TASK-528-A: BuildGuidance contract substrate

> Contract-only substrate for the external `BuildGuidance` data shape. This card intentionally keeps runtime behavior unchanged: no guidance generation, no rendering, no semantic validation, and end-to-end `build_guidance = None`.

## Stage 0

- Fetch live `origin/main` before implementation and confirm TASK-507-A/B/508 and TASK-526-B as-built behavior matches this substrate.
- `CURRENT_SCHEMA_VERSION` is v8. This card adds an optional field inside persisted `plan_json` with a default of `None`, so it does not bump v9.
- If implementation requires a new table or column, stop and report to the architect before changing schema version.

## Goal

Add a nullable sibling on `ModelGenerationPlan`:

```python
ModelGenerationPlan.build_guidance: BuildGuidance | None = None
```

The field is additive and must not rewrite or reinterpret `build_steps`. During TASK-528-A every path keeps `build_guidance=None`; later cards wire generation, validation, display, and evaluation.

## Contract Shape

`BuildGuidance`

- `version: Literal["v1"]`
- `assessment: GuidanceAssessment`
- `details: list[GuidanceDetail]`
- `gaps: list[GuidanceGap]`

`GuidanceAssessment`

- `content_status: Literal["reproducible_candidate","outline_with_gaps","outline_only"]`
- `environment_status: Literal["not_checked","compatible","missing_toolbox","incompatible"]`
- `overall_status: Literal["reproducible_ready","reproducible_candidate_env_unchecked","outline_with_gaps","outline_only"]`
- `blocking_gap_ids: list[str]`

`GuidanceDetail`

- `detail_id: str`
- `step_id: str`
- `detail_kind: Literal["block_selection","subsystem_internal_structure","connection","parameter_value","configuration","verification","gap_notice"]`
- `basis: Literal["document_extracted","engineering_convention","user_confirmation_required"]`
- `actionability: Literal["actionable","notice_only","blocked_pending_confirmation"]`
- `display_text: str`
- `evidence: list[PaperEvidenceEntry]`
- `convention_code: str | None`
- `confirmation_reason_code: str | None`

`GuidanceGap`

- `gap_id: str`
- `gap_kind: Literal["missing_support_component","missing_parameter_value","toolbox_unverified","library_variant_unresolved","missing_connection_detail","missing_configuration_detail","insufficient_document_evidence"]`
- `scope: Literal["plan","step","subsystem"]`
- `step_id: str | None`
- `basis: Literal["engineering_convention","user_confirmation_required"]`
- `severity: Literal["blocking","warning"]`
- `display_text: str`

Evidence reuses `PaperEvidenceEntry`; do not introduce explanation-system `SourceRef`.

## Implementation Scope

- Domain dataclasses: add `BuildGuidance`, `GuidanceAssessment`, `GuidanceDetail`, and `GuidanceGap`.
- Pydantic schemas: add matching child schemas and `ModelGenerationPlanSchema.build_guidance`.
- JSON schema export: update generated `schemas/paper_plan.schema.json` and nested response schemas.
- Freeze tests: update expected field/model shape.
- Schema tests: cover default/missing/explicit null, enum boundaries, and required structure only.
- Docs: update `docs/06_OUTPUT_CONTRACTS.md` with the public contract.
- Frontend: update TypeScript types only; no rendering changes.
- Golden/sample fixtures: include `build_guidance: null` in default-state plan fixtures.

## Non-Goals

- No guidance content generation.
- No prompt changes.
- No frontend rendering changes.
- No `build_steps` generation, validation, `display_text`, or fail-closed behavior changes.
- No semantic validation for cross-field combinations; TASK-528-C owns that.
- No changes to `05_EXPLANATION_STYLE_GUIDE.md` or eval; TASK-528-E owns that.
- No schema version bump unless Stage 0 discovers an unavoidable storage migration.

## Acceptance

- Freeze, JSON schema export, TypeScript type checks, and targeted schema tests pass.
- Existing persisted plans without `build_guidance` load and round-trip with `None`.
- End-to-end plan paths keep `build_guidance=None`.
- Existing `build_steps` output is unchanged.
- Full test suite remains green.
- Real-machine light check confirms null pass-through using repo-local settings and temporary storage without exposing keys.

## Handoff Report Requirements

- Include each decision 13 sync item and its diff.
- Include evidence that `build_guidance` remains `None` and `build_steps` output has no diff.
- State whether v9 was touched.
- State any deviation from the requested shape, or explicitly say there was none.
