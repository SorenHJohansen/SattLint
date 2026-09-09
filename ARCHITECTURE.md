# Architecture Summary

This is the short architecture summary for onboarding and AI routing.
For deeper design rationale, principles, and operating details, use
`AGENTS_REFERENCE.md`.

## Layering

```mermaid
flowchart LR
    subgraph User["User-Facing"]
        CLI["sattlint CLI/TUI"]
    end

    subgraph App["Application Layer"]
        CLI_LAYER["cli/ (entry, commands, startup)"]
        APPL["application/ (workflows)"]
        UI["ui/ (Textual shell)"]
        CONFIG["config/"]
    end

    subgraph Analysis["Analysis Layer"]
        ANALYZERS["analyzers/"]
        CORE["core/ (semantic snapshot)"]
        ENGINE["engine.py"]
        RESOLUTION["resolution/"]
        REPORTING["reporting/"]
    end

    subgraph Parser["External Parser Layer"]
        PARSER["sattline-parser (PyPI)"]
    end

    CLI --> CLI_LAYER
    CLI_LAYER --> APPL
    CLI_LAYER --> UI
    CLI_LAYER --> CONFIG
    APPL --> ANALYZERS
    APPL --> ENGINE
    APPL --> CONFIG
    ENGINE --> PARSER
    CORE --> ANALYZERS
    CORE --> RESOLUTION
    CORE --> REPORTING
    ANALYZERS --> PARSER
```

### Layer responsibilities

- `src/sattlint/cli/` owns the CLI entry point (`startup.py`), subcommand dispatch, and interactive-shell startup.
- `src/sattlint/application/` owns terminal-agnostic workflows: menu commands, checks, and project-driven analysis entry points.
- `src/sattlint/ui/` owns the Textual interactive shell (no subcommand).
- `src/sattlint/config/` owns settings loading, defaults, and validation.
- `src/sattlint/core/` owns the semantic snapshot helpers used by analysis.
- `src/sattlint/change_review/` owns the Change Review capability: a semantic diff and
  impact analysis between an official (`.x`) and a draft (`.s`) version of a project,
  producing a compact JSON + Markdown review artifact. It reuses the semantic snapshot
  and is fully independent of static analysis.
- `src/sattlint/analyzers/` owns the heuristic analyzers and the registry.
- `sattline-parser` (external dependency, `sattline-parser>=2026.9.1`) owns the SattLine grammar, parse tree transformation, and AST models.

## Operational Layer

- `src/sattlint/` owns runtime product code. Repository maintenance tooling and generated health dashboards are not shipped.
- `.github/` owns CI workflows and scoped instruction files.

## Actual Runtime Entry Map

- `sattlint` enters at `src/sattlint/cli/startup.py`. With a subcommand it dispatches to the non-interactive handlers in `src/sattlint/cli/commands.py` (`syntax-check`, `analyze`, `validate-config`, `cache-prune`); with no subcommand it starts the interactive Textual shell from `src/sattlint/ui/`.
- The interactive UI (`sattlint` with no arguments) provides Analyze, Setup, and Help views.

## Critical Boundaries

- Parser core ships as the external `sattline-parser` package and does not depend on application layers.
- All retained analyzers use the same semantic engine and findings model.
- The analyzer registry is the single rule catalog; CLI, UI, and reporting read from it rather than duplicating rule lists.

## Quality Anchors

- Fast local gate: `python -m pre_commit run --all-files` (when configured) or `ruff check`, `pyright`, and focused `pytest`
- Pyright runs `strict` package-wide except `src/sattlint/ui/`, a deliberate carve-out: `ignore` in `pyproject.toml` `[tool.pyright]` suppresses diagnostics there because the Textual shell drives dynamic runtime APIs that are not practical under strict typing. The shell is exercised by the full pytest suite instead of the type checker.
- Full suite: `python -m pytest -q`
- CI: GitHub Actions workflow `ci.yml` runs ruff, pyright, and the full pytest suite plus wheel smokes on pull request and push to `main`.
