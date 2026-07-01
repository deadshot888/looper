from __future__ import annotations

import sys

import pytest

from looper.core.config import LooperConfig
from looper.core.runner import Runner


def _cfg(command: str) -> LooperConfig:
    return LooperConfig.model_validate(
        {
            "name": "runner-test",
            "artifacts": [{"id": "prompt", "type": "prompt", "path": "prompt.md"}],
            "runner": {"command": command, "result_path": ".looper/result.json"},
            "metric": {"name": "score", "direction": "maximize"},
        }
    )


def test_runner_parses_result_json(tmp_path):
    script = tmp_path / "write_result.py"
    script.write_text(
        """
import json
import os
from pathlib import Path

Path(os.environ["LOOPER_RESULT_PATH"]).write_text(
    json.dumps({"score": 0.75, "metrics": {"ok": True}, "notes": "done"}),
    encoding="utf-8",
)
print(os.environ["LOOPER_ARTIFACTS"])
""".strip(),
        encoding="utf-8",
    )

    result, stdout, stderr = Runner(_cfg(f'"{sys.executable}" "{script}"')).run(
        tmp_path,
        "exp_test",
    )

    assert result.score == 0.75
    assert result.metrics == {"ok": True}
    assert "prompt.md" in stdout
    assert stderr == ""


def test_runner_rejects_invalid_result_json(tmp_path):
    script = tmp_path / "write_bad_result.py"
    script.write_text(
        """
import os
from pathlib import Path

Path(os.environ["LOOPER_RESULT_PATH"]).write_text("{", encoding="utf-8")
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        Runner(_cfg(f'"{sys.executable}" "{script}"')).run(tmp_path, "exp_bad")
