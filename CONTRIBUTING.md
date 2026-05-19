# Contributing to SattLint

This guide covers setting up a development environment for contributing to SattLint.

## Prerequisites

- Python 3.13 or newer
- Git
- A SattLine codebase for testing

## Development Setup

Preferred local bootstrap uses `uv` because CI already installs through `uv`.
`pip install -e .[dev]` remains acceptable when `uv` is unavailable.

### Option 1: Linux or macOS

#### 1. Install Dependencies

```bash
# Install Python 3.13 (via your preferred method: pyenv, mise, uv, or system package)

# Clone repository
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint

# Preferred: install through uv
uv venv
source .venv/bin/activate
uv pip install -e .[dev,lsp]

# Fallback
# python -m venv .venv
# source .venv/bin/activate
# pip install -e .[dev,lsp]
```

#### 2. Editor Setup

Configure your editor with:

- Python language server (pyright or pylance)
- Ruff for linting and formatting
- Pyright for type checking

Consult your editor's documentation for the appropriate LSP and formatter plugins.

### Option 2: Windows with Visual Studio Code

#### 1. Install Dependencies (Windows)

```powershell
# Install Python from python.org or Windows Store
# Clone repository
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint

# Preferred: install through uv
uv venv
python scripts/run_repo_python.py -m pip install -e .[dev,lsp]

# Fallback
# python -m venv .venv
# python scripts/run_repo_python.py -m pip install -e .[dev,lsp]

# Recommended VS Code extensions are listed in .vscode/extensions.json
```

To run the local SattLine VS Code extension client:

```powershell
pip install -e .[lsp]
```

Then copy or symlink `vscode\sattline-vscode` into your VS Code user extensions directory as `local.sattline-vscode-0.1.0` and reload the window. There is no npm or TypeScript build step in the current client.

If you need a packaged extension artifact, run the extension-local packaging script from WSL:

```bash
cd vscode/sattline-vscode
npm run package:vsix
```

#### 2. VS Code Configuration

The repository includes `.vscode/settings.json` which configures:

- Cross-platform Python interpreter discovery via `.venv`
- Ruff for linting
- Pylance in `openFilesOnly` mode for lower editor overhead in this AI-first repo
- Pyright CLI runs as the authoritative type-check gate
- Pytest for testing
- Context Optimizer line budget alignment for AI context files
- Search visibility for machine-readable audit reports under `artifacts/audit/`

Use the workspace task runner in `.vscode/tasks.json` for the common AI and validation flows.

## Development Workflow

### Code Quality

All code quality tools are configured in `pyproject.toml`:

```bash
# Format code
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Type check
pyright src tests

# Run tests
pytest tests/ -v

# Run tests with the enforced coverage baseline
pytest -q --tb=short

# Auto-fix touched Python files after AI edits
python scripts/run_ai_edit_gate.py

# Lint GitHub Actions workflows via the repo wrapper used by pre-commit and CI
python scripts/run_actionlint.py

# Lint Markdown via the repo wrapper used by pre-commit and CI
python scripts/run_markdownlint.py --config .markdownlint-cli2.jsonc

# Run the fast local pre-commit gate
python -m pre_commit run --all-files

# Run the local pre-push gate
sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit

# Audit installed Python dependencies
pip-audit

# Run the repository audit report (audit and CI workflow)
sattlint-repo-audit --profile full --output-dir artifacts/audit
```

The canonical audit entry point is `sattlint-repo-audit`.

- Use `--profile quick` for fast edit-and-verify loops.
- Use `--profile full` for the complete lint, type, test, security, dead-code, and repo-audit pass.
- Open `artifacts/audit/status.json` first; it is the compact machine-readable summary intended for tooling and AI agents.
- The full details remain in `artifacts/audit/summary.json`, `artifacts/audit/findings.json`, and `artifacts/audit/pipeline/`.
- `python scripts/context_health.py --check` is the fast AI-control-plane gate.
- `python scripts/repo_health.py --check --audit-dir artifacts/audit` emits the repo health dashboard from the current audit artifacts.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_cli.py
```

The repository currently enforces a ratcheted minimum coverage threshold in `pyproject.toml`.
Raise that threshold incrementally as test surface expands instead of jumping directly to the long-term target.

### Local Setup

```bash
pip install -e .[dev]
pre-commit install
python scripts/run_ai_edit_gate.py
python -m pre_commit run --all-files
```

Use `python scripts/run_ai_edit_gate.py` after AI or scripted edits to auto-fix touched Python files with Ruff and to rerun context health when the AI-control plane changes.
Use `python -m pre_commit run --all-files` as the fast local hygiene gate for staged formatting, changed Markdown lint, SattLine syntax-check, and targeted context-health checks.
Use `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` as the real local pre-push gate. It selects the right finish gate for the current slice and carries the broader proof burden.
Use the workspace tasks `Quality: Recommend Pipeline Checks` and `Quality: Shared Pipeline Finish Gate` when you need the narrower shared-pipeline routing described in the CLI docs without running the full repo-audit wrapper.
Use `Quality: Structural Ratchet` before or after larger refactors that may move file-size or method-size budgets.
Use `Analysis: Fixture Corpus Runner` when parser or analyzer changes need proof against the checked-in corpus manifests.
Use `Metrics: Observability Snapshot` only for manual local diagnostics; it is not part of the normal finish gate.

## AI-First Workflow

Use one scoped task contract and one scoped handoff per work unit.

1. Claim files in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state.
2. Start from `.ai/tasks/task-contract.example.json`, then create or update `.ai/tasks/<task-id>.json`.
3. Work on `ai/task-<task-id>` or a dedicated worktree.
4. Start from `.ai/handoffs/handoff.example.json`, then emit `.ai/handoffs/<task-id>.json` when the slice moves to test or review.
5. Run `python scripts/run_ai_edit_gate.py`, then the focused owner validation, then `python -m pre_commit run --all-files`, then `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`.

Recommended branch names:

- `ai/task-<id>`
- `test/task-<id>`
- `review/task-<id>`
- `develop/integration` for staged merge trains only

Recommended context workflow in VS Code:

- `@context-optimizer /audit`
- `@context-optimizer /compare`
- `@context-optimizer /optimize`

## Project Structure

- `src/sattlint/` - Main source code
- `tests/` - Test suite
- `grammar/` - SattLine grammar files
- `pyproject.toml` - Project configuration and dependencies
- `.editorconfig` - Cross-editor formatting rules
- `.vscode/settings.json` - VS Code workspace configuration
- `vscode/sattline-vscode/` - Local VS Code extension client for `sattlint_lsp`
- `src/sattlint_lsp/` - Python LSP server implementation used by the VS Code client

## Making Changes

1. Create a scoped branch or worktree: `ai/task-<id>`, `test/task-<id>`, or `review/task-<id>`.
2. Keep the slice small and update the task contract or handoff when scope changes.
3. Run `python scripts/run_ai_edit_gate.py`, then focused validation, then `python -m pre_commit run --all-files`, then `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`.
4. Fill in the pull request template with task ID, handoff path, commands run, and remaining risks.
5. Push and create the pull request.

## Platform-Specific Notes

### Windows-Specific Tool

Note: `src/sattlint/docgenerator/configgen.py` generates Excel configuration workbooks and now requires an explicit root directory argument instead of relying on a workstation-specific default path. It is not required for core SattLint functionality.

### Cross-Platform Compatibility

- Use `pathlib.Path` for file operations
- Avoid hard-coded paths in new code
- Keep `.vscode/settings.json` platform-neutral by pointing at the virtual environment root instead of OS-specific executables
- Test changes on both platforms if possible
