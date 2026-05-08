---
name: codegraph-routing
description: 'Use CodeGraph first for SattLint exploration when .codegraph/ is present. Covers symbol lookup, call-flow tracing, index scope, and fallbacks.'
argument-hint: 'Describe the symbol, owner surface, or exploration question'
---

# CodeGraph Routing

Use this skill when you need read-only codebase exploration before editing and `.codegraph/` is initialized in the repo.

## When To Prefer CodeGraph

- Exact symbol lookup before opening files.
- Caller, callee, or impact checks before touching shared code.
- Broad exploration across Python owner surfaces and the VS Code client.

## Procedure

1. If CodeGraph tools are available, start with the lightest query that can answer the question: symbol lookup, single-node details, callers or callees, then impact.
2. For broader exploration, run an `Explore` subagent and instruct it to use CodeGraph as its primary source.
3. Do not reread files that CodeGraph already returned unless you need one nearby detail or a file it did not include.
4. Fall back to `rg`, semantic search, and targeted file reads only when CodeGraph is unavailable or the needed file is outside the index.
5. If indexed results look stale after code changes, rebuild the index before concluding the symbol is missing.

## Index Scope

- Python under `src/` and `tests/`.
- JavaScript for `vscode/sattline-vscode/`.
- Generated outputs, caches, virtualenvs, and `artifacts/` stay excluded.

## Health Check

- VS Code MCP wiring lives in `.vscode/mcp.json`.
- Repo index settings live in `.codegraph/config.json`.
- Local CLI check: `command -v codegraph && codegraph --version`.

## Guardrails

- Do not start with broad text search when a symbol lookup or call graph can answer faster.
- Do not treat CodeGraph as authoritative for excluded paths or unindexed languages.
- Do not widen scope just because CodeGraph can show more of the repo.
