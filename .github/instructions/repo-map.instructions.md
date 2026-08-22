---
description: "Use when routing work to the owning SattLint surface or choosing the closest repo area for a change. Provides the condensed repo map that was removed from AGENTS.md for context efficiency."
name: "Repo Map Instructions"
applyTo: ["src/**", "tests/**", "scripts/**", ".github/**", "docs/**", "metrics/**"]
---
# Repo Map

| Path | Purpose |
| --- | --- |
| `sattline-parser` (external) | Parser core: grammar, transformer, AST models; installed from PyPI and owned by the `sattline-parser` repo |
| `src/sattlint/` | CLI, analyzers, reporting, config |
| `src/sattlint/core/` | Shared semantic and document helpers |
| `src/sattlint/devtools/` | Repo audit, pipeline, health and structural reporting |
| `tests/` | Owner suites and regression coverage |
| `.github/` | CI, instructions, hooks, and optional chat customizations |
| `metrics/` | Maintainer operating thresholds and curated health history |
| `artifacts/` | Machine-readable audit outputs |

## Search Routing

- Start repo exploration with Semble MCP search so behavior- and symbol-level queries route to the right owner surface quickly.
- Use `mcp_semble_search` first with a natural-language behavior, feature, or symbol query against the repo root.
- If a result is promising but you need sibling implementations or adjacent call paths, use `mcp_semble_find_related` with that result's `file_path` and `line`.
- Read full files only when the returned chunk is not enough local context to edit or validate safely.
- Use `rg` or grep only when you need exhaustive literal matches, exact-string confirmation, or a quick file inventory.
- If you need the CLI instead of MCP, run `semble ...` and fall back to `uvx --from "semble[mcp]" semble ...` when `semble` is not on `$PATH`.
