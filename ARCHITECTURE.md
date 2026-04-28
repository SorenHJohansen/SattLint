# Architecture

This document describes the high-level architecture of SattLint. If you want to familiarize yourself with the code base, you are just in the right place!

See also the [design docs](docs/design-docs/index.md), which discuss design decisions in more detail.

Also see [core beliefs](docs/design-docs/core-beliefs.md), which define the golden principles that guide all development.

## Bird's Eye View

On the highest level, SattLint is a thing which accepts input SattLine source code from the client and produces a structured semantic model of the code, along with analysis results and diagnostics.

More specifically, input data consists of a set of SattLine files and information about project structure, captured in the so called `ProjectGraph`. The project graph specifies which files are program roots, which libraries are analyzed, and what dependencies exist between the programs.

SattLint keeps all this input data in memory and uses a project-level analysis model. Because the input data is source code, which typically measures in megabytes at most, keeping everything in memory is fine.

A "structured semantic model" is basically an object-oriented representation of programs, blocks, variables, and expressions which appear in the source code. This representation is fully "resolved": all expressions have types, all references are bound to declarations, etc.

The client can submit a small delta of input data (typically, a change to a single file) and get fresh analysis results which account for the changes.

The underlying engine makes sure that analysis is computed lazily (on-demand) and can be quickly updated for small modifications.

## Code Map

This section talks briefly about various important directories and data structures. Pay attention to the **Architecture Invariant** sections. They often talk about things which are deliberately absent in the source code.

### `src/sattline_parser/`

This is the **parser core** of SattLint. It contains the Lark grammar, the transformer, and AST models.

-   `grammar/` contains the `.lark` grammar file and Lark-specific configuration
-   `transformer/` contains the transformation logic from parse tree to AST
-   `models/` contains the AST node definitions (data classes)
-   `utils/` contains parser utilities

**Architecture Invariant:** the parser is independent of the particular analysis backend. It transforms SattLine source text into an AST and nothing more. This independence allows us to parse both source code and macro input. It should also unlock efficient light-parsing approaches.

**Architecture Invariant:** parsing never fails in the traditional sense. The parser produces a best-effort parse tree with errors attached, rather than failing outright. This matches how IDEs need to work with incomplete or invalid code.

### `src/sattlint/`

This is the **main application** crate. It contains the CLI, configuration, analyzers, and reporting.

-   `analyzers/` contains 30+ registered analysis passes
-   `core/` contains shared semantic helpers (symbol lookup, completions)
-   `models/` contains application-level data structures
-   `transformer/` contains AST transformation for analysis
-   `reporting/` contains output formatters and reporters
-   `resolution/` contains symbol resolution logic
-   `contracts/` contains contract definitions
-   `devtools/` contains developer tooling (pipeline, audit, corpus)

**Architecture Invariant:** `sattlint/` knows about the SattLine domain but nothing about LSP or specific editor integrations. This is the **API Boundary** for library usage.

### `src/sattlint/analyzers/`

The analyzer crate is the **brain** of SattLint. This is the analysis part of the IDE.

The analyzers work with raw AST and semantic information. There's strong ECS flavor here: analyzers query the database directly and work with raw IDs.

Name resolution, type inference, and dataflow analysis all happen here.

**Architecture Invariant:** these crates are not, and will never be, an API boundary. They define internal analysis logic.

**Architecture Invariant:** analyzers explicitly care about being incremental. The core invariant is: "typing inside a program never invalidates global derived data."

### `src/sattlint_lsp/`

This crate implements the **Language Server Protocol** server.

-   `server.py` contains the LSP server implementation
-   `workspace_store.py` contains the incremental parsing and workspace snapshot logic

**Architecture Invariant:** `sattlint_lsp` is the only crate that knows about LSP and JSON-RPC. If you want to expose a data structure to LSP, create a serializable counterpart here and manually convert between the two.

**Architecture Invariant:** the LSP server should be partially available even when analysis fails. Reloading process should not prevent IDE features from working.

### `src/sattlint/core/`

This crate provides **shared semantic helpers** for editor integration. It contains symbol lookup, completions, and diagnostics support.

This is an **API Boundary**. If you want to use SattLint as a library for a custom editor, this is the facade you'll talk to.

### `src/sattlint/devtools/`

Developer tooling for analysis and validation workflows:

-   `pipeline.py` runs batch analysis
-   `repo_audit.py` checks public-readiness
-   `corpus.py` runs corpus-based tests
-   `arch_linter.py` enforces layered architecture
-   `doc_gardener.py` scans for stale documentation
-   `observability.py` collects metrics
-   `review_tool.py` runs comprehensive reviews

### `src/sattlint_gui/`

Desktop GUI application using PyQt.

### `vscode/sattline-vscode/`

VS Code extension. No-build configuration.

### `tests/`

Test fixtures and regression coverage.

### `docs/`

Design docs, execution plans, and reference material.

## Cross-Cutting Concerns

This section talks about things which are everywhere and nowhere in particular.

### Code Generation

Some components are generated automatically. The grammar generates the AST models via the transformer.

### Cancellation

The analysis engine supports cancellation. When a user types while analysis is running, the analysis should be cancelled. Results are now stale.

SattLint maintains a global revision counter. When applying a change, the counter is bumped and the analysis state is marked stale.

### Testing

SattLint has three interesting system boundaries to concentrate tests on:

The outermost boundary is the `sattlint_lsp` crate, which defines an LSP interface. We do integration testing of this component by feeding it LSP requests and checking responses.

The middle boundary is `sattlint`. Unlike LSP, it uses Python API and is intended for use by various tools.

The innermost boundary is `sattline_parser`. Tests here verify parser behavior against known inputs.

**Architecture Invariant:** tests are data-driven. Tests which directly call various API functions are a liability because they make refactoring harder. Most tests look like:

```python
def check(input_text: str, expected_errors: list[str]) -> None:
    # The single place that exercises a particular API
```

### Error Handling

**Architecture Invariant:** core parts of SattLint (`sattlint/`, `sattline_parser/`) don't interact with the outside world and thus can't fail. Only parts touching LSP or file I/O are allowed to do I/O.

Internals need to deal with broken code, but this is not an error condition. SattLint is robust: various analysis compute results with errors attached rather than failing.

### Observability

SattLint is a long-running process, so it's important to understand what's going on inside.

The observability module collects:
- Test metrics (passed/failed/skipped)
- Coverage metrics (line/branch coverage)
- Lint metrics (warnings/errors)
- Build metrics (install/lint/test success)

These are written to `artifacts/observability.json` for consumption by external tools.

### Architecture Linting

We enforce architecture constraints mechanically via `arch_linter.py`:

- Fixed set of layers with strictly validated dependency directions
- Parser core never imports application code
- LSP → Core → Analyzers → Parser (dependency direction)

**Architecture Invariant:** within a module, agents have freedom of expression. Between modules, boundaries are enforced strictly.

### Documentation Quality

We treat documentation as code. The `doc_gardener.py` tool:
- Checks AGENTS.md is under 100 lines
- Validates dead links
- Scans for stale docs (not updated when code changed)
- Validates docs/ directory structure
- Updates quality-score.md with findings

**Architecture Invariant:** stale documentation is worse than no documentation. Docs rot is tracked as technical debt.
