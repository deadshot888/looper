# Architecture

## Core components

```text
CLI
 ↓
Config loader
 ↓
Experiment engine
 ↓
Workspace backend
 ↓
Mutator
 ↓
Runner
 ↓
Gates
 ↓
Evaluator/result parser
 ↓
Selector
 ↓
Report
```

## Components

### Config loader

Reads `looper.yaml` and validates schema.

### Workspace backend

Creates isolated workspaces for experiments.

V0 can use copy-based workspaces.
V1 should support git worktrees.

### Mutator

Creates artifact variants.

V0:

- `stub` mutator for deterministic demos
- `command` mutator for custom external mutation scripts

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

Writes markdown/HTML summary.

## State directory

```text
.looper/
  state.json
  workspaces/
  experiments/
  reports/
```

## Important design constraints

- local-first
- inspectable state
- no lock-in to a framework
- no hidden magic
- all experiment outcomes preserved
- gates first-class
- accept step explicit
