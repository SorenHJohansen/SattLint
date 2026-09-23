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
- `sattline-parser` (external dependency, `sattline-parser>=2026.9.1`) owns the SattLine grammar, parse tree transformation, AST models, **and the SattLine project layer**: `SattLineProject` owns search roots, load mode, file discovery, dependency resolution, and the resolved dependency graph (`SattLineProgram` per logical program/library). SattLint routes project loading directly through `sattlint.project.loader_config.build_parser_binding` + `parser_adapter` (`load_parser_project`/`convert_project_into_graph`), which re-validates and re-indexes the parser result into the SattLint `ProjectGraph` analysis index.

## Operational Layer

- `src/sattlint/` owns runtime product code. Repository maintenance tooling and generated health dashboards are not shipped.
- `.github/` owns CI workflows and scoped instruction files.

## Actual Runtime Entry Map

- `sattlint` enters at `src/sattlint/cli/startup.py`. It takes no arguments and starts the interactive Textual shell from `src/sattlint/ui/`.
- The interactive UI (`sattlint` with no arguments) provides Analyze, Setup, and Help views.

## Analyzer Workflow

Analyzers live in `src/sattlint/analyzers/` and are described by `AnalyzerSpec`
(key, name, description, a `run(context) -> Report` callable, category, enabled,
and scope). The registry at `src/sattlint/analyzers/registry/__init__.py`
builds the `AnalyzerCatalog` once from the static spec templates. The framework
primitives (`AnalysisContext`, `AnalysisSharedArtifacts`, `AnalyzerSpec`,
`Report`) live in `src/sattlint/analyzers/framework/`.

### Mental model — select an analyzer, get its output

```mermaid
flowchart LR
    Select["You select an analyzer<br/>(UI checkbox)"]
    Registry["Registry<br/>key -> AnalyzerSpec (catalog)"]
    Run["Run analyzer<br/>run(context) -> Report"]
    Output["Your output<br/>summary + findings"]

    Select --> Registry --> Run --> Output
```

Selection is exact: the analyzers that run are exactly the ones selected — no
analyzer is added, dropped, reordered, or collapsed into another. Each analyzer
is self-contained; it never depends on another analyzer having run first.

### Stage 1 — Selection and dispatch

Entry: `sattlint analyze` (CLI) or the Textual Analyze view. Both end up at
`run_checks` / `run_checks_result` in `src/sattlint/application/checks.py`.

```mermaid
flowchart TB
    Keys["Selected keys<br/>(or the default CLI set, `DEFAULT_CLI_ANALYZER_KEYS`)"]
    Canon["canonicalize_analyzer_keys<br/>(legacy aliases, casefold)"]
    Filter["get_cli_dispatch_analyzers<br/>resolve_selected_analyzers (exact filter)"]
    Split{"checks.py splits by scope"}
    Batch["per-target analyzers<br/>(run once per target)"]
    Whole["per-run analyzers<br/>(icf — runs once per whole run)"]

    Keys --> Canon --> Filter --> Split
    Split --> Batch
    Split --> Whole
```

### Stage 2 — Per-target execution pipeline

For every loaded target, `collect_run_checks_result` builds one `AnalysisContext`
(shared across all analyzers of that target) and then runs each per-target
analyzer. Each analyzer's `Report` is post-processed before it becomes a result.

```mermaid
flowchart TB
    Load["iter_loaded_projects(cfg)<br/>(target_name, BasePicture, ProjectGraph)"]
    Ctx["build_analysis_context<br/>+ AnalysisSharedArtifacts"]
    Loop{"for each per-target analyzer"}
    Cache["run_with_analysis_report_cache<br/>(disk cache hit -> reuse Report)"]
    Run["run_registry_analyzer<br/>spec.run(context)"]
    Post["Post-process<br/>rewrite typedef paths -> normalize target<br/>name -> extract findings"]
    Res["ChecksAnalyzerResult"]
    Target["ChecksTargetResult (one per target)"]
    RunResult["ChecksRunResult<br/>output_lines + findings"]

    Load --> Ctx --> Loop
    Loop --> Cache --> Run --> Post --> Res --> Loop
    Loop -->|"all analyzers done"| Target --> RunResult
    RunResult -->|"persisted"| RunRecord["RunRecord (runs history)"]
```

