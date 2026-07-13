from __future__ import annotations

from looper.core.config import LooperConfig
from looper.core.models import Experiment, State


class Selector:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def select_best(self, state: State) -> str | None:
        candidates = [
            exp
            for exp in state.experiments
            if exp.status == "passed" and exp.score is not None and exp.gates_passed
        ]
        if not candidates:
            return None

        if self.cfg.metric.direction == "maximize":
            best = max(candidates, key=lambda e: e.score if e.score is not None else float("-inf"))
        else:
            best = min(candidates, key=lambda e: e.score if e.score is not None else float("inf"))

        return best.id

    def improved_over_baseline(self, baseline: Experiment | None, best: Experiment | None) -> bool:
        if baseline is None or baseline.score is None or best is None or best.score is None:
            return False
        if self.cfg.metric.direction == "maximize":
            return best.score - baseline.score > self.cfg.search.min_improvement
        return baseline.score - best.score > self.cfg.search.min_improvement

    def better_than(self, candidate: Experiment, parent: Experiment) -> bool:
        if candidate.score is None or parent.score is None:
            return False
        if self.cfg.metric.direction == "maximize":
            return candidate.score - parent.score > self.cfg.search.min_improvement
        return parent.score - candidate.score > self.cfg.search.min_improvement
