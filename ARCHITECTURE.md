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
  -> Report
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
```

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
```

### Evaluator

Parses `result.json`.

### Gates

Runs pass/fail shell commands.

### Selector

Chooses the best passing experiment.

### Report

Writes a markdown summary.

## State Directory

```text
.looper/
  state.json
  workspaces/
  experiments/
  reports/
```

## Important Design Constraints

- local-first
- inspectable state
- no lock-in to a framework
- no hidden magic
- all experiment outcomes preserved
- gates first-class
- accept step explicit
