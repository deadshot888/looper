from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console

from looper import __version__
from looper.core.config import LooperConfig, load_config
from looper.core.engine import Engine
from looper.core.errors import LooperError
from looper.core.models import Experiment, State
from looper.core.state import StateStore

app = typer.Typer(
    help="Run inspectable improvement loops for agent artifacts.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
console = Console()
error_console = Console(stderr=True)

EXAMPLES = {
    "prompt": "prompt_optimization",
    "instructions": "agent_instructions",
    "schema": "tool_schema",
    "mcp": "mcp_tool_selection",
    "dogfood": "repo_dogfood",
}


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"looper {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed Looper version and exit.",
    ),
) -> None:
    """Looper keeps every candidate reviewable before it can be accepted."""


def _gate_summary(exp: Experiment) -> str:
    if not exp.gates:
        return "no gates"
    return ", ".join(f"{gate.name}={'pass' if gate.passed else 'fail'}" for gate in exp.gates)


def _copy_resource_tree(source: Traversable, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, target)
        elif not target.exists():
            target.write_bytes(child.read_bytes())


def _copy_example(example_dir: str, root: Path) -> Path | None:
    destination = root / "examples" / example_dir
    if destination.exists():
        return destination

    development_source = Path(__file__).resolve().parent.parent / "examples" / example_dir
    if development_source.is_dir():
        shutil.copytree(development_source, destination)
        return destination

    package_source = resources.files("looper.templates").joinpath("examples", example_dir)
    if not package_source.is_dir():
        return None
    _copy_resource_tree(package_source, destination)
    return destination


def _engine(config: str) -> Engine:
    return Engine(load_config(Path(config)), Path.cwd())


def _abort(exc: Exception) -> None:
    if isinstance(exc, ValidationError):
        message = "Invalid looper.yaml:\n" + str(exc)
    else:
        message = str(exc) or exc.__class__.__name__
    error_console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=1)


@app.command()
def init(
    example: str | None = typer.Option(
        None,
        help="Initialize with an example: prompt, instructions, schema, mcp, or dogfood.",
    ),
) -> None:
    """Initialize a Looper project without overwriting existing files."""
    try:
        root = Path.cwd()
        looper_dir = root / ".looper"
        for name in ("workspaces", "reports", "experiments"):
            (looper_dir / name).mkdir(parents=True, exist_ok=True)
        store = StateStore(root)
        if not store.path.exists():
            store.save(State())

        if example is None:
            cfg = root / "looper.yaml"
            if not cfg.exists():
                cfg.write_text(LooperConfig.example_yaml(), encoding="utf-8")
                console.print("[green]Created looper.yaml.[/green]")
            console.print("[green]Initialized .looper/[/green]")
            return

        example_dir = EXAMPLES.get(example)
        if example_dir is None:
            available = ", ".join(sorted(EXAMPLES))
            raise typer.BadParameter(f"Unknown example {example!r}. Choose one of: {available}.")
        copied_example = _copy_example(example_dir, root)
        if copied_example is None:
            raise LooperError(f"Packaged {example!r} example is missing.")
        source_config = copied_example / "looper.yaml"
        destination_config = root / "looper.yaml"
        if not destination_config.exists():
            shutil.copyfile(source_config, destination_config)
            console.print(f"[green]Created looper.yaml from {example} example.[/green]")
        else:
            console.print("[yellow]looper.yaml already exists; leaving it unchanged.[/yellow]")

        if example == "dogfood" and not (root / "README.md").exists():
            target = copied_example / "target_README.md"
            if not target.exists():
                raise LooperError("The dogfood example is missing target_README.md.")
            shutil.copyfile(target, root / "README.md")
            console.print("[green]Created a README.md dogfood target.[/green]")
        console.print(f"[green]Copied example files to examples/{example_dir}/[/green]")
        console.print("[green]Initialized .looper/[/green]")
    except typer.Exit:
        raise
    except Exception as exc:
        _abort(exc)


@app.command()
def baseline(
    config: str = typer.Option("looper.yaml", help="Path to config file."),
    force: bool = typer.Option(
        False, "--force", help="Archive the active state and create a fresh baseline."
    ),
) -> None:
    """Run and store an isolated baseline."""
    try:
        result = _engine(config).run_baseline(force=force)
        console.print(f"[green]Baseline score: {result.score}[/green]")
        console.print(f"[green]Baseline gates: {_gate_summary(result)}[/green]")
    except Exception as exc:
        _abort(exc)


