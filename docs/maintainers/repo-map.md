# Repository Map

This map is the shortest route through the repository for both humans and agents.
Use it before widening into subsystem docs.

## Core Surfaces

| Path | Role | First validation |
| --- | --- | --- |
| `sattline-parser` (external) | Parser grammar, AST, transformer, strict syntax behavior | `sattlint syntax-check` or targeted parser pytest |
| `src/sattlint/app.py`, `src/sattlint/cli/` | CLI entrypoints and command handlers | Targeted owner pytest, then Ruff and Pyright |
| `src/sattlint/analyzers/` | Heuristic analyzers and the rule registry | Targeted analyzer pytest |
| `src/sattlint/core/` | Shared semantic snapshot and document helpers | Targeted semantic pytest |
| `src/sattlint/project/` | `.slproj` project model and loading | `tests/test_project*.py`, targeted pytest |
| `src/sattlint/` (ICF, graphics, validation, engine) | ICF analysis, graphics rules, strict syntax validation | Targeted owner pytest |
| `src/sattlint/app_textual.py` | Textual interactive UI | `tests/test_app_textual*.py` |
| `src/sattlint/structural/` | Graphics layout helpers retained from the structural reports | Targeted pytest |
| `src/sattlint/tracing.py` | Engine-internal analysis trace recorder | Targeted pytest |
| `tests/` | Owner suites and regression proofs | Narrow pytest slice first |
| `.github/` | CI workflows and scoped instructions | Diagnostics or config validation, then workflow run if needed |

## Primary Entrypoints

- `sattlint`
- `python -m pre_commit run --all-files`
- `python -m ruff check .`
- `python -m pyright src/sattlint`
- `python -m pytest -q --tb=short`

## Actual Runtime Map

- Stable CLI commands enter through `sattlint -> src/sattlint/app.py`, then route
  into the shared app helpers, analyzers, reporting, and parser-backed semantic
  loaders.
- The interactive menu also starts in `src/sattlint/app.py`; it is shipped, but
  its UX contract is looser than the stable CLI commands.

## Assistant Anchors

- `AGENTS.md` is the stable AI table of contents.
- `AGENTS.md` owns context loading order and default workflow rules.
- `docs/maintainers/analyzer-authoring.md` defines the default analyzer pattern.
- `docs/maintainers/quality-gates.md` defines stage-by-stage validation commands.
- `docs/public/architecture.md` captures the short architecture boundary summary.
