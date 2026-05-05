---
description: "Fix a workspace loading, editor API, LSP, or VS Code client issue in SattLint using the workspace specialist"
name: "Workspace LSP Fix"
argument-hint: "Describe workspace or LSP bug to fix"
agent: "Workspace LSP"
---

# Workspace LSP Fix

Investigate and fix the requested workspace, semantic-core, or LSP issue in SattLint.

## Requirements

- Read `.git/sattlint-ai-coordination/current_work_lock.json` before first edit and claim exact touched files before the first edit.
- Start from the nearest controlling workspace-store, editor facade, dirty-buffer, or diagnostic path.
- Preserve the distinction between strict single-file validation and dependency-aware workspace analysis.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md), then restart with `sattlineLsp.restartServer` if the touched surface requires it.
- Report the changed files, validation run, and whether LSP restart is required.
