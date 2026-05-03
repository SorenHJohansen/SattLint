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

Repository audit and quality checks. Primary entry point for CI and audit workflows. Local pre-push gate is `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`.

```bash
# Quick audit (fast iteration during development)
sattlint-repo-audit --profile quick --output-dir artifacts/audit

# Full audit (comprehensive lint, type, test, security, dead-code, and repo checks)
sattlint-repo-audit --profile full --output-dir artifacts/audit

# List every individually runnable full-audit check and its exact command
sattlint-repo-audit --profile full --list-checks

# Recommend the narrowest repo-audit slice for the current git diff or explicit changed files
sattlint-repo-audit --profile full --recommend-checks
sattlint-repo-audit --profile full --recommend-checks --changed-file docs/references/cli-commands.md

# Run the recommended combined slice in one command
sattlint-repo-audit --profile full --run-recommended-slice --changed-file docs/references/cli-commands.md --output-dir artifacts/audit

# Run the recommended finish gate in one command
sattlint-repo-audit --profile full --run-recommended-finish-gate --changed-file docs/references/cli-commands.md --output-dir artifacts/audit

# Let the tool choose the right finish gate for the current change set and print one JSON result
sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit
sattlint-repo-audit --profile full --check-my-changes --changed-file src/sattlint/devtools/repo_audit.py --output-dir artifacts/audit

# Print the authoritative planning report for the current or explicit change set
sattlint-repo-audit --profile full --planning-context --changed-file src/sattlint/app.py --output-dir artifacts/audit

# Run one repo-audit-specific full check without the shared pipeline
sattlint-repo-audit --profile full --check public-readiness --skip-pipeline --output-dir artifacts/audit

# Verify recommendation metadata drift directly
sattlint-repo-audit --profile full --check verify-recommendations --skip-pipeline --output-dir artifacts/audit

# Run the full CLI consistency report by itself
sattlint-repo-audit --profile full --check cli-consistency --skip-pipeline --output-dir artifacts/audit

# Fail if findings exceed threshold
sattlint-repo-audit --profile quick --fail-on medium --output-dir artifacts/audit
sattlint-repo-audit --profile full --fail-on high --output-dir artifacts/audit
```

AI edit autofix:

```bash
python scripts/run_ai_edit_gate.py
python scripts/run_ai_edit_gate.py scripts/context_health.py tests/test_ai_edit_gate.py
```

Fast local pre-commit gate:

```bash
python -m pre_commit run --all-files
```

That hook set is now intentionally fast and file-scoped. It auto-fixes Python formatting with Ruff, lints changed Markdown files, checks staged SattLine files, and reruns context health only when the AI-control plane is touched.

Local pre-push gate:

```bash
sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit
```

Use the pre-push gate for the heavier proof burden: focused owner tests, touched-file Ruff and Pyright, ratchet policy, and the recommended repo-audit slice for the current change set.

Output:

- `artifacts/audit/status.json`  -  Compact machine-readable summary (start here)
- `artifacts/audit/summary.json`  -  Detailed findings by category
- `artifacts/audit/findings.json`  -  Complete finding records with line/column info
- `artifacts/audit/pipeline/`  -  Component-level check outputs (linting, typing, tests, etc.)

Requirement:

- Every full-profile repo-audit check must be individually runnable and listed by `sattlint-repo-audit --profile full --list-checks`.
- Shared pipeline checks are exposed through the same catalog but run via `sattlint-analysis-pipeline --check ...` commands.
- `--recommend-checks` prints machine-readable routing metadata for the current git diff unless `--changed-file` is repeated explicitly.
- `--run-recommended-slice` reuses that routing and runs only the recommended shared-pipeline and repo-audit checks.
- `--run-recommended-finish-gate` runs the recommended slice plus touched-file Ruff, touched-file Pyright, and focused owner pytest targets. When touched `src/**/*.py` files exist, the owner pytest step also emits focused coverage output and the finish gate evaluates changed-line coverage first, then touched-file coverage when no executable changed lines exist.
- `--planning-context` is the default machine entrypoint for agents. It returns changed files, owning surface, required instruction files, first focused validation, finish-gate plan, blocking invariants, and proof requirements in one response.
- `--check-my-changes` reuses the same routing, auto-selects the shared pipeline finish gate when no repo-audit-specific checks are needed, otherwise runs the combined repo-audit finish gate, writes `check_my_changes.json`, and records the same focused coverage-proof obligations used by `--planning-context`.
- Planning and finish-gate reports now carry `proof_requirements` so agents can see whether a focused behavior test is required, whether changed-line or touched-file coverage proof applies, and whether parser, validation, or routing changes deserve mutation or property-style follow-up.
- `--check verify-recommendations --skip-pipeline` fails when catalog metadata is missing, dead, obviously overbroad, or when the checked-in generated AI routing maps drift from the live build.

---

### sattlint-structural-ratchet

Run only the structural budget ratchet check without the rest of the repository audit pipeline.

```bash
# Fast structural-ratchet check against the checked-in baseline
sattlint-structural-ratchet

# Machine-readable status for scripting
sattlint-structural-ratchet --json
```

Used to:

- Verify whether structural budget regressions exist before running the full repo audit
- Inspect the checked-in ratchet status and regressions quickly during local edits
- Override the repo root or ratchet file when debugging with `--repo-root` or `--ratchet-path`

Exit code:

- `0` when the ratchet passes
- `1` when the ratchet is missing, invalid, or regressed

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

# List the individually runnable pipeline checks for the chosen profile
sattlint-analysis-pipeline --profile full --list-checks

# Recommend the narrowest pipeline slice for the current git diff or explicit changed files
sattlint-analysis-pipeline --profile full --recommend-checks
sattlint-analysis-pipeline --profile full --recommend-checks --changed-file src/sattlint/devtools/repo_audit.py

# Run the recommended pipeline slice in one command
sattlint-analysis-pipeline --profile full --run-recommended-slice --changed-file src/sattlint/devtools/repo_audit.py --output-dir artifacts/audit/pipeline

# Run the recommended pipeline finish gate in one command
sattlint-analysis-pipeline --profile full --run-recommended-finish-gate --changed-file src/sattlint/devtools/repo_audit.py --output-dir artifacts/audit/pipeline

# Run one full-profile pipeline check in isolation
sattlint-analysis-pipeline --profile full --check ruff --output-dir artifacts/audit/pipeline
sattlint-analysis-pipeline --profile full --check structural-reports --output-dir artifacts/audit/pipeline
```

Orchestrates:

- Parser correctness checks
- Semantic analysis
- Code quality metrics
- Structural budget enforcement
- Security and dependency audits

Output feeds into `sattlint-repo-audit` and CI checks.

For AI-assisted review of a narrow change set, prefer `--recommend-checks` first and `--run-recommended-finish-gate` when you want one executable finish gate. Full pipeline runs now also emit `recommendation_drift.json` when changed files are known, so CI can catch non-passing checks that were omitted from the recommended slice.

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
