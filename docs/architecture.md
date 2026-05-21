# Architecture Summary

This is the short architecture summary for onboarding and AI routing.
For deeper design rationale, use `ARCHITECTURE.md` and `docs/design-docs/`.

## Layering

```text
VS Code client -> LSP -> editor facade / semantic core -> analyzers / engine -> parser core
Preview GUI ------------------------------^            -> reporting / documentation
CLI + repo audit -------------------------------------> app / devtools helpers
```

- `vscode/sattline-vscode/` hosts the preview editor client for the Python LSP.
- `src/sattlint_lsp/` owns workspace loading, document state, and protocol handling.
- `src/sattlint/editor_api.py` is the public editor-facing compatibility facade.
- `src/sattlint/core/` owns the semantic helpers behind that facade.
- `src/sattlint/` owns CLI flows, analyzers, reporting, config, and documentation generation.
- `src/sattlint_gui/` hosts the preview desktop GUI shell.
- `src/sattline_parser/` owns grammar, parse tree transformation, and AST models.

## Operational Layer

- `src/sattlint/devtools/` owns repo audit, pipeline checks, ratchets, layer lint, reporting, and health artifacts.
- `.github/` owns instructions, prompts, agent definitions, GitHub workflows, and coordination.
- `.ai/` owns task and handoff contracts for executor, test, and reviewer workflows.
- `metrics/` owns ratchet configuration and curated health history snapshots.

## Actual Runtime Entry Map

- `sattlint` enters at `src/sattlint/app.py`. Stable command-mode flows and the preview menu both start there, then fan into app helpers, analyzers, reporting, and parser-backed semantic loading.
- `sattlint-gui` enters at `src/sattlint_gui/main.py`, builds `SattLintWindow`, and reuses the same config and workflow helpers as the CLI. This GUI is shipped but still preview-only.
- `sattlint-lsp` enters at `src/sattlint_lsp/server.py`, which owns the language server, snapshot store, and document lifecycle hooks.
- External editor integrations should enter through `src/sattlint/editor_api.py`; that module intentionally forwards into `src/sattlint/core/semantic.py` so compatibility consumers and the LSP share one semantic pipeline.
- `sattlint-repo-audit` and `sattlint-layer-lint` enter through `src/sattlint/devtools/`. They are repository tooling surfaces, not part of the parser or editor runtime loop.
- `vscode/sattline-vscode/` is the local preview client that talks to `sattlint-lsp`. It is shipped in-repo, but it is not the owner of Python-side semantic or audit logic.

## Critical Boundaries

- Parser core does not depend on application or editor layers.
- Editor-facing code degrades only through documented workspace or dirty-buffer paths, and `src/sattlint/editor_api.py` remains a compatibility boundary rather than a second semantic core.
- Devtools report through machine-readable JSON artifacts rather than ad hoc text.
- Global AI guidance stays thin; scoped rules live in `.github/instructions/` and `.github/agents/`.

## Quality Anchors

- AI edit gate: `python scripts/run_ai_edit_gate.py`
- Fast local gate: `python -m pre_commit run --all-files`
- Pre-push gate: `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`
- Context health gate: `python scripts/context_health.py --check`
- Repo health gate: `python scripts/repo_health.py --check --audit-dir artifacts/audit`

## Why This Split Works

- Runtime code remains separate from repo operations and policy checks.
- AI routing stays explicit through repo maps, task contracts, and handoff artifacts.
- Health reporting stays deterministic because it reads the same audit artifacts that CI and humans already inspect.
