from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from looper.core.command_env import build_command_env
from looper.core.config import LooperConfig
from looper.core.errors import CommandTimeoutError
from looper.core.models import RunResult
from looper.core.process import run_command


class Runner:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def run(self, workspace: Path, experiment_id: str) -> tuple[RunResult, str, str]:
        samples: list[dict] = []
        scores: list[float] = []
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        duration = 0.0

        for evaluation_index in range(self.cfg.runner.repeats):
            raw, stdout, stderr, elapsed = self._run_once(
                workspace,
                experiment_id,
                evaluation_index,
            )
            score = _finite_score(raw.get("score"))
            samples.append(raw)
            scores.append(score)
            duration += elapsed
            stdout_parts.append(f"[evaluation {evaluation_index + 1}]\n{stdout}".rstrip())
            if stderr:
                stderr_parts.append(f"[evaluation {evaluation_index + 1}]\n{stderr}".rstrip())

        metrics = _aggregate_metrics(samples)
        score = statistics.fmean(scores)
        score_stddev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        cost_usd = sum(_extract_cost(sample) for sample in samples)
        if cost_usd:
            metrics["cost_usd"] = cost_usd

        notes = " | ".join(
            str(sample.get("notes", "")).strip() for sample in samples if str(sample.get("notes", "")).strip()
        )
        raw_result = {
            "score": score,
            "score_stddev": score_stddev,
            "score_samples": scores,
            "metrics": metrics,
            "notes": notes,
            "evaluations": samples,
        }
        result = RunResult(
            score=score,
            metrics=metrics,
            notes=notes,
            raw=raw_result,
            score_samples=scores,
            duration_seconds=duration,
            cost_usd=cost_usd,
        )
        return result, "\n\n".join(stdout_parts), "\n\n".join(stderr_parts)

    def _run_once(
        self,
        workspace: Path,
        experiment_id: str,
        evaluation_index: int,
    ) -> tuple[dict, str, str, float]:
        result_path = (workspace / self.cfg.runner.result_path).resolve()
        workspace_root = workspace.resolve()
        if not result_path.is_relative_to(workspace_root / ".looper"):
            raise ValueError("runner.result_path must stay inside the workspace .looper directory")
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.unlink(missing_ok=True)

        env = build_command_env(
            workspace,
            [artifact.path for artifact in self.cfg.artifacts],
            experiment_id,
            self.cfg.execution,
            {
                "LOOPER_RESULT_PATH": str(result_path),
                "LOOPER_EVALUATION_INDEX": str(evaluation_index),
                "LOOPER_SEED": str(self.cfg.search.seed + evaluation_index),
            },
        )
        completed = run_command(
            self.cfg.runner.command,
            workspace,
            env,
            float(self.cfg.runner.timeout_seconds),
            int(self.cfg.runner.max_output_chars),
        )
        if completed.timed_out:
            raise CommandTimeoutError(
                f"Runner timed out for {experiment_id} after {self.cfg.runner.timeout_seconds:g} seconds."
            )
        if completed.exit_code != 0:
            raise RuntimeError(
                f"Runner failed for {experiment_id} with exit code {completed.exit_code}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        if not result_path.exists():
            raise FileNotFoundError(f"Runner did not write result JSON: {result_path}")

        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Runner wrote invalid JSON to {result_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"Result JSON must be an object: {result_path}")
        if "score" not in raw:
            raise ValueError(f"Result JSON must include 'score': {result_path}")
        _finite_score(raw["score"])
        metrics = raw.get("metrics", {})
        if not isinstance(metrics, dict):
            raise ValueError("Result 'metrics' must be a JSON object")
        return raw, completed.stdout, completed.stderr, completed.duration_seconds


def _finite_score(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Result score must be a finite number, not a boolean")
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"Result score must be numeric: {value!r}")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Result score must be numeric: {value!r}") from exc
    if not math.isfinite(score):
        raise ValueError("Result score must be finite")
    return score


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


def _extract_cost(raw: dict) -> float:
    value = raw.get("cost_usd", raw.get("metrics", {}).get("cost_usd", 0.0))
    if isinstance(value, bool):
        return 0.0
    try:
        cost = float(value)
    except (TypeError, ValueError):
        return 0.0
    return cost if math.isfinite(cost) and cost >= 0 else 0.0


def _aggregate_metrics(samples: list[dict]) -> dict:
    keys = sorted({key for sample in samples for key in sample.get("metrics", {})})
    aggregated: dict = {}
    for key in keys:
        values = [sample.get("metrics", {}).get(key) for sample in samples]
        numeric = [
            float(value)
            for value in values
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if key == "cost_usd" and len(numeric) == len(values):
            aggregated[key] = sum(numeric)
        elif len(numeric) == len(values):
            aggregated[key] = statistics.fmean(numeric)
        elif all(isinstance(value, bool) for value in values):
            aggregated[key] = all(values)
        else:
            aggregated[key] = values[-1]
    return aggregated
