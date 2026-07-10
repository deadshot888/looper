from __future__ import annotations

from typer.testing import CliRunner

from looper.cli import app


def test_init_example_copies_packaged_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["init", "--example", "prompt"])

    assert result.exit_code == 0
    assert (tmp_path / "looper.yaml").exists()
    assert (tmp_path / ".looper" / "state.json").exists()
    assert (
        tmp_path
        / "examples"
        / "prompt_optimization"
        / "prompts"
        / "support_agent.md"
    ).exists()


def test_run_writes_version_log_reviews_and_dashboard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    init_result = runner.invoke(app, ["init", "--example", "prompt"])
    assert init_result.exit_code == 0, init_result.output

    run_result = runner.invoke(app, ["run", "--rounds", "1", "--variants", "1"])
    assert run_result.exit_code == 0, run_result.output

    assert (tmp_path / ".looper" / "versions.jsonl").exists()
    assert (tmp_path / ".looper" / "experiments" / "exp_0001" / "diff.patch").exists()
    assert (tmp_path / ".looper" / "experiments" / "exp_0001" / "review.md").exists()
    dashboard = tmp_path / ".looper" / "reports" / "dashboard.html"
    assert dashboard.exists()
    html = dashboard.read_text(encoding="utf-8")
    assert "Version Reviews" in html
    assert "Python" in html
