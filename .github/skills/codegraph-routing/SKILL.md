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

1. Run `python scripts/context_health.py --check --section codegraph` once per session before the first CodeGraph lookup.
2. If the health result is `healthy`, start with the lightest query that can answer the question: symbol lookup, single-node details, callers/callees, then impact.
3. If the health result is `degraded`, run one sync or rebuild path, rerun the health check once, and only then use CodeGraph. Do not keep retrying failing MCP calls.
4. If the health result is `fallback_to_rg`, skip CodeGraph MCP tools for that session and use `rg`, semantic search, and targeted file reads instead.
5. For broader exploration, use `codegraph_explore` in the main session to gather source sections in one call, then pass them inline to any subagent. Do NOT tell subagents to use codegraph tools — they lack MCP access.
6. Do not reread files that CodeGraph already returned unless you need one nearby detail or a file it did not include.

## Index Scope

- Python under `src/` and `tests/`.
- JavaScript for `vscode/sattline-vscode/`.
- Generated outputs, caches, virtualenvs, and `artifacts/` stay excluded.

## Health Check

- VS Code MCP wiring lives in `.vscode/mcp.json`.
- Repo index settings live in `.codegraph/config.json`.
- Repo-owned preflight: `python scripts/context_health.py --check --section codegraph`.
- Local CLI check: `command -v codegraph && codegraph --version`.

## Guardrails

- Do not start with broad text search when a symbol lookup or call graph can answer faster.
- Do not retry failing CodeGraph MCP calls more than once after a non-healthy health check.
- Do not treat CodeGraph as authoritative for excluded paths or unindexed languages.
- Do not widen scope just because CodeGraph can show more of the repo.
