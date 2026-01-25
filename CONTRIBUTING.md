# Contributing to SattLint

This guide covers setting up a development environment for contributing to SattLint.

## Prerequisites
- Python 3.11 or newer
- Git
- A SattLine codebase for testing

## Development Setup

### Option 1: Linux with Neovim

#### 1. Install Dependencies
```bash
# Install mise for Python version management
curl https://mise.run | sh

# Install Python 3.13
mise install python@3.13

# Clone repository
git clone <repository-url>
cd SattLint

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .[dev]
```

#### 2. Neovim Configuration
Ensure you have these LSP servers configured:
- `pyright` for Python language server
- `ruff` for linting and formatting
- `null-ls` can integrate ruff/black/mypy

Example nvim-lspconfig:
```lua
require'lspconfig'.pyright.setup{
    settings = {
        python = {
            analysis = {
                autoSearchPaths = true,
                diagnosticMode = "openFilesOnly",
                useLibraryCodeForTypes = true
            }
        }
    }
}
```

### Option 2: Windows with Visual Studio Code

#### 1. Install Dependencies
```powershell
# Install Python from python.org or Windows Store
# Clone repository
git clone <repository-url>
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
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# This will run black, ruff, mypy before each commit
```

## Project Structure

- `src/sattlint/` - Main source code
- `tests/` - Test suite
- `grammar/` - SattLine grammar files
- `pyproject.toml` - Project configuration and dependencies
- `.editorconfig` - Cross-editor formatting rules
- `.vscode/settings.json` - VS Code workspace configuration

## Making Changes

1. Create a feature branch: `git checkout -b feature-name`
2. Make your changes
3. Run tests and code quality checks
4. Commit with clear messages
5. Push and create pull request

## Platform-Specific Notes

### Windows-Specific Tool
Note: `src/sattlint/docgenerator/configgen.py` contains Windows-specific paths and is intended for Windows environments. This tool generates Excel configuration files and is not required for core SattLint functionality.

### Cross-Platform Compatibility
- Use `pathlib.Path` for file operations
- Avoid hard-coded paths in new code
- Test changes on both platforms if possible