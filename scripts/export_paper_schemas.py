"""Export paper-to-model Pydantic schemas to schemas/paper_*.schema.json.

Run as a module from project root:
    python -m scripts.export_paper_schemas
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from features.paper.paper_ask_schemas import PaperAskRequestSchema, PaperAskResponseSchema
from features.paper.paper_schemas import (
    MissingParameterPromptSchema,
    ModelGenerationPlanSchema,
    PaperEvidenceEntrySchema,
    PaperSpecSchema,
    TuningSuggestionSchema,
)

OUTPUTS = {
    Path("schemas/paper_evidence.schema.json"): PaperEvidenceEntrySchema,
    Path("schemas/paper_spec.schema.json"): PaperSpecSchema,
    Path("schemas/paper_plan.schema.json"): ModelGenerationPlanSchema,
    Path("schemas/paper_tuning.schema.json"): TuningSuggestionSchema,
    Path("schemas/paper_missing.schema.json"): MissingParameterPromptSchema,
    Path("schemas/paper_ask_request.schema.json"): PaperAskRequestSchema,
    Path("schemas/paper_ask_response.schema.json"): PaperAskResponseSchema,
}


def main() -> int:
    """Export the current paper-to-model JSON Schemas."""
    for path, schema_model in OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        schema = schema_model.model_json_schema()
        path.write_bytes((json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
