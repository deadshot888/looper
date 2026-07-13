# Looper Product Specification

## Thesis

```text
editable artifact + mutator + evaluator + gates + selector = inspectable improvement loop
```

Looper helps developers run controlled local experiments over agent artifacts. Its trust layer is the immutable candidate snapshot, stored evidence, and explicit acceptance step—not an unsupported promise that arbitrary commands are sandboxed.

## Supported Artifacts and Mutators

Artifacts may be prompts, Markdown, YAML, JSON, code, or generic files. A project can configure one or more relative artifact paths.

Current mutators:

- `stub`: deterministic text guidance for examples;
- `command`: a trusted local command that edits configured artifacts in an isolated workspace.

Model-backed providers are not accepted by the schema until implemented.

## Required Lifecycle

```text
init -> validate/doctor -> baseline -> iterative rounds -> report/diff -> accept dry-run -> accept
```

Each round creates variants from one parent. Round one uses the baseline. Later rounds use the prior round winner only when it passes every gate and clears the configured improvement threshold.

## Evaluation

The evaluator must write a JSON object containing a finite numeric `score`. It may include metrics, `cost_usd`, and notes. Repeated evaluations produce stored score samples, a mean used for selection, and a population standard deviation in the raw result.

## Gates

Gates are hard command constraints. A candidate is selectable only when the evaluator succeeds, artifact integrity remains intact, and every gate exits successfully before its timeout.

## Budgets

The engine can stop on total experiment count, reported cost, or experiment duration. Budget termination is recorded in state and reports.

## Version Evidence

Every version records:

- session, parent, round and variant identifiers;
- hypothesis and change summary;
- cumulative baseline diff and artifact hashes;
- mean score, samples, metrics, costs and durations;
- gates, stdout, stderr and status;
- configuration/project fingerprints;
- generated review and recommendation.

## Acceptance Requirements

The engine must reject stale, failed, gate-blocked, missing, moved, or hash-mismatched candidates. Root edits after the baseline must block acceptance unless the user explicitly forces it after review. Successful acceptance must preserve rollback copies and write an audit entry.

## Non-goals

- security sandboxing for hostile commands;
- hosted orchestration;
- framework-specific agent execution;
- automatic publishing, branching, or pull requests;
- model-provider integrations in the core V0.x schema.
