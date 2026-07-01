from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path.cwd()
SCHEMA = ROOT / "examples" / "tool_schema" / "schemas" / "lookup_customer.json"
RESULT_PATH = Path(os.environ.get("LOOPER_RESULT_PATH", ROOT / ".looper" / "result.json"))

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
parameters = schema.get("parameters", {})
properties = parameters.get("properties", {})
email = properties.get("email", {})

checks = {
    "tool_has_clear_description": len(schema.get("description", "")) >= 20,
    "email_has_description": len(email.get("description", "")) >= 20,
    "email_is_required": "email" in parameters.get("required", []),
    "rejects_extra_properties": parameters.get("additionalProperties") is False,
}

score = sum(1 for passed in checks.values() if passed) / len(checks)

RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
RESULT_PATH.write_text(
    json.dumps(
        {
            "score": score,
            "metrics": checks,
            "notes": "Toy deterministic eval for a JSON tool schema.",
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(f"score={score}")
