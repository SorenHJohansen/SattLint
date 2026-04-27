---
description: "Use when changing workspace loading, semantic core, editor facade, dirty-buffer parsing, LSP diagnostics, or VS Code client behavior in SattLint. Covers workspace-specific invariants and restart rules."
name: "Workspace LSP Instructions"
applyTo: ["src/sattlint_lsp/**", "src/sattlint/core/**", "src/sattlint/editor_api.py", "vscode/sattline-vscode/**", "tests/test_lsp*.py"]
---
# Workspace LSP

- Preserve the distinction between strict `syntax-check` and dependency-aware workspace analysis.
- Live LSP analysis is for `.s` and `.x`; `.l` and `.z` remain dependency-name lists.
- `ControlLib` stays an expected unavailable dependency in workspace flows.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) before broader checks.
- After changes under `src/sattlint_lsp/`, `src/sattlint/core/`, `src/sattlint/editor_api.py`, or `vscode/sattline-vscode/`, restart with `sattlineLsp.restartServer`.
