---
description: "Explore SattLint code paths with CodeGraph-first routing before editing"
name: "Explore Codebase"
argument-hint: "Symbol, owner surface, or behavior to explore"
agent: "Explore"
---

# Explore Codebase

Explore the requested SattLint code path before any edit recommendation.

Requirements:

- Use the `codegraph-routing` skill first. This prompt is for a Planner or Executor — use `codegraph_explore` in the main session to gather source sections, then pass them inline to any subagent. Subagents cannot access MCP tools.
- Prefer CodeGraph symbol, caller, callee, or impact lookups before broad text search.
- If CodeGraph returns the needed source, do not reread the same files unless one nearby detail is still missing.
- Fall back to `rg`, semantic search, and targeted file reads only when CodeGraph is unavailable, stale, or outside index scope.
- Return the controlling file or symbol, the nearby call flow or owner surface that matters, and the smallest next file or test to inspect.
