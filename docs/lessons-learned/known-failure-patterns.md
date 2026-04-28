# Known Failure Patterns

Agents should learn from prior mistakes. Update after each root-cause analysis.

## Past Root Causes

### Hardcoded Machine Paths
- **Pattern**: Absolute paths like `/home/sorenhj/...` or `C:\Users\SQHJ\...` in committed files.
- **Root cause**: Developers copying local paths into docs/examples without converting to repo-relative.
- **Fix**: Use repo-relative paths or config-driven paths. Grep for `/home/` and `C:\Users` in CI.
- **Prevention**: Pre-commit hook or audit rule for absolute paths.

### Unused Imports Accumulation
- **Pattern**: `import os`, `import sys`, `from typing import Dict, List` left after refactoring.
- **Root cause**: Incremental changes removing usage but not imports.
- **Fix**: Run `ruff check --fix` regularly. CI fails on ruff findings.
- **Prevention**: Pre-commit hook with ruff.

### Typing Imports Deprecated
- **Pattern**: `from typing import Dict, List, Tuple, Set` instead of built-in `dict`, `list`, `tuple`, `set`.
- **Root cause**: Old Python 3.8- habits, copy-paste from legacy code.
- **Fix**: Replace with built-in types. `Dict[str, Any]` → `dict[str, Any]`.
- **Prevention**: Ruff rule `UP006` + `UP035` enforce modern typing.

## Historical Regressions

### Print() in Library Modules
- **Incident**: Multiple `src/sattlint/app_*.py` files using `print()` instead of logging.
- **Impact**: Inconsistent output, not observable by LSP or CI.
- **Root cause**: Quick prototyping, never refactored to proper logging.
- **Status**: Medium-severity audit finding (12 occurrences).
- **Fix**: Replace `print()` with structured logging or return values.

### Deprecated Typing Imports Causing Pyright Errors
- **Incident**: `Dict[str, Any]` in return type annotations causing pyright failures.
- **Impact**: CI fails, blocking PRs.
- **Root cause**: Mixed use of `typing.Dict` and built-in `dict`.
- **Fix**: Mass replace to `dict[str, Any]`.
- **Lesson**: Standardize on one style, enforce with lint.

## Common Anti-Patterns

### Direct `sys.exit()` in Library Code
- **Anti-pattern**: Calling `sys.exit()` inside `src/sattlint/devtools/*.py`.
- **Why bad**: Kills entire process, not testable, breaks LSP.
- **Better**: Return exit code, let CLI entry point call `sys.exit()`.

### Unused Variables from Unpacking
- **Anti-pattern**: `returncode, stdout, stderr = run_command(...)` then ignoring `returncode`.
- **Why bad**: Hides errors, pyright/ruff warnings.
- **Better**: `_, stdout, _ = run_command(...)` or prefix with `_returncode`.

### Duplicate Dict Keys
- **Anti-pattern**: `{"passed": ..., "passed": ...}` in return dicts.
- **Why bad**: Silent overwrite, confusing behavior.
- **Better**: Review dict construction, remove duplicates.

### No Newline at End of File
- **Anti-pattern**: Files missing trailing newline.
- **Why bad**: POSIX standard, breaks some tools.
- **Better**: Always end files with `\n`. Ruff rule `W292`.

## Migration Lessons

### Typing Module → Built-in Types (Python 3.9+)
- **Old**: `from typing import Dict, List, Tuple, Set, Optional`
- **New**: Use `dict`, `list`, `tuple`, `set`, `X | None` directly.
- **Tooling**: `ruff --select=UP006,UP035` enforces.
- **Gotcha**: `typing.NamedTuple` still needed (can't use built-in `tuple` for classes).

### Print → Structured Logging
- **Old**: `print(f"Result: {value}")`
- **New**: `logger.info("Result", extra={"value": value})` or return values.
- **Tooling**: Custom lint rule `unexpected-print` in audit.
- **Gotcha**: CLI entry points allowed to print; library code must not.

### Imports: typing → collections.abc
- **Old**: `from typing import Sequence, Iterable`
- **New**: `from collections.abc import Sequence, Iterable`
- **Note**: Only for Python 3.9+. This repo targets 3.9+, so safe to migrate.
