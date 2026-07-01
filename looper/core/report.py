from __future__ import annotations

from pathlib import Path

from looper.core.config import LooperConfig
from looper.core.models import Experiment, State


class Reporter:
    def __init__(self, cfg: LooperConfig, root: Path):
        self.cfg = cfg
        self.root = root

    def write(self, state: State) -> Path:
        reports_dir = self.root / ".looper" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / "latest.md"

        best = self._find(state, state.best_experiment_id)
        lines = [
            f"# Looper Report: {self.cfg.name}",
            "",
            "## Baseline",
            "",
        ]

        if state.baseline:
            lines.append(f"- Score: `{state.baseline.score}`")
            lines.append(f"- Status: `{state.baseline.status}`")
            lines.append(f"- Gates: {self._gate_summary(state.baseline)}")
            if state.baseline.result_path:
                lines.append(f"- Result: `{state.baseline.result_path}`")
        else:
            lines.append("- No baseline run found.")

        lines.extend(["", "## Experiments", ""])

        if not state.experiments:
            lines.append("No experiments found.")
        else:
            lines.append("| Experiment | Score | Status | Gates | Changed artifacts | Result |")
            lines.append("|---|---:|---|---|---|---|")
            for exp in state.experiments:
                changed = ", ".join(f"`{path}`" for path in exp.artifacts) or "none"
                result = f"`{exp.result_path}`" if exp.result_path else "n/a"
                lines.append(
                    f"| {exp.id} | {exp.score} | {exp.status} | "
                    f"{self._gate_summary(exp)} | {changed} | {result} |"
                )

        lines.extend(["", "## Best", ""])

        if best:
            lines.append(f"- Best experiment: `{best.id}`")
            lines.append(f"- Score: `{best.score}`")
            improvement = "yes" if state.improvement_found else "no"
            lines.append(f"- Improves baseline: `{improvement}`")
            if state.baseline and state.baseline.score is not None and best.score is not None:
                lines.append(f"- Delta: `{best.score - state.baseline.score:+.4f}`")
            lines.append("- Changed artifact paths:")
            for artifact in best.artifacts:
                lines.append(f"  - `{artifact}`")
        else:
            lines.append("No passing best experiment selected.")

        lines.extend(["", "## Next Recommended Action", ""])
        if best and state.improvement_found:
            lines.append("Accept the winning artifact diff:")
            lines.append("")
            lines.append("```bash")
            lines.append("looper accept best")
            lines.append("```")
        elif best:
            lines.append(
                "Review the best variant manually or run another round; it does not improve the baseline."
            )
        else:
            lines.append("Run more variants or fix failing gates before accepting a change.")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _find(self, state: State, experiment_id: str | None) -> Experiment | None:
        if experiment_id is None:
            return None
        for exp in state.experiments:
            if exp.id == experiment_id:
                return exp
        return None

    def _gate_summary(self, exp: Experiment) -> str:
        if not exp.gates:
            return "none"
        return ", ".join(
            f"{gate.name}:{'pass' if gate.passed else 'fail'}"
            for gate in exp.gates
        )
