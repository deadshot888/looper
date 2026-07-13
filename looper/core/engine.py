from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from looper import __version__
from looper.core.command_env import active_python, active_python_version
from looper.core.config import LooperConfig, validate_project_paths
from looper.core.diffs import DiffSummary, build_artifact_diff
from looper.core.errors import ArtifactIntegrityError, LooperError, StateConflictError
from looper.core.gates import GateRunner
from looper.core.integrity import artifact_hashes, config_hash, project_fingerprint
from looper.core.models import Experiment, GateResult, RunSession, State, VersionReview
from looper.core.mutator import MutationResult, Mutator
from looper.core.report import Reporter
from looper.core.review import review_experiment
from looper.core.runner import Runner
from looper.core.selector import Selector
from looper.core.state import StateStore
from looper.core.workspace import WorkspaceBackend


@dataclass(frozen=True)
class AcceptResult:
    experiment_id: str
    dry_run: bool
    backup_path: str = ""


class Engine:
    def __init__(self, cfg: LooperConfig, root: Path):
        self.cfg = cfg
        self.root = root.resolve()
        validate_project_paths(cfg, self.root)
        self.artifact_paths = [artifact.path for artifact in cfg.artifacts]
        self.cfg_hash = config_hash(cfg)
        self.store = StateStore(self.root)
        self.runner = Runner(cfg)
        self.gates = GateRunner(cfg)
        self.mutator = Mutator(cfg)
        self.selector = Selector(cfg)
        self.workspace = WorkspaceBackend(self.root, cfg.workspace, self.artifact_paths)
        self._validate_artifacts_exist()

    def run_baseline(self, force: bool = False) -> Experiment:
        with self.store.lock():
            state = self.store.load()
            if state.baseline is not None and not force:
                raise LooperError(
                    "A baseline already exists. Use 'looper baseline --force' to archive it and start over."
                )
            if force and (state.baseline is not None or state.experiments):
                self.store.reset(archive=True)
                state = State()
            return self._run_baseline(state)

    def _run_baseline(self, state: State) -> Experiment:
        created_at = self._now()
        session_id = datetime.now(UTC).strftime("run_%Y%m%dT%H%M%S%fZ_") + self.cfg_hash[:8]
        baseline_hashes = artifact_hashes(self.root, self.artifact_paths)
        project_hash, git_commit, git_dirty = project_fingerprint(
            self.root,
            self.artifact_paths,
            self.cfg_hash,
        )
        state.session = RunSession(
            id=session_id,
            created_at=created_at,
            config_hash=self.cfg_hash,
            config_snapshot=self.cfg.model_dump(mode="json"),
            baseline_artifact_hashes=baseline_hashes,
            project_hash=project_hash,
            git_commit=git_commit,
            git_dirty=git_dirty,
            looper_version=__version__,
            seed=self.cfg.search.seed,
        )
        workspace = self.workspace.create(f"baseline-{session_id}")
        candidate_hashes = artifact_hashes(workspace, self.artifact_paths)

        started = time.monotonic()
        try:
            result, stdout, stderr = self.runner.run(workspace, "baseline")
            gates = self.gates.run_all(workspace, "baseline")
            self._assert_artifacts_unchanged(workspace, candidate_hashes, "baseline evaluation")
        except Exception:
            self.store.save(state)
            raise
        duration = time.monotonic() - started
        result_path = self._persist_outputs("baseline", result.raw, gates, stdout, stderr)
        baseline = Experiment(
            id="baseline",
            session_id=session_id,
            parent="root",
            created_at=created_at,
            score=result.score,
            score_samples=result.score_samples,
            metrics=result.metrics,
            notes=result.notes,
            hypothesis="Baseline run captures the current artifact behavior before new variants.",
            change_summary="No mutation was applied; this is the comparison point.",
            gates=gates,
            status="passed" if all(gate.passed for gate in gates) else "failed",
            workspace=self._relative(workspace),
            artifacts=self.artifact_paths,
            result_path=self._relative(result_path),
            stdout=stdout,
            stderr=stderr,
            config_hash=self.cfg_hash,
            baseline_artifact_hashes=baseline_hashes,
            candidate_artifact_hashes=candidate_hashes,
            project_hash=project_hash,
            duration_seconds=duration,
            cost_usd=result.cost_usd,
        )
        baseline.review = review_experiment(baseline, None, self.cfg.metric.direction)
        self._persist_review(baseline.id, baseline.review)
        state.baseline = baseline
        state.stop_reason = ""
        self._refresh_selection(state)
        self.store.save(state)
        self._append_version_log(baseline, state)
        return baseline

    def run(self) -> State:
        with self.store.lock():
            state = self.store.load()
            if state.baseline is None:
                self._run_baseline(state)
                state = self.store.load()
            self._assert_session_current(state)
            if state.accepted_experiment_id:
                raise StateConflictError(
                    "The active session has already been accepted. Run 'looper baseline --force' before starting more experiments."
                )

            state.stop_reason = ""
            experiment_number = len(state.experiments) + 1
            round_number = max((exp.round_index or 0 for exp in state.experiments), default=0) + 1
            parent = self._starting_parent(state)

            for round_offset in range(self.cfg.search.rounds):
                round_experiments: list[Experiment] = []
                for variant_index in range(1, self.cfg.search.variants_per_round + 1):
                    stop_reason = self._budget_stop_reason(state)
                    if stop_reason:
                        state.stop_reason = stop_reason
                        self.store.save(state)
                        return state

                    exp_id = f"exp_{experiment_number:04d}"
                    exp = self._run_experiment(
                        state,
                        exp_id,
                        experiment_number - 1,
                        round_number + round_offset,
                        variant_index,
                        parent,
                    )
                    experiment_number += 1
                    round_experiments.append(exp)
                    state.experiments.append(exp)
                    self._refresh_selection(state)
                    self.store.save(state)
                    self._append_version_log(exp, state)

                parent = self._next_parent(parent, round_experiments)

            return state

    def _run_experiment(
        self,
        state: State,
        exp_id: str,
        experiment_index: int,
        round_index: int,
        variant_index: int,
        parent: Experiment,
    ) -> Experiment:
        if state.session is None:
            raise LooperError("Missing run session metadata.")
        parent_workspace = self._workspace_path(parent)
        if not parent_workspace.exists():
            raise LooperError(
                f"Parent workspace is missing: {parent_workspace}. Start a new baseline with 'looper baseline --force'."
            )
        workspace = self.workspace.create(exp_id, source=parent_workspace)
        mutation = MutationResult(
            artifacts=[],
            hypothesis="Version failed before mutation metadata was available.",
            change_summary="No mutation completed.",
        )
        diff = DiffSummary(patch="", additions=0, deletions=0)
        diff_path = ""
        candidate_hashes: dict[str, str] = {}
        started = time.monotonic()
        try:
            mutation = self.mutator.mutate(workspace, experiment_index)
            candidate_hashes = artifact_hashes(workspace, self.artifact_paths)
            diff = build_artifact_diff(self.root, workspace, self.artifact_paths)
            diff_path = self._persist_diff(exp_id, diff.patch)
            result, stdout, stderr = self.runner.run(workspace, exp_id)
            gates = self.gates.run_all(workspace, exp_id)
            self._assert_artifacts_unchanged(workspace, candidate_hashes, f"evaluation for {exp_id}")
            status: Literal["passed", "failed"] = "passed" if all(gate.passed for gate in gates) else "failed"
            result_path = self._persist_outputs(exp_id, result.raw, gates, stdout, stderr)
            exp = Experiment(
                id=exp_id,
                session_id=state.session.id,
                parent=parent.id,
                created_at=self._now(),
                round_index=round_index,
                variant_index=variant_index,
                score=result.score,
                score_samples=result.score_samples,
                metrics=result.metrics,
                notes=result.notes,
                hypothesis=mutation.hypothesis,
                change_summary=mutation.change_summary,
                diff_path=diff_path,
                additions=diff.additions,
                deletions=diff.deletions,
                gates=gates,
                status=status,
                workspace=self._relative(workspace),
                artifacts=mutation.artifacts,
                result_path=self._relative(result_path),
                stdout=stdout,
                stderr=stderr,
                config_hash=self.cfg_hash,
                baseline_artifact_hashes=state.session.baseline_artifact_hashes,
                candidate_artifact_hashes=candidate_hashes,
                project_hash=state.session.project_hash,
                duration_seconds=time.monotonic() - started,
                cost_usd=result.cost_usd,
            )
        except Exception as exc:
            if diff.patch and not diff_path:
                diff_path = self._persist_diff(exp_id, diff.patch)
            self._persist_error(exp_id, str(exc))
            exp = Experiment(
                id=exp_id,
                session_id=state.session.id,
                parent=parent.id,
                created_at=self._now(),
                round_index=round_index,
                variant_index=variant_index,
                hypothesis=mutation.hypothesis,
                change_summary=mutation.change_summary,
                diff_path=diff_path,
                additions=diff.additions,
                deletions=diff.deletions,
                status="error",
                workspace=self._relative(workspace),
                artifacts=mutation.artifacts,
                stderr=str(exc),
                config_hash=self.cfg_hash,
                baseline_artifact_hashes=state.session.baseline_artifact_hashes,
                candidate_artifact_hashes=candidate_hashes,
                project_hash=state.session.project_hash,
                duration_seconds=time.monotonic() - started,
            )
        exp.review = review_experiment(exp, state.baseline, self.cfg.metric.direction)
        self._persist_review(exp.id, exp.review)
        return exp

    def generate_report(self) -> Path:
        return Reporter(self.cfg, self.root).write(self.store.load())

    def generate_dashboard(self) -> Path:
        return Reporter(self.cfg, self.root).write_dashboard(self.store.load())

    def accept(self, target: str = "best", dry_run: bool = False, force: bool = False) -> AcceptResult:
        with self.store.lock():
            state = self.store.load()
            self._assert_session_current(state, force=force)
            exp_id = state.best_experiment_id if target == "best" else target
            if not exp_id:
                raise LooperError("No experiment selected.")
            if target == "best" and not state.improvement_found:
                raise LooperError(
                    "Best experiment does not improve the baseline. Pass an experiment id to accept it explicitly."
                )
            exp = next((candidate for candidate in state.experiments if candidate.id == exp_id), None)
            if exp is None:
                raise LooperError(f"Experiment not found: {exp_id}")
            if exp.status != "passed" or not exp.gates_passed:
                raise LooperError(f"Cannot accept experiment with status {exp.status}: {exp_id}")
            if exp.config_hash != self.cfg_hash:
                raise StateConflictError("The experiment was created with a different configuration.")

            current_hashes = artifact_hashes(self.root, self.artifact_paths)
            if not force and current_hashes != exp.baseline_artifact_hashes:
                raise StateConflictError(
                    "Configured artifacts changed after the baseline. Review those edits, then rerun the baseline or use --force."
                )
            workspace = self._workspace_path(exp)
            if not workspace.resolve().is_relative_to(self.workspace.workspaces_dir.resolve()):
                raise StateConflictError(f"Experiment workspace is outside .looper/workspaces: {workspace}")
            self._assert_artifacts_unchanged(workspace, exp.candidate_artifact_hashes, "acceptance")
            sources = [
                (workspace / artifact.path, self.root / artifact.path) for artifact in self.cfg.artifacts
            ]
            for source, destination in sources:
                if not source.is_file():
                    raise FileNotFoundError(f"Accepted artifact missing: {source}")
                if not destination.resolve().is_relative_to(self.root):
                    raise StateConflictError(f"Accepted artifact escapes project root: {destination}")
            if dry_run:
                return AcceptResult(exp_id, dry_run=True)

            backup_path = self._apply_with_backup(state, exp, sources)
            state.accepted_experiment_id = exp_id
            state.accepted_at = self._now()
            state.accepted_backup_path = backup_path
            self.store.save(state)
            self._append_acceptance_log(exp, backup_path)
            return AcceptResult(exp_id, dry_run=False, backup_path=backup_path)

    def reset(self) -> Path | None:
        with self.store.lock():
            return self.store.reset(archive=True)

    def _apply_with_backup(
        self,
        state: State,
        exp: Experiment,
        sources: list[tuple[Path, Path]],
    ) -> str:
        if state.session is None:
            raise LooperError("Missing session metadata.")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = self.root / ".looper" / "backups" / f"{timestamp}-{exp.id}"
        staging_dir = self.root / ".looper" / "accept-staging" / f"{timestamp}-{exp.id}"
        backup_dir.mkdir(parents=True, exist_ok=False)
        staging_dir.mkdir(parents=True, exist_ok=False)

        staged: list[tuple[Path, Path]] = []
        for source, destination in sources:
            relative = destination.relative_to(self.root)
            backup = backup_dir / relative
            stage = staging_dir / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup)
            shutil.copy2(source, stage)
            staged.append((stage, destination))

        applied: list[Path] = []
        try:
            for stage, destination in staged:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage, destination)
                applied.append(destination)
        except Exception:
            for destination in reversed(applied):
                backup = backup_dir / destination.relative_to(self.root)
                if backup.exists():
                    shutil.copy2(backup, destination)
            raise
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
        return self._relative(backup_dir)

    def _assert_session_current(self, state: State, force: bool = False) -> None:
        if state.session is None:
            raise StateConflictError(
                "Saved state predates session tracking. Run 'looper baseline --force' to archive and rebuild it."
            )
        if state.session.config_hash != self.cfg_hash:
            raise StateConflictError(
                "looper.yaml changed after the baseline. Run 'looper baseline --force' to start a new session."
            )
        current_hash, _, _ = project_fingerprint(self.root, self.artifact_paths, self.cfg_hash)
        if not force and current_hash != state.session.project_hash:
            raise StateConflictError(
                "The project changed after the baseline. Run 'looper baseline --force' or use --force only after reviewing the changes."
            )

    def _assert_artifacts_unchanged(
        self,
        workspace: Path,
        expected: dict[str, str],
        phase: str,
    ) -> None:
        actual = artifact_hashes(workspace, self.artifact_paths)
        changed = [path for path in self.artifact_paths if actual.get(path) != expected.get(path)]
        if changed:
            raise ArtifactIntegrityError(
                f"Configured artifacts changed during {phase}: {', '.join(changed)}. "
                "Evaluators and gates must treat candidate artifacts as read-only."
            )

    def _starting_parent(self, state: State) -> Experiment:
        if state.best_experiment_id and state.improvement_found:
            best = next((exp for exp in state.experiments if exp.id == state.best_experiment_id), None)
            if best is not None:
                return best
        if state.baseline is None:
            raise LooperError("Baseline is missing.")
        return state.baseline

    def _next_parent(self, parent: Experiment, experiments: list[Experiment]) -> Experiment:
        candidates = [
            exp
            for exp in experiments
            if exp.status == "passed" and exp.gates_passed and exp.score is not None
        ]
        if not candidates:
            return parent
        if self.cfg.metric.direction == "maximize":
            best = max(candidates, key=lambda exp: exp.score if exp.score is not None else float("-inf"))
        else:
            best = min(candidates, key=lambda exp: exp.score if exp.score is not None else float("inf"))
        return best if self.selector.better_than(best, parent) else parent

    def _budget_stop_reason(self, state: State) -> str:
        budget = self.cfg.budget
        if budget.max_experiments is not None and len(state.experiments) >= budget.max_experiments:
            return f"Experiment budget reached ({budget.max_experiments})."
        total_cost = sum(exp.cost_usd for exp in state.experiments)
        if budget.max_total_cost_usd is not None and total_cost >= budget.max_total_cost_usd:
            return f"Cost budget reached (${budget.max_total_cost_usd:g})."
        total_duration = sum(exp.duration_seconds for exp in state.experiments)
        if (
            budget.max_total_duration_seconds is not None
            and total_duration >= budget.max_total_duration_seconds
        ):
            return f"Duration budget reached ({budget.max_total_duration_seconds:g}s)."
        return ""

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
        result_path.write_text(json.dumps(raw_result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
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
            "looper_version": __version__,
            "project": self.cfg.name,
            "session_id": exp.session_id,
            "config_hash": exp.config_hash,
            "project_hash": exp.project_hash,
            "experiment_id": exp.id,
            "parent": exp.parent,
            "round_index": exp.round_index,
            "variant_index": exp.variant_index,
            "status": exp.status,
            "score": exp.score,
            "score_samples": exp.score_samples,
            "metric_name": self.cfg.metric.name,
            "metric_direction": self.cfg.metric.direction,
            "duration_seconds": exp.duration_seconds,
            "cost_usd": exp.cost_usd,
            "hypothesis": exp.hypothesis,
            "change_summary": exp.change_summary,
            "artifacts": exp.artifacts,
            "candidate_artifact_hashes": exp.candidate_artifact_hashes,
            "diff_path": exp.diff_path,
            "result_path": exp.result_path,
            "review": exp.review.model_dump(),
            "selected_best_after_version": state.best_experiment_id,
            "improvement_found_after_version": state.improvement_found,
            "python": {"executable": str(active_python()), "version": active_python_version()},
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, allow_nan=False) + "\n")

    def _append_acceptance_log(self, exp: Experiment, backup_path: str) -> None:
        path = self.root / ".looper" / "acceptances.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "accepted_at": self._now(),
                        "session_id": exp.session_id,
                        "experiment_id": exp.id,
                        "backup_path": backup_path,
                        "candidate_artifact_hashes": exp.candidate_artifact_hashes,
                    }
                )
                + "\n"
            )

    def _validate_artifacts_exist(self) -> None:
        missing = [path for path in self.artifact_paths if not (self.root / path).is_file()]
        if missing:
            raise FileNotFoundError(f"Configured artifacts not found: {', '.join(missing)}")

    def _workspace_path(self, exp: Experiment) -> Path:
        path = Path(exp.workspace)
        return path if path.is_absolute() else self.root / path

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()
