from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path.cwd()
PROMPT = ROOT / "examples" / "prompt_optimization" / "prompts" / "support_agent.md"
RESULT_PATH = Path(os.environ.get("LOOPER_RESULT_PATH", ROOT / ".looper" / "result.json"))

text = PROMPT.read_text(encoding="utf-8").lower()

checks = {
    "cite_policy": "cite the policy" in text or "cite the source" in text,
    "clarifying_question": "clarifying question" in text,
    "do_not_invent": "do not invent" in text,
    "escalate": "escalate" in text,
}

score = sum(1 for value in checks.values() if value) / len(checks)

RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
RESULT_PATH.write_text(
    json.dumps(
        {
            "score": score,
            "metrics": checks,
            "notes": "Toy deterministic eval for the starter repo."
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(f"score={score}")
