from __future__ import annotations

import sys
from pathlib import Path

import pytest

from looper.core.config import LooperConfig
from looper.core.engine import Engine
from looper.core.errors import CommandTimeoutError, StateConflictError
from looper.core.runner import Runner


def _write_eval(root: Path, body: str) -> Path:
    script = root / "eval.py"
    script.write_text(body.strip(), encoding="utf-8")
    return script


def _config(root: Path, command: str, **extra) -> LooperConfig:
    data = {
        "name": "hardening-test",
        "artifacts": [{"id": "prompt", "type": "prompt", "path": "prompt.md"}],
        "runner": {"command": command, "result_path": ".looper/result.json"},
        "metric": {"name": "score", "direction": "maximize"},
        "search": {"rounds": 1, "variants_per_round": 1},
        **extra,
    }
    return LooperConfig.model_validate(data)


def _deterministic_project(tmp_path: Path) -> tuple[Engine, Path]:
    artifact = tmp_path / "prompt.md"
    artifact.write_text("base\n", encoding="utf-8")
    script = _write_eval(
        tmp_path,
        """
import json
import os
from pathlib import Path

text = Path("prompt.md").read_text(encoding="utf-8")
Path(os.environ["LOOPER_RESULT_PATH"]).write_text(
    json.dumps({"score": text.count("When answering") + text.count("If key information")}),
    encoding="utf-8",
)
""",
    )
    cfg = _config(tmp_path, f'"{sys.executable}" "{script}"')
    return Engine(cfg, tmp_path), artifact


def test_result_path_must_stay_in_looper_directory(tmp_path):
    (tmp_path / "prompt.md").write_text("base", encoding="utf-8")
    cfg = LooperConfig.model_validate(
        {
            "artifacts": [{"id": "prompt", "path": "prompt.md"}],
            "runner": {"command": "echo ok", "result_path": "README.md"},
        }
    )

    with pytest.raises(ValueError, match="inside .looper"):
        Engine(cfg, tmp_path)


def test_rounds_advance_from_previous_winner(tmp_path):
    engine, _ = _deterministic_project(tmp_path)
    engine.cfg.search.rounds = 2

    state = engine.run()

    assert len(state.experiments) == 2
    assert state.experiments[0].parent == "baseline"
    assert state.experiments[1].parent == "exp_0001"


def test_evaluator_cannot_change_candidate_artifact(tmp_path):
    artifact = tmp_path / "prompt.md"
    artifact.write_text("base\n", encoding="utf-8")
    script = _write_eval(
        tmp_path,
        """
import json
import os
from pathlib import Path

if os.environ["LOOPER_EXPERIMENT_ID"] != "baseline":
    Path("prompt.md").write_text("tampered\\n", encoding="utf-8")
Path(os.environ["LOOPER_RESULT_PATH"]).write_text(json.dumps({"score": 1}), encoding="utf-8")
""",
    )
    engine = Engine(_config(tmp_path, f'"{sys.executable}" "{script}"'), tmp_path)

    state = engine.run()

    assert state.experiments[0].status == "error"
    assert "changed during evaluation" in state.experiments[0].stderr
    assert artifact.read_text(encoding="utf-8") == "base\n"


def test_accept_detects_root_conflict_and_keeps_user_edit(tmp_path):
    engine, artifact = _deterministic_project(tmp_path)
    state = engine.run()
    assert state.improvement_found
    artifact.write_text("user edit\n", encoding="utf-8")

    with pytest.raises(StateConflictError, match="project changed"):
        engine.accept("best")

    assert artifact.read_text(encoding="utf-8") == "user edit\n"


def test_accept_dry_run_then_writes_backup(tmp_path):
    engine, artifact = _deterministic_project(tmp_path)
    engine.run()

    preview = engine.accept("best", dry_run=True)
    assert preview.dry_run
    assert artifact.read_text(encoding="utf-8") == "base\n"

    accepted = engine.accept("best")
    assert not accepted.dry_run
    assert "When answering" in artifact.read_text(encoding="utf-8")
    backup = tmp_path / accepted.backup_path / "prompt.md"
    assert backup.read_text(encoding="utf-8") == "base\n"


def test_budget_caps_experiments(tmp_path):
    engine, _ = _deterministic_project(tmp_path)
    engine.cfg.search.rounds = 3
    engine.cfg.search.variants_per_round = 2
    engine.cfg.budget.max_experiments = 1

    state = engine.run()

    assert len(state.experiments) == 1
    assert "budget reached" in state.stop_reason.lower()


def test_runner_averages_repeated_evaluations(tmp_path):
    (tmp_path / "prompt.md").write_text("base", encoding="utf-8")
    script = _write_eval(
        tmp_path,
        """
import json
import os
from pathlib import Path

score = int(os.environ["LOOPER_EVALUATION_INDEX"])
Path(os.environ["LOOPER_RESULT_PATH"]).write_text(json.dumps({"score": score}), encoding="utf-8")
""",
    )
    cfg = _config(
        tmp_path,
        f'"{sys.executable}" "{script}"',
        runner={
            "command": f'"{sys.executable}" "{script}"',
            "result_path": ".looper/result.json",
            "repeats": 3,
        },
    )

    result, _, _ = Runner(cfg).run(tmp_path, "repeat")

    assert result.score == 1.0
    assert result.score_samples == [0.0, 1.0, 2.0]


def test_runner_timeout_is_bounded(tmp_path):
    (tmp_path / "prompt.md").write_text("base", encoding="utf-8")
    script = _write_eval(tmp_path, "import time; time.sleep(5)")
    cfg = _config(
        tmp_path,
        f'"{sys.executable}" "{script}"',
        runner={
            "command": f'"{sys.executable}" "{script}"',
            "result_path": ".looper/result.json",
            "timeout_seconds": 0.1,
        },
    )

    with pytest.raises(CommandTimeoutError):
        Runner(cfg).run(tmp_path, "timeout")


def test_runner_output_is_capped_while_process_runs(tmp_path):
    (tmp_path / "prompt.md").write_text("base", encoding="utf-8")
    script = _write_eval(
        tmp_path,
        """
import json
import os
from pathlib import Path

print("x" * 10000)
Path(os.environ["LOOPER_RESULT_PATH"]).write_text(json.dumps({"score": 1}), encoding="utf-8")
""",
    )
    cfg = _config(
        tmp_path,
        f'"{sys.executable}" "{script}"',
        runner={
            "command": f'"{sys.executable}" "{script}"',
            "result_path": ".looper/result.json",
            "max_output_chars": 100,
        },
    )

    _, stdout, _ = Runner(cfg).run(tmp_path, "output-cap")

    assert "truncated" in stdout
    assert len(stdout) < 200
