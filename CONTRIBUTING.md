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

For a human-readable CLI reference, see [FEATURE_GUIDE.md](FEATURE_GUIDE.md).

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

Preferred local bootstrap uses `uv`. `pip install -e .[dev]` remains acceptable when `uv` is unavailable. CI installs with `pip install -e ".[dev]"`.

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

Configure your editor manually with Python interpreter discovery, Ruff,
Pylance/Pyright, and pytest. The repository does not ship a `.vscode/settings.json`.

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
python -m pytest tests/app/test_cli.py

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
- Keep editor settings platform-neutral by pointing at the virtual environment root instead of OS-specific executables
- Test changes on both platforms if possible

---

## Releasing SattLint

Releases are cut from `main` by tagging a commit with `vYYYY.M.number`; the
`Publish` workflow (`.github/workflows/publish.yml`) builds, gates, and
publishes to PyPI via trusted publishing (OIDC). The version is single-sourced
from `src/sattlint/__version__.py` and read dynamically by `pyproject.toml`.

### Versioning

SattLint uses calendar versioning (`vYYYY.M.number`) to match `sattline-parser`:
`YYYY` is the year, `M` the month, and `number` the release count within that
month (starting at 1).

### Pre-release checklist

Run every item and confirm before tagging:

- [ ] Working tree is clean on `main` (or the release branch is fully merged).
- [ ] Full local gate is green:
      `python -m pre_commit run --all-files`,
      `python -m ruff check .`,
      `python -m ruff format --check .`,
      `python -m pyright src/sattlint`,
      `python -m pytest -q --tb=short`.
- [ ] `CHANGELOG.md` has a dated `## [YYYY.M.number]` entry for the release and
      the `[Unreleased]` block is empty.
- [ ] `sattlint --version` reports the intended version.
- [ ] `python -m build` and `python -m twine check dist/*` pass with no
      warnings (including no license deprecation warning).
- [ ] Documentation references match the shipped surface (commands, paths,
      exit codes).

### PyPI environment protection (manual, GitHub settings)

`publish.yml` targets the `pypi-release` deployment environment. Trusted
publishing (OIDC) is enabled, but **required-reviewer protection is not
configured in the repository**. Before the first production release, configure
the environment in GitHub settings:

1. Open **Settings > Environments > pypi-release**.
2. Add **Required reviewers** (at least one account with write access).
3. Optionally restrict the deployment branch to `main`.

Until a reviewer is configured, a tag push can publish without human review.

### Tag and publish

The `Publish` workflow runs the full CI gate (`ci.yml` as a reusable workflow)
on the tagged commit before building. A tag on a commit whose CI gate fails
cannot proceed to `build`.

```sh
# From a clean main
git tag vYYYY.M.number
git push origin vYYYY.M.number
```

The workflow then:

1. Runs the CI gate on the tagged commit.
2. Builds sdist + wheel and runs `twine check`.
3. Runs a clean-venv smoke (`--version`, `--help`, one `syntax-check`).
4. Publishes to PyPI via trusted publishing.

### Release automation decisions (recorded 2026-09-08)

- **GitHub Release creation**: manual. The `Publish` workflow does not create
  releases; the release is made from the tag with the CHANGELOG entry as notes.
- **Artifact attestations**: not enabled; revisit if supply-chain requirements
  change.
- **`CODEOWNERS` review gate for the release path**: not added; the
  `pypi-release` environment reviewer protection is the human gate.

### Post-publish verification

- [ ] `pipx install sattlint` (or `pipx upgrade sattlint`) succeeds.
- [ ] `sattlint --version` reports the released version.
- [ ] `sattlint --help` lists the documented commands.
- [ ] `sattlint syntax-check <sample.s>` behaves as documented.
- [ ] Create a GitHub Release for the tag with the CHANGELOG entry as notes
      (the `Publish` workflow does not create releases automatically).
