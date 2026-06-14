"""Export ProjectOverview Pydantic schema to schemas/project_overview.schema.json.

Run as a module from project root:
    python -m scripts.export_overview_schema

Output:
    schemas/project_overview.schema.json (overwrite if exists)

Exit code:
    0 = success
    non-zero = output dir not writable / JSON serialization failed

This script is idempotent: running it multiple times produces the same JSON
(modulo pydantic version diff). It does NOT validate against an existing
baseline. See tests/features/overview/test_schema_freeze.py for semantic drift
detection, and use `make verify-schema` to confirm the committed JSON is in sync.

Direct invocation as `python scripts/export_overview_schema.py` is NOT
supported, because sys.path[0] would be scripts/ and the
`from features.overview...` import would fail. Always use `python -m`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from features.overview.overview_schemas import ProjectOverviewSchema

OUTPUT_PATH = Path("schemas") / "project_overview.schema.json"


def main() -> int:
    """Export the current ProjectOverview JSON Schema."""
    schema = ProjectOverviewSchema.model_json_schema()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(
        (json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
