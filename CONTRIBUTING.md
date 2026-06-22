# Contributing to SattLint

This guide covers setting up a development environment for contributing to SattLint.

For public support boundaries, see [SUPPORT.md](SUPPORT.md) and [docs/references/public-support-matrix.md](docs/references/public-support-matrix.md). All contributors are expected to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Maintainer operating docs now start at [docs/maintainers/README.md](docs/maintainers/README.md), including the routing map, quality gates, and validation map.

## How to Contribute as a Human Contributor

### Reporting Bugs

1. Check the [public support matrix](docs/references/public-support-matrix.md) to confirm whether the affected surface is stable or preview.
2. Search existing [issues](https://github.com/SorenHJohansen/SattLint/issues) to avoid duplicates.
3. Open a [bug report](https://github.com/SorenHJohansen/SattLint/issues/new?template=bug_report.md) with:
   - SattLint version (`sattlint --version`)
   - Install method and operating system
   - Exact command that triggered the issue
   - Minimal reproduction input (safe to share)
   - Expected vs actual behavior

### Suggesting Features

1. Read the [public support matrix](docs/references/public-support-matrix.md) to understand stable vs preview boundaries.
2. Open a [feature request](https://github.com/SorenHJohansen/SattLint/issues/new?template=feature_request.md) describing the problem you are solving, the desired behavior, and any current workaround.

### Submitting Pull Requests

1. Fork the repository and create a focused branch (`feature/`, `fix/`, or `chore/`).
2. Keep changes small and scoped to a single concern.
3. Run the pre-commit gate before pushing:

   ```bash
   python -m pre_commit run --all-files
   ```

4. Run the full audit if your change touches source or test files:

   ```bash
   sattlint-repo-audit --profile full --output-dir artifacts/audit
   ```

5. Open a pull request against `main`. Fill in the PR template with commands run and remaining risks.
6. A maintainer will review your changes. Expect questions or requests for narrower scope.

For human-readable CLI reference, see [docs/public/feature-guide.md](docs/public/feature-guide.md) and [docs/public/cli-commands.md](docs/public/cli-commands.md).

### Getting Help

- Usage questions: open a GitHub issue with the question template.
- Security vulnerabilities: follow [SECURITY.md](SECURITY.md) and report privately.
- Anything else: open a GitHub issue.

---

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

To run the local SattLine VS Code extension client preview:

```powershell
pip install -e .[lsp]
```

Then copy or symlink `vscode\sattline-vscode` into your VS Code user extensions directory under a folder such as `local.sattline-vscode-dev` and reload the window. There is no npm or TypeScript build step in the current client, and this client remains a preview-only surface until it has a public publisher and release story.

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
The committed task list is intentionally short; keep one-off investigation commands out of the shared workspace file.

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

# Lint GitHub Actions workflows via the repo wrapper used by pre-commit and CI
python scripts/run_actionlint.py

# Lint Markdown via the repo wrapper used by pre-commit and CI
python scripts/run_markdownlint.py --config .markdownlint-cli2.jsonc

# Run the fast local pre-commit gate
python -m pre_commit run --all-files

# Run the AI post-change drift gate
sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit

# Audit installed Python dependencies
pip-audit

# Run the local pre-push or CI audit
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
python scripts/context_health.py --check
python -m pre_commit run --all-files
```

Run focused owner validation immediately after the first substantive edit.
Use `python scripts/context_health.py --check` when the AI-control plane changes.
Use `python -m pre_commit run --all-files` as the fast local hygiene gate for staged formatting, changed Markdown lint, SattLine syntax-check, and targeted context-health checks.
Use `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` as the AI post-change drift gate.
Use `sattlint-repo-audit --profile full --output-dir artifacts/audit` as the real local pre-push gate before you push or when you want CI-equivalent repo proof.
Use the shared workspace tasks only as thin wrappers around those same commands when you want them in VS Code.
Use `python scripts/run_ai_edit_gate.py <touched paths...>` only when you are debugging the `.github/hooks/ai-edit-gate.json` hook itself.

## AI-First Workflow

Use one focused branch or worktree per slice.

1. Start from `AGENTS.md` and the owning file, failing command, or failing test.
2. Keep the slice small enough that focused validation is obvious.
3. Run the first focused owner validation immediately.
4. Run `python scripts/context_health.py --check` when AI-control files changed.
5. AI-touched files are additionally blocked through `.github/hooks/ai-edit-gate.json`; rerun `python scripts/run_ai_edit_gate.py <touched paths...>` only when debugging that hook locally.
6. Run `python -m pre_commit run --all-files`, then `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` while iterating, and finish with `sattlint-repo-audit --profile full --output-dir artifacts/audit` before pushing.

Repository structure for maintainer work:

- `AGENTS.md` is the human-authored AI workflow contract.
- `.ai/` is reserved for machine-authored AI artifacts and handoff data.
- `docs/maintainers/` holds human maintainer docs.
- `.github/workflows/` should stay small: CI, nightly, and publish.
- `.vscode/` should stay repo-wide and stable, not issue-specific.

Recommended branch names:

- `feature/<topic>`
- `fix/<topic>`
- `chore/<topic>`

Recommended context workflow in VS Code:

- `@context-optimizer /audit`

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

1. Create a focused branch or worktree.
2. Keep the slice small and run the first focused validation immediately.
3. Run `python scripts/context_health.py --check` when AI-control files changed, then `python -m pre_commit run --all-files`, then `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`, and use `sattlint-repo-audit --profile full --output-dir artifacts/audit` before pushing.
4. Fill in the pull request template with commands run and remaining risks.
5. Push and create the pull request.

## Platform-Specific Notes

### Windows-Specific Tool

Note: `src/sattlint/docgenerator/configgen.py` generates Excel configuration workbooks and now requires an explicit root directory argument instead of relying on a workstation-specific default path. It is not required for core SattLint functionality.

### Cross-Platform Compatibility

- Use `pathlib.Path` for file operations
- Avoid hard-coded paths in new code
- Keep `.vscode/settings.json` platform-neutral by pointing at the virtual environment root instead of OS-specific executables
- Test changes on both platforms if possible
