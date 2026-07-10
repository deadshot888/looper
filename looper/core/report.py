from __future__ import annotations

import html
from pathlib import Path

from looper.core.command_env import active_python, active_python_version
from looper.core.config import LooperConfig
from looper.core.models import Experiment, State, VersionReview


class Reporter:
    def __init__(self, cfg: LooperConfig, root: Path):
        self.cfg = cfg
        self.root = root

    def write(self, state: State) -> Path:
        reports_dir = self.root / ".looper" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / "latest.md"
        dashboard = self.write_dashboard(state)

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
            lines.append(f"- Hypothesis: {state.baseline.hypothesis}")
            if state.baseline.result_path:
                lines.append(f"- Result: `{self._display_path(state.baseline.result_path)}`")
        else:
            lines.append("- No baseline run found.")

        lines.extend(["", "## Version Ledger", ""])
        lines.append(f"- Dashboard: `{self._relative(dashboard)}`")
        lines.append("- Append-only log: `.looper/versions.jsonl`")
        lines.append(f"- Runtime: Python `{active_python_version()}` at `{active_python()}`")

        lines.extend(["", "## Experiments", ""])

        if not state.experiments:
            lines.append("No experiments found.")
        else:
            lines.append(
                "| Experiment | Score | Delta | Status | Gates | Hypothesis | Diff | Recommendation |"
            )
            lines.append("|---|---:|---:|---|---|---|---|---|")
            for exp in state.experiments:
                diff = f"`{self._display_path(exp.diff_path)}`" if exp.diff_path else "n/a"
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            exp.id,
                            self._score(exp),
                            self._delta(exp, state.baseline),
                            exp.status,
                            self._gate_summary(exp),
                            self._md_cell(exp.hypothesis),
                            diff,
                            self._md_cell(self._review(exp).recommendation),
                        ]
                    )
                    + " |"
                )

        lines.extend(["", "## Selected Candidate", ""])

        if best:
            lines.append(f"- Selected experiment: `{best.id}`")
            lines.append(f"- Score: `{best.score}`")
            improvement = "yes" if state.improvement_found else "no"
            lines.append(f"- Improves baseline: `{improvement}`")
            lines.append(f"- Delta: `{self._delta(best, state.baseline)}`")
            lines.append(f"- Hypothesis: {best.hypothesis}")
            lines.append(f"- Change summary: {best.change_summary}")
            lines.append(f"- Diff: `{self._display_path(best.diff_path) if best.diff_path else 'n/a'}`")
        else:
            lines.append("No passing candidate selected.")

        lines.extend(["", "## Version Reviews", ""])
        versions = [exp for exp in [state.baseline, *state.experiments] if exp is not None]
        for exp in versions:
            review = self._review(exp)
            lines.extend(
                [
                    f"### {exp.id}",
                    "",
                    review.summary or "No review summary recorded.",
                    "",
                    "**What worked**",
                    "",
                ]
            )
            lines.extend(f"- {item}" for item in review.what_worked or ["No clear positive signal yet."])
            lines.extend(["", "**What to improve**", ""])
            lines.extend(
                f"- {item}"
                for item in review.what_to_improve
                or ["Use manual review to decide whether any part is worth keeping."]
            )
            lines.extend(["", f"**Recommendation:** {review.recommendation}", ""])

        lines.extend(["## Next Recommended Action", ""])
        if best and state.improvement_found:
            lines.append("Inspect the selected diff, then accept it or copy the useful parts into a new variant:")
            lines.append("")
            lines.append("```bash")
            lines.append("looper accept best")
            lines.append("```")
        elif best:
            lines.append(
                "Review the passing variants manually or run another round; the selected candidate does not improve the baseline."
            )
        else:
            lines.append("Run more variants or fix failing gates before accepting a change.")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_dashboard(self, state: State) -> Path:
        reports_dir = self.root / ".looper" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / "dashboard.html"
        path.write_text(self._dashboard_html(state), encoding="utf-8")
        return path

    def _dashboard_html(self, state: State) -> str:
        best = self._find(state, state.best_experiment_id)
        versions = [exp for exp in [state.baseline, *state.experiments] if exp is not None]
        passed = [exp for exp in state.experiments if exp.status == "passed" and exp.gates_passed]
        failed = [exp for exp in state.experiments if exp.status != "passed" or not exp.gates_passed]
        score_values = [exp.score for exp in versions if exp.score is not None]
        min_score = min(score_values) if score_values else 0.0
        max_score = max(score_values) if score_values else 1.0

        rows = "\n".join(
            self._version_row(exp, state.baseline, min_score, max_score)
            for exp in state.experiments
        ) or '<p class="empty">No experiment versions yet.</p>'

        reviews = "\n".join(self._review_panel(exp, state.baseline) for exp in versions)
        best_title = html.escape(best.id if best else "No candidate")
        best_delta = self._delta(best, state.baseline) if best else "n/a"
        improvement = "Yes" if state.improvement_found else "No"
        subtitle = (
            f"{len(state.experiments)} experiment version(s) compared against "
            f"baseline {self._score(state.baseline)}."
        )

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Looper Dashboard - {html.escape(self.cfg.name)}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #18191f;
      --muted: #5f6673;
      --line: #d9dee7;
      --teal: #0f766e;
      --blue: #2563eb;
      --amber: #b45309;
      --rose: #be123c;
      --green-soft: #dff6ed;
      --blue-soft: #e6efff;
      --amber-soft: #fff3d6;
      --rose-soft: #ffe4e8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      padding: 28px clamp(18px, 5vw, 56px) 20px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 6px; font-size: 30px; line-height: 1.12; letter-spacing: 0; }}
    h2 {{ font-size: 17px; margin-bottom: 14px; letter-spacing: 0; }}
    h3 {{ font-size: 15px; margin-bottom: 8px; letter-spacing: 0; }}
    main {{ padding: 22px clamp(18px, 5vw, 56px) 48px; }}
    .eyebrow {{
      margin-bottom: 8px;
      color: var(--teal);
      font-size: 12px;
      font-weight: 750;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .subtitle {{ max-width: 820px; color: var(--muted); margin-bottom: 0; }}
    .runtime {{
      min-width: 220px;
      align-self: start;
      padding-top: 2px;
      color: var(--muted);
      font-size: 13px;
      text-align: right;
    }}
    .runtime strong {{ display: block; color: var(--ink); font-size: 14px; }}
    .band {{
      width: 100%;
      margin-top: 18px;
      padding: 18px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .kpi {{
      min-height: 96px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }}
    .label {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }}
    .value {{ margin-top: 10px; font-size: 24px; line-height: 1.1; font-weight: 780; }}
    .note {{ color: var(--muted); font-size: 13px; margin: 8px 0 0; }}
    .candidate {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(260px, .8fr);
      gap: 18px;
      align-items: start;
    }}
    .pillrow {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 3px 9px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }}
    .pill.good {{ background: var(--green-soft); color: #075f54; border-color: #b7e9d6; }}
    .pill.warn {{ background: var(--amber-soft); color: #824007; border-color: #f1d28b; }}
    .pill.bad {{ background: var(--rose-soft); color: #9f1239; border-color: #f4b8c2; }}
    .version-list {{ display: grid; gap: 10px; }}
    .version-row {{
      display: grid;
      grid-template-columns: 120px 110px minmax(180px, 1fr) 120px;
      gap: 12px;
      align-items: center;
      padding: 13px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }}
    .scorebar {{
      height: 10px;
      width: 100%;
      overflow: hidden;
      border-radius: 999px;
      background: #e8ebf0;
    }}
    .scorebar span {{ display: block; height: 100%; border-radius: 999px; background: var(--blue); }}
    .scorebar span.pass {{ background: var(--teal); }}
    .scorebar span.fail {{ background: var(--rose); }}
    .status {{
      justify-self: start;
      min-width: 72px;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 750;
      text-align: center;
    }}
    .status.passed {{ background: var(--green-soft); color: #075f54; }}
    .status.failed, .status.error {{ background: var(--rose-soft); color: #9f1239; }}
    .review-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .review-panel {{
      padding: 15px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }}
    .review-panel ul {{ margin: 8px 0 0; padding-left: 18px; }}
    .review-panel li {{ margin: 6px 0; color: var(--muted); }}
    .summary {{ color: var(--muted); margin-bottom: 12px; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }}
    .links a {{ color: var(--blue); font-weight: 700; text-decoration: none; }}
    .links a:hover {{ text-decoration: underline; }}
    .empty {{ color: var(--muted); margin-bottom: 0; }}
    @media (max-width: 900px) {{
      header, .candidate {{ grid-template-columns: 1fr; display: grid; }}
      header {{ gap: 12px; }}
      .runtime {{ text-align: left; }}
      .kpis, .review-grid {{ grid-template-columns: 1fr 1fr; }}
      .version-row {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 560px) {{
      .kpis, .review-grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 25px; }}
      .value {{ font-size: 21px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <p class="eyebrow">Looper dashboard</p>
      <h1>{html.escape(self.cfg.name)}</h1>
      <p class="subtitle">{html.escape(subtitle)}</p>
    </div>
    <div class="runtime">
      <strong>Python {html.escape(active_python_version())}</strong>
      {html.escape(str(active_python()))}
    </div>
  </header>
  <main>
    <section class="band kpis" aria-label="Run summary">
      <div class="kpi"><div class="label">Baseline</div><div class="value">{html.escape(self._score(state.baseline))}</div><p class="note">{html.escape(state.baseline.status if state.baseline else "not run")}</p></div>
      <div class="kpi"><div class="label">Experiments</div><div class="value">{len(state.experiments)}</div><p class="note">{len(passed)} passed, {len(failed)} blocked</p></div>
      <div class="kpi"><div class="label">Selected</div><div class="value">{best_title}</div><p class="note">Delta {html.escape(best_delta)}</p></div>
      <div class="kpi"><div class="label">Improves</div><div class="value">{improvement}</div><p class="note">{html.escape(self.cfg.metric.name)} / {html.escape(self.cfg.metric.direction)}</p></div>
    </section>

    <section class="band candidate" aria-label="Selected candidate">
      <div>
        <h2>Selected Candidate</h2>
        <h3>{best_title}</h3>
        <p class="summary">{html.escape(best.hypothesis if best else "No selected candidate recorded.")}</p>
        <p>{html.escape(best.change_summary if best else "")}</p>
        {self._candidate_links(best)}
      </div>
      <div>
        <h2>Decision Signals</h2>
        <div class="pillrow">
          <span class="pill {'good' if state.improvement_found else 'warn'}">Improves baseline: {improvement}</span>
          <span class="pill {'good' if best and best.gates_passed else 'bad'}">Gates: {html.escape(self._gate_summary(best) if best else 'n/a')}</span>
          <span class="pill">Diff: {html.escape((self._display_path(best.diff_path) if best and best.diff_path else 'n/a'))}</span>
        </div>
      </div>
    </section>

    <section class="band" aria-label="Version scores">
      <h2>Version Scores</h2>
      <div class="version-list">
        {rows}
      </div>
    </section>

    <section class="band" aria-label="Version reviews">
      <h2>Version Reviews</h2>
      <div class="review-grid">
        {reviews}
      </div>
    </section>
  </main>
</body>
</html>
"""

    def _version_row(
        self,
        exp: Experiment,
        baseline: Experiment | None,
        min_score: float,
        max_score: float,
    ) -> str:
        score = self._score(exp)
        width = self._score_width(exp.score, min_score, max_score)
        bar_class = "pass" if exp.status == "passed" and exp.gates_passed else "fail"
        return f"""<div class="version-row">
  <div><strong>{html.escape(exp.id)}</strong><p class="note">Round {exp.round_index or '-'} / Variant {exp.variant_index or '-'}</p></div>
  <div><div class="label">Score</div><strong>{html.escape(score)}</strong><p class="note">{html.escape(self._delta(exp, baseline))}</p></div>
  <div><div class="scorebar" aria-label="score"><span class="{bar_class}" style="width:{width}%"></span></div><p class="note">{html.escape(exp.hypothesis or 'No hypothesis recorded.')}</p></div>
  <div><span class="status {html.escape(exp.status)}">{html.escape(exp.status)}</span></div>
</div>"""

    def _review_panel(self, exp: Experiment, baseline: Experiment | None) -> str:
        review = self._review(exp)
        worked = "".join(f"<li>{html.escape(item)}</li>" for item in review.what_worked)
        improve = "".join(f"<li>{html.escape(item)}</li>" for item in review.what_to_improve)
        links = self._candidate_links(exp)
        return f"""<article class="review-panel">
  <h3>{html.escape(exp.id)} <span class="pill">{html.escape(self._delta(exp, baseline))}</span></h3>
  <p class="summary">{html.escape(review.summary or 'No summary recorded.')}</p>
  <div class="label">What worked</div>
  <ul>{worked or '<li>No clear positive signal yet.</li>'}</ul>
  <div class="label">What to improve</div>
  <ul>{improve or '<li>Use manual review to decide what to keep.</li>'}</ul>
  <p class="summary"><strong>Recommendation:</strong> {html.escape(review.recommendation)}</p>
  {links}
</article>"""

    def _candidate_links(self, exp: Experiment | None) -> str:
        if exp is None:
            return ""
        links: list[str] = []
        if exp.diff_path:
            links.append(f'<a href="{html.escape(self._report_link(exp.diff_path))}">Diff</a>')
        if exp.result_path:
            links.append(f'<a href="{html.escape(self._report_link(exp.result_path))}">Result JSON</a>')
        review_path = f".looper/experiments/{exp.id}/review.md"
        links.append(f'<a href="{html.escape(self._report_link(review_path))}">Review</a>')
        return f'<div class="links">{"".join(links)}</div>'

    def _find(self, state: State, experiment_id: str | None) -> Experiment | None:
        if experiment_id is None:
            return None
        for exp in state.experiments:
            if exp.id == experiment_id:
                return exp
        return None

    def _gate_summary(self, exp: Experiment | None) -> str:
        if exp is None:
            return "n/a"
        if not exp.gates:
            return "none"
        return ", ".join(
            f"{gate.name}:{'pass' if gate.passed else 'fail'}"
            for gate in exp.gates
        )

    def _score(self, exp: Experiment | None) -> str:
        if exp is None or exp.score is None:
            return "n/a"
        return f"{exp.score:.4f}".rstrip("0").rstrip(".")

    def _delta(self, exp: Experiment | None, baseline: Experiment | None) -> str:
        if exp is None or baseline is None or exp.score is None or baseline.score is None:
            return "n/a"
        return f"{exp.score - baseline.score:+.4f}"

    def _score_width(self, score: float | None, min_score: float, max_score: float) -> int:
        if score is None:
            return 0
        if max_score == min_score:
            return 100
        value = (score - min_score) / (max_score - min_score)
        if self.cfg.metric.direction == "minimize":
            value = 1 - value
        return max(8, min(100, int(12 + value * 88)))

    def _review(self, exp: Experiment) -> VersionReview:
        if exp.review.summary or exp.review.what_worked or exp.review.what_to_improve:
            return exp.review
        return VersionReview(
            summary="No review summary recorded.",
            what_worked=["No clear positive signal yet."],
            what_to_improve=["Use manual review to decide whether any part is worth keeping."],
            recommendation="Review manually.",
        )

    def _md_cell(self, value: str) -> str:
        return (value or "n/a").replace("|", "\\|").replace("\n", " ")

    def _report_link(self, path: str) -> str:
        normalized = path.replace("\\", "/")
        if normalized.startswith(".looper/"):
            return "../" + normalized[len(".looper/"):]
        return normalized

    def _display_path(self, path: str) -> str:
        return path.replace("\\", "/")

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()
