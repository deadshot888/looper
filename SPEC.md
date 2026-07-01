# Looper V0 Spec

## Core Thesis

Looper is a generic local-first loop runner for improving agentic systems.

It starts from a simple interface:

```text
editable artifact + eval command + gates = improvement loop
```

## Primary User

A developer building or tuning an agentic system.

## V0 Positioning

**Set up self-improving loops for your agents.**

The first version should be boring, local, and useful. It should run in a repo and produce a diff.

## Artifacts

V0 artifact types:

| Type | Example |
|---|---|
| prompt | `prompts/support_agent.md` |
| markdown | `AGENTS.md`, `CLAUDE.md` |
| yaml | LangGraph/CrewAI config |
| json | MCP tool schema |
| code | Python file |
| generic | any file |

## Loop Lifecycle

```text
init
  -> baseline
  -> variant generation
  -> evaluation
  -> gates
  -> selection
  -> report
  -> accept
```

## Baseline

Baseline is the current system before mutation.

## Variant

A variant is a candidate change to one or more artifacts.

Each variant should store:

- id
- parent
- artifact changes
- score
- metric details
- gates
- stdout/stderr
- workspace path
- status

## Gates

Gates are hard constraints.

An experiment can improve score and still be rejected if gates fail.

Examples:

- tests pass
- no schema break
- cost below threshold
- no forbidden phrase
- no policy violation
- valid JSON output

## Reports

Report should be the trust layer.

It should answer:

- Did anything improve?
- Which variant won?
- By how much?
- What changed?
- Which gates passed/failed?
- Should I accept the diff?

## Future Direction

After V0:

1. OpenAI/Anthropic mutator providers
2. MCP tool-schema optimization template
3. RAG config optimization template
4. LangGraph adapter
5. CrewAI adapter
6. GitHub Action
7. PR creation
8. experiment graph/tree search
9. Pareto selection
10. shared experiment memory