@app.command()
def run(
    rounds: int | None = typer.Option(None, min=1, help="Number of iterative rounds."),
    variants: int | None = typer.Option(None, min=1, help="Variants per round."),
    config: str = typer.Option("looper.yaml", help="Path to config file."),
) -> None:
    """Run variants, advancing each round from the previous winner."""
    try:
        cfg = load_config(Path(config))
        if rounds is not None:
            cfg.search.rounds = rounds
        if variants is not None:
            cfg.search.variants_per_round = variants
        engine = Engine(cfg, Path.cwd())
        before_count = len(engine.store.load().experiments)
        state = engine.run()
        for exp in state.experiments[before_count:]:
            score = "n/a" if exp.score is None else str(exp.score)
            console.print(
                f"{exp.id}: parent={exp.parent} score={score} status={exp.status} gates={_gate_summary(exp)}"
            )
        best = state.best_experiment_id or "none"
        improvement = "yes" if state.improvement_found else "no"
        console.print(
            f"[green]Run complete. Best experiment: {best}. Improves baseline: {improvement}[/green]"
        )
        if state.stop_reason:
            console.print(f"[yellow]Stopped: {state.stop_reason}[/yellow]")
        console.print(f"[green]Report written to {engine.generate_report()}[/green]")
        console.print(f"[green]Dashboard written to {engine.generate_dashboard()}[/green]")
    except Exception as exc:
        _abort(exc)


@app.command()
def report(config: str = typer.Option("looper.yaml", help="Path to config file.")) -> None:
    """Generate a Markdown report and HTML dashboard."""
    try:
        engine = _engine(config)
        console.print(f"[green]Report written to {engine.generate_report()}[/green]")
        console.print(f"[green]Dashboard written to {engine.generate_dashboard()}[/green]")
    except Exception as exc:
        _abort(exc)


@app.command()
def dashboard(config: str = typer.Option("looper.yaml", help="Path to config file.")) -> None:
    """Generate the static HTML dashboard."""
    try:
        console.print(f"[green]Dashboard written to {_engine(config).generate_dashboard()}[/green]")
    except Exception as exc:
        _abort(exc)


@app.command()
def accept(
    target: str = typer.Argument("best"),
    config: str = typer.Option("looper.yaml", help="Path to config file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Verify acceptance without changing artifacts."),
    force: bool = typer.Option(False, "--force", help="Bypass project-change conflicts after manual review."),
) -> None:
    """Accept a passing candidate with conflict checks and rollback backup."""
    try:
        result = _engine(config).accept(target, dry_run=dry_run, force=force)
        if result.dry_run:
            console.print(f"[green]Dry run passed for experiment: {result.experiment_id}[/green]")
        else:
            console.print(f"[green]Accepted experiment: {result.experiment_id}[/green]")
            console.print(f"[green]Backup written to {result.backup_path}[/green]")
    except Exception as exc:
        _abort(exc)


@app.command("validate")
def validate_command(config: str = typer.Option("looper.yaml", help="Path to config file.")) -> None:
    """Validate configuration, artifact paths, and provider support."""
    try:
        engine = _engine(config)
        console.print(f"[green]Configuration is valid for {engine.cfg.name}.[/green]")
    except Exception as exc:
        _abort(exc)


