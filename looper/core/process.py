from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


@dataclass
class _CappedCapture:
    limit: int
    parts: list[str]
    length: int = 0
    removed: int = 0

    def add(self, chunk: str) -> None:
        remaining = max(0, self.limit - self.length)
        if remaining:
            kept = chunk[:remaining]
            self.parts.append(kept)
            self.length += len(kept)
        self.removed += max(0, len(chunk) - remaining)

    def render(self) -> str:
        value = "".join(self.parts)
        if self.removed:
            value += f"\n...[truncated {self.removed} characters]"
        return value


def run_command(
    command: str,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    max_output_chars: int,
) -> CommandResult:
    kwargs: dict = {
        "args": command,
        "shell": True,
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    started = time.monotonic()
    process = subprocess.Popen(**kwargs)
    stdout_capture = _CappedCapture(max_output_chars, [])
    stderr_capture = _CappedCapture(max_output_chars, [])
    stdout_thread = threading.Thread(
        target=_drain_stream,
        args=(process.stdout, stdout_capture),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_drain_stream,
        args=(process.stderr, stderr_capture),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_tree(process)
        process.wait()
    stdout_thread.join()
    stderr_thread.join()
    duration = time.monotonic() - started

    stdout = stdout_capture.render()
    stderr = stderr_capture.render()
    if timed_out:
        message = f"Command timed out after {timeout_seconds:g} seconds."
        stderr = _truncate(f"{stderr}\n{message}".strip(), max_output_chars)

    return CommandResult(
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        timed_out=timed_out,
    )


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        with suppress(ProcessLookupError):
            cast(Any, os).killpg(process.pid, cast(Any, signal).SIGKILL)
    with suppress(OSError):
        process.kill()


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    removed = len(value) - limit
    return value[:limit] + f"\n...[truncated {removed} characters]"


def _drain_stream(stream, capture: _CappedCapture) -> None:
    if stream is None:
        return
    try:
        for chunk in iter(lambda: stream.read(4096), ""):
            capture.add(chunk)
    finally:
        stream.close()
