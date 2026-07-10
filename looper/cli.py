from __future__ import annotations

import shutil
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from looper.core.config import LooperConfig, load_config
from looper.core.engine import Engine
from looper.core.models import Experiment, State
from looper.core.state import StateStore

app = typer.Typer(help="Set up self-improving loops for your agents.")
console = Console()

EXAMPLES = {
    "prompt": "prompt_optimization",
    "instructions": "agent_instructions",
    "schema": "tool_schema",
    "mcp": "mcp_tool_selection",
    "dogfood": "repo_dogfood",
}


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
    dev_source = root / "examples" / example_dir
    destination = root / "examples" / example_dir
    if dev_source.exists():
        return dev_source

    package_source = resources.files("looper.templates").joinpath("examples", example_dir)
    if not package_source.is_dir():
        return None
    _copy_resource_tree(package_source, destination)
    return destination


@app.command()
def init(
    example: Optional[str] = typer.Option(
        None,
        help="Initialize with an example: prompt, instructions, schema, mcp, or dogfood.",
    ),
) -> None:
    """Initialize a Looper project."""
    root = Path.cwd()
    looper_dir = root / ".looper"
    looper_dir.mkdir(exist_ok=True)
    (looper_dir / "workspaces").mkdir(exist_ok=True)
    (looper_dir / "reports").mkdir(exist_ok=True)
    (looper_dir / "experiments").mkdir(exist_ok=True)
    store = StateStore(root)
    if not store.path.exists():
        store.save(State())

    if example is not None:
        example_dir = EXAMPLES.get(example)
        if example_dir is None:
            available = ", ".join(sorted(EXAMPLES))
            raise typer.BadParameter(f"Unknown example {example!r}. Choose one of: {available}.")

        copied_example = _copy_example(example_dir, root)
        if copied_example is None:
            console.print(f"[yellow]{example} example not found; created .looper directory only.[/yellow]")
            console.print("[green]Initialized .looper/[/green]")
            return

        src = copied_example / "looper.yaml"
        dst = root / "looper.yaml"
        if src.exists() and not dst.exists():
            shutil.copyfile(src, dst)
            console.print(f"[green]Created looper.yaml from {example} example.[/green]")
            console.print(f"[green]Copied example files to examples/{example_dir}/[/green]")
        elif dst.exists():
            console.print("[yellow]looper.yaml already exists; leaving it unchanged.[/yellow]")
    else:
        cfg = root / "looper.yaml"
        if not cfg.exists():
            cfg.write_text(LooperConfig.example_yaml(), encoding="utf-8")
            console.print("[green]Created looper.yaml.[/green]")
    console.print("[green]Initialized .looper/[/green]")


@app.command()
def baseline(config: str = typer.Option("looper.yaml", help="Path to config file.")) -> None:
    """Run and store the baseline score."""
    cfg = load_config(Path(config))
    engine = Engine(cfg, Path.cwd())
    result = engine.run_baseline()
    console.print(f"[green]Baseline score: {result.score}[/green]")
    console.print(f"[green]Baseline gates: {_gate_summary(result)}[/green]")


@app.command()
def run(
    rounds: Optional[int] = typer.Option(None, help="Number of rounds."),
    variants: Optional[int] = typer.Option(None, help="Variants per round."),
    config: str = typer.Option("looper.yaml", help="Path to config file."),
) -> None:
    """Run improvement experiments."""
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
        console.print(f"{exp.id}: score={score} status={exp.status} gates={_gate_summary(exp)}")
    best = state.best_experiment_id or "none"
    improvement = "yes" if state.improvement_found else "no"
    console.print(f"[green]Run complete. Best experiment: {best}. Improves baseline: {improvement}[/green]")
    report_path = engine.generate_report()
    dashboard_path = engine.generate_dashboard()
    console.print(f"[green]Report written to {report_path}[/green]")
    console.print(f"[green]Dashboard written to {dashboard_path}[/green]")


@app.command()
def report(config: str = typer.Option("looper.yaml", help="Path to config file.")) -> None:
    """Generate a markdown report and HTML dashboard."""
    cfg = load_config(Path(config))
    engine = Engine(cfg, Path.cwd())
    path = engine.generate_report()
    console.print(f"[green]Report written to {path}[/green]")
    console.print(f"[green]Dashboard written to {engine.generate_dashboard()}[/green]")


@app.command()
def dashboard(config: str = typer.Option("looper.yaml", help="Path to config file.")) -> None:
    """Generate the static HTML dashboard."""
    cfg = load_config(Path(config))
    engine = Engine(cfg, Path.cwd())
    path = engine.generate_dashboard()
    console.print(f"[green]Dashboard written to {path}[/green]")


@app.command()
def accept(
    target: str = typer.Argument("best"),
    config: str = typer.Option("looper.yaml", help="Path to config file."),
) -> None:
    """Accept the best experiment by copying its artifact changes into the main workspace."""
    cfg = load_config(Path(config))
    engine = Engine(cfg, Path.cwd())
    accepted = engine.accept(target)
    console.print(f"[green]Accepted experiment: {accepted}[/green]")


if __name__ == "__main__":
    app()
