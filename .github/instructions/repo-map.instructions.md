---
description: "Use when routing work to the owning SattLint surface or choosing the closest repo area for a change. Provides the condensed repo map that was removed from AGENTS.md for context efficiency."
name: "Repo Map Instructions"
applyTo: ["src/**", "tests/**", "scripts/**", ".github/**", ".ai/**", "docs/**", "vscode/**", "metrics/**", "artifacts/**"]
---
# Repo Map

| Path | Purpose |
| --- | --- |
| `src/sattline_parser/` | Parser core: grammar, transformer, AST models |
| `src/sattlint/` | CLI, analyzers, reporting, config, doc generation |
| `src/sattlint/core/` | Shared semantic and document helpers |
| `src/sattlint/devtools/` | Repo audit, pipeline, ratchets, health reporting |
| `src/sattlint_lsp/` | Language server and workspace loading |
| `vscode/sattline-vscode/` | No-build VS Code client for SattLine editing in external workspaces; not the default owner for this repo's Python-side health or audit UX |
| `tests/` | Owner suites and regression coverage |
| `.github/` | CI, instructions, prompts, agents, coordination |
| `.ai/` | Task contracts and handoffs |
| `metrics/` | Ratchets and curated health history |
| `artifacts/` | Machine-readable audit outputs |
