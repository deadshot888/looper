from __future__ import annotations

import json
import subprocess
from pathlib import Path

from looper.core.config import LooperConfig
from looper.core.command_env import build_command_env
from looper.core.models import RunResult


class Runner:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def run(self, workspace: Path, experiment_id: str) -> tuple[RunResult, str, str]:
        result_path = workspace / self.cfg.runner.result_path
        result_path.parent.mkdir(parents=True, exist_ok=True)
        if result_path.exists():
            result_path.unlink()

        env = build_command_env(
            workspace,
            [a.path for a in self.cfg.artifacts],
            experiment_id,
            {"LOOPER_RESULT_PATH": str(result_path)},
        )

        completed = subprocess.run(
            self.cfg.runner.command,
            shell=True,
            cwd=str(workspace),
            env=env,
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            raise RuntimeError(
                f"Runner failed for {experiment_id} with exit code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )

        if not result_path.exists():
            raise FileNotFoundError(f"Runner did not write result JSON: {result_path}")

        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Runner wrote invalid JSON to {result_path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Result JSON must be an object: {result_path}")
        if "score" not in raw:
            raise ValueError(f"Result JSON must include 'score': {result_path}")

        result = RunResult(
            score=float(raw["score"]),
            metrics=raw.get("metrics", {}),
            notes=raw.get("notes", ""),
            raw=raw,
        )
        return result, completed.stdout, completed.stderr
