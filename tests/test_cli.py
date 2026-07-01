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
