from __future__ import annotations

import subprocess

from looper.core.workspace import WorkspaceBackend


def test_git_workspace_keeps_required_artifact_and_excludes_local_files(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.py"
    tracked.write_text("print('tracked')\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py", ".gitignore"], cwd=tmp_path, check=True)

    required = tmp_path / "prompt.md"
    required.write_text("untracked artifact\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("untracked local note\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")

    workspace = WorkspaceBackend(tmp_path, required_paths=["prompt.md"]).create("exp_0001")

    assert (workspace / "tracked.py").exists()
    assert (workspace / "prompt.md").exists()
    assert not (workspace / "notes.txt").exists()
    assert not (workspace / ".env").exists()