@app.command()
def doctor(
    config: str = typer.Option("looper.yaml", help="Path to config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Preflight the project before spending evaluation time."""
    try:
        engine = _engine(config)
        file_count, byte_count = engine.workspace.estimate()
        git = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        payload = {
            "project": engine.cfg.name,
            "looper_version": __version__,
            "artifacts": engine.artifact_paths,
            "workspace_files": file_count,
            "workspace_mib": round(byte_count / 1024 / 1024, 2),
            "git_dirty": bool(git.stdout.strip()) if git.returncode == 0 else None,
            "inherits_environment": engine.cfg.execution.inherit_env,
            "runner_timeout_seconds": engine.cfg.runner.timeout_seconds,
            "runner_repeats": engine.cfg.runner.repeats,
        }
        if json_output:
            console.print_json(data=payload)
        else:
            console.print(f"[green]Project: {payload['project']}[/green]")
            console.print(f"Artifacts: {len(engine.artifact_paths)}")
            console.print(f"Workspace copy: {file_count} files / {payload['workspace_mib']} MiB")
            console.print(
                f"Runner: {engine.cfg.runner.repeats} evaluation(s), {engine.cfg.runner.timeout_seconds:g}s timeout"
            )
            if engine.cfg.execution.inherit_env:
                console.print(
                    "[yellow]Commands inherit the complete environment; prefer env_allowlist where possible.[/yellow]"
                )
            console.print("[green]Doctor checks passed.[/green]")
    except Exception as exc:
        _abort(exc)


@app.command("list")
def list_versions(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """List baseline and experiment versions from the active session."""
    try:
        state = StateStore(Path.cwd()).load()
        versions = [exp for exp in [state.baseline, *state.experiments] if exp is not None]
        if json_output:
            console.print_json(data=[exp.model_dump(mode="json") for exp in versions])
            return
        if not versions:
            console.print("No versions found.")
            return
        for exp in versions:
            score = "n/a" if exp.score is None else f"{exp.score:g}"
            selected = " [best]" if exp.id == state.best_experiment_id else ""
            console.print(f"{exp.id}: score={score} status={exp.status} parent={exp.parent}{selected}")
    except Exception as exc:
        _abort(exc)


@app.command()
def show(
    experiment_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Show one stored experiment."""
    try:
        state = StateStore(Path.cwd()).load()
        exp = _find_experiment(state, experiment_id)
        if json_output:
            console.print_json(data=exp.model_dump(mode="json"))
        else:
            console.print(f"[bold]{exp.id}[/bold] ({exp.status})")
            console.print(f"Parent: {exp.parent}")
            console.print(f"Score: {exp.score}")
            console.print(f"Samples: {exp.score_samples}")
            console.print(f"Gates: {_gate_summary(exp)}")
            console.print(f"Hypothesis: {exp.hypothesis}")
            console.print(f"Diff: {exp.diff_path or 'n/a'}")
            console.print(f"Recommendation: {exp.review.recommendation}")
    except Exception as exc:
        _abort(exc)


@app.command("diff")
def diff_command(experiment_id: str) -> None:
    """Print the recorded artifact diff for an experiment."""
    try:
        exp = _find_experiment(StateStore(Path.cwd()).load(), experiment_id)
        if not exp.diff_path:
            console.print("No diff was recorded.")
            return
        path = Path.cwd() / exp.diff_path
        if not path.is_file():
            raise FileNotFoundError(f"Diff file not found: {path}")
        console.print(path.read_text(encoding="utf-8"), markup=False)
    except Exception as exc:
        _abort(exc)


@app.command()
def reset(yes: bool = typer.Option(False, "--yes", help="Archive active state without prompting.")) -> None:
    """Archive active state and prepare a fresh session."""
    try:
        if not yes:
            console.print("[yellow]Dry run: pass --yes to archive active state and reset it.[/yellow]")
            return
        store = StateStore(Path.cwd())
        with store.lock():
            archived = store.reset(archive=True)
        console.print(f"[green]State reset. Archive: {archived or 'none'}[/green]")
    except Exception as exc:
        _abort(exc)


@app.command()
def clean(
    all_artifacts: bool = typer.Option(False, "--all", help="Also remove experiment results and reports."),
    yes: bool = typer.Option(False, "--yes", help="Perform the cleanup; otherwise only preview it."),
) -> None:
    """Preview or remove generated workspaces and optional result artifacts."""
    try:
        root = Path.cwd().resolve()
        looper_dir = (root / ".looper").resolve()
        targets = [looper_dir / "workspaces", looper_dir / "bin"]
        if all_artifacts:
            targets.extend([looper_dir / "experiments", looper_dir / "reports"])
        existing = [path for path in targets if path.exists()]
        byte_count = sum(
            file.stat().st_size for target in existing for file in target.rglob("*") if file.is_file()
        )
        console.print(f"Cleanup target: {len(existing)} directories / {byte_count / 1024 / 1024:.2f} MiB")
        if not yes:
            console.print("[yellow]Dry run only. Pass --yes to remove these generated files.[/yellow]")
            return
        for target in existing:
            if not target.resolve().is_relative_to(looper_dir):
                raise LooperError(f"Refusing to clean path outside .looper: {target}")
            shutil.rmtree(target)
        if all_artifacts:
            store = StateStore(root)
            with store.lock():
                store.reset(archive=True)
        console.print("[green]Generated files cleaned.[/green]")
    except Exception as exc:
        _abort(exc)


def _find_experiment(state: State, experiment_id: str) -> Experiment:
    if experiment_id == "baseline" and state.baseline is not None:
        return state.baseline
    exp = next((candidate for candidate in state.experiments if candidate.id == experiment_id), None)
    if exp is None:
        raise LooperError(f"Experiment not found: {experiment_id}")
    return exp


if __name__ == "__main__":
    app()
