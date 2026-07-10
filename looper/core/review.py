from __future__ import annotations

from looper.core.config import Direction
from looper.core.models import Experiment, VersionReview


def review_experiment(
    exp: Experiment,
    baseline: Experiment | None,
    direction: Direction,
) -> VersionReview:
    delta = _score_delta(exp, baseline)
    directional_delta = _directional_delta(delta, direction)
    what_worked: list[str] = []
    what_to_improve: list[str] = []

    if exp.status == "passed" and exp.gates_passed:
        what_worked.append("All configured gates passed.")
    elif exp.gates:
        failed = [gate.name for gate in exp.gates if not gate.passed]
        if failed:
            what_to_improve.append(f"Fix failing gates: {', '.join(failed)}.")

    if exp.notes:
        what_worked.append(exp.notes)

    if delta is not None:
        if directional_delta > 0:
            what_worked.append(f"Improved the primary score by {_format_delta(delta)}.")
        elif directional_delta == 0:
            what_to_improve.append("Matched the baseline score; look for qualitative differences.")
        else:
            what_to_improve.append(f"Moved the primary score by {_format_delta(delta)} versus baseline.")

    metric_changes = _metric_changes(exp, baseline)
    if metric_changes:
        what_worked.extend(metric_changes[:2])

    if exp.diff_path:
        what_worked.append(
            f"Captured a reviewable diff with +{exp.additions}/-{exp.deletions} line changes."
        )
    elif exp.id != "baseline":
        what_to_improve.append("No artifact diff was captured for this version.")

    if exp.stderr:
        what_to_improve.append("Review stderr output before accepting this version.")

    if not what_worked:
        what_worked.append("No clear positive signal was detected yet.")
    if not what_to_improve:
        what_to_improve.append("Use manual review to check whether the diff matches the hypothesis.")

    return VersionReview(
        summary=_summary(exp, baseline, directional_delta),
        what_worked=what_worked,
        what_to_improve=what_to_improve,
        recommendation=_recommendation(exp, directional_delta),
    )


def _summary(
    exp: Experiment,
    baseline: Experiment | None,
    directional_delta: float | None,
) -> str:
    if exp.id == "baseline":
        return "Baseline run establishes the reference score and gate behavior."
    if exp.status == "error":
        return "This version did not complete, so it should be treated as execution feedback."
    if exp.status != "passed":
        return "This version produced a result but is blocked by gates or status checks."
    if baseline is None or directional_delta is None:
        return "This version passed, but there is no baseline score for comparison."
    if directional_delta > 0:
        return "This version passed gates and beat the baseline."
    if directional_delta == 0:
        return "This version passed gates and tied the baseline."
    return "This version passed gates but did not beat the baseline."


def _recommendation(exp: Experiment, directional_delta: float | None) -> str:
    if exp.id == "baseline":
        return "Use as the comparison point for later versions."
    if exp.status == "error":
        return "Do not accept; fix the command or inputs and rerun."
    if exp.status != "passed" or not exp.gates_passed:
        return "Do not accept until the failing gates are addressed."
    if directional_delta is None:
        return "Review manually; no baseline comparison is available."
    if directional_delta > 0:
        return "Strong candidate; inspect the diff and consider accepting or combining its best ideas."
    return "Mine for useful parts, then run another iteration."


def _score_delta(exp: Experiment, baseline: Experiment | None) -> float | None:
    if baseline is None or baseline.score is None or exp.score is None:
        return None
    return exp.score - baseline.score


def _directional_delta(delta: float | None, direction: Direction) -> float | None:
    if delta is None:
        return None
    return delta if direction == "maximize" else -delta


def _format_delta(delta: float) -> str:
    return f"{delta:+.4f}"


def _metric_changes(exp: Experiment, baseline: Experiment | None) -> list[str]:
    if baseline is None:
        return []
    changes: list[tuple[float, str]] = []
    for key, value in exp.metrics.items():
        base_value = baseline.metrics.get(key)
        if not isinstance(value, (int, float)) or not isinstance(base_value, (int, float)):
            continue
        delta = float(value) - float(base_value)
        if delta == 0:
            continue
        changes.append((abs(delta), f"Metric `{key}` changed by {_format_delta(delta)}."))
    changes.sort(reverse=True, key=lambda item: item[0])
    return [message for _, message in changes]
