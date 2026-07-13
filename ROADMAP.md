# Roadmap

Roadmap phases are intentionally separate from package release numbers.

## Completed: Trustworthy Local Loop

- strict configuration and path validation;
- isolated baseline and candidate workspaces;
- iterative parent/child rounds;
- repeated evaluations, gates, thresholds, seeds, and budgets;
- immutable candidate verification;
- project/session fingerprints and atomic state;
- review reports, dashboard, version ledger, acceptance dry-run and backups;
- deterministic prompt, instruction, schema, MCP, and dogfood examples;
- cross-platform CI and installed-wheel smoke tests.

## Next: Model-backed Mutation

- OpenAI, Anthropic, and local-model adapters behind optional dependencies;
- typed mutation prompts per artifact kind;
- token/cost telemetry and provider retry policy;
- redaction-safe environment and trace capture.

## Next: Search Quality

- statistical confidence intervals and paired evaluations;
- top-k frontier, epsilon-greedy exploration and failure memory;
- Pareto selection across quality, cost and latency;
- experiment graph visualization and candidate combination.

## Next: Repository Workflow

- Git worktree backend;
- branch/commit creation after acceptance;
- optional pull-request workflow through GitHub CLI;
- merge-conflict-aware patch application.

## Later: Framework and Hosted Adapters

- LangGraph, CrewAI and OpenAI Agents SDK discovery;
- RAG and workflow configuration templates;
- remote workers and parallel scheduling;
- shared private evaluation registries and team experiment history.
