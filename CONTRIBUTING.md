# Contributing to SattLint

This guide covers setting up a development environment for contributing to SattLint.

## Prerequisites
- Python 3.13 or newer
- Git
- A SattLine codebase for testing

## Development Setup

### Option 1: Linux or macOS

#### 1. Install Dependencies
```bash
# Install Python 3.13 (via your preferred method: pyenv, mise, uv, or system package)

# Clone repository
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .[dev]
```

#### 2. Editor Setup
Configure your editor with:
- Python language server (pyright or pylance)
- Ruff for linting and formatting
- Black for formatting
- MyPy for type checking

Consult your editor's documentation for the appropriate LSP and formatter plugins.

### Option 2: Windows with Visual Studio Code

#### 1. Install Dependencies
```powershell
# Install Python from python.org or Windows Store
# Clone repository
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install in development mode
pip install -e .[dev]

# Install VS Code extensions (prompted automatically)
# - Python
# - Pylance (automatically installed with Python extension)
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
- Python interpreter detection
- Ruff for linting
- Black for formatting
- MyPy for type checking
- Pytest for testing

## Development Workflow

### Code Quality
All code quality tools are configured in `pyproject.toml`:

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/

# Run tests
pytest tests/ -v

# Run the repository audit
sattlint-repo-audit --output-dir artifacts/audit
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/sattlint

# Run specific test file
pytest tests/test_analyzer.py
```

### Pre-commit Hooks (Optional)
```bash
# Install pre-commit framework
pip install pre-commit
pre-commit install

# This will run formatting, linting, and type checks before each commit
```

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

1. Create a feature branch: `git checkout -b feature-name`
2. Make your changes
3. Run tests and code quality checks
4. Commit with clear messages
5. Push and create pull request

## Platform-Specific Notes

### Windows-Specific Tool
Note: `src/sattlint/docgenerator/configgen.py` generates Excel configuration workbooks and now requires an explicit root directory argument instead of relying on a workstation-specific default path. It is not required for core SattLint functionality.

### Cross-Platform Compatibility
- Use `pathlib.Path` for file operations
- Avoid hard-coded paths in new code
- Test changes on both platforms if possible
