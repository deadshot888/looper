from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path.cwd()
README = ROOT / "README.md"
RESULT_PATH = Path(os.environ.get("LOOPER_RESULT_PATH", ROOT / ".looper" / "result.json"))

text = README.read_text(encoding="utf-8")
lower = text.lower()

checks = {
    "has_dogfood_section": "## dogfood looper on this repo" in lower,
    "uses_config_flag": "--config examples/repo_dogfood/looper.yaml" in text,
    "points_to_report": ".looper/reports/latest.md" in text,
    "mentions_test_before_commit": "`pytest` before committing" in lower,
}

score = sum(1 for passed in checks.values() if passed) / len(checks)

RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
RESULT_PATH.write_text(
    json.dumps(
        {
            "score": score,
            "metrics": checks,
            "notes": "Dogfood eval for Looper's own README.",
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(f"score={score}")
