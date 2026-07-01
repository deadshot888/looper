from __future__ import annotations

import json
import os
from pathlib import Path

artifact_paths = json.loads(os.environ["LOOPER_ARTIFACTS"])
experiment_index = int(os.environ["LOOPER_EXPERIMENT_INDEX"])
schema_path = Path(artifact_paths[0])

schema = json.loads(schema_path.read_text(encoding="utf-8"))
parameters = schema.setdefault("parameters", {})
properties = parameters.setdefault("properties", {})
email = properties.setdefault("email", {"type": "string"})

steps = [
    "email_description",
    "email_required",
    "no_extra_properties",
]

for step in steps[: experiment_index % len(steps) + 1]:
    if step == "email_description":
        email["description"] = "Customer email address used to find exactly one customer record."
    elif step == "email_required":
        required = parameters.setdefault("required", [])
        if "email" not in required:
            required.append("email")
    elif step == "no_extra_properties":
        parameters["additionalProperties"] = False

schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
print(f"updated={schema_path}")
