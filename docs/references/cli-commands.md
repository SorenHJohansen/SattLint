# SattLint CLI Commands Reference

Comprehensive reference for all SattLint command-line interfaces.

## User-Facing Commands

### sattlint

The main SattLint command. Opens an interactive menu by default; also supports non-interactive subcommands.

#### Interactive Mode (Default)

```bash
sattlint
```

Opens the interactive menu with options for:

- File syntax checking
- Project analysis
- Configuration management
- Variable analysis
- Documentation generation
- Cache management

#### Subcommands

**syntax-check**  -  Validate a SattLine file for syntax errors (strict single-file parsing):

```bash
sattlint syntax-check path/to/Program.s
```

**analyze**  -  Run semantic analysis on configured project:

```bash
sattlint analyze
sattlint analyze --list-checks        # Show available checks
sattlint analyze --config path/to/config.toml
sattlint analyze --no-cache           # Skip caching layer
```

**validate-config**  -  Validate configuration file:

```bash
sattlint validate-config
sattlint validate-config --config path/to/config.toml --verbose
```

**docgen**  -  Generate Word documentation:

```bash
sattlint docgen --output-dir docs-out
sattlint docgen --config path/to/config.toml --output-dir docs-out
```

**format-icf**  -  Format Industrial Control Format:

```bash
sattlint format-icf
sattlint format-icf --check              # Check mode only
sattlint format-icf --config path/to/config.toml
```

**repo-audit**  -  Audit repository structure and health:

```bash
sattlint repo-audit --profile quick
sattlint repo-audit --profile full
sattlint repo-audit --fail-on high       # Exit with error if findings exceed threshold
```

#### Global Flags

```bash
sattlint --config path/to/config.toml [subcommand]
sattlint --verbose [subcommand]
sattlint --quiet [subcommand]
sattlint --no-cache [subcommand]
```

---

### sattlint-gui

Desktop GUI shell for SattLint operations.

```bash
sattlint-gui
```

Features:

- Configuration editing
- Self-check and cache tools
- Variable analysis launcher
- Non-interactive DOCX generation

---

### sattlint-lsp

Language Server Protocol (LSP) server for SattLine support in editors like VS Code.

```bash
sattlint-lsp
```

Used by the VS Code extension (`vscode/sattline-vscode/`) to provide:

- Syntax diagnostics
- Code completion
- Definition lookup
- References
- Hover information
- Workspace symbol resolution

---

## Developer / DevTools Commands

### sattlint-repo-audit

Repository audit and quality checks. Primary entry point for continuous integration and pre-commit verification.

```bash
# Quick audit (fast iteration during development)
sattlint-repo-audit --profile quick --output-dir artifacts/audit

# Full audit (comprehensive lint, type, test, security, dead-code, and repo checks)
sattlint-repo-audit --profile full --output-dir artifacts/audit

# Fail if findings exceed threshold
sattlint-repo-audit --profile quick --fail-on medium --output-dir artifacts/audit
sattlint-repo-audit --profile full --fail-on high --output-dir artifacts/audit
```

Output:

- `artifacts/audit/status.json`  -  Compact machine-readable summary (start here)
- `artifacts/audit/summary.json`  -  Detailed findings by category
- `artifacts/audit/findings.json`  -  Complete finding records with line/column info
- `artifacts/audit/pipeline/`  -  Component-level check outputs (linting, typing, tests, etc.)

---

### sattlint-doc-gardener

Documentation maintenance and validation tool.

```bash
sattlint-doc-gardener
```

Validates:

- Documentation structure and consistency
- Markdown syntax
- Cross-file reference integrity
- Execution plan alignment

Used in CI to keep docs synchronized with code changes.

---

### sattlint-corpus-runner

Test corpus execution and validation for SattLine test suites.

```bash
sattlint-corpus-runner
```

Used to:

- Run regression test suites across fixture corpora
- Validate analyzer behavior on standardized samples
- Track coverage metrics over time

---

### sattlint-analysis-pipeline

Internal analysis pipeline for generating structured audit artifacts.

```bash
sattlint-analysis-pipeline
```

Orchestrates:

- Parser correctness checks
- Semantic analysis
- Code quality metrics
- Structural budget enforcement
- Security and dependency audits

Output feeds into `sattlint-repo-audit` and CI checks.

---

## Specialized Commands

### sattlint-layer-lint

HA (Hierarchical Architecture) layer validation.

```bash
sattlint-layer-lint
```

Enforces SattLine module hierarchy and layering rules.

---

### sattlint-review

Code review assistant tool.

```bash
sattlint-review
```

Provides structured feedback on SattLine code changes.

---

### sattlint-observability

Observability and tracing tools.

```bash
sattlint-observability
```

Used for performance profiling and execution analysis.

---

### sattlint-trace

Parser and analyzer execution tracer.

```bash
sattlint-trace
```

Produces detailed execution traces for:

- Parser debugging
- Semantic analysis inspection
- Performance diagnostics

---

## Installation

All commands are installed via:

```bash
pipx install .           # From SattLint repository root
# or
pip install -e .         # For development
pip install -e ".[dev]"  # With all dev tools
```

Console scripts are declared in `pyproject.toml` and automatically added to `PATH` during installation.

---

## Configuration

Most user-facing commands respect a shared configuration file:

- **Windows:** `%APPDATA%\sattlint\config.toml`
- **Linux/macOS:** `~/.config/sattlint/config.toml`

Override with `--config path/to/custom.toml` on any command.

---

## Exit Codes

| Code | Meaning                                    |
| ---- | ------------------------------------------ |
| 0    | Success                                    |
| 1    | Execution error (check output for details) |
| 2    | Invalid arguments or configuration         |

Audit commands may exit with 1 if findings exceed `--fail-on` threshold (not an error, but explicit status).

---

## See Also

- `CONTRIBUTING.md`  -  Development setup and workflow
- `README.md`  -  Getting started guide
- `docs/context-loading-order.md`  -  Documentation navigation strategy
- `docs/design-docs/index.md`  -  Architecture and design documents
