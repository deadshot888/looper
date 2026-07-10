from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from looper.core.command_env import active_python, active_python_version
from looper.core.config import LooperConfig
from looper.core.diffs import DiffSummary, build_artifact_diff
from looper.core.gates import GateRunner
from looper.core.models import Experiment, GateResult, State, VersionReview
from looper.core.mutator import MutationResult, Mutator
from looper.core.report import Reporter
from looper.core.review import review_experiment
from looper.core.runner import Runner
from looper.core.selector import Selector
from looper.core.state import StateStore
from looper.core.workspace import WorkspaceBackend


class Engine:
    def __init__(self, cfg: LooperConfig, root: Path):
        self.cfg = cfg
        self.root = root
        self.store = StateStore(root)
        self.runner = Runner(cfg)
        self.gates = GateRunner(cfg)
        self.mutator = Mutator(cfg)
        self.selector = Selector(cfg)
        self.workspace = WorkspaceBackend(root)

    def run_baseline(self) -> Experiment:
        state = self.store.load()
        result, stdout, stderr = self.runner.run(self.root, "baseline")
        gates = self.gates.run_all(self.root, "baseline")
        result_path = self._persist_outputs("baseline", result.raw, gates, stdout, stderr)
        baseline = Experiment(
            id="baseline",
            parent="root",
            created_at=self._now(),
            score=result.score,
            metrics=result.metrics,
            notes=result.notes,
            hypothesis="Baseline run captures the current artifact behavior before new variants.",
            change_summary="No mutation was applied; this is the comparison point.",
            gates=gates,
            status="passed" if all(g.passed for g in gates) else "failed",
            workspace=str(self.root),
            artifacts=[a.path for a in self.cfg.artifacts],
            result_path=self._relative(result_path),
            stdout=stdout,
            stderr=stderr,
        )
        baseline.review = review_experiment(baseline, None, self.cfg.metric.direction)
        self._persist_review(baseline.id, baseline.review)
        state.baseline = baseline
        self._refresh_selection(state)
        self.store.save(state)
        self._append_version_log(baseline, state)
        return baseline

    def run(self) -> State:
        state = self.store.load()
        if state.baseline is None:
            self.run_baseline()
            state = self.store.load()

        start_idx = len(state.experiments) + 1
        total = self.cfg.search.rounds * self.cfg.search.variants_per_round

        for i in range(total):
            exp_id = f"exp_{start_idx + i:04d}"
            experiment_index = start_idx + i - 1
            round_index = i // self.cfg.search.variants_per_round + 1
            variant_index = i % self.cfg.search.variants_per_round + 1
            workspace = self.workspace.create(exp_id)
            mutation = MutationResult(
                artifacts=[],
                hypothesis="Version failed before mutation metadata was available.",
                change_summary="No mutation completed.",
            )
            diff = DiffSummary(patch="", additions=0, deletions=0)
            diff_path = ""
            try:
                mutation = self.mutator.mutate(workspace, experiment_index)
                diff = build_artifact_diff(self.root, workspace, mutation.artifacts)
                diff_path = self._persist_diff(exp_id, diff.patch)
                result, stdout, stderr = self.runner.run(workspace, exp_id)
                gates = self.gates.run_all(workspace, exp_id)
                status = "passed" if all(g.passed for g in gates) else "failed"
                result_path = self._persist_outputs(exp_id, result.raw, gates, stdout, stderr)
                exp = Experiment(
                    id=exp_id,
                    parent="baseline",
                    created_at=self._now(),
                    round_index=round_index,
                    variant_index=variant_index,
                    score=result.score,
                    metrics=result.metrics,
                    notes=result.notes,
                    hypothesis=mutation.hypothesis,
                    change_summary=mutation.change_summary,
                    diff_path=diff_path,
                    additions=diff.additions,
                    deletions=diff.deletions,
                    gates=gates,
                    status=status,
                    workspace=str(workspace),
                    artifacts=mutation.artifacts,
                    result_path=self._relative(result_path),
                    stdout=stdout,
                    stderr=stderr,
                )
            except Exception as exc:
                if diff.patch and not diff_path:
                    diff_path = self._persist_diff(exp_id, diff.patch)
                self._persist_error(exp_id, str(exc))
                exp = Experiment(
                    id=exp_id,
                    parent="baseline",
                    created_at=self._now(),
                    round_index=round_index,
                    variant_index=variant_index,
                    hypothesis=mutation.hypothesis,
                    change_summary=mutation.change_summary,
                    diff_path=diff_path,
                    additions=diff.additions,
                    deletions=diff.deletions,
                    status="error",
                    workspace=str(workspace),
                    artifacts=mutation.artifacts,
                    stderr=str(exc),
                )
            exp.review = review_experiment(exp, state.baseline, self.cfg.metric.direction)
            self._persist_review(exp.id, exp.review)
            state.experiments.append(exp)
            self._refresh_selection(state)
            self.store.save(state)
            self._append_version_log(exp, state)

        return state

    def generate_report(self) -> Path:
        state = self.store.load()
        return Reporter(self.cfg, self.root).write(state)

    def generate_dashboard(self) -> Path:
        state = self.store.load()
        return Reporter(self.cfg, self.root).write_dashboard(state)

    def accept(self, target: str = "best") -> str:
        state = self.store.load()
        exp_id = state.best_experiment_id if target == "best" else target
        if not exp_id:
            raise RuntimeError("No experiment selected.")
        if target == "best" and not state.improvement_found:
            raise RuntimeError(
                "Best experiment does not improve the baseline. Pass an experiment id to accept it anyway."
            )

        exp = next((e for e in state.experiments if e.id == exp_id), None)
        if exp is None:
            raise RuntimeError(f"Experiment not found: {exp_id}")
        if exp.status != "passed":
            raise RuntimeError(f"Cannot accept experiment with status {exp.status}: {exp_id}")

        workspace = Path(exp.workspace)
        for artifact in self.cfg.artifacts:
            src = workspace / artifact.path
            dst = self.root / artifact.path
            if not src.exists():
                raise FileNotFoundError(f"Accepted artifact missing: {src}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)

        return exp_id

    def _refresh_selection(self, state: State) -> None:
        state.best_experiment_id = self.selector.select_best(state)
        best = next((exp for exp in state.experiments if exp.id == state.best_experiment_id), None)
        state.improvement_found = self.selector.improved_over_baseline(state.baseline, best)

    def _persist_outputs(
        self,
        experiment_id: str,
        raw_result: dict,
        gates: list[GateResult],
        stdout: str,
        stderr: str,
    ) -> Path:
        exp_dir = self.root / ".looper" / "experiments" / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        result_path = exp_dir / "result.json"
        result_path.write_text(json.dumps(raw_result, indent=2) + "\n", encoding="utf-8")
        (exp_dir / "gates.json").write_text(
            json.dumps([gate.model_dump() for gate in gates], indent=2) + "\n",
            encoding="utf-8",
        )
        (exp_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (exp_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        return result_path

    def _persist_diff(self, experiment_id: str, patch: str) -> str:
        if not patch:
            return ""
        exp_dir = self.root / ".looper" / "experiments" / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        path = exp_dir / "diff.patch"
        path.write_text(patch, encoding="utf-8")
        return self._relative(path)

    def _persist_review(self, experiment_id: str, review: VersionReview) -> None:
        exp_dir = self.root / ".looper" / "experiments" / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "review.json").write_text(
            json.dumps(review.model_dump(), indent=2) + "\n",
            encoding="utf-8",
        )
        lines = [
            f"# Review: {experiment_id}",
            "",
            review.summary,
            "",
            "## What Worked",
            "",
            *[f"- {item}" for item in review.what_worked],
            "",
            "## What To Improve",
            "",
            *[f"- {item}" for item in review.what_to_improve],
            "",
            "## Recommendation",
            "",
            review.recommendation,
            "",
        ]
        (exp_dir / "review.md").write_text("\n".join(lines), encoding="utf-8")

    def _persist_error(self, experiment_id: str, message: str) -> None:
        exp_dir = self.root / ".looper" / "experiments" / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "error.txt").write_text(message, encoding="utf-8")

    def _append_version_log(self, exp: Experiment, state: State) -> None:
        log_path = self.root / ".looper" / "versions.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "logged_at": self._now(),
            "project": self.cfg.name,
            "experiment_id": exp.id,
            "parent": exp.parent,
            "round_index": exp.round_index,
            "variant_index": exp.variant_index,
            "status": exp.status,
            "score": exp.score,
            "metric_name": self.cfg.metric.name,
            "metric_direction": self.cfg.metric.direction,
            "hypothesis": exp.hypothesis,
            "change_summary": exp.change_summary,
            "artifacts": exp.artifacts,
            "diff_path": exp.diff_path,
            "result_path": exp.result_path,
            "review": exp.review.model_dump(),
            "selected_best_after_version": state.best_experiment_id,
            "improvement_found_after_version": state.improvement_found,
            "python": {
                "executable": str(active_python()),
                "version": active_python_version(),
            },
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()
