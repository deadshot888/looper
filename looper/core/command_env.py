from __future__ import annotations

import json
import os
import platform
import stat
import sys
from pathlib import Path


def active_python() -> Path:
    override = os.environ.get("LOOPER_PYTHON")
    if override:
        return Path(override)
    return Path(sys.executable)


def active_python_version() -> str:
    return platform.python_version()


def build_command_env(
    workspace: Path,
    artifact_paths: list[str],
    experiment_id: str,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    shim_dir = ensure_python_shims(workspace)
    python = active_python()

    env["LOOPER_EXPERIMENT_ID"] = experiment_id
    env["LOOPER_ARTIFACTS"] = json.dumps(artifact_paths)
    env["LOOPER_PYTHON"] = str(python)
    env["LOOPER_PYTHON_VERSION"] = active_python_version()
    env["PYTHON"] = str(python)
    env["PYTHON3"] = str(python)
    env["PATH"] = f"{shim_dir}{os.pathsep}{python.parent}{os.pathsep}{env.get('PATH', '')}"
    if extra:
        env.update(extra)
    return env


def ensure_python_shims(workspace: Path) -> Path:
    shim_dir = workspace / ".looper" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    python = active_python()

    if os.name == "nt":
        _write_if_changed(shim_dir / "python.bat", f'@echo off\r\n"{python}" %*\r\n')
        _write_if_changed(shim_dir / "python3.bat", f'@echo off\r\n"{python}" %*\r\n')
    else:
        script = f'#!/bin/sh\nexec "{python}" "$@"\n'
        for name in ("python", "python3"):
            path = shim_dir / name
            _write_if_changed(path, script)
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return shim_dir


def _write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
