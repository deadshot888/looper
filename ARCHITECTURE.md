# Architecture

## Core Components

```text
CLI
  -> Config loader
  -> Experiment engine
  -> Workspace backend
  -> Mutator
  -> Runner
  -> Gates
  -> Evaluator/result parser
  -> Selector
  -> Review + Report + Dashboard
```

## Components

### Config Loader

Reads `looper.yaml` and validates schema.

### Workspace Backend

Creates isolated workspaces for experiments.

V0 uses copy-based workspaces.
V1 should support git worktrees.

### Mutator

Creates artifact variants.

V0:

- `stub` mutator for deterministic text demos
- `command` mutator for custom external mutation scripts

The included command-mutator examples cover JSON tool schemas and MCP tool-selection metadata.

The command mutator runs from the workspace root and receives:

```text
LOOPER_ARTIFACTS
LOOPER_EXPERIMENT_INDEX
LOOPER_WORKSPACE
LOOPER_MUTATION_META_PATH
LOOPER_PYTHON
LOOPER_PYTHON_VERSION
```

If the command writes JSON to `LOOPER_MUTATION_META_PATH`, Looper records the variant hypothesis, change summary, and changed artifact list in the version ledger.

Later:

- OpenAI
- Anthropic
- local models
- Claude Code plugin
- Codex plugin

### Runner

Runs the configured command inside each workspace.

It injects:

```text
LOOPER_RESULT_PATH
LOOPER_ARTIFACTS
LOOPER_EXPERIMENT_ID
LOOPER_PYTHON
LOOPER_PYTHON_VERSION
```

Looper creates `.looper/bin/python` and `.looper/bin/python3` launchers in the workspace before command execution. Both point to the active Python 3 runtime, or to `LOOPER_PYTHON` when explicitly set.

### Evaluator

Parses `result.json`.

### Gates

Runs pass/fail shell commands.

### Selector

Chooses the best passing experiment.

### Review

Evaluates every version against the baseline and records:

- what worked
- what needs improvement
- whether the version is accept-ready, blocked, or useful for parts

### Report + Dashboard

Writes a markdown summary and a static HTML dashboard. The dashboard is generated under `.looper/reports/dashboard.html`.

## State Directory

```text
.looper/
  state.json
  versions.jsonl
  workspaces/
  experiments/
    exp_0001/
      result.json
      gates.json
      diff.patch
      review.md
  reports/
    latest.md
    dashboard.html
```

## Important Design Constraints

- local-first
- inspectable state
- no lock-in to a framework
- no hidden magic
- all experiment outcomes preserved
- gates first-class
- accept step explicit
