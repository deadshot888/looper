from __future__ import annotations

import json
import shutil
from pathlib import Path

from looper.core.config import LooperConfig
from looper.core.gates import GateRunner
from looper.core.models import Experiment, GateResult, State
from looper.core.mutator import Mutator
from looper.core.report import Reporter
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
            score=result.score,
            metrics=result.metrics,
            notes=result.notes,
            gates=gates,
            status="passed" if all(g.passed for g in gates) else "failed",
            workspace=str(self.root),
            artifacts=[a.path for a in self.cfg.artifacts],
            result_path=self._relative(result_path),
            stdout=stdout,
            stderr=stderr,
        )
        state.baseline = baseline
        self._refresh_selection(state)
        self.store.save(state)
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
            workspace = self.workspace.create(exp_id)
            changed: list[str] = []
            try:
                changed = self.mutator.mutate(workspace, i)
                result, stdout, stderr = self.runner.run(workspace, exp_id)
                gates = self.gates.run_all(workspace, exp_id)
                status = "passed" if all(g.passed for g in gates) else "failed"
                result_path = self._persist_outputs(exp_id, result.raw, gates, stdout, stderr)
                exp = Experiment(
                    id=exp_id,
                    parent="baseline",
                    score=result.score,
                    metrics=result.metrics,
                    notes=result.notes,
                    gates=gates,
                    status=status,
                    workspace=str(workspace),
                    artifacts=changed,
                    result_path=self._relative(result_path),
                    stdout=stdout,
                    stderr=stderr,
                )
            except Exception as exc:
                self._persist_error(exp_id, str(exc))
                exp = Experiment(
                    id=exp_id,
                    parent="baseline",
                    status="error",
                    workspace=str(workspace),
                    artifacts=changed,
                    stderr=str(exc),
                )
            state.experiments.append(exp)
            self._refresh_selection(state)
            self.store.save(state)

        return state

    def generate_report(self) -> Path:
        state = self.store.load()
        return Reporter(self.cfg, self.root).write(state)

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

    def _persist_error(self, experiment_id: str, message: str) -> None:
        exp_dir = self.root / ".looper" / "experiments" / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "error.txt").write_text(message, encoding="utf-8")

    def _relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))
