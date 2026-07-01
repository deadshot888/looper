# Launch Notes

## Show HN Draft

Title:

```text
Show HN: Looper - a local CLI for self-improving agent artifacts
```

First comment:

```text
I built Looper as a small local-first CLI for improving agent artifacts with evals and gates.

The loop is intentionally plain: editable artifact + mutator + shell runner + JSON score + gates + selector. It creates isolated workspaces, tries variants, writes a report, and lets you accept the best passing artifact diff.

The repo includes deterministic examples for prompt optimization, agent instructions, JSON tool schemas, MCP tool selection, and a dogfood loop where Looper improved its own README.

I would be especially interested in feedback on the abstraction and which agent artifacts people would want to optimize first: prompts, MCP schemas, RAG configs, workflow YAML, or code.
```