#### How a project loads (parser-adapted)

`iter_loaded_projects` and `load_project` resolve one target through the
parser project layer, then re-validate and re-index it back into the SattLint
analysis index. `loading.py` builds the parser binding
(`loader_config.build_parser_binding`) and drives both the recursive load-graph
seam (`loading._load_parser_graph`/`_visit_target_into_graph`) and reads
dependency names via `parser_adapter.find_dependency_path`/`read_dependency_names`.

```mermaid
flowchart LR
Loading["loader_config.build_parser_binding<br/>+ loading.load_project / load_program_ast"]
    Adapter["parser_adapter.py<br/>load_parser_project,<br/>convert_project_into_graph"]
    Parser["sattline-parser project layer<br/>SattLineProject.load(cache_dir=None)<br/>discovery, resolution, parse"]
    Graph["ProjectGraph<br/>(analysis index + timings)"]
    SattLint["sattlint caches<br/>ASTCache / AnalysisReportCache"]

    Loading --> Adapter --> Parser
    Adapter --> Graph
    Graph --> SattLint
```

### Shared artifacts — opportunistic, not a dependency contract

The `variables` analyzer fills `AnalysisSharedArtifacts`
(`src/sattlint/analyzers/framework/_shared_analysis.py`): the **foundation**
(type graph, indices, root env, any-variable index) and the **collected views**
(access graph, usage tracker, alias links, effect flow). Downstream analyzers
such as `sfc` may reuse those memoized artifacts when they
happen to run together; otherwise they build what they need themselves. The
cache is opportunistic — there is no `requires` validation and no analyzer
reads another analyzer's `Report`.

```mermaid
flowchart LR
    V["variables"]
    F["foundation<br/>type graph, indices,<br/>root env, any-var index"]
    CV["collected views<br/>access graph, usage tracker,<br/>alias links, effect flow"]
    SFC["sfc<br/>(may reuse)"]
    ICF["icf<br/>(whole-run, config-based)"]

    V --> F
    V --> CV
    F --> SFC
    CV --> SFC
    ICF
```

Two special cases worth knowing before changing anything:

- **`icf`** is a whole-run analyzer: it does not run per target. `checks.py` pulls it
  out of the batch and runs it once over the whole config after all targets are done.
- **`datatype-fields`** is an opt-in split of the `variables` analyzer that always
  scans the reverse consumers of the analyzed target, so it is more expensive than
  a plain `variables` run and must be chosen explicitly.

## Critical Boundaries

- Parser core ships as the external `sattline-parser` package and does not depend on application layers.
- All SattLine discovery, `.s/.g/.l/.x/.y/.z` reading, dependency resolution, and parsing happen in
  `sattline-parser`'s project layer (`SattLineProject.load`, hermetic via `cache_dir=None`); SattLint
  routes every load through `loader_config.build_parser_binding` + `src/sattlint/project/parser_adapter.py`
  (`load_parser_project`/`convert_project_into_graph`), then re-validates and re-indexes into `ProjectGraph`.
  Cache ownership is split: the parser owns its per-file lookup/AST caches
  (`FileLookupCache`/`FileASTCache`); SattLint owns the analysis caches
  (`ASTCache`/`AnalysisReportCache`/foundation).
- All retained analyzers use the same semantic engine and findings model.
- The analyzer registry is the single rule catalog; CLI, UI, and reporting read from it rather than duplicating rule lists.

## Quality Anchors

- Fast local gate: `python -m pre_commit run --all-files` (when configured) or `ruff check`, `pyright`, and focused `pytest`
- Pyright runs `strict` package-wide except `src/sattlint/ui/`, a deliberate carve-out: `ignore` in `pyproject.toml` `[tool.pyright]` suppresses diagnostics there because the Textual shell drives dynamic runtime APIs that are not practical under strict typing. The shell is exercised by the full pytest suite instead of the type checker.
- Full suite: `python -m pytest -q`
- CI: GitHub Actions workflow `ci.yml` runs ruff, pyright, and the full pytest suite plus wheel smokes on pull request and push to `main`.
