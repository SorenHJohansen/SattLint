# AI Assistant Reference For SattLint

This file supplements `AGENTS.md`. It is a compact reference, not a second workflow authority.

- Follow direct user instructions first.
- Follow code and tests over stale documentation.
- Use `AGENTS.md` for stable workflow rules, safety guidance, and critical invariants.

## Canonical Files

- `AGENTS.md` for workflow rules and guardrails.
- `docs/maintainers/repo-map.md` for owner routing.
- `docs/maintainers/quality-gates.md` for validation order.
- `docs/maintainers/validation-map.md` for first focused checks.
- `.ai/README.md` for machine-authored AI artifacts.

## Default Commands

- `python scripts/context_health.py --check` after AI-control edits.
- `python -m pre_commit run --all-files` for the fast repo-wide hygiene gate.
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` for local pre-push proof.
- `sattlint-repo-audit --profile full --output-dir artifacts/audit` for the full CI or nightly pass.

## Working Rules

- Start from the owning file, symbol, failing command, or failing behavior.
- Read only the `.github/instructions/*.md` files that match the touched surface.
- Make the smallest local edit that tests the current hypothesis.
- Run the first focused validation immediately before widening.

## Routing Notes

- Generated routing registries are not the default maintainer entrypoint.
- Prefer the maintainer docs first and use checked-in generated routing files only when a tool explicitly depends on them.
- Keep new machine-authored AI artifacts out of `docs/` when a non-docs home is available.

### Run Variable Analysis

```python
from sattlint.analyzers.variables import analyze_variables

report = analyze_variables(bp, debug=False)
print(report.summary())
```

### Generate Documentation

```python
from sattlint.config import get_documentation_config
from sattlint.docgenerator.docgen import generate_docx

generate_docx(bp, "output.docx", documentation_config=get_documentation_config())
```

### Run Tests From The Repo Venv

```powershell
python scripts/run_repo_python.py -m pytest
```

### Trace A Concrete File

```bash
sattlint-trace path/to/Program.s
```

### Run The Dev-Analysis Pipeline

```bash
sattlint-analysis-pipeline --profile full
```

Use `--profile quick` for fast local loops. Read `artifacts/analysis/status.json` first before opening the larger report set.

---

## Key File Map

### Core Application

- `src/sattlint/app.py`: CLI entry point and interactive menu.
- `src/sattlint/config.py`: persistent config, self-checks, analyzed-target validation.
- `src/sattlint/engine.py`: syntax validation, project loading, parser-core integration.
- `src/sattlint/cache.py`: AST caching.

### Shared Editor Semantics

- `src/sattlint/core/semantic.py`: workspace discovery, symbol lookup, snapshots.
- `src/sattlint/core/document.py`: shared document and offset helpers.
- `src/sattlint/editor_api.py`: public compatibility facade (external boundary only).

### Parser Core

- `src/sattline_parser/api.py`: parser-core entry points.
- `src/sattline_parser/grammar/sattline.lark`: grammar definition.
- `src/sattline_parser/grammar/constants.py`: grammar constants.
- `src/sattline_parser/transformer/sl_transformer.py`: transformer implementation.
- `src/sattline_parser/models/ast_model.py`: AST node dataclasses.
- `src/sattline_parser/utils/text_processing.py`: comment stripping.
- `src/sattline_parser/utils/formatter.py`: AST formatting helpers.

### Analyzers And Reporting

- `src/sattlint/analyzers/variables.py`: variable-usage analyzer.
- `src/sattlint/analyzers/spec_compliance.py`: engineering-spec compliance checks.
- `src/sattlint/analyzers/shadowing.py`: shadowing analyzer.
- `src/sattlint/analyzers/mms.py`: MMS analysis.
- `src/sattlint/analyzers/comment_code.py`: commented-out code detection.
- `src/sattlint/reporting/variables_report.py`: variable report formatting.
- `src/sattlint/devtools/pipeline.py`: repeatable repo-audit pipeline.
- `src/sattlint/tracing.py`: parser and analyzer tracing.

### LSP

- `src/sattlint_lsp/document_state.py`: per-document text state and cached local analysis metadata.
- `src/sattlint_lsp/local_parser.py`: incremental parser backend.
- `src/sattlint_lsp/workspace_store.py`: cached workspace snapshots and invalidation.
- `src/sattlint_lsp/server.py`: Pygls language server.
- `vscode/sattline-vscode/extension.js`: VS Code client.
- `vscode/sattline-vscode/package.json`: extension metadata.

### Tests And Fixtures

- `tests/fixtures/sample_sattline_files/`: real SattLine examples.
- `tests/test_app.py`: interactive CLI coverage.
- `tests/test_editor_api.py`: editor-facing snapshot and lookup coverage.
- `tests/test_lsp_server.py`: LSP behavior and invalidation coverage.

### Reference Docs

- `sattline_language_reference.md`: language syntax and semantics.
- `sattline_graphics_reference.md`: graphics and interaction objects.
- `sattline_execution_reference.md`: execution model and scan groups.
- `sattline_system_procedures_reference.md`: system procedures and utility functions.
- `SattLineReferenceDocs/`: broader vendor and domain references.

---

## Practical Reminders

- Use the sample fixtures when unsure about real syntax.
- Use token constants rather than literal token strings when extending grammar or validation code.
- Keep analyzer changes aligned with existing framework and registry patterns.
- Preserve the distinction between strict single-file validation and dependency-aware workspace behavior.
- Restart the VS Code language server after LSP or client changes so on-disk code matches the live editor state.
