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
    assert (tmp_path / "examples" / "prompt_optimization" / "prompts" / "support_agent.md").exists()


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


def test_operational_commands_are_usable_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    assert runner.invoke(app, ["--version"]).exit_code == 0
    assert runner.invoke(app, ["init", "--example", "prompt"]).exit_code == 0
    assert runner.invoke(app, ["validate"]).exit_code == 0

    doctor = runner.invoke(app, ["doctor", "--json"])
    assert doctor.exit_code == 0, doctor.output
    assert '"workspace_files"' in doctor.output

    run_result = runner.invoke(app, ["run", "--rounds", "1", "--variants", "1"])
    assert run_result.exit_code == 0, run_result.output

    listing = runner.invoke(app, ["list", "--json"])
    assert listing.exit_code == 0
    assert "exp_0001" in listing.output

    shown = runner.invoke(app, ["show", "exp_0001", "--json"])
    assert shown.exit_code == 0
    assert "candidate_artifact_hashes" in shown.output

    diff = runner.invoke(app, ["diff", "exp_0001"])
    assert diff.exit_code == 0
    assert "support_agent.md" in diff.output

    preview = runner.invoke(app, ["accept", "best", "--dry-run"])
    assert preview.exit_code == 0, preview.output
    accepted = runner.invoke(app, ["accept", "best"])
    assert accepted.exit_code == 0, accepted.output
    assert "Backup written" in accepted.output

    stale_run = runner.invoke(app, ["run", "--rounds", "1", "--variants", "1"])
    assert stale_run.exit_code == 1
    assert "Error:" in stale_run.output

    clean_preview = runner.invoke(app, ["clean", "--all"])
    assert clean_preview.exit_code == 0
    assert "Dry run only" in clean_preview.output
    cleaned = runner.invoke(app, ["clean", "--all", "--yes"])
    assert cleaned.exit_code == 0, cleaned.output


def test_invalid_config_is_reported_without_traceback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "looper.yaml").write_text("", encoding="utf-8")
    result = CliRunner().invoke(app, ["validate"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output
