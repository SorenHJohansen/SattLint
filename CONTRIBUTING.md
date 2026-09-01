# Contributing to SattLint

This guide covers setting up a development environment for contributing to SattLint.

For public support boundaries, see [SUPPORT.md](SUPPORT.md). All contributors are expected to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## How to Contribute as a Human Contributor

### Reporting Bugs

1. Check [SUPPORT.md](SUPPORT.md) to confirm whether the affected surface is stable or preview.
2. Search existing [issues](https://github.com/SorenHJohansen/SattLint/issues) to avoid duplicates.
3. Open a [bug report](https://github.com/SorenHJohansen/SattLint/issues/new?template=bug_report.md) with:
   - SattLint version (`sattlint --version`)
   - Install method and operating system
   - Exact command that triggered the issue
   - Minimal reproduction input (safe to share)
   - Expected vs actual behavior

### Suggesting Features

1. Read [SUPPORT.md](SUPPORT.md) to understand stable vs preview boundaries.
2. Open a [feature request](https://github.com/SorenHJohansen/SattLint/issues/new?template=feature_request.md) describing the problem you are solving, the desired behavior, and any current workaround.

### Submitting Pull Requests

1. Fork the repository and create a focused branch (`feature/`, `fix/`, or `chore/`).
2. Keep changes small and scoped to a single concern.
3. Run the pre-commit gate before pushing:

   ```bash
   python -m pre_commit run --all-files
   ```

4. Run the full validation set if your change touches source or test files:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m pyright src/sattlint
   python -m pytest -q --tb=short
   ```

5. Open a pull request against `main`. Fill in the PR template with commands run and remaining risks.
6. A maintainer will review your changes. Expect questions or requests for narrower scope.

For a human-readable CLI reference, see [docs/public/feature-guide.md](docs/public/feature-guide.md).

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
uv pip install -e ".[dev]"

# Fallback
# python -m venv .venv
# source .venv/bin/activate
# pip install -e ".[dev]"
```

#### 2. Editor Setup

Configure your editor with:

- Python language server (pyright or pylance)
- Ruff for linting and formatting
- Pyright for type checking

### Option 2: Windows

#### 1. Install Dependencies

```powershell
# Install Python from python.org or Windows Store
# Clone repository
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint

# Preferred: install through uv
uv venv
.venv\Scripts\activate
uv pip install -e ".[dev]"

# Fallback
# python -m venv .venv
# .venv\Scripts\activate
# pip install -e ".[dev]"
```

#### 2. VS Code Configuration

The repository includes `.vscode/settings.json` which configures Python interpreter
discovery, Ruff, Pylance, Pyright, and pytest.

## Development Workflow

### Code Quality

All code quality tools are configured in `pyproject.toml`:

```bash
# Format code
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Type check production code
pyright src/sattlint

# Run tests
pytest -q --tb=short
```

Run the fast local hygiene gate before pushing:

```bash
python -m pre_commit run --all-files
```

The pre-commit gate runs Ruff fix and format, Pyright on `src/sattlint`,
SattLine `syntax-check` on staged SattLine fixtures, and the standard
pre-commit-hooks checks.

### Running Tests

```bash
# Run all tests
python -m pytest

# Run a focused test module
python -m pytest tests/test_cli.py

# Run focused owner validation after editing
python -m pytest <focused-paths> -q --tb=short
```

Run focused owner validation immediately after the first substantive edit, then
widen to the full suite.

## Project Structure

- `src/sattlint/` - Main source code
- `tests/` - Test suite
- `pyproject.toml` - Project configuration and dependencies
- `.editorconfig` - Cross-editor formatting rules
- `.vscode/settings.json` - VS Code workspace configuration

## Making Changes

1. Create a focused branch or worktree.
2. Keep the slice small and run the first focused validation immediately.
3. Run `python -m pre_commit run --all-files`, then the full validation set above
   before pushing.
4. Fill in the pull request template with commands run and remaining risks.
5. Push and create the pull request.

## Platform-Specific Notes

### Cross-Platform Compatibility

- Use `pathlib.Path` for file operations
- Avoid hard-coded paths in new code
- Keep `.vscode/settings.json` platform-neutral by pointing at the virtual environment root instead of OS-specific executables
- Test changes on both platforms if possible
