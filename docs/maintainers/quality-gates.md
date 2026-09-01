# Quality Gates

SattLint has a small, honest lint, type, and test path. This file defines the
layered operating contract so single-chat assistant work and human workflows use
the same gate names.

## Validation Stages

| Stage | Responsibility | Required commands | Expected proof |
| --- | --- | --- | --- |
| Focused local | Immediate correctness on the touched slice | Focused pytest, touched-file Pyright when Python files changed | One focused executable check before widening |
| Pre-commit | Fast local hygiene before sharing work | `python -m pre_commit run --all-files` | Ruff fix, Ruff format, Pyright on `src/sattlint`, SattLine syntax-check on staged fixtures |
| Full local | Broader branch health | `python -m ruff check .`, `python -m ruff format --check .`, `python -m pyright src/sattlint`, `python -m pytest -q --tb=short` | Full lint, type, and test pass |
| CI | Full trust on PRs and main | `ci.yml`: clean install, the full local set, clean-wheel smokes (Linux + Windows) | Deterministic install and retained-command smokes |

## Focused Local Contract

1. Start from the controlling file or symbol.
2. Make the smallest local edit.
3. Run the first focused executable validation immediately.
4. Only widen after the local check passes.
5. Summarize outcome and remaining risk directly in the final response when needed.

## Pre-Commit Gate

`python -m pre_commit run --all-files`

This is the default local safety gate. It is fast and file-scoped: Ruff
autofix, Ruff format, Pyright on `src/sattlint`, SattLine syntax-check on staged
SattLine fixtures, and the standard pre-commit-hooks checks.

## CI Gate

`ci.yml` is the single required workflow. It runs Ruff lint and format, Pyright
on production code, the full pytest suite, and clean-wheel install smokes on
Linux and Windows. No required command masks failures.

`publish.yml` builds distributions, checks metadata, smokes a clean wheel, and
publishes to PyPI only on explicit `v*` tag pushes.
