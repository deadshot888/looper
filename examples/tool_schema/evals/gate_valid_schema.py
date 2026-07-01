from __future__ import annotations

import json
from pathlib import Path

schema = json.loads(
    Path("examples/tool_schema/schemas/lookup_customer.json").read_text(encoding="utf-8"),
)
parameters = schema.get("parameters", {})

if not schema.get("name"):
    raise SystemExit("Tool schema must include a name.")
if parameters.get("type") != "object":
    raise SystemExit("Tool parameters must be an object.")
if not isinstance(parameters.get("properties"), dict):
    raise SystemExit("Tool parameters must include properties.")

raise SystemExit(0)
