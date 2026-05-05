# Repository Map

This map is the shortest route through the repository for both humans and agents.
Use it before widening into subsystem docs.

## Core Surfaces

| Path | Role | First validation |
| --- | --- | --- |
| `src/sattline_parser/` | Parser grammar, AST, transformer, strict syntax behavior | `sattlint syntax-check` or targeted parser pytest |
| `src/sattlint/` | CLI, analyzers, reporting, config, documentation workflows | Targeted owner pytest, then Ruff and Pyright |
| `src/sattlint/core/` | Shared semantic and document helpers used by editor flows | Targeted semantic pytest, then LSP restart if editor surfaces changed |
| `src/sattlint/devtools/` | Repo audit, pipeline, ratchets, health reports, policy checks | Targeted devtools pytest, then `sattlint-repo-audit --check-my-changes` |
| `src/sattlint_lsp/` | Language server and workspace loading | Targeted LSP pytest, then restart language server |
| `vscode/sattline-vscode/` | No-build VS Code client | Workspace or extension validation plus LSP restart |
| `tests/` | Owner suites and regression proofs | Narrow pytest slice first |
| `.github/` | CI, AI instructions, prompts, agents, coordination ledger | Diagnostics or config validation, then workflow run if needed |
| `.vscode/` | Local task runner, settings, extension recommendations | `python scripts/context_health.py --check` |
| `.ai/` | Machine-readable task contracts and handoff artifacts | JSON schema validation via `python scripts/context_health.py --check` |
| `metrics/` | Ratchets and historical health snapshots | `python scripts/repo_health.py --check --audit-dir artifacts/audit` |
| `scripts/` | Thin local entrypoints and policy helpers | Touched-file Ruff and Pyright, then focused script execution |

## Primary Entrypoints

- `python scripts/run_ai_edit_gate.py`
- `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit`
- `python -m pre_commit run --all-files`
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`
- `python scripts/context_health.py --check`
- `python scripts/repo_health.py --check --audit-dir artifacts/audit`

## AI Workflow Anchors

- `AGENTS.md` is the stable AI table of contents.
- `docs/context-loading-order.md` defines context loading order.
- `docs/quality-gates.md` defines stage-by-stage validation commands.
- `docs/ai-workflows.md` defines executor, test, and reviewer handoffs.
- `.git/sattlint-ai-coordination/current_work_lock.json` is the shared active-claim lock.
- `.ai/tasks/task-contract.schema.json` defines machine-readable task contracts.
- `.ai/handoffs/handoff.schema.json` defines executor to test to reviewer handoffs.

## Safe Edit Order

1. Start from the owning surface.
2. Read the matching instruction file if one applies.
3. Make the smallest local change.
4. Run the first focused validation immediately.
5. Only then widen to the finish gate.

## Health Outputs

- `artifacts/audit/` contains machine-readable audit artifacts.
- `metrics/ratchet.json` contains the AI-first operating thresholds.
- `metrics/history/` stores curated health snapshots.
