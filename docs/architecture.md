# Architecture Summary

This is the short architecture summary for onboarding and AI routing.
For deeper design rationale, use `ARCHITECTURE.md` and `docs/design-docs/`.

## Layering

```text
VS Code client -> LSP -> semantic core -> analyzers / engine -> parser core
                                      -> devtools / reporting
```

- `vscode/sattline-vscode/` hosts the editor client.
- `src/sattlint_lsp/` owns workspace loading and protocol handling.
- `src/sattlint/core/` owns shared semantic and document helpers.
- `src/sattlint/` owns CLI flows, analyzers, reporting, config, and documentation generation.
- `src/sattline_parser/` owns grammar, parse tree transformation, and AST models.

## Operational Layer

- `src/sattlint/devtools/` owns repo audit, pipeline checks, ratchets, reporting, and health artifacts.
- `.github/` owns instructions, prompts, agent definitions, GitHub workflows, and coordination.
- `.ai/` owns task and handoff contracts for executor, test, and reviewer workflows.
- `metrics/` owns ratchet configuration and curated health history snapshots.

## Critical Boundaries

- Parser core does not depend on application or editor layers.
- Editor-facing code degrades only through documented workspace or dirty-buffer paths.
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
