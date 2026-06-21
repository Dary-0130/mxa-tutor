"""Export MATLAB bridge Pydantic schemas to schemas/bridge_*.schema.json.

Run as a module from project root:
    python -m scripts.export_bridge_schemas
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from features.matlab_bridge.bridge_diagnostic_schemas import (
    BridgeDiagnosticReceiptModel,
    BridgeDiagnosticRequest,
    BridgeErrorResponse,
)

OUTPUTS = {
    Path("schemas/bridge_diagnostic_request.schema.json"): BridgeDiagnosticRequest,
    Path("schemas/bridge_diagnostic_receipt.schema.json"): BridgeDiagnosticReceiptModel,
    Path("schemas/bridge_error_response.schema.json"): BridgeErrorResponse,
}


def main() -> int:
    """Export the current MATLAB bridge JSON Schemas."""
    for path, schema_model in OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        schema = schema_model.model_json_schema()
        path.write_bytes((json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
