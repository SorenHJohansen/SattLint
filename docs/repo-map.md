# Repository Map

This map is the shortest route through the repository for both humans and agents.
Use it before widening into subsystem docs.

## Core Surfaces

| Path | Role | First validation |
| --- | --- | --- |
| `src/sattline_parser/` | Parser grammar, AST, transformer, strict syntax behavior | `sattlint syntax-check` or targeted parser pytest |
| `src/sattlint/` | CLI flows, analyzers, reporting, config, documentation workflows, and shared app orchestration | Targeted owner pytest, then Ruff and Pyright |
| `src/sattlint/editor_api.py` | Public editor-facing compatibility facade over `src/sattlint/core/semantic.py` | `tests/test_editor_api.py`, then LSP restart if editor surfaces changed |
| `src/sattlint/core/` | Shared semantic and document helpers behind the editor facade and LSP | Targeted semantic pytest, then LSP restart if editor surfaces changed |
| `src/sattlint/devtools/` | Repo audit, pipeline, ratchets, health reports, policy checks | Targeted devtools pytest, then `sattlint-repo-audit --check-my-changes` |
| `src/sattlint_lsp/` | Language server and workspace loading | Targeted LSP pytest, then restart language server |
| `vscode/sattline-vscode/` | Preview no-build VS Code client for the Python LSP | Workspace or extension validation plus LSP restart |
| `tests/` | Owner suites and regression proofs | Narrow pytest slice first |
| `.github/` | CI, AI instructions, prompts, agents, coordination ledger | Diagnostics or config validation, then workflow run if needed |
| `.vscode/` | Local task runner, settings, extension recommendations | `python scripts/context_health.py --check` |
| `.ai/` | Machine-readable task contracts and handoff artifacts | JSON schema validation via `python scripts/context_health.py --check` |
| `metrics/` | Ratchets and historical health snapshots | `python scripts/repo_health.py --check --audit-dir artifacts/audit` |
| `scripts/` | Thin local entrypoints and policy helpers | Touched-file Ruff and Pyright, then focused script execution |

## Primary Entrypoints

- `sattlint`
- `sattlint-lsp`
- `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit`
- `python scripts/run_ai_edit_gate.py`
- `python -m pre_commit run --all-files`
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`
- `python scripts/context_health.py --check`
- `python scripts/repo_health.py --check --audit-dir artifacts/audit`

## Actual Runtime Map

- Stable CLI commands enter through `sattlint -> src/sattlint/app.py`, then route into the shared app helpers, analyzers, reporting, and parser-backed semantic loaders.
- The preview interactive menu also starts in `src/sattlint/app.py`; it is shipped, but its UX contract is looser than `syntax-check` and `repo-audit`.
- Editor-facing library consumers should enter through `src/sattlint/editor_api.py`; that file is a compatibility facade over `src/sattlint/core/semantic.py`, not a second semantic implementation.
- The stable language server enters through `sattlint-lsp -> src/sattlint_lsp/server.py`, which owns JSON-RPC, workspace snapshots, and editor protocol behavior.
- Repo-audit and layer-lint are maintainer-facing entrypoints under `src/sattlint/devtools/`; they are runtime-adjacent tooling, not part of the editor or parser control path.
- The VS Code client in `vscode/sattline-vscode/` is a preview repository-local client for the Python LSP, not the default owner of Python runtime logic.

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
